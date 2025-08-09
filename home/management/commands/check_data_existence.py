from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from home.models import UserGroup, ObratOddelekGroup

class Command(BaseCommand):
    help = 'Check the existence of specific UserGroups and ObratOddelekGroups.'

    def handle(self, *args, **kwargs):
        User = get_user_model()

        # Check if UserGroup 'tc lj' exists
        if UserGroup.objects.filter(name='tc lj').exists():
            self.stdout.write(self.style.SUCCESS("UserGroup 'tc lj' exists."))
        else:
            self.stdout.write(self.style.ERROR("UserGroup 'tc lj' does not exist."))

        # Check if ObratOddelekGroup 'SIEE' exists
        if ObratOddelekGroup.objects.filter(name='SIEE').exists():
            self.stdout.write(self.style.SUCCESS("ObratOddelekGroup 'SIEE' exists."))
        else:
            self.stdout.write(self.style.ERROR("ObratOddelekGroup 'SIEE' does not exist."))

        # Check if ObratOddelekGroup 'Lean Team Obdelava LJ' exists
        if ObratOddelekGroup.objects.filter(name='Lean Team Obdelava LJ').exists():
            self.stdout.write(self.style.SUCCESS("ObratOddelekGroup 'Lean Team Obdelava LJ' exists."))
        else:
            self.stdout.write(self.style.ERROR("ObratOddelekGroup 'Lean Team Obdelava LJ' does not exist."))

        # Check if user 'dominika' exists and list all groups they are part of
        try:
            dominika = User.objects.get(username='dominika')
            dominika_groups = dominika.user_groups.all()
            self.stdout.write(self.style.SUCCESS("\nGroups that 'dominika' is part of:"))
            for group in dominika_groups:
                self.stdout.write(f"- {group.name}")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("User 'dominika' does not exist."))
