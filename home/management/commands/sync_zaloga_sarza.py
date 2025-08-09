from django.core.management.base import BaseCommand
from django.db import connections
from decimal import Decimal
from vgradni_deli.models import ZalogaSarza

class Command(BaseCommand):
    help = 'Sync the Django-managed ZalogaSarza table with all valid data from the external ZalogaSarza table.'

    def handle(self, *args, **options):
        self.stdout.write("Starting sync from external ZalogaSarza to Django-managed ZalogaSarza...")
        self.sync_zaloga_sarza()
        self.stdout.write(self.style.SUCCESS('Sync complete.'))

    def sync_zaloga_sarza(self):
        """
        Fetch all valid data (non-NaN) from the external ZalogaSarza table and insert it into the Django-managed ZalogaSarza table.
        """
        # Fetch valid data (non-NaN zaloga) from the external ZalogaSarza table
        with connections['external_db'].cursor() as cursor:
            cursor.execute("""
                SELECT 
                    dobavni_nalog, del_id, del_opis, sarza, datum_dobave, zaloga
                FROM zaloga_sarza
                WHERE zaloga IS NOT NULL AND zaloga NOT IN ('NaN')
            """)
            external_data = cursor.fetchall()

        # Prepare entries for bulk creation
        zaloga_objects = [
            ZalogaSarza(
                dobavni_nalog=row[0],
                del_id=row[1],
                del_opis=row[2],
                sarza=row[3],
                datum_dobave=row[4],
                zaloga=Decimal(row[5])
            )
            for row in external_data
        ]

        # Bulk create to improve performance
        ZalogaSarza.objects.bulk_create(zaloga_objects, ignore_conflicts=True)

        self.stdout.write(f"Populated {len(zaloga_objects)} records into ZalogaSarza.")
