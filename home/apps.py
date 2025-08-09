from django.apps import AppConfig

class HomeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = 'home'

    def ready(self):
        # Use a relative import to avoid import timing issues
        from . import signals  # Import signals to connect handlers
