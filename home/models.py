from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone
from django.db.models import Max
import uuid

class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(username, email, password, **extra_fields)

class ObratiOddelki(models.Model):
    obrati_oddelki_id = models.AutoField(primary_key=True)
    obrat = models.CharField(max_length=50, null=False)
    oddelek = models.CharField(max_length=50, null=False)

    class Meta:
        db_table = 'obrati_oddelki'
        unique_together = (('obrat', 'oddelek'),)

class UserGroup(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    members = models.ManyToManyField('User', related_name='user_groups')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_groups'
        unique_together = ('name', 'created_by')  # Ensure uniqueness on name and created_by fields together

    def __str__(self):
        return self.name
    
class ObratOddelekGroup(models.Model):
    """
    This model represents a group that is specific to an obrat and oddelek.
    Only supervisors or admins can manage the members of these groups.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    members = models.ManyToManyField('User', related_name='obrat_oddelek_groups')
    obrat_oddelek = models.ForeignKey('ObratiOddelki', on_delete=models.CASCADE, related_name='groups')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_obrat_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'obrat_oddelek_groups'
        unique_together = ('name', 'obrat_oddelek')

    def __str__(self):
        return f"{self.name} - {self.obrat_oddelek.obrat} - {self.obrat_oddelek.oddelek}"

class User(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True)
    user_role = models.CharField(max_length=50)
    obrat_oddelek = models.ForeignKey('ObratiOddelki', related_name='users_obrat_oddelek', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    password = models.CharField(max_length=128, default='!', editable=False)
    groups = models.ManyToManyField(UserGroup, related_name='group_members', blank=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)  # Tracks user activity
    is_rezija = models.BooleanField(default=True)

    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.username

    def is_online(self):
        """
        Check if user is active within the last minute.
        """
        return self.last_heartbeat and (timezone.now() - self.last_heartbeat).seconds < 60

class Terminal(models.Model):
    """
    Model to represent a terminal or signal data on the factory floor.
    """
    terminal_hostname = models.CharField(max_length=100, unique=True, null=True, blank=True)  # Replaces hostname
    label_rom = models.CharField(max_length=50, null=True, blank=True)
    network_type = models.CharField(max_length=10, null=True, blank=True)  # LAN or WIFI
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    roboservice_url = models.URLField(null=True, blank=True)
    opis = models.CharField(max_length=255, null=True, blank=True)  # Added opis
    is_rom = models.BooleanField(default=False)  # Added is_rom
    delovno_mesto = models.CharField(max_length=100, null=True, blank=True)  # Added delovno_mesto
    postaja = models.CharField(max_length=50, null=True, blank=True)  # Added postaja

    class Meta:
        db_table = 'terminals'

    def __str__(self):
        return f"{self.terminal_hostname} - {self.label_rom}"

    def save(self, *args, **kwargs):
        # Automatically set is_rom to True if label_rom starts with 'ROM'
        if self.label_rom and self.label_rom.startswith('ROM'):
            self.is_rom = True
        else:
            self.is_rom = False
        super().save(*args, **kwargs)  # Call the original save method

    def get_last_get_request(self):
        """Get the timestamp of the last GET request."""
        return Signal.get_last_get_request(self)

    def get_last_put_request(self):
        """Get the timestamp of the last PUT request."""
        return Signal.get_last_put_request(self)


class TerminalMachine(models.Model):
    """
    Machine model for multiple machines linked to a terminal.
    """
    terminal = models.ForeignKey(Terminal, on_delete=models.CASCADE, related_name="terminal_machines")
    machine_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'terminal_machines'

    def __str__(self):
        return f"{self.terminal.terminal_hostname} - {self.machine_name}"

class Signal(models.Model):
    terminal = models.ForeignKey(Terminal, on_delete=models.CASCADE, related_name="signals")
    timestamp = models.DateTimeField()  # Remove auto_now_add to use parsed timestamp
    level = models.CharField(max_length=10)  # e.g., INFO, WARNING, ERROR
    message = models.TextField()

    class Meta:
        unique_together = ('terminal', 'timestamp', 'message')

    def __str__(self):
        return f"Signal for {self.terminal} at {self.timestamp}"

    @staticmethod
    def get_last_get_request(terminal):
        """Get the timestamp of the last GET request for a specific terminal."""
        last_get_signal = Signal.objects.filter(
            terminal=terminal,
            message__icontains='GET'
        ).order_by('-timestamp').first()
        return last_get_signal.timestamp if last_get_signal else None

    @staticmethod
    def get_last_put_request(terminal):
        """Get the timestamp of the last PUT request for a specific terminal."""
        last_put_signal = Signal.objects.filter(
            terminal=terminal,
            message__icontains='PUT'
        ).order_by('-timestamp').first()
        return last_put_signal.timestamp if last_put_signal else None
    
    @property
    def last_get_signal(self):
        """Get the last GET Signal object for this terminal."""
        if not hasattr(self, '_last_get_signal'):
            self._last_get_signal = self.signals.filter(
                message__icontains='GET'
            ).order_by('-timestamp').first()
        return self._last_get_signal

    @property
    def last_put_signal(self):
        """Get the last PUT Signal object for this terminal."""
        if not hasattr(self, '_last_put_signal'):
            self._last_put_signal = self.signals.filter(
                message__icontains='PUT'
            ).order_by('-timestamp').first()
        return self._last_put_signal


    
class SignalLimit(models.Model):
    terminal = models.ForeignKey(Terminal, on_delete=models.CASCADE)
    signal_key = models.CharField(max_length=100)  # e.g., @Temperatura
    limit_value = models.FloatField()
    notification_email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"Limit for {self.signal_key} on {self.terminal} - {self.limit_value}"

class OnlineUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_terminal = models.BooleanField(default=False)
    sign_in_time = models.DateTimeField(default=timezone.now)
    sign_out_time = models.DateTimeField(null=True, blank=True)
    can_receive_notifications = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)  # Add this field

    class Meta:
        db_table = 'online_users'
        indexes = [
            models.Index(fields=['user', 'sign_out_time']),
            models.Index(fields=['terminal', 'sign_out_time']),
        ]

    def __str__(self):
        if self.is_terminal and self.terminal:
            return f"{self.user.username} on terminal {self.terminal}"
        return f"{self.user.username} at IP {self.ip_address}"

    def is_active(self):
        return self.sign_out_time is None

class ClientToken(models.Model):
    """
    Session-specific token for user or terminal-based notification routing.
    """
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_tokens')
    terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, blank=True, related_name='client_tokens')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'client_tokens'
        unique_together = ('user', 'terminal')
        indexes = [
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['terminal', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.user.username}'s Token ({self.token})"

    def is_expired(self):
        """
        Checks if token has expired.
        """
        return self.expires_at and timezone.now() > self.expires_at

class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=100)  # Šifra sporočila
    sender_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    receiver_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_notifications')
    receiver_token = models.ForeignKey(ClientToken, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    receiver_terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, blank=True)
    notification_content = models.TextField()
    reply_content = models.TextField(null=True, blank=True)
    receiver_notified = models.BooleanField(default=False)
    time_sent = models.DateTimeField(auto_now_add=True)
    time_received = models.DateTimeField(null=True, blank=True)
    time_replied = models.DateTimeField(null=True, blank=True)
    notify_response_email = models.BooleanField(default=False)  # New field

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['receiver_user', 'receiver_notified']),
            models.Index(fields=['receiver_terminal', 'receiver_notified']),
        ]
    
    def __str__(self):
        return f"Notification {self.key} from {self.sender_user} to {self.receiver_user or self.receiver_terminal}"

class NotificationStatus(models.Model):
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE, related_name='status')
    status = models.CharField(
        max_length=50,
        choices=[
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('read', 'Read'),
            ('replied', 'Replied'),
        ],
        default='sent'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_statuses'

    def __str__(self):
        return f"Notification {self.notification.key} is {self.status}"

class RoleGroup(models.Model):
    role_group_id = models.AutoField(primary_key=True)
    role_group = models.CharField(max_length=255, unique=True, null=False)

    class Meta:
        db_table = 'role_groups'

class RoleGroupMapping(models.Model):
    role_group_mapping_id = models.AutoField(primary_key=True)
    role_group = models.ForeignKey(RoleGroup, on_delete=models.CASCADE)
    app_role = models.CharField(max_length=50, null=False)
    user_role_mapping = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'role_group_mappings'

class AplikacijeObratiOddelki(models.Model):
    aplikacije_obrati_oddelki_id = models.AutoField(primary_key=True)
    url = models.CharField(max_length=255, unique=True, null=False)
    aplikacija = models.CharField(max_length=50, null=False)
    type = models.CharField(max_length=50, choices=[('režija', 'Režija'), ('proizvodnja', 'Proizvodnja')])
    role_group = models.ForeignKey('RoleGroup', on_delete=models.CASCADE)
    obrat_oddelek = models.ForeignKey('ObratiOddelki', related_name='aplikacije_obrat_oddelek', on_delete=models.CASCADE)

    class Meta:
        db_table = 'aplikacije_obrati_oddelki'
        unique_together = (('url', 'obrat_oddelek'),)

class UserAppRole(models.Model):
    user_app_roles_id = models.AutoField(primary_key=True)
    username = models.ForeignKey(User, on_delete=models.CASCADE)
    app_url_id = models.ForeignKey(AplikacijeObratiOddelki, on_delete=models.CASCADE)
    app_url = models.CharField(max_length=255, null=True, blank=True)  # Adding the app_url column
    role_name = models.CharField(max_length=50, null=False)  # basic, elevated, admin, etc.

    class Meta:
        db_table = 'user_app_roles'
