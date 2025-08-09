# home/signals.py

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from .models import OnlineUser, Terminal
from utils.utils import get_client_ip  # Assuming you have a utility function to get client IP

@receiver(user_logged_in)
def create_online_user(sender, request, user, **kwargs):
    # Get the client's IP address
    client_ip = get_client_ip(request)

    # Check if the IP matches any terminal
    try:
        terminal = Terminal.objects.get(ip_address=client_ip)
        is_terminal = True
    except Terminal.DoesNotExist:
        terminal = None
        is_terminal = False

    # Sign out any previous sessions for this user
    OnlineUser.objects.filter(user=user, sign_out_time__isnull=True).update(sign_out_time=timezone.now())

    # Create an OnlineUser instance
    online_user = OnlineUser.objects.create(
        user=user,
        terminal=terminal,
        ip_address=client_ip,
        is_terminal=is_terminal,
        sign_in_time=timezone.now(),
        can_receive_notifications=True
    )
    print(f"OnlineUser created: {online_user}")
