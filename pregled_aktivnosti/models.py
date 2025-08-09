from django.db import models
import uuid
from home.models import ObratiOddelki, UserGroup  # Importing from the home app

class Stepper(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    project = models.CharField(max_length=255, blank=False, null=False)
    assigner = models.CharField(max_length=255, blank=False, null=False)
    assignee = models.CharField(max_length=255, blank=False, null=False)
    assignee_username = models.CharField(max_length=255, blank=False, null=False)
    loggedusername = models.CharField(max_length=255, blank=False, null=False)
    obrat_oddelek = models.ForeignKey(ObratiOddelki, on_delete=models.CASCADE, related_name='steppers')
    groups = models.ManyToManyField(UserGroup, blank=True, related_name='steppers')

    class Meta:
        db_table = 'stepper'
        constraints = [
            models.UniqueConstraint(fields=['project', 'assigner'], name='unique_project_assigner')
        ]


class TaskStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    exp_time = models.DateTimeField(null=False, blank=False)
    order = models.IntegerField(blank=False, null=False)
    status = models.CharField(max_length=50, default="Queued")
    stepper = models.ForeignKey('Stepper', on_delete=models.CASCADE, related_name='steps')
    machine = models.CharField(max_length=255, blank=True, null=True)
    product = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=False, null=False)
    priority = models.IntegerField(choices=[(1, 'Nizka'), (2, 'Srednja'), (3, 'Visoka')], default=2)
    status_modified_at = models.DateTimeField(null=True, blank=True)  # Removed auto_now=True to allow manual setting
    status_modified_by = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'task_step'


class Action(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    action_name = models.CharField(max_length=255, blank=False, null=False)
    task_step = models.ForeignKey(TaskStep, on_delete=models.CASCADE, related_name='actions')
    user = models.CharField(max_length=255, blank=False, null=False)

    class Meta:
        db_table = 'action'


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_step = models.ForeignKey(TaskStep, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attachment'

    def __str__(self):
        return f"Attachment for TaskStep {self.task_step.id}: {self.file.name}"
