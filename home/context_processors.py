from .models import AplikacijeObratiOddelki, User, UserAppRole, ObratiOddelki
from utils.utils import get_short_obrat, get_long_obrat
from django.db.models import Q

def get_client_ip(request):
    print(f"Request META: {request.META}")  # Log full headers
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    print(f"Detected client IP: {ip}")
    return ip

def client_ip_processor(request):
    client_ip = get_client_ip(request)
    return {
        'client_ip': client_ip
    }

def current_obrat(request):
    return {
        'current_obrat': request.session.get('current_obrat', '')
    }


def obrat_mapping(request):
    obrat_code = request.session.get('current_obrat', '')
    long_name = get_long_obrat(obrat_code)  # Correctly convert the short name to the long name
    short_name = obrat_code  # Keep the short name as is from the session

    return {
        'current_obrat': short_name,
        'current_obrat_name': short_name,
        'obrat_short_name': short_name,
        'obrat_long_name': long_name,
    }


def available_users_processor(request):
    # Determine the obrat value from the session or request
    obrat_short = request.GET.get('obrat') or request.session.get('current_obrat', 'LTH')

    # Example mapping, update accordingly if you have a different mapping logic
    obrat_long = get_long_obrat(obrat_short)  # Correctly convert the short name to the long name

    # Filter users based on the selected 'obrat'
    if obrat_short == 'LTH':
        available_users = User.objects.all()
    else:
        available_users = User.objects.filter(obrat_oddelek__obrat=obrat_long) | User.objects.filter(obrat_oddelek__obrat='LTH')

    return {'available_users': available_users}

def user_obrati_oddelki_processor(request):
    """Determines the available ObratiOddelki for the current user based on their roles."""
    current_user = request.user
    if not current_user.is_authenticated:
        return {'available_obrat_oddelki': []}

    # Fetch the searched user from the session if available
    searched_user_id = request.session.get('searched_user_id')
    searched_user = User.objects.filter(id=searched_user_id).first() if searched_user_id else None

    # Fetch the relevant ObratiOddelki based on the user's role
    if current_user.user_role == 'osnovni':
        relevant_obrati_oddelki = ObratiOddelki.objects.filter(obrati_oddelki_id=current_user.obrat_oddelek.obrati_oddelki_id).order_by('obrat', 'oddelek')
    else:
        user_roles = UserAppRole.objects.filter(username=current_user)
        if current_user.obrat_oddelek.obrat == 'LTH':
            relevant_obrati_oddelki = ObratiOddelki.objects.all().order_by('obrat', 'oddelek')
        else:
            relevant_obrati_oddelki = ObratiOddelki.objects.filter(
                Q(obrat=current_user.obrat_oddelek.obrat) | 
                Q(obrati_oddelki_id__in=user_roles.values('app_url_id__obrat_oddelek'))
            ).distinct().order_by('obrat', 'oddelek')

    # Prefill with the searched user's ObratOddelek if available
    prefilled_obrat_oddelek = searched_user.obrat_oddelek if searched_user else None

    return {
        'available_obrat_oddelki': relevant_obrati_oddelki,
        'prefilled_obrat_oddelek': prefilled_obrat_oddelek,
    }