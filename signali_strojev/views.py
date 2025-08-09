# views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, filters
from .models import TimConfig, TimDefinition, StrojEntry, StrojZastojOpombaEntry
from .serializers import TimConfigSerializer, TimDefinitionSerializer, StrojEntrySerializer
from home.models import Terminal, Signal, SignalLimit
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from django.http import JsonResponse
from utils.utils import get_long_obrat, URL_TO_RAW_MAPPING
from django.db import connections
from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
from datetime import datetime
import pandas as pd
import json
from .utils.data_fetching import fetch_production_data_per_stroj_izmena
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Subquery, OuterRef, F, Value, FloatField, DurationField
from django.db.models.functions import Now, Cast
from django.utils import timezone

# from .utils.data_fetching import fetch_machine_data
# from .utils.data_processing import process_machine_data
# from .utils.ag_grid_helpers import generate_ag_grid_json

class TimConfigViewSet(viewsets.ModelViewSet):
    queryset = TimConfig.objects.all()
    serializer_class = TimConfigSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['obrat', 'oddelek', 'team_label']

    @action(detail=False, methods=['get'])
    def by_obrat_oddelek(self, request):
        obrat = request.query_params.get('obrat')
        oddelek = request.query_params.get('oddelek')
        team_label = request.query_params.get('team_label')
        queryset = self.filter_queryset(self.get_queryset())

        if obrat:
            queryset = queryset.filter(obrat=obrat)
        if oddelek:
            queryset = queryset.filter(oddelek=oddelek)
        if team_label:
            queryset = queryset.filter(team_label=team_label)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class TimDefinitionViewSet(viewsets.ModelViewSet):
    queryset = TimDefinition.objects.all()
    serializer_class = TimDefinitionSerializer

    def perform_create(self, serializer):
        serializer.save()

    def get_queryset(self):
        queryset = super().get_queryset()
        tim_config_id = self.request.query_params.get('tim_config')
        if tim_config_id:
            queryset = queryset.filter(tim_config_id=tim_config_id)
        return queryset

class StrojEntryViewSet(viewsets.ModelViewSet):
    queryset = StrojEntry.objects.all()
    serializer_class = StrojEntrySerializer

def get_distinct_team_labels(request):
    team_labels = TimConfig.objects.values_list('team_label', flat=True).distinct()
    return JsonResponse(list(team_labels), safe=False)

# views.py
def pregled(request, safe_obrat, safe_oddelek):
    context = {'safe_obrat': safe_obrat, 'safe_oddelek': safe_oddelek}
    print(context)  # Inspect if these values are correct
    obrat_short = request.session.get('current_obrat', '')
    obrat_long = get_long_obrat(obrat_short)
    raw_oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek, safe_oddelek)

    team_labels = TimConfig.objects.filter(
        obrat=obrat_long, oddelek=raw_oddelek
    ).values('team_label', 'team_label_slug').distinct()

    # Pair each team_label with a color
    colors_list = [
        '#33acff', 
        '#bfbfbf',
        '#b5e3ff',
        '#a98ff9',
        '#f6f386', 
        '#3ddc3d', 
        '#6cf2e5', 
        '#b18a81',
        '#869eb8',
        '#e2cc7c'
    ]

    colors_list = colors_list[:team_labels.count()]
    team_labels_with_colors = zip(team_labels, colors_list)

    context = {
        'safe_obrat': safe_obrat,
        'safe_oddelek': safe_oddelek,
        'team_labels_with_colors': team_labels_with_colors,
        'long_obrat': obrat_long,
        'raw_oddelek': raw_oddelek,
    }
    return render(request, 'pages/statusi_skupine_strojev.html', context)


def team_label_view(request, safe_obrat, safe_oddelek, team_label_slug):
    obrat_short = request.session.get('current_obrat', '')
    obrat_long = get_long_obrat(obrat_short)
    raw_oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek, safe_oddelek)

    tim_configs = TimConfig.objects.filter(
        obrat=obrat_long, oddelek=raw_oddelek, team_label_slug=team_label_slug
    )

    if not tim_configs.exists():
        raise Http404("No TimConfigs found with this team label")

    team_label = tim_configs.first().team_label

    # Define the colors (adjust or extend this list as needed)
    colors_list = [
        '#33acff', 
        '#bfbfbf',
        '#b5e3ff',
        '#a98ff9',
        '#f6f386', 
        '#3ddc3d', 
        '#6cf2e5', 
        '#b18a81',
        '#869eb8',
        '#e2cc7c'
    ]

    # Adjust colors_list length to match tim_configs count
    colors_list = colors_list[:tim_configs.count()]

    # Pair each tim_config with a color
    tim_configs_with_colors = zip(tim_configs, colors_list)

    context = {
        'safe_obrat': safe_obrat,
        'safe_oddelek': safe_oddelek,
        'team_label': team_label,
        'team_label_slug': team_label_slug,
        'tim_configs_with_colors': tim_configs_with_colors,
    }
    return render(request, 'pages/team_label_view.html', context)

@login_required
def tim_detail(request, safe_obrat, safe_oddelek, team_label_slug, team_name_slug):
    if team_name_slug == 'rom':
        return terminali_overview(request, safe_obrat, safe_oddelek, team_label_slug, team_name_slug)
    else:
        # Resolve the long name of the obrat
        obrat_short = request.session.get('current_obrat', '')
        obrat_long = get_long_obrat(obrat_short)

        # Map `safe_oddelek` to its original raw value
        raw_oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek, safe_oddelek)

        # Fetch the specific TimConfig
        tim_config = get_object_or_404(
            TimConfig,
            obrat=obrat_long,
            oddelek=raw_oddelek,
            team_label_slug=team_label_slug,
            team_name_slug=team_name_slug
        )

        # Fetch associated TimDefinitions and StrojEntries
        tim_definitions = tim_config.definitions.all().prefetch_related('stroj_entries')
        context = {
            'safe_obrat': safe_obrat,
            'safe_oddelek': safe_oddelek,
            'team_label': tim_config.team_label,
            'tim_config': tim_config,
            'tim_definitions': tim_definitions,
        }
        return render(request, 'pages/tim_detail.html', context)

@login_required
def konfiguracija_lean_teami(request, safe_obrat, safe_oddelek):
    obrat_short = request.session.get('current_obrat', '')
    obrat_long = get_long_obrat(obrat_short)

    # Map `safe_oddelek` to its original raw value
    raw_oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek, safe_oddelek)

    context = {
        'safe_obrat': obrat_long,
        'safe_oddelek': raw_oddelek,
    }
    return render(request, 'pages/konfiguracija_lean_teami.html', context)

def get_ag_grid_data(request, team_name_slug):
    try:
        print(f"Received request for team: {team_name_slug}")

        # Retrieve start and end dates from query parameters
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        print(f"Start date: {start_date_str}, End date: {end_date_str}")

        if not start_date_str or not end_date_str:
            print("Missing start_date or end_date")
            return JsonResponse({'error': 'Missing start_date or end_date'}, status=400)

        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        print(f"Parsed dates - Start: {start_date}, End: {end_date}")

        # Get the team config
        tim_config = get_object_or_404(TimConfig, team_name_slug=team_name_slug)
        print(f"Found TimConfig: {tim_config}")

        # Get the stroj entries
        stroj_entries = StrojEntry.objects.filter(tim_definition__tim_config=tim_config)
        print(f"Stroj entries count: {stroj_entries.count()}")

        if not stroj_entries.exists():
            print("No Stroj entries found")
            return JsonResponse({'columns': [], 'rows': []})  # Empty response for no data

        # Get the list of stroji
        list_of_stroji = list(stroj_entries.values_list('stroj', flat=True).distinct())
        print(f"List of stroji: {list_of_stroji}")

        # Get zastoj entries
        zastoj_entries = StrojZastojOpombaEntry.objects.filter(
            stroj__in=list_of_stroji,
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        print(f"Zastoj entries count: {zastoj_entries.count()}")

        zastoj_dict = {}
        for entry in zastoj_entries:
            key = (entry.stroj, entry.izmena)
            zastoj_dict[key] = {
                'opomba': entry.opomba,
                'zastoj_entries': entry.zastoj_entries
            }
        print(f"Zastoj dict: {zastoj_dict}")

        # Fetch production data
        production_data_df = fetch_production_data_per_stroj_izmena(list_of_stroji, start_date, end_date)
        print(f"Fetched production data:\n{production_data_df}")

        # Build data rows
        data_rows = []
        for stroj in list_of_stroji:
            for izmena in [1, 2, 3]:
                row_data = production_data_df[
                    (production_data_df['Stroj'] == stroj) & (production_data_df['Izmena'] == izmena)
                ]
                if not row_data.empty:
                    dobri = int(row_data.iloc[0]['Dobri'])
                    izmet = int(row_data.iloc[0]['Izmet'])
                else:
                    dobri, izmet = 0, 0

                plan = 0  # Replace with actual plan logic if available
                primanjkljaj = plan - dobri
                opomba = ''
                zastoj_entries_value = []
                key = (stroj, izmena)
                if key in zastoj_dict:
                    opomba = zastoj_dict[key]['opomba']
                    zastoj_entries_value = zastoj_dict[key]['zastoj_entries']

                data_rows.append({
                    'Stroj': stroj,
                    'Izmena': izmena,
                    'Dobri': dobri,
                    'Izmet': izmet,
                    'Plan': plan,
                    'Primanjkljaj': primanjkljaj,
                    'Opomba': opomba,
                    'Zastoj': zastoj_entries_value,
                })
        print(f"Built data rows: {data_rows}")

        # Prepare column definitions for AG Grid
        columns = [
            {'headerName': 'Stroj', 'field': 'Stroj', 'editable': False},
            {'headerName': 'Izmena', 'field': 'Izmena', 'editable': False},
            {'headerName': 'Dobri', 'field': 'Dobri', 'editable': False},
            {'headerName': 'Izmet', 'field': 'Izmet', 'editable': False},
            {'headerName': 'Plan', 'field': 'Plan', 'editable': False},
            {'headerName': 'Primanjkljaj', 'field': 'Primanjkljaj', 'editable': False},
            {'headerName': 'Zastoj', 'field': 'Zastoj', 'editable': True},
            {'headerName': 'Opomba', 'field': 'Opomba', 'editable': True},
        ]
        print(f"Column definitions: {columns}")

        return JsonResponse({'columns': columns, 'rows': data_rows})

    except Exception as e:
        print(f"Error in get_ag_grid_data: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def update_opomba(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        stroj = data.get('stroj')
        izmena = data.get('izmena')
        opomba = data.get('opomba')
        zastoj_entries = data.get('zastoj_entries', [])
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        # Save or update the entry
        zastoj_entry, created = StrojZastojOpombaEntry.objects.update_or_create(
            stroj=stroj,
            izmena=izmena,
            start_date=start_date,
            end_date=end_date,
            defaults={
                'opomba': opomba,
                'zastoj_entries': zastoj_entries,
            }
        )
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error'}, status=400)
    

def terminali_overview(request, safe_obrat=None, safe_oddelek=None, team_label_slug=None, team_name_slug=None):
    # Get filters from request
    network_type = request.GET.get('network_type', '')
    delovno_mesto = request.GET.get('delovno_mesto', '')
    postaja = request.GET.get('postaja', '')
    is_rom = request.GET.get('is_rom', 'on')  # Default to 'on'
    page = request.GET.get('page', 1)

    # Fetch all terminals
    terminals = Terminal.objects.all()

    # Apply filters
    if network_type:
        terminals = terminals.filter(network_type=network_type)
    if delovno_mesto:
        terminals = terminals.filter(delovno_mesto__icontains=delovno_mesto)
    if postaja:
        terminals = terminals.filter(postaja__icontains=postaja)
    if is_rom == 'on':
        terminals = terminals.filter(is_rom=True)

    # Annotate terminals with last_get_request, last_get_raw_data, last_put_request, last_put_raw_data
    last_get_signals = Signal.objects.filter(
        terminal=OuterRef('pk'),
        message__icontains='GET'
    ).order_by('-timestamp')

    last_put_signals = Signal.objects.filter(
        terminal=OuterRef('pk'),
        message__icontains='PUT'
    ).order_by('-timestamp')

    terminals = terminals.annotate(
        last_get_request=Subquery(last_get_signals.values('timestamp')[:1]),
        last_get_message=Subquery(last_get_signals.values('message')[:1]),
        last_put_request=Subquery(last_put_signals.values('timestamp')[:1]),
        last_put_message=Subquery(last_put_signals.values('message')[:1]),
    )

    # Paginate the terminals
    paginator = Paginator(terminals, 50)  # 50 terminals per page
    try:
        terminals_page = paginator.page(page)
    except PageNotAnInteger:
        terminals_page = paginator.page(1)
    except EmptyPage:
        terminals_page = paginator.page(paginator.num_pages)

    # Compute hours_since_last_get and hours_since_last_put in Python
    for terminal in terminals_page:
        if terminal.last_get_request:
            delta_get = timezone.now() - terminal.last_get_request
            terminal.hours_since_last_get = delta_get.total_seconds() / 3600
        else:
            terminal.hours_since_last_get = None

        if terminal.last_put_request:
            delta_put = timezone.now() - terminal.last_put_request
            terminal.hours_since_last_put = delta_put.total_seconds() / 3600
        else:
            terminal.hours_since_last_put = None

    context = {
        'terminals': terminals_page,
    }

    # HTMX handling
    if request.headers.get('HX-Request'):
        return render(request, 'pages/terminali_table.html', context)

    return render(request, 'pages/terminali_overview.html', context)


@login_required
def manage_limits(request, terminal_id):
    terminal = get_object_or_404(Terminal, pk=terminal_id)
    current_user = request.user

    if request.method == "POST":
        # Fetch data from POST request
        signal_key = request.POST['signal_key']
        limit_value = request.POST['limit_value']
        email = request.POST['email']

        # Create or update the user's limit
        SignalLimit.objects.update_or_create(
            user=current_user,
            terminal=terminal,
            signal_key=signal_key,
            defaults={
                'limit_value': limit_value,
                'notification_email': email,
            }
        )
        return redirect('manage_limits', terminal_id=terminal.id)

    # Fetch limits specific to the current user for this terminal
    limits = SignalLimit.objects.filter(user=current_user, terminal=terminal)

    context = {
        'terminal': terminal,
        'limits': limits,
    }
    return render(request, 'limits.html', context)

@login_required
def delete_limit(request, limit_id):
    limit = get_object_or_404(SignalLimit, pk=limit_id, user=request.user)
    limit.delete()
    return redirect('manage_limits', terminal_id=limit.terminal.id)

