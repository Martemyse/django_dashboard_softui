from django.contrib.auth.backends import BaseBackend
from .models import User  # Import your custom User model

class DevelopmentAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        print(f"Authenticating user: {username}")
        if username:
            try:
                # Fetch the user from your custom User model
                user = User.objects.get(username__iexact=username)
                print(f"User {username} found, bypassing password check")
                return user
            except User.DoesNotExist:
                print(f"User {username} not found")
                return None
        print("Username not provided")
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
