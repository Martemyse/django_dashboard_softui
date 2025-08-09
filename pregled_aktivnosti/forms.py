from django import forms
from .models import Stepper, TaskStep, Attachment
from home.models import UserGroup, ObratiOddelki, User
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
import os

class StepperForm(forms.ModelForm):
    project = forms.CharField(
        label="Projekt",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    assigner = forms.CharField(
        label="Vodja",
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    assignee = forms.CharField(
        label="Dodeljenec",
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    assignee_username = forms.CharField(
        label="AD uporabniško ime (prijavno ime za PC/Infor)",
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=UserGroup.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        required=False,
        label="Skupine uporabnikov"
    )
    obrat_oddelek = forms.ModelChoiceField(
        label="Obrat in Oddelek",
        queryset=ObratiOddelki.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="--- Izberite obrat in oddelek ---"
    )

    class Meta:
        model = Stepper
        fields = ['project','assigner', 'assignee', 'assignee_username', 'groups', 'obrat_oddelek']


class TaskStepForm(forms.ModelForm):
    PRIORITY_CHOICES = [
        ('1', 'Nizka - 1'),
        ('2', 'Srednja - 2'),
        ('3', 'Visoka - 3')
    ]

    machine = forms.CharField(
        label="Stroj",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    product = forms.CharField(
        label="Artikel",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        label="Opis naloge",
        widget=forms.Textarea(attrs={'class': 'form-control'}),
        required=True
    )
    class TaskStepForm(forms.ModelForm):
        exp_time = forms.DateField(
            label="Datum izteka",
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=True
        )

        def clean_exp_time(self):
            exp_time = self.cleaned_data['exp_time']
            return timezone.make_aware(datetime.combine(exp_time, datetime.min.time()))
        
    priority = forms.ChoiceField(
        label="Prioriteta",
        choices=PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )

    class Meta:
        model = TaskStep
        fields = ['machine', 'product', 'description', 'exp_time', 'priority']


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True  # Allow multiple files to be selected

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class AttachmentForm(forms.Form):
    files = MultipleFileField(
        label="Dodajte datoteke", 
        required=False
    )

    class Meta:
        model = Attachment
        fields = ['files']

    def save(self, task_step, username, *args, **kwargs):
        files = self.cleaned_data.get('files', [])
        for file in files:
            # Get the base filename
            filename = os.path.basename(file.name)
            
            # Define the user-specific path
            user_directory = os.path.join('uploads', username)
            full_directory_path = os.path.join(settings.MEDIA_ROOT, user_directory)
            
            # Ensure the user directory exists
            if not os.path.exists(full_directory_path):
                os.makedirs(full_directory_path)
            
            # Construct the file path
            file_path = os.path.join(user_directory, filename)
            
            # Overwrite the file if it already exists
            if default_storage.exists(file_path):
                default_storage.delete(file_path)  # Delete existing file

            # Save the new file
            saved_path = default_storage.save(file_path, file)
            
            # Create the Attachment object in the database
            Attachment.objects.create(task_step=task_step, file=saved_path)


class GroupForm(forms.ModelForm):
    name = forms.CharField(
        label="Ime skupine",
        max_length=255,
        widget=forms.TextInput(attrs={'id': 'new_group_name_add_group', 'class': 'form-control'})
    )

    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'id': 'user_selection_add_group'}),
        label="Člani skupine"
    )

    class Meta:
        model = UserGroup
        fields = ['name', 'members']
