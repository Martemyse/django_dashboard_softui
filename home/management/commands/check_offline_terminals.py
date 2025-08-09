# import threading
# from django.core.management.base import BaseCommand
# from django.utils import timezone
# from datetime import timedelta
# from home.models import OnlineUser

# class Command(BaseCommand):
#     help = 'Checks for terminals that have gone offline every 3 minutes'

#     def handle(self, *args, **options):
#         # Use an event for more efficient timing control
#         stop_event = threading.Event()

#         def check_offline_terminals():
#             while not stop_event.wait(timeout=180):  # 180 seconds = 3 minutes
#                 timeout = timezone.now() - timedelta(minutes=2)
#                 offline_terminals = OnlineUser.objects.filter(
#                     is_terminal=True,
#                     last_seen__lt=timeout,
#                     sign_out_time__isnull=True
#                 )
#                 for terminal in offline_terminals:
#                     terminal.sign_out_time = timezone.now()
#                     terminal.save()
#                     print(f"Terminal {terminal.terminal.terminal_hostname} marked as offline.")

#         # Start the loop in a separate thread to allow for smooth execution
#         check_thread = threading.Thread(target=check_offline_terminals, daemon=True)
#         check_thread.start()

#         # Keep the main thread running, waiting for a manual stop (CTRL+C or stop command)
#         try:
#             while check_thread.is_alive():
#                 check_thread.join(1)  # Keep the main thread alive
#         except KeyboardInterrupt:
#             print("Stopping offline terminal check...")
#             stop_event.set()
#             check_thread.join()
