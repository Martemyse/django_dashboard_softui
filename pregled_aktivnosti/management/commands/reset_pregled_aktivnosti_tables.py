from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Drops and recreates the tables for the pregled_aktivnosti app by unapplying and reapplying migrations.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Unapplying migrations...'))

        # Unapply all migrations for the pregled_aktivnosti app
        call_command('migrate', 'pregled_aktivnosti', 'zero')
        self.stdout.write(self.style.SUCCESS('All migrations unapplied.'))

        # Reapply migrations for the pregled_aktivnosti app
        self.stdout.write(self.style.WARNING('Reapplying migrations...'))
        call_command('migrate', 'pregled_aktivnosti')
        self.stdout.write(self.style.SUCCESS('All migrations reapplied.'))
