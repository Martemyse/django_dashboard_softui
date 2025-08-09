# vgradni_deli/management/commands/sync_montaza.py

from django.core.management.base import BaseCommand
from django.db import connections, transaction
from django.utils.timezone import now
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from vgradni_deli.models import PostajeStrojevTisna0104Montaza


class Command(BaseCommand):
    help = 'Sync PostajeStrojevTisna0104Montaza with external PostajeStrojevTisna0104 and set logic fields.'

    # Define script-level flags for overwriting
    OVERWRITE_ZALOGOVNIK = False
    OVERWRITE_PRODUCTION_FIELD = True

    def handle(self, *args, **options):
        # 1) Pull data from external table
        source_data_dicts = self.fetch_external_montaza_records()

        # 2) For each record, update or create local Montaza table
        with transaction.atomic():
            for src in source_data_dicts:
                obj, created = PostajeStrojevTisna0104Montaza.objects.update_or_create(
                    stroj=src['Stroj'],
                    postaja_stroja=src['Postaja stroja'],
                    defaults={
                        'opis_stroja': src['Opis stroja'],
                        'opis_postaje': src['Opis postaje'],
                        'delovno_mesto': src['Delovno mesto'],
                        'opis_delovnega_mesta': src['Opis delovnega mesta'],
                        'postaje_v_zaporedju': src['Postaje v zaporedju'],
                        'paralel': src['Paralel'],
                    }
                )
                # If newly created, set default 'zalogovnik'
                if created:
                    obj.zalogovnik = src['Delovno mesto']

                # Possibly overwrite 'zalogovnik' if the user-defined flag is True
                if self.OVERWRITE_ZALOGOVNIK:
                    obj.zalogovnik = src['Delovno mesto']

                # 3) Determine 'production_reported_on_postaja' and 'postaja_logic_used'
                #    only if we choose to overwrite it or if it's empty.
                if self.OVERWRITE_PRODUCTION_FIELD or not obj.production_reported_on_postaja:
                    logic_result = self.determine_production_postaja_logic(obj.stroj, obj.postaja_stroja)

                    # logic_result is a dict: {'postaja': '...', 'logic_used': '...'}
                    production_postaja = logic_result.get('postaja')
                    logic_used = logic_result.get('logic_used')

                    obj.production_reported_on_postaja = production_postaja
                    obj.postaja_logic_used = logic_used

                obj.save()

        self.stdout.write(self.style.SUCCESS('Montaza table synchronized and logic fields updated successfully.'))

    def fetch_external_montaza_records(self):
        # Example of pulling from external table
        with connections['external_db'].cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM public.postaje_strojev_tisna0104
                WHERE LOWER("Opis postaje") LIKE %s
            """, ['%mon%'])

            source_data = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

        # Convert to list of dicts
        return [dict(zip(column_names, row)) for row in source_data]

    def determine_production_postaja_logic(self, stroj, postaja_stroja):
        """
        Determine which postaja is actually used for production for a given stroj & postaja_stroja.
        We'll compare the last 7 days' data at `postaja_stroja` vs. any other "highest" postaja 
        for the same stroj.

        Return a dict with:
        {
            'postaja': 'xxx',
            'logic_used': 'actual_postaja' or 'highest_postaja' or 'none_found'
        }
        """
        seven_days_ago = timezone.now() - relativedelta(days=7)

        # Production data on the actual postaja
        production_report_on_actual = self.fetch_reported_production(
            stroj=stroj,
            postaja=postaja_stroja,
            since_date=seven_days_ago
        )

        # Find whichever postaja has the highest production volume (in the last 7 days) for this stroj
        highest_postaja, production_report_on_highest = self.fetch_highest_production_postaja(
            stroj=stroj,
            since_date=seven_days_ago
        )

        # If no highest_postaja found or production is zero, fallback
        if highest_postaja is None:
            # No production data found for this stroj at all
            if production_report_on_actual > 0:
                return {
                    'postaja': postaja_stroja,
                    'logic_used': 'actual_postaja'
                }
            else:
                return {
                    'postaja': postaja_stroja,  # or some default
                    'logic_used': 'none_found'
                }

        # If actual postaja is at least 80% of the highest, assume actual postaja
        if production_report_on_highest > 0 and production_report_on_actual >= Decimal(production_report_on_highest) * Decimal('0.8'):
            return {
                'postaja': postaja_stroja,
                'logic_used': 'actual_postaja'
            }
        else:
            # Fallback to highest postaja
            return {
                'postaja': highest_postaja,
                'logic_used': 'highest_postaja'
            }


    def fetch_reported_production(self, stroj, postaja, since_date):
        """
        Query the external DB (realizacija_proizvodnje_postaje_opravila) for the total produced 
        parts from 'since_date' until now, for a given stroj & postaja, 
        where Opravilo=2250 (the relevant production code).

        Return a numeric volume (good_parts + bad_parts) or 0 if none found.
        """
        query = """
            SELECT
                COALESCE(SUM("Kolicina celice" + "Izmet celice"), 0) AS total_produced
            FROM realizacija_proizvodnje_postaje_opravila
            WHERE "Stroj" = %s
            AND "Postaja" = %s
            AND "Opravilo" = CAST(%s AS TEXT)
            AND "Dnevni datum" >= %s
        """

        with connections['external_db'].cursor() as c:
            c.execute(query, [stroj, postaja, '2250', since_date])
            result = c.fetchone()
            return result[0] if result else Decimal('0')


    def fetch_highest_production_postaja(self, stroj, since_date):
        """
        Find the postaja (for the given stroj) that has the highest production
        volume in the last 7 days (since_date), where Opravilo=2250.

        Return a tuple: (postaja_str, volume)
        If no production data is found, return (None, Decimal('0')).
        """
        query = """
            SELECT "Postaja",
                COALESCE(SUM("Kolicina celice" + "Izmet celice"), 0) AS total_produced
            FROM realizacija_proizvodnje_postaje_opravila
            WHERE "Stroj" = %s
            AND "Opravilo" = CAST(%s AS TEXT)
            AND "Dnevni datum" >= %s
            GROUP BY "Postaja"
            ORDER BY total_produced DESC
            LIMIT 1
        """
        with connections['external_db'].cursor() as c:
            c.execute(query, [stroj, '2250', since_date])
            result = c.fetchone()
            return result if result else (None, Decimal('0'))
