from django.conf import settings
import json
import logging
from collections import defaultdict

from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .context_processors import obrat_mapping, available_users_processor, user_obrati_oddelki_processor
from utils.utils import get_long_obrat, get_client_ip, send_notification_via_rabbitmq, generate_and_register_token, register_token_in_rabbitmq, send_notification_email

from .forms import DevelopmentAuthenticationForm, UserForm, GroupForm
from .models import AplikacijeObratiOddelki, UserAppRole, User, ObratiOddelki, UserGroup, RoleGroupMapping, ObratOddelekGroup, Notification, OnlineUser, Terminal, ClientToken, NotificationStatus
from pregled_aktivnosti.models import TaskStep, Stepper, Action

from django.db.models.functions import TruncMonth, Coalesce, Greatest
from django.db.models import Count, OuterRef, Subquery, Max, F, Value, Q, CharField, Case, When
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import uuid
import pika

User = get_user_model()
logger = logging.getLogger('home')



@login_required
def index(request):
    current_user = request.user
    obrat_short = request.session.get('current_obrat', '')
    obrat_long = get_long_obrat(obrat_short)

    if not obrat_long or (current_user.user_role != 'admin' and obrat_long != 'LTH' and current_user.obrat_oddelek.obrat != obrat_long):
        del request.session['current_obrat']
        return render(request, 'accounts/login_failed.html', {'error_messages': ["You do not have permission to view this obrat."]})

    users = User.objects.filter(obrat_oddelek__obrat=obrat_long)

    recent_notifications = Notification.objects.filter(
        Q(sender_user=current_user) | Q(receiver_user=current_user)
    ).order_by('-time_sent')[:3]

    default_date = timezone.make_aware(datetime.min)

    latest_action_subquery = Action.objects.filter(
        task_step=OuterRef('pk')
    ).order_by('-timestamp')

    latest_action_timestamp_subquery = latest_action_subquery.values('timestamp')[:1]
    latest_action_user_subquery = latest_action_subquery.values('user')[:1]

    tasksteps_modified_by_others = TaskStep.objects.filter(
        stepper__assigner=current_user.username
    ).annotate(
        latest_action_timestamp=Subquery(latest_action_timestamp_subquery),
        latest_action_user=Subquery(latest_action_user_subquery),
        status_modified_at_defaulted=Coalesce('status_modified_at', Value(default_date)),
        latest_action_timestamp_defaulted=Coalesce('latest_action_timestamp', Value(default_date)),
        latest_event=Greatest('status_modified_at_defaulted', 'latest_action_timestamp_defaulted'),
        latest_event_user=Case(
            When(
                status_modified_at_defaulted__gte=F('latest_action_timestamp_defaulted'),
                then=F('status_modified_by')
            ),
            When(
                latest_action_timestamp_defaulted__gte=F('status_modified_at_defaulted'),
                then=F('latest_action_user')
            ),
            output_field=CharField(),
        ),
        latest_event_type=Case(
            When(
                status_modified_at_defaulted__gte=F('latest_action_timestamp_defaulted'),
                then=Value('status_change')
            ),
            When(
                latest_action_timestamp_defaulted__gte=F('status_modified_at_defaulted'),
                then=Value('action')
            ),
            output_field=CharField(),
        )
    ).filter(
        Q(
            Q(status_modified_by__isnull=False) &
            ~Q(status_modified_by=current_user.username)
        ) |
        Q(
            Q(latest_action_user__isnull=False) &
            ~Q(latest_action_user=current_user.username) &
            Q(status_modified_at__lt=F('latest_action_timestamp'))
        )
    ).order_by('-latest_event')[:3]

    tasksteps_assigned_to_user = TaskStep.objects.filter(
        stepper__assignee_username=current_user.username,
        status='Queued'
    ).annotate(
        max_created_at=Max('created_at')
    ).order_by('-created_at').distinct()

    # Prepare the expiration data for each task step
    for taskstep in tasksteps_assigned_to_user:
        remaining_time = taskstep.exp_time - timezone.now()
        days_left = max(remaining_time.days, 0)  # Set to 0 if negative
        hours_left = max(remaining_time.seconds // 3600, 0) if remaining_time.days >= 0 else 0  # Set to 0 if negative

        # Update taskstep attributes
        taskstep.remaining_days = days_left
        taskstep.remaining_hours = hours_left
        taskstep.expiring_soon = remaining_time < timedelta(days=1) and remaining_time.total_seconds() > 0

    # Repeat the same preparation for `tasksteps_modified_by_others`
    for taskstep in tasksteps_modified_by_others:
        remaining_time = taskstep.exp_time - timezone.now()
        days_left = max(remaining_time.days, 0)
        hours_left = max(remaining_time.seconds // 3600, 0) if remaining_time.days >= 0 else 0

        # Update taskstep attributes
        taskstep.remaining_days = days_left
        taskstep.remaining_hours = hours_left
        taskstep.expiring_soon = remaining_time < timedelta(days=1) and remaining_time.total_seconds() > 0


    context = {
        'users': users,
        'recent_notifications': recent_notifications,
        'tasksteps_modified_by_others': tasksteps_modified_by_others,
        'tasksteps_assigned_to_user': tasksteps_assigned_to_user,
    }

    return render(request, 'pages/index.html', context)


@csrf_exempt
def get_obrat_name(request):
    # Fetch the obrat code from the session
    obrat_code = request.session.get('current_obrat', '')
    # Map the short codes to their friendly names
    mapping = {
        'LJ': 'Ljubljana',
        'SL': 'Škofja Loka',
        'TR': 'Trata',
        'BE': 'Benkovac',
        'CK': 'Čakovec',
        'OH': 'Ohrid',
        'LTH': 'LTH'
    }
    # Get the friendly name for the obrat
    friendly_name = mapping.get(obrat_code, 'N/A')
    return JsonResponse({'current_obrat_name': friendly_name})

@csrf_exempt
def get_short_obrat_name(request):
    # Fetch the obrat code (short name) from the session
    obrat_code = request.session.get('current_obrat', '')

    # Convert the short obrat name to the long name using the utility function
    obrat_long_name = get_long_obrat(obrat_code)

    # Return both the short and long names in the response
    return JsonResponse({'current_obrat_name': obrat_code, 'current_obrat_long_name': obrat_long_name})


@csrf_exempt
@require_POST
def set_obrat_ajax(request):
    try:
        # Log the raw request body for debugging
        # print(f"Raw request body: {request.body}")

        # Attempt to parse the JSON data from the request
        data = json.loads(request.body)
        obrat = data.get('obrat')

        if not obrat:
            # print("No obrat provided in the request.")  # Debugging
            return JsonResponse({'success': False, 'error': 'No obrat provided'}, status=400)

        # Add both long and short names to the mapping
        mapping = {
            'Ljubljana': 'LJ',
            'Škofja Loka': 'SL',
            'Trata': 'TR',
            'Benkovac': 'BE',
            'Čakovec': 'CK',
            'Ohrid': 'OH',
            'LJ': 'LJ',
            'SL': 'SL',
            'TR': 'TR',
            'BE': 'BE',
            'CK': 'CK',
            'OH': 'OH',
            'LTH': 'LTH'
        }
        
        # Convert to short code if provided long name, otherwise keep as is
        obrat_code = mapping.get(obrat)

        if not obrat_code:
            # print(f"Invalid obrat name provided: {obrat}")  # Debugging
            return JsonResponse({'success': False, 'error': 'Invalid obrat name'}, status=400)

        # Set the obrat in session
        request.session['current_obrat'] = obrat_code
        # print(f"Obrat set successfully in session: {obrat_code}")  # Debugging
        return JsonResponse({'success': True})

    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {str(e)}")  # Debugging
        return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)

    except Exception as e:
        print(f"Exception occurred: {str(e)}")  # Debugging
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def navigation_dynamic_obrati_ajax(request):
    user = request.user
    obrats_accessible = set()

    # Fetch user roles for the authenticated user
    user_roles = UserAppRole.objects.filter(username=user).select_related('app_url_id__obrat_oddelek')

    # Check if the user has access to the obrati and add them to the set
    for role in user_roles:
        if role.role_name != 'brez dostopa':  # Skip roles that indicate no access
            app = role.app_url_id  # Get the app associated with the role
            obrat_code = app.obrat_oddelek.obrat  # Retrieve the obrat code
            obrats_accessible.add(obrat_code)  # Add the obrat code to the set

    # Prepare the options to return as a JSON response
    obrat_options = [{'value': obrat, 'text': obrat} for obrat in obrats_accessible]

    # Debugging: Log the generated options
    # print(f"Accessible obrat options for {user.username}: {obrat_options}")

    return JsonResponse({'options': obrat_options})

def get_or_create_terminal_user(hostname):
    username = f"terminal_{hostname}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'first_name': 'Terminal',
            'last_name': hostname,
            'email': None,  # Optional: Provide a default or leave as None
            'is_staff': False,
            'is_active': True
        }
    )
    return user

@csrf_exempt
def pair_terminal(request):
    if request.method == 'POST':
        hostname = request.POST.get('hostname')
        external_ip = request.POST.get('external_ip')

        # Authenticate or create the terminal user
        user = get_or_create_terminal_user(hostname)

        # Find or create the Terminal instance based on hostname
        terminal, _ = Terminal.objects.get_or_create(
            terminal_hostname=hostname,
            defaults={'ip_address': external_ip}
        )

        # Attempt to retrieve an existing token for the terminal
        token_obj = ClientToken.objects.filter(user=user, terminal=terminal).first()
        
        # Check if token exists and is expired
        if token_obj and token_obj.expires_at < timezone.now():
            # Update the existing token if expired
            token_obj.token = uuid.uuid4()
            token_obj.expires_at = timezone.now() + timezone.timedelta(hours=1)
            token_obj.save()
        elif not token_obj:
            # If no token exists, create a new one
            token_obj = ClientToken.objects.create(
                user=user,
                terminal=terminal,
                token=uuid.uuid4(),
                expires_at=timezone.now() + timezone.timedelta(hours=1)
            )
        else:
            # Token exists and is valid; overwrite it to refresh
            token_obj.token = uuid.uuid4()
            token_obj.expires_at = timezone.now() + timezone.timedelta(hours=1)
            token_obj.save()

        # Update the OnlineUser record
        OnlineUser.objects.update_or_create(
            user=user,
            terminal=terminal,
            defaults={
                'ip_address': external_ip,
                'is_terminal': True,
                'sign_in_time': timezone.now(),
                'sign_out_time': None,  # Reset sign_out_time
                'can_receive_notifications': True,
                'last_seen': timezone.now()
            }
        )

        # Register the token in RabbitMQ
        register_token_in_rabbitmq(str(token_obj.token))

        return JsonResponse({
            'token': str(token_obj.token),
            'expires_at': token_obj.expires_at.isoformat()  # Convert datetime to ISO format
        }, status=200)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
def terminal_sign_out(request):
    if request.method == 'POST':
        hostname = request.POST.get('hostname')
        try:
            user = User.objects.get(username=hostname)
            online_user = OnlineUser.objects.filter(user=user, is_terminal=True).first()
            if online_user:
                online_user.sign_out_time = timezone.now()
                online_user.save()
                return JsonResponse({'status': 'success'}, status=200)
            else:
                return JsonResponse({'error': 'OnlineUser record not found'}, status=404)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)


def notification_detail(request, notification_id):
    # Fetch the specific notification by ID
    notification = get_object_or_404(Notification, id=notification_id)
    
    # Fetch all notifications with the same key
    related_notifications = Notification.objects.filter(key=notification.key)

    context = {
        'notification': notification,
        'related_notifications': related_notifications,
    }

    return render(request, 'notifications/notification_detail.html', context)

def print_all_tokens():
    all_tokens = ClientToken.objects.all()
    for token in all_tokens:
        terminal_hostname = token.terminal.terminal_hostname if token.terminal else "None"
        logger.info(
            f"Token ID: {token.token}, Terminal: {terminal_hostname}, "
            f"Expires At: {token.expires_at}, Is Expired: {timezone.now() > token.expires_at}"
        )

@csrf_exempt
def terminal_heartbeat(request):
    if request.method == 'POST':
        hostname = request.POST.get('hostname')
        token_str = request.POST.get('token')
        logger.info(f"Received heartbeat for hostname: {hostname} with token: {token_str}")

        try:
            # Look up the terminal by hostname
            terminal = Terminal.objects.get(terminal_hostname=hostname)
            online_user = OnlineUser.objects.filter(terminal=terminal, is_terminal=True).first()
            
            if online_user:
                # Update the last_seen time to indicate active status
                online_user.last_seen = timezone.now()
                online_user.save()
                # logger.info(f"Heartbeat registered for terminal '{hostname}' at {timezone.now()}.")
                # Find the ClientToken object
                try:
                    token_obj = ClientToken.objects.get(user=online_user, token=token_str)
                    # Check if token is expired
                    if token_obj.expires_at and token_obj.expires_at < timezone.now():
                        logger.warning(f"Token for hostname '{hostname}' is expired.")
                        return JsonResponse({'error': 'Token expired'}, status=401)
                    else:
                        # Token is valid, update last_seen
                        online_user, _ = OnlineUser.objects.update_or_create(
                            user=online_user,
                            terminal=token_obj.terminal,
                            defaults={'last_seen': timezone.now()}
                        )
                        logger.info(f"Heartbeat registered for terminal '{hostname}' at {timezone.now()}.")
                        return JsonResponse({'status': 'success'}, status=200)
                except ClientToken.DoesNotExist:
                    logger.warning(f"Invalid token received for hostname '{hostname}'.")
                    return JsonResponse({'error': 'Invalid token'}, status=401)
            else:
                logger.warning(f"No OnlineUser record found for terminal '{hostname}'.")
                return JsonResponse({'error': 'OnlineUser record not found'}, status=404)

        except Terminal.DoesNotExist:
            logger.error(f"Terminal with hostname '{hostname}' not found.")
            return JsonResponse({'error': 'Terminal not found'}, status=404)
    
    else:
        logger.warning("Invalid request method received in terminal_heartbeat.")
        return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def create_notification(request):
    if request.method == 'POST':
        # Determine the notification recipient type
        recipient_type = request.POST.get('recipient_type')
        notify_email = request.POST.get('notify_email') == 'true'
        logger.info(f"Request POST data: {request.POST}")
        print(f"Request POST data: {request.POST}")

        key = request.POST.get('key')
        content = request.POST.get('notification_content')
        sender = request.user

        if not key or not content:
            return JsonResponse({'error': 'Missing required fields'}, status=400)


        if recipient_type == 'user':
            receiver_user_id = request.POST.get('receiver_user')
            receiver_user = User.objects.get(id=receiver_user_id)
            # Check if the user is currently online
            online_user = OnlineUser.objects.filter(
                user=receiver_user,
                sign_out_time__isnull=True
            ).first()

            # Send email if selected
            if notify_email:
                try:
                    send_notification_email(
                        recipient=receiver_user,
                        subject=f"Obvestilo: {key}",
                        message_content=content
                    )
                except Exception as e:
                    logger.error(f"Error sending email to {receiver_user.email}: {e}")

            if online_user:
                # Check if user can receive notifications
                can_receive_notifications = online_user.can_receive_notifications

                # Create the notification record without receiver_ip
                notification = Notification.objects.create(
                    key=key,
                    sender_user=sender,
                    receiver_user=receiver_user,
                    receiver_token=None,  # Replace with an actual token if needed
                    receiver_terminal=None,
                    notification_content=content,
                )

                # Create NotificationStatus with status 'sent'
                NotificationStatus.objects.create(
                    notification=notification,
                    status='sent'
                )

                # Send the notification if user can receive notifications
                if can_receive_notifications:
                    send_notification_via_rabbitmq(notification)

                return JsonResponse({'success': True})
            else:
                # User is not online
                return JsonResponse({'success': False, 'error': 'Uporabnik ni aktiven.'}, status=400)

        elif recipient_type == 'terminal':
            receiver_terminal_hostname = request.POST.get('receiver_terminal_hostname')
            if recipient_type == 'terminal':
                try:
                    receiver_terminal = Terminal.objects.get(terminal_hostname=receiver_terminal_hostname)
                except Terminal.DoesNotExist:
                    logger.error(f"Terminal with hostname '{receiver_terminal_hostname}' not found.")
                    return JsonResponse({'success': False, 'error': 'Terminal not found.'}, status=400)

            # Debug print of all tokens
            print_all_tokens()

            # Retrieve the ClientToken for the terminal
            client_token = ClientToken.objects.filter(
                terminal=receiver_terminal,
                expires_at__gt=timezone.now()
            ).first()

            if not client_token:
                return JsonResponse({'success': False, 'error': 'No valid token for terminal.'}, status=400)

            # Create the notification with receiver_token
            notification = Notification.objects.create(
                key=key,
                sender_user=sender,
                receiver_user=None,
                receiver_token=client_token,
                receiver_terminal=receiver_terminal,
                notification_content=content,
            )

            # Create NotificationStatus with status 'sent'
            NotificationStatus.objects.create(
                notification=notification,
                status='sent'
            )

            send_notification_via_rabbitmq(notification)  # Send via RabbitMQ

            return JsonResponse({'success': True})

        # Handle unknown recipient type
        return JsonResponse({'success': False, 'error': 'Neznana napaka.'}, status=400)

    # Render notification creation page
    # Fetch only active users and terminals
    online_users = OnlineUser.objects.filter(sign_out_time__isnull=True, is_terminal=False)
    online_terminals = OnlineUser.objects.filter(sign_out_time__isnull=True, is_terminal=True)

    # Pass the Terminal instances directly for display details
    terminal_info = Terminal.objects.filter(id__in=online_terminals.values('terminal_id'))

    return render(request, 'notifications/create_notification.html', {
        'online_users': online_users,
        'online_terminals': terminal_info,  # Now passing Terminal instances directly
    })

def notification_sent(request):
    return render(request, 'notifications/notification_sent.html')  # Create a template for this view

def obvestila_view(request):
    # Fetch filter values from the GET request
    key_filter = request.GET.get('key', '')
    sender_user_filter = request.GET.get('sender_user', '')
    receiver_user_filter = request.GET.get('receiver_user', '')
    receiver_terminal_filter = request.GET.get('receiver_terminal', '')
    content_filter = request.GET.get('content', '')
    hours_filter = request.GET.get('hours_filter', '')

    # Start with all notifications
    notifications = Notification.objects.all()

    # Apply filters if provided
    if key_filter:
        notifications = notifications.filter(key__icontains=key_filter)
    if sender_user_filter:
        notifications = notifications.filter(sender_user__id=sender_user_filter)
    if receiver_user_filter:
        notifications = notifications.filter(receiver_user__id=receiver_user_filter)
    if receiver_terminal_filter:
        notifications = notifications.filter(receiver_terminal__id=receiver_terminal_filter)
    if content_filter:
        notifications = notifications.filter(notification_content__icontains=content_filter)
    if hours_filter:
        try:
            last_n_hours = int(hours_filter)
            time_threshold = timezone.now() - datetime.timedelta(hours=last_n_hours)
            notifications = notifications.filter(time_sent__gte=time_threshold)
        except ValueError:
            pass

    # Fetch all users and terminals for the filters
    users = User.objects.all()
    terminals = Terminal.objects.all()

    # Set up pagination
    paginator = Paginator(notifications, 10)  # Show 10 notifications per page
    page = request.GET.get('page', 1)

    try:
        notifications_page = paginator.page(page)
    except PageNotAnInteger:
        notifications_page = paginator.page(1)
    except EmptyPage:
        notifications_page = paginator.page(paginator.num_pages)

    context = {
        'notifications': notifications_page,
        'users': users,
        'terminals': terminals,
    }

    if request.headers.get('HX-Request'):
        # If it's an HTMX request, only return the table portion
        return render(request, 'notifications/notifications_table.html', context)

    # Otherwise, return the full page
    return render(request, 'notifications/obvestila.html', context)

def terminali_overview(request):
    # Fetch filter values from the GET request
    is_terminal_filter = request.GET.get('is_terminal', 'on')
    hours_filter = request.GET.get('hours_filter', '')
    user_filter = request.GET.get('user', '')
    terminal_hostname_filter = request.GET.get('terminal_hostname', '')

    # Start with all online users
    online_users = OnlineUser.objects.all()

    # Apply filters if provided
    if is_terminal_filter == 'on':  # Check for "on" to confirm checkbox is checked
        online_users = online_users.filter(is_terminal=True)
    if hours_filter:
        try:
            last_n_hours = int(hours_filter)
            time_threshold = timezone.now() - timedelta(hours=last_n_hours)
            online_users = online_users.filter(last_seen__gte=time_threshold)
        except ValueError:
            pass
    if user_filter:
        online_users = online_users.filter(user__id=user_filter)
    if terminal_hostname_filter:
        online_users = online_users.filter(terminal__terminal_hostname__icontains=terminal_hostname_filter)

    # Fetch all users and terminals for filters
    users = User.objects.all()
    terminals = Terminal.objects.all()

    # Set up pagination
    paginator = Paginator(online_users, 10)  # Show 10 online users per page
    page = request.GET.get('page', 1)

    try:
        online_users_page = paginator.page(page)
    except PageNotAnInteger:
        online_users_page = paginator.page(1)
    except EmptyPage:
        online_users_page = paginator.page(paginator.num_pages)

    context = {
        'online_users': online_users_page,
        'users': users,
        'terminals': terminals,
    }

    if request.headers.get('HX-Request'):
        # If it's an HTMX request, only return the table portion
        return render(request, 'notifications/terminali_table.html', context)

    # Otherwise, return the full page
    return render(request, 'notifications/terminali_overview.html', context)

@csrf_exempt  # Exempt CSRF verification for AJAX requests
def login_dynamic_obrati_ajax(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            # Get the username from the request data
            username = request.POST.get('username', '').lower()

            if not username:
                return JsonResponse({'error': 'Username not provided'}, status=400)

            # Fetch the user object
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return JsonResponse({'error': 'User does not exist'}, status=404)

            # Fetch all the apps that the user has any access to
            user_roles = UserAppRole.objects.filter(username=user).select_related('app_url_id__obrat_oddelek')

            obrats_accessible = set()  # Set to store unique obrats

            # Iterate over all the roles to gather accessible obrats
            for role in user_roles:
                if role.role_name != 'brez dostopa':  # Check if the user has access
                    app = role.app_url_id  # Use the foreign key reference
                    obrat_code = app.obrat_oddelek.obrat  # Get the obrat code
                    obrats_accessible.add(obrat_code)  # Add it to the set of accessible obrats

            # Prepare the options to return as a JSON response
            obrat_options = [
                {'value': obrat, 'text': obrat} for obrat in obrats_accessible
            ]

            return JsonResponse({'options': obrat_options})

        except Exception as e:
            # Log the exception to server logs
            print(f"Error occurred: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        # Return an error if the request is not AJAX
        return JsonResponse({'error': 'Invalid request type'}, status=400)

def custom_login(request):
    logger.debug("Logging in ..")
    next_url = request.GET.get('next', reverse('index'))
    obrat = request.session.get('current_obrat', '')

    if request.method == 'POST':
        form = DevelopmentAuthenticationForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username').lower()
            obrat_selected = request.POST.get('obrat')

            user = authenticate(request, username=username)
            if user is not None:
                login(request, user)

                # Update or create OnlineUser entry
                online_user, created = OnlineUser.objects.update_or_create(
                    user=user,
                    sign_out_time__isnull=True,  # Find an existing active session
                    defaults={
                        'ip_address': get_client_ip(request),
                        'is_terminal': False,  # Adjust if terminal login
                        'sign_in_time': timezone.now(),
                        'last_seen': timezone.now(),
                    }
                )

                # Check permission for selected obrat
                user_roles = UserAppRole.objects.filter(username=user).select_related('app_url_id__obrat_oddelek')
                accessible_obrati = {role.app_url_id.obrat_oddelek.obrat for role in user_roles if role.role_name != 'brez dostopa'}

                if obrat_selected not in accessible_obrati:
                    messages.error(request, f"You do not have permission to log into obrat: {obrat_selected}.")
                    return render(request, 'accounts/login.html', {
                        'form': form,
                        'next': next_url,
                        'obrat': obrat,
                    })

                # Set the obrat in the session
                request.session['current_obrat'] = obrat_selected
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password')
                return redirect('login_failed')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DevelopmentAuthenticationForm()

    client_ip = get_client_ip(request)

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': next_url,
        'obrat': obrat,
        'client_ip': client_ip,
    })

def unregister_token_from_rabbitmq(token):
    """Unregister the token from RabbitMQ by deleting the associated queue."""
    try:
        credentials = pika.PlainCredentials(settings.RABBITMQ_USERNAME, settings.RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT, credentials=credentials)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        queue_name = f'queue_{token}'
        channel.queue_delete(queue=queue_name)
        
        connection.close()
        print(f"Unregistered token {token} from RabbitMQ")
    except Exception as e:
        print(f"Failed to unregister token from RabbitMQ: {e}")

def custom_logout(request):
    print("Custom logout triggered")  # Debug statement to check if the function is called

    # Delete all OnlineUser entries for the current user
    OnlineUser.objects.filter(user=request.user).delete()

    # Delete expired tokens associated with the user
    expired_tokens = ClientToken.objects.filter(user=request.user, expires_at__lte=timezone.now())
    
    for token in expired_tokens:
        unregister_token_from_rabbitmq(token.token)
        token.delete()

    # Perform the logout operation
    logout(request)
    return redirect('login')  # Redirect to login page or desired page

def register(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User registered successfully')
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def user_add_success(request):
    return render(request, 'accounts/user_add_success.html')

def get_oddelki(request):
    obrat = request.GET.get('obrat')
    # print(f"Received obrat: {obrat}")  # Debug statement

    oddelki = list(ObratiOddelki.objects.filter(obrat=obrat).values_list('oddelek', flat=True))
    # print(f"Found oddelki: {oddelki}")  # Debug statement

    return JsonResponse({'oddelki': oddelki})

def sidebar_context_ajax(request):
    user_role = request.user.user_role
    selected_app_type = request.GET.get('appType', 'režija')  # Get 'appType' from GET parameters
    current_obrat_short = request.session.get('current_obrat', '')  # Get from session
    current_obrat_long = get_long_obrat(current_obrat_short)

    if not current_obrat_long:
        return JsonResponse({'grouped_data': {}})

    # Define the apps that should be grouped with 'oddelek' as the second level
    group_apps_by_oddelek_2nd_level = ['LTH Pregled aktivnosti'] if selected_app_type == 'režija' else []

    # Define static links for režija and proizvodnja
    static_links_rezija = {
        'Obdelava': [
            {
                'aplikacija': 'Lean Team Obdelava',
                'url': 'https://example.com/lean-team',
                'icon': 'fa-solid fa-users'
            }
        ],
        'Vzdrževanje': [
            {
                'aplikacija': 'Maintenance Portal',
                'url': 'https://example.com/maintenance',
                'icon': 'fa-solid fa-industry'
            }
        ]
    }
    static_links_proizvodnja = {}  # Currently empty, but can be defined as needed

    # Select static links based on app type
    static_links = static_links_rezija if selected_app_type == 'režija' else static_links_proizvodnja

    # Define icons for 1st level (oddelek)
    first_level_icons = {
        'Obdelava': 'fa-solid fa-users',
        'Vzdrževanje': 'fa-solid fa-industry',
        'LTH Pregled aktivnosti': 'fa-solid fa-chart-bar',
        'Ekologija': 'fa-solid fa-leaf',
        'Kakovost': 'fa-solid fa-check-circle',
        'Varnost': 'fa-solid fa-shield-alt'
    }

    # Fetch records based on the selected obrat and app type
    obrati_oddelki = AplikacijeObratiOddelki.objects.filter(
        obrat_oddelek__obrat=current_obrat_long,
        type=selected_app_type
    ).select_related('obrat_oddelek')

    # Initialize grouped_data
    grouped_data = {}

    for item in obrati_oddelki:
        aplikacija = item.aplikacija
        oddelek = item.obrat_oddelek.oddelek
        item_url = item.url if item.url.startswith('/') else f'/{item.url}'

        if selected_app_type == 'režija' and aplikacija in group_apps_by_oddelek_2nd_level:
            # Group by aplikacija first, then oddelek for režija
            if aplikacija not in grouped_data:
                grouped_data[aplikacija] = {}
            if oddelek not in grouped_data[aplikacija]:
                grouped_data[aplikacija][oddelek] = []
            grouped_data[aplikacija][oddelek].append({
                'url': item_url
            })
        else:
            # Default grouping by oddelek first, then aplikacija
            if oddelek not in grouped_data:
                grouped_data[oddelek] = {}
            if aplikacija not in grouped_data[oddelek]:
                grouped_data[oddelek][aplikacija] = []
            grouped_data[oddelek][aplikacija].append({
                'url': item_url
            })

    # Merge static links into grouped_data
    for oddelek, apps in static_links.items():
        if oddelek not in grouped_data:
            grouped_data[oddelek] = {}
        for app in apps:
            aplikacija = app['aplikacija']
            if aplikacija not in grouped_data[oddelek]:
                grouped_data[oddelek][aplikacija] = []
            grouped_data[oddelek][aplikacija].append({
                'url': app['url'],
                'icon': app['icon']
            })

    # Ensure that all values in grouped_data are arrays
    for oddelek, aplikacije in grouped_data.items():
        for aplikacija, items in aplikacije.items():
            if not isinstance(items, list):
                grouped_data[oddelek][aplikacija] = [items]  # Wrap single items in a list

    # Send icons for 1st level labels to the frontend
    return JsonResponse({
        'grouped_data': grouped_data,
        'group_apps_by_oddelek_2nd_level': group_apps_by_oddelek_2nd_level,
        'first_level_icons': first_level_icons
    })


@login_required
def manage_permissions(request):
    current_user = request.user
    print(f"Request method: {request.method}")  # Debug the request method

    if request.method == 'POST':
        print("POST request detected")  # Confirm POST request handling

        user_username = request.POST.get('user')
        print(f"User selected: {user_username}")  # Debugging the selected user

        # List to collect error messages
        error_messages = []

        if user_username == current_user.username:
            error_messages.append("You cannot update your own permissions.")
            return redirect_to_failed_page(request, error_messages)

        selected_user = get_object_or_404(User, username=user_username)

        # Fetch roles for current user
        current_user_roles = UserAppRole.objects.filter(username=current_user)

        # Restrict permission changes based on current user roles
        for app_id in request.POST.getlist('app_id[]'):
            role_name = request.POST.get(f'role_{app_id}')
            print(f"Updating app {app_id} with role {role_name}")  # Debugging the role assignment
            app = AplikacijeObratiOddelki.objects.get(aplikacije_obrati_oddelki_id=app_id)

            # Check if the current user can manage this app
            current_user_app_role = current_user_roles.filter(app_url_id=app).first()
            if not current_user_app_role or current_user_app_role.role_name == 'osnovni':
                error_messages.append(f"You do not have permission to manage app {app_id}.")
                continue  # Skip apps the user does not have permission for

            # Fetch the selected user's role for the app
            selected_user_app_role = UserAppRole.objects.filter(username=selected_user, app_url_id=app).first()
            selected_user_current_role = selected_user_app_role.role_name if selected_user_app_role else 'osnovni'

            # Check if current user is attempting to modify an admin
            if selected_user_current_role == 'admin' and current_user_app_role.role_name != 'admin':
                error_messages.append(f"You cannot modify admin roles for app {app_id} without admin rights.")
                continue

            # Ensure vodjas cannot assign admin roles
            if current_user_app_role.role_name == 'vodja' and (role_name == 'admin' or selected_user_current_role == 'admin'):
                error_messages.append(f"You cannot assign or modify admin roles for app {app_id}.")
                continue

            # Ensure the selected user is in the same department for vodja/admin roles
            selected_obrat = selected_user.obrat_oddelek.obrat
            selected_oddelek = selected_user.obrat_oddelek.oddelek
            current_obrat = current_user.obrat_oddelek.obrat
            current_oddelek = current_user.obrat_oddelek.oddelek

            # Check if the user has wildcard permissions (LTH) for either obrat or oddelek
            if not (
                (current_obrat == 'LTH' or current_obrat == selected_obrat) and
                (current_oddelek == 'LTH' or current_oddelek == selected_oddelek)
            ):
                error_messages.append(f"You do not manage {selected_user.username}'s obrat or oddelek.")
                continue

            # Update or create the user's role for the app
            UserAppRole.objects.update_or_create(
                username=selected_user,
                app_url_id=app,
                defaults={'role_name': role_name}
            )

        if error_messages:
            return redirect_to_failed_page(request, error_messages)

        # Redirect to the success page when permissions are updated successfully
        return redirect_to_success_page(request)

    print("Handling GET request")  # Debug if GET request is handled

    # Handle GET requests
    users = User.objects.exclude(username=current_user.username)  # Exclude current user
    selected_user = None

    # Fetch apps that the current logged-in user can manage
    user_roles = UserAppRole.objects.filter(username=current_user)
    admin_apps = user_roles.filter(role_name='admin').values_list('app_url_id', flat=True)
    vodja_apps = user_roles.filter(role_name='vodja').values_list('app_url_id', flat=True)

    # Fetch apps based on current user's roles
    apps = AplikacijeObratiOddelki.objects.filter(
        aplikacije_obrati_oddelki_id__in=admin_apps.union(vodja_apps)
    ).select_related('obrat_oddelek').order_by('aplikacija', 'obrat_oddelek__obrat', 'obrat_oddelek__oddelek')

    # Prepare roles by app
    roles_by_app = {}
    for app in apps:
        # Fetch the mapped roles for the app's role group
        role_group_mappings = RoleGroupMapping.objects.filter(role_group=app.role_group)
        mapped_roles = list(role_group_mappings.values_list('app_role', flat=True))
        roles_by_app[app.aplikacije_obrati_oddelki_id] = mapped_roles

    # Group apps by their name (aplikacija)
    grouped_apps = defaultdict(list)
    for app in apps:
        app_role = UserAppRole.objects.filter(username=selected_user, app_url_id=app).first()
        app.current_role = app_role.role_name if app_role else 'osnovni'
        max_role = user_roles.filter(app_url_id=app).first().role_name

        # Adjust available roles based on the current user's maximum role for the app
        available_roles = roles_by_app[app.aplikacije_obrati_oddelki_id]

        # If the selected user has admin role, ensure only admins can modify
        if app.current_role == 'admin' and max_role != 'admin':
            available_roles = ['admin']  # Limit modification if the user is not an admin
        elif app.current_role == 'admin':
            available_roles = roles_by_app[app.aplikacije_obrati_oddelki_id]  # Allow admin changes if user is admin

        app.available_roles = available_roles
        grouped_apps[app.aplikacija].append(app)

    # Convert defaultdict to regular dict for template compatibility
    grouped_apps = dict(grouped_apps)

    # Debugging: Print grouped_apps structure
    for app_name, app_list in grouped_apps.items():
        print(f"App Name: {app_name}")
        for app in app_list:
            print(f"  - {app.obrat_oddelek.obrat} - {app.obrat_oddelek.oddelek}: {app.current_role}")

    context = {
        'users': users,
        'selected_user': selected_user,
        'grouped_apps': grouped_apps,
        'roles_by_app': roles_by_app,
    }

    return render(request, 'accounts/manage_permissions.html', context)

def redirect_to_failed_page(request, error_messages):
    """Utility function to redirect to the failed page with error messages."""
    context = {'error_messages': error_messages}
    return render(request, 'accounts/manage_permissions_failed.html', context)

def redirect_to_success_page(request):
    """Utility function to redirect to the success page."""
    context = {'success_message': 'Permissions updated successfully.'}
    return render(request, 'accounts/manage_permissions_success.html', context)

@login_required
def manage_permissions_ajax(request):
    print(f"manage_permissions_ajax received for AJAX update")
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        user_username = request.GET.get('user')
        if user_username:
            selected_user = get_object_or_404(User, username=user_username)
            current_user = request.user

            if selected_user == current_user:
                return HttpResponseBadRequest("You cannot update your own permissions.")

            # Fetch apps that the current logged-in user can manage
            user_roles = UserAppRole.objects.filter(username=current_user)
            admin_apps = user_roles.filter(role_name='admin').values_list('app_url_id', flat=True)
            vodja_apps = user_roles.filter(role_name='vodja').values_list('app_url_id', flat=True)

            # Fetch apps based on current user's roles
            apps = AplikacijeObratiOddelki.objects.filter(
                aplikacije_obrati_oddelki_id__in=admin_apps.union(vodja_apps)
            ).select_related('obrat_oddelek').order_by('aplikacija', 'obrat_oddelek__obrat', 'obrat_oddelek__oddelek')

            # Prepare roles_by_app with a fallback to 'osnovni' if no mapped roles are found
            roles_by_app = {}
            for app in apps:
                role_group_mappings = RoleGroupMapping.objects.filter(role_group=app.role_group)
                mapped_roles = list(role_group_mappings.values_list('app_role', flat=True))

                if not mapped_roles:
                    mapped_roles = ['osnovni']  # Default to 'osnovni' if no mapped roles are found
                
                roles_by_app[app.aplikacije_obrati_oddelki_id] = mapped_roles

            # Group apps by their name (aplikacija)
            grouped_apps = defaultdict(list)
            for app in apps:
                app_role = UserAppRole.objects.filter(username=selected_user, app_url_id=app).first()
                app.current_role = app_role.role_name if app_role else 'osnovni'
                max_role = user_roles.filter(app_url_id=app).first().role_name

                # Adjust available roles based on the current user's maximum role for the app
                available_roles = roles_by_app[app.aplikacije_obrati_oddelki_id][:roles_by_app[app.aplikacije_obrati_oddelki_id].index(max_role) + 1]

                # If the selected user has admin role, ensure only admins can modify
                if app.current_role == 'admin' and max_role != 'admin':
                    available_roles = ['admin']  # Limit modification if the user is not an admin
                elif app.current_role == 'admin':
                    available_roles = roles_by_app[app.aplikacije_obrati_oddelki_id]  # Allow admin changes if user is admin

                app.available_roles = available_roles
                grouped_apps[app.aplikacija].append(app)

            # Convert defaultdict to regular dict for template compatibility
            grouped_apps = dict(grouped_apps)

            # Debugging: Print grouped_apps structure
            for app_name, app_list in grouped_apps.items():
                print(f"App Name: {app_name}")
                for app in app_list:
                    print(f"  - {app.obrat_oddelek.obrat} - {app.obrat_oddelek.oddelek}: {app.current_role}")

            # Prepare context for rendering
            context = {
                'grouped_apps': grouped_apps,
                'roles_by_app': roles_by_app,
                'selected_user': selected_user,
            }

            html_response = render_to_string('accounts/manage_permissions_partial.html', context)

            if not html_response.strip():  # Check if the response is empty
                html_response = "<p>There was an issue rendering the user permissions.</p>"

            return JsonResponse({'html': html_response})

        return HttpResponseBadRequest("Invalid user")

    return HttpResponseBadRequest("Invalid request")


def manage_permissions_success(request):
    return render(request, 'accounts/manage_permissions_success.html')

def manage_permissions_failed(request):
    return render(request, 'accounts/manage_permissions_failed.html')

def profile_view(request):
    print("Profile view is being rendered")
    return render(request, 'pages/profile.html')

@login_required
def add_user(request):
    current_user = request.user
    user_roles = UserAppRole.objects.filter(username=current_user)

    # Determine the relevant 'obrati' and 'oddelki' based on the user's role
    if current_user.user_role == 'osnovni':
        # For 'osnovni' users, limit 'obrati' and 'oddelki' to their own
        relevant_obrati_oddelek = current_user.obrat_oddelek
        relevant_obrati_oddelki = ObratiOddelki.objects.filter(
            obrati_oddelki_id=relevant_obrati_oddelek.obrati_oddelki_id
        ).order_by('obrat', 'oddelek')
        logger.debug(f"ObratiOddelki for 'osnovni' user: {relevant_obrati_oddelki}")
    else:
        # For 'vodja' or 'admin', fetch all 'obrati' and 'oddelki'
        # If the user's obrat is 'LTH', fetch all; otherwise, filter by the user's obrat
        if current_user.obrat_oddelek.obrat == 'LTH':
            relevant_obrati_oddelki = ObratiOddelki.objects.all().order_by('obrat', 'oddelek')
        else:
            relevant_obrati_oddelki = ObratiOddelki.objects.filter(
                Q(obrat=current_user.obrat_oddelek.obrat)  # Filter by the current user's obrat
            ).order_by('obrat', 'oddelek')
        
        logger.debug(f"ObratiOddelki for 'vodja' or 'admin' user: {relevant_obrati_oddelki}")

    # Pass available oddelki to JavaScript
    available_oddelki = json.dumps(list(relevant_obrati_oddelki.values('obrati_oddelki_id', 'obrat', 'oddelek')), cls=DjangoJSONEncoder)  

    # Fetch all groups created by the current user
    available_groups = UserGroup.objects.filter(created_by=current_user)
    # Fetch all obrat_oddelek groups
    available_obrat_oddelek_groups = ObratOddelekGroup.objects.filter(
        Q(obrat_oddelek__obrat=current_user.obrat_oddelek.obrat) | 
        Q(obrat_oddelek__obrat='LTH')
    )

    groups_json = json.dumps([
        {'id': group.id, 'name': group.name}
        for group in available_groups
    ])

    if request.method == 'POST':
        form = UserForm(request.POST, current_user=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()  # Save the user first to create or update the instance

            # Assign the selected groups to the user
            group_ids = request.POST.getlist('groups[]')  # Ensure matching name attribute
            logger.debug(f"Groups received from form submission: {group_ids}")  # Debugging statement
            user.groups.set(group_ids)

            obrat_oddelek_group_ids = request.POST.getlist('obrat_oddelek_groups[]')
            if can_edit_obrat_oddelek_groups(current_user, user):
                user.obrat_oddelek_groups.set(obrat_oddelek_group_ids)

            user.save()
            messages.success(request, 'User added successfully')
            return redirect('user_add_success')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserForm(current_user=request.user)
        form.fields['obrat_oddelek'].queryset = relevant_obrati_oddelki
        logger.debug(f"Form 'obrat_oddelek' queryset: {form.fields['obrat_oddelek'].queryset}")

    context = {
        'form': form,
        'obrati': relevant_obrati_oddelki.values_list('obrat', flat=True).distinct(),
        'oddelki': relevant_obrati_oddelki,
        'available_oddelki': available_oddelki,
        'selected_obrat': request.POST.get('obrat'),
        'selected_oddelek': request.POST.get('oddelek'),
        'available_groups': available_groups,
        'available_obrat_oddelek_groups': available_obrat_oddelek_groups,
        'groups_json': groups_json,
    }
    return render(request, 'accounts/add_user.html', context)

def can_edit_obrat_oddelek_groups(current_user, target_user):
    # Determine if the current user can edit obrat_oddelek_groups of the target user
    if current_user.user_role == 'vodja' and current_user.obrat_oddelek == target_user.obrat_oddelek:
        return True
    if current_user.user_role == 'admin':
        return True
    return False

@csrf_exempt
def add_user_ajax(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            group_ids = data.get('groups', [])

            print(f"Username received for AJAX update: {username}")
            print(f"Groups received for update: {group_ids}")

            # Ensure group IDs are correctly processed as integers
            group_ids = [int(id) for id in group_ids]

            user = get_object_or_404(User, username=username)
            
            # Update the user's information
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            user.email = data.get('email', user.email)
            user.user_role = data.get('user_role', user.user_role)
            user.obrat_oddelek_id = data.get('obrat_oddelek', user.obrat_oddelek_id)

            # Update the user's groups
            user.user_groups.set(group_ids)
            user.save()

            # Debug: Fetch groups to confirm
            updated_groups = user.user_groups.all()
            print(f"Current groups for user {username} after update: {[group.name for group in updated_groups]}")

            return JsonResponse({'success': True})
        
        except json.JSONDecodeError:
            print("Invalid JSON format received")
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
        except Exception as e:
            print(f"Error updating user: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    print("Invalid request for add_user_ajax.")
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@csrf_exempt
def update_user_groups(request):
    if request.method == 'POST':
        try:
            # Log the raw request body for debugging
            print(f"Raw request body: {request.body}")

            # Parse JSON data from the request
            data = json.loads(request.body)
            username = data.get('username')
            group_ids = data.get('groups', [])

            # Log the parsed data
            print(f"Username received for group update: {username}")
            print(f"Groups received for update: {group_ids}")

            # Convert group IDs to integers
            group_ids = [int(id) for id in group_ids]

            # Fetch the user and update groups
            user = get_object_or_404(User, username=username)
            user.user_groups.set(group_ids)
            user.save()

            # Log the updated groups for the user
            updated_groups = user.user_groups.all()
            print(f"Updated groups for user {username}: {[group.name for group in updated_groups]}")

            return JsonResponse({'success': True})

        except json.JSONDecodeError:
            print("Invalid JSON format received")
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
        except Exception as e:
            print(f"Error updating user: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    print("Invalid request for update_user_groups.")
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def user_search(request):
    query = request.GET.get('q', '')
    logger.debug(f"Search query received: {query}")
    current_user = request.user

    if len(query) > 2:
        User = get_user_model()
        try:
            user = User.objects.get(username=query)
            user_groups = user.user_groups.all()  # Fetch groups from UserGroup model
            obrat_oddelek_groups = user.obrat_oddelek_groups.all()  # Fetch groups from ObratOddelekGroup model

            # Determine if the current user can edit the searched user
            can_edit = True
            if current_user == user:
                can_edit = False

            # Check user role hierarchy
            role_hierarchy = {'osnovni': 1, 'vodja': 2, 'admin': 3}
            if role_hierarchy.get(current_user.user_role, 0) <= role_hierarchy.get(user.user_role, 0):
                can_edit = False

            # Check obrat and oddelek permissions
            if current_user.user_role == 'vodja' and can_edit:
                if current_user.obrat_oddelek != user.obrat_oddelek:
                    if current_user.obrat_oddelek.obrat != 'LTH' and current_user.obrat_oddelek != 'LTH':
                        can_edit = False
                    elif current_user.obrat_oddelek.obrat == 'LTH' and current_user.obrat_oddelek.oddelek != user.obrat_oddelek.oddelek:
                        can_edit = False
                    elif current_user.obrat_oddelek.oddelek == 'LTH' and current_user.obrat_oddelek.obrat != user.obrat_oddelek.obrat:
                        can_edit = False

            # Retrieve obrat_oddelek details for debugging
            obrat_oddelek_instance = user.obrat_oddelek
            logger.debug(f"User's obrat_oddelek ID: {user.obrat_oddelek_id}")
            logger.debug(f"User's obrat_oddelek instance: {obrat_oddelek_instance}")

            # Store the searched user's ID in the session
            request.session['searched_user_id'] = user.id

            # Prepare user data to be returned
            user_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'user_role': user.user_role,
                'obrat_oddelek': {
                    'id': obrat_oddelek_instance.obrati_oddelki_id if obrat_oddelek_instance else None,
                    'label': f"{obrat_oddelek_instance.obrat} - {obrat_oddelek_instance.oddelek}" if obrat_oddelek_instance else ''
                },
                'groups': [group.name for group in user_groups],  # Include all UserGroups
                'obrat_oddelek_groups': [group.name for group in obrat_oddelek_groups],  # Include all ObratOddelekGroups
                'can_edit': can_edit
            }

            logger.debug(f"User found: {user_data}")
            return JsonResponse({'users': [user_data]})

        except User.DoesNotExist:
            logger.error("User not found.")
            return JsonResponse({'users': []}, status=404)
        except Exception as e:
            logger.error(f"Error occurred in user_search: {str(e)}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    else:
        logger.error("No valid search query or too short")
        return JsonResponse({'users': []}, status=400)

@csrf_exempt
def update_group_members(request):
    
    if request.method == 'POST':
        print("Received POST request in update_group_members")
        data = json.loads(request.body)
        print(f"Data received: {data}")

        group_id = data.get('group_id')
        user_ids = data.get('user_ids', [])  # List of selected user IDs

        print(f"Group ID: {group_id}, User IDs: {user_ids}")

        try:
            # Fetch the group, ensuring it exists and was created by the current user
            group = get_object_or_404(UserGroup, id=group_id, created_by=request.user)
            print(f"Found group: {group.name}")

            # Fetch users based on IDs
            users = User.objects.filter(id__in=user_ids)
            print(f"Users found for IDs: {[user.username for user in users]}")

            # Update group members
            group.members.set(users)
            group.save()  # Ensure changes are saved
            print(f"Updated members for group: {group.name}")

            # Debugging: Check current members after update
            current_members = group.members.all()
            print(f"Current members in group after update: {[member.username for member in current_members]}")

            return JsonResponse({'success': True})
        except Exception as e:
            print(f"Error updating group members: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        print("Invalid request method for update_group_members")
        return JsonResponse({'success': False})



@csrf_exempt
def add_group_ajax(request):
    if request.method == 'POST':
        print("Received POST request in add_group_ajax")
        try:
            data = json.loads(request.body)
            print(f"Data received: {data}")

            group_name = data.get('name')
            print(f"Group name: {group_name}")

            if group_name:
                group, created = UserGroup.objects.get_or_create(name=group_name, created_by=request.user)
                print(f"Group {'created' if created else 'found'}: {group.name}, ID: {group.id}")
                return JsonResponse({'success': True, 'group_id': group.id})
            
            print("Group name missing in request data")
            return JsonResponse({'success': False, 'error': 'Group name missing'})
        
        except json.JSONDecodeError:
            print("Invalid JSON format received")
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
    else:
        print("Invalid request method for add_group_ajax")
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


def manage_groups(request):
    
    print("manage_groups view accessed")
    group_id = request.GET.get('group_id')
    print(f"Group ID from request: {group_id}")

    if group_id:
        # Use prefetch_related instead of select_related for many-to-many relationships
        group = get_object_or_404(UserGroup.objects.prefetch_related('members'), id=group_id, created_by=request.user)
        members = group.members.all()  # This fetches the latest members
        members_data = [{'id': member.id, 'name': f"{member.first_name} {member.last_name}"} for member in members]
        print(f"Members of group '{group.name}': {members_data}")
        return JsonResponse({'success': True, 'members': members_data})

    groups = UserGroup.objects.filter(created_by=request.user).prefetch_related('members')
    context = {'groups': groups}
    print("Rendering manage_groups template")
    return render(request, 'accounts/manage_groups.html', context)


def add_group(request):
    # Get the selected 'obrat' from the request parameters

    obrat_short = request.session.get('current_obrat', '')
    context_from_processor = available_users_processor(request)
    available_users = context_from_processor['available_users']

    user_groups = UserGroup.objects.filter(created_by=request.user)

    # Handle the form submission
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            form.save_m2m()
            messages.success(request, 'Skupina uspešno dodana.')
            return redirect('manage_groups')
        else:
            messages.error(request, 'Prosim popravite napake spodaj.')
    else:
        form = GroupForm()

    # Serialize available users to JSON
    users_json = json.dumps([
        {'id': user.id, 'name': f"{user.first_name} {user.last_name} ({user.username})"}
        for user in available_users
    ])

    context = {
        'form': form,
        'available_users': available_users,
        'user_groups': user_groups,
        'users_json': users_json,
    }

    return render(request, 'accounts/add_group.html', context)

#%% Obrat Oddelek Group
@login_required
def get_obrat_oddelek_groups(request):
    """Fetch Obrat Oddelek Groups dynamically based on selection."""
    logger.debug("Received request to get_obrat_oddelek_groups")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request GET parameters: {request.GET}")

    obrat_oddelek_id = request.GET.get('obrat_oddelek_id')
    logger.debug(f"Extracted obrat_oddelek_id: {obrat_oddelek_id}")

    if obrat_oddelek_id:
        try:
            # Use pk instead of id
            obrat_oddelek = get_object_or_404(ObratiOddelki, pk=obrat_oddelek_id)
            groups = ObratOddelekGroup.objects.filter(obrat_oddelek=obrat_oddelek)
            logger.debug(f"Found groups: {groups}")
            return render(request, 'partials/obrat_oddelek_groups.html', {'groups': groups})
        except Exception as e:
            logger.error(f"Error fetching groups: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    else:
        logger.warning("Invalid request: obrat_oddelek_id is missing")
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)



@login_required
def add_obrat_oddelek_group(request):
    """View to add a new Obrat Oddelek Group or manage existing ones."""

    # Retrieve the searched user from the session
    searched_user_id = request.session.get('searched_user_id')
    if not searched_user_id:
        messages.error(request, 'No user selected for this operation.')
        return redirect('user_search')  # Redirect to search if no user is found

    searched_user = get_object_or_404(User, id=searched_user_id)

    # Fetch the context data for available ObratiOddelki
    context_data = user_obrati_oddelki_processor(request)

    # Handle the form submission
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            form.save_m2m()
            messages.success(request, 'Obrat Oddelek Group successfully added.')
            if request.htmx:
                # Return a partial template if it's an HTMX request
                return render(request, 'partials/obrat_oddelek_group_form.html', context_data)
            else:
                return redirect('manage_obrat_oddelek_groups')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = GroupForm()

    context = {
        'form': form,
        'available_users': context_data['available_obrat_oddelki'],
        'obrat_oddelek_groups': ObratOddelekGroup.objects.filter(obrat_oddelek=searched_user.obrat_oddelek),
        'users_json': json.dumps([
            {'id': user.id, 'name': f"{user.first_name} {user.last_name} ({user.username})"}
            for user in User.objects.filter(obrat_oddelek=searched_user.obrat_oddelek)
        ]),
        'available_obrat_oddelki': context_data['available_obrat_oddelki'],
        'prefilled_obrat_oddelek': context_data['prefilled_obrat_oddelek'],
    }

    if request.htmx:
        # Return partial template for HTMX requests
        return render(request, 'partials/obrat_oddelek_group_form.html', context)

    # Render the full template for regular requests
    return render(request, 'accounts/add_obrat_oddelek_group.html', context)


@login_required
def manage_obrat_oddelek_groups(request):
    """View to manage Obrat Oddelek Groups."""
    group_id = request.GET.get('group_id')
    if group_id:
        group = get_object_or_404(ObratOddelekGroup, id=group_id)
        members = group.members.all()
        context = {'available_users': members}
        return render(request, 'partials/user_selection.html', context)
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)



@csrf_exempt
def add_obrat_oddelek_group_ajax(request):
    """AJAX handler for adding a new Obrat Oddelek Group."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            group_name = data.get('name')
            obrat_oddelek_id = data.get('obrat_oddelek_id')

            if group_name and obrat_oddelek_id:
                obrat_oddelek = get_object_or_404(ObratiOddelki, id=obrat_oddelek_id)
                group, created = ObratOddelekGroup.objects.get_or_create(name=group_name, obrat_oddelek=obrat_oddelek)
                
                # Respond with the new group data to HTMX
                return JsonResponse({'success': True, 'group_id': group.id})
            
            return JsonResponse({'success': False, 'error': 'Group name or Obrat Oddelek ID missing'})
        
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@login_required
def get_taskstep_status_data(request):
    # Get the current obrat from the session (or any other way you manage it)
    obrat_code = request.session.get('current_obrat', '')
    # print(f"Obrat Code from session: {obrat_code}")

    obrat_long = get_long_obrat(obrat_code)
    # print(f"Converted short obrat '{obrat_code}' to long obrat '{obrat_long}'")

    # Define the start and end dates for the current month
    today = timezone.now()
    start_of_month = today.replace(day=1)
    end_of_month = start_of_month + relativedelta(months=1, days=-1)
    # print(f"Start of month: {start_of_month}, End of month: {end_of_month}")

    # Filter task steps that belong to steppers of the current obrat and have status modified this month
    task_steps = TaskStep.objects.filter(
        stepper__obrat_oddelek__obrat=obrat_long,
        status_modified_at__range=[start_of_month, end_of_month]
    )
    print(f"Number of TaskSteps found: {task_steps.count()}")

    # Aggregate counts for each status grouped by oddelki
    status_data = task_steps.values('status', 'stepper__obrat_oddelek__oddelek').annotate(count=Count('id'))
    # print(f"Status Data by Oddelki: {list(status_data)}")

    # Map statuses to specific colors for the frontend based on your theme palette
    statuses = {
        "Queued": {"color": "#6c757d", "label": "Queued"},
        "Active": {"color": "#17a2b8", "label": "Active"},
        "Complete": {"color": "#28a745", "label": "Complete"},
        "Expired": {"color": "#dc3545", "label": "Expired"},
        "ExpiredComplete": {"color": "#ffc107", "label": "Expired & Complete"}
    }
    # print(f"Defined Statuses: {statuses}")

    # Group the data by statuses and oddelki
    grouped_data = {}
    for item in status_data:
        status_label = statuses[item['status']]['label']
        oddelek = item['stepper__obrat_oddelek__oddelek']
        count = item['count']

        if status_label not in grouped_data:
            grouped_data[status_label] = {}
        grouped_data[status_label][oddelek] = count

    # print(f"Grouped Data: {grouped_data}")

    # Prepare the data in the format required for Chart.js
    # Use `.get()` to avoid KeyError when a status is missing
    chart_data = {
        'labels': [statuses[status]['label'] for status in statuses.keys()],  # Labels for the statuses
        'counts': [sum(grouped_data.get(statuses[status]['label'], {}).values()) for status in statuses.keys()],  # Total count per status
        'colors': [statuses[status]['color'] for status in statuses.keys()],
        'grouped_data': grouped_data  # Include the grouped data for the tooltip
    }
    # print(f"Prepared Chart Data: {chart_data}")

    return JsonResponse(chart_data)

@login_required
def get_taskstep_trend_data(request):
    obrat_code = request.session.get('current_obrat', '')
    print(f"Obrat Code from session: {obrat_code}")

    obrat_long = get_long_obrat(obrat_code)
    print(f"Converted short obrat '{obrat_code}' to long obrat '{obrat_long}'")

    # Define the date range: past 12 months including the current month
    today = timezone.now()
    start_date = (today - relativedelta(months=11)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_date = today

    print(f"Fetching data from {start_date} to {end_date}")

    # Query for TaskSteps with status "Expired" or "Complete", within the date range
    task_steps = TaskStep.objects.filter(
        stepper__obrat_oddelek__obrat=obrat_long,
        status__in=["Expired", "Complete"],
        status_modified_at__range=[start_date, end_date]
    ).annotate(month=TruncMonth('status_modified_at')).values('month', 'status').annotate(count=Count('id')).order_by('month')

    print(f"Number of TaskSteps found: {task_steps.count()}")

    # Prepare data for chart.js
    months = [start_date + relativedelta(months=i) for i in range(12)]
    labels = [month.strftime('%b %Y') for month in months]
    expired_data = [0] * 12
    complete_data = [0] * 12

    # Create a mapping from month to index in the data arrays
    month_indices = {month.strftime('%Y-%m'): idx for idx, month in enumerate(months)}

    # Populate the data arrays with counts from the query results
    for entry in task_steps:
        month_str = entry['month'].strftime('%Y-%m')
        idx = month_indices.get(month_str)
        if idx is not None:
            if entry['status'] == 'Expired':
                expired_data[idx] = entry['count']
            elif entry['status'] == 'Complete':
                complete_data[idx] = entry['count']

    print(f"Final Labels: {labels}")
    print(f"Final Expired Data: {expired_data}")
    print(f"Final Complete Data: {complete_data}")

    # Return the data in JSON format
    chart_data = {
        'labels': labels,
        'expired_data': expired_data,
        'complete_data': complete_data
    }

    return JsonResponse(chart_data)

@login_required
def get_taskstep_status_oddelki_data(request):
    obrat_code = request.session.get('current_obrat', '')
    obrat_long = get_long_obrat(obrat_code)
    today = timezone.now()
    start_of_month = today.replace(day=1)
    end_of_month = start_of_month + relativedelta(months=1, days=-1)

    # Filter task steps that belong to steppers of the current obrat and have status "Expired" or "Complete" this month
    task_steps = TaskStep.objects.filter(
        stepper__obrat_oddelek__obrat=obrat_long,
        status_modified_at__range=[start_of_month, end_of_month],
        status__in=["Expired", "Complete"]
    )

    # Group by oddelek and status and count
    oddelek_data = task_steps.values('stepper__obrat_oddelek__oddelek', 'status').annotate(count=Count('id'))

    # Prepare dictionaries to hold expired and complete counts by oddelek
    expired_counts = {}
    complete_counts = {}

    for item in oddelek_data:
        oddelek = item['stepper__obrat_oddelek__oddelek']
        status = item['status']
        count = item['count']
        
        if status == "Expired":
            expired_counts[oddelek] = count
        elif status == "Complete":
            complete_counts[oddelek] = count

    # Prepare the labels and counts
    labels = list(set(expired_counts.keys()).union(set(complete_counts.keys())))

    # Ensure there are zeros for missing statuses in oddelki
    expired_data = [expired_counts.get(label, 0) for label in labels]
    complete_data = [complete_counts.get(label, 0) for label in labels]

    # Sort labels by the total count of expired + complete tasksteps, descending
    sorted_data = sorted(zip(labels, expired_data, complete_data), key=lambda x: (x[1] + x[2]), reverse=True)

    sorted_labels = [item[0] for item in sorted_data]
    sorted_expired_data = [item[1] for item in sorted_data]
    sorted_complete_data = [item[2] for item in sorted_data]

    # Print statements for debugging
    print(f"Labels: {sorted_labels}")
    print(f"Expired Data: {sorted_expired_data}")
    print(f"Complete Data: {sorted_complete_data}")

    # Prepare chart data for frontend
    chart_data = {
        'labels': sorted_labels,
        'expired_data': sorted_expired_data,
        'complete_data': sorted_complete_data,
    }

    return JsonResponse(chart_data)

