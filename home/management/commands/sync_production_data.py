# vgradni_deli/management/commands/sync_production_data.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from django.db import connections

from vgradni_deli.models import (
    Part, Batch, ProductionTransaction, InboundTransaction, AdjustmentTransaction,
    InboundVirtualBatchAllocation, InboundVirtualBatchItem,
    StrojArtikelSarzaTrenutno, TiBOMKosovnica,
    ZalogaSarza, CumulativeCount, PostajeStrojevTisna0104Montaza
)

from utils.log_production_event import log_production_event, initialize_log_file
import csv

class Command(BaseCommand):
    help = 'Sync production and inbound data incrementally (differential approach) and update CumulativeCount.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        start_date = today - relativedelta(days=7)  # Start 7 days ago

        for day in range(7):  # Loop for the last 7 days
            sync_date = start_date + timedelta(days=day)  # Increment date in the range
            self.stdout.write(f"Syncing data for: {sync_date}")
            
            self.sync_production_data(sync_date)
            self.sync_inbound_data(sync_date)

        self.stdout.write(self.style.SUCCESS('Incremental Sync complete for the last 7 days.'))

    def sync_production_data(self, day_date):
        """
        Fetch cumulative production data for the given day_date, calculate differences,
        insert only incremental transactions. Update CumulativeCount accordingly,
        and log the results to CSV.
        """
        # Prepare a CSV log file
        log_file_path = f"production_sync_{day_date}.csv"
    
        # Initialize log file to overwrite existing data
        initialize_log_file(log_file_path)
        
        # Open the log file in append mode to write events
        with open(log_file_path, mode='a', newline='', encoding='utf-8') as log_file:
            csv_writer = csv.writer(log_file, delimiter=';')

            # 1) Get relevant (stroj, postaja)
            relevant_combinations = PostajeStrojevTisna0104Montaza.objects.filter(
                production_reported_on_postaja__isnull=False
            ).values_list('stroj', 'production_reported_on_postaja')

            relevant_combinations = list(relevant_combinations)
            if not relevant_combinations:
                self.stdout.write(self.style.WARNING("No relevant machines or postaja combos found."))
                return

            # Prepare placeholders
            placeholders = ", ".join(["(%s, %s)"] * len(relevant_combinations))
            params = [item for combo in relevant_combinations for item in combo]

            query = f"""
                SELECT
                    "Artikel",
                    "Stroj",
                    "Postaja",
                    "Opravilo",
                    COALESCE("Kolicina celice", 0) + COALESCE("Izmet celice", 0) AS total_parts,
                    "Dnevni datum" AS datum
                FROM realizacija_proizvodnje_postaje_opravila
                WHERE DATE("Dnevni datum") = %s
                  AND "Opravilo" ~ '^\d+$'
                  AND CAST("Opravilo" AS INTEGER) = 2250
                  AND ("Stroj", "Postaja") IN ({placeholders})
            """

            with connections['external_db'].cursor() as cursor:
                cursor.execute(query, [day_date] + params)
                production_data = cursor.fetchall()

            if not production_data:
                self.stdout.write(self.style.WARNING(f"No production data for {day_date}"))
                return

            for rec in production_data:
                artikel, stroj, postaja, opravilo, total_parts, datum = rec
                total_parts = Decimal(total_parts)

                # Log that we found a row
                log_production_event(
                    csv_writer,
                    artikel=artikel,
                    stroj=stroj,
                    postaja=postaja,
                    del_id="",  # No del_id yet
                    sarza="",
                    event_type="INFO",
                    message=f"Found production row with total_parts={total_parts}"
                )

                # 2) Fetch BOM items
                with connections['external_db'].cursor() as bom_cursor:
                    bom_cursor.execute("""
                        SELECT del_id, "kolicina" AS quantity_per_artikel
                        FROM tibom1110_kosovnica
                        WHERE artikel = %s
                    """, [artikel])
                    bom_items = bom_cursor.fetchall()

                # If no BOM, log & continue
                if not bom_items:
                    log_production_event(
                        csv_writer,
                        artikel=artikel,
                        stroj=stroj,
                        postaja=postaja,
                        del_id="",
                        sarza="",
                        event_type="WARNING",
                        message="No BOM items found."
                    )
                    continue

                for del_id, quantity_per_artikel in bom_items:
                    quantity_per_artikel = Decimal(quantity_per_artikel or '1.0')
                    # Attempt to find sarza (Trenutno)
                    try:
                        trenutna = StrojArtikelSarzaTrenutno.objects.get(
                            stroj=stroj,
                            artikel=artikel,
                            del_id=del_id
                        )
                    except StrojArtikelSarzaTrenutno.DoesNotExist:
                        # Log missing sarza
                        log_production_event(
                            csv_writer,
                            artikel=artikel,
                            stroj=stroj,
                            postaja=postaja,
                            del_id=del_id,
                            sarza="",
                            event_type="WARNING",
                            message="No active sarza found for this part."
                        )
                        continue

                    part, _ = Part.objects.get_or_create(del_id=del_id)
                    batch, _ = Batch.objects.get_or_create(
                        part=part,
                        sarza=trenutna.sarza,
                        defaults={'datum_dobave': day_date}
                    )

                    new_cumulative = total_parts * quantity_per_artikel
                    old_cumulative = self.get_old_cumulative(artikel, stroj, postaja, del_id, trenutna.sarza)
                    difference = new_cumulative - old_cumulative

                    if difference != 0:
                        # Create ProductionTransaction
                        prod_tx = ProductionTransaction.objects.create(
                            part=part,
                            batch=batch,
                            stroj=stroj,
                            postaja=postaja,
                            artikel=artikel,
                            quantity_consumed=difference,
                            day_date=day_date
                        )

                        # Update CumulativeCount
                        self.save_new_cumulative(
                            artikel, stroj, postaja,
                            del_id, trenutna.sarza, new_cumulative
                        )

                        # Log success
                        log_production_event(
                            csv_writer,
                            artikel=artikel,
                            stroj=stroj,
                            postaja=postaja,
                            del_id=del_id,
                            sarza=trenutna.sarza,
                            event_type="INFO",
                            message=f"Created ProductionTransaction id={prod_tx.id}, consumed={difference}"
                        )
                    else:
                        # Log that nothing was consumed because difference <= 0
                        log_production_event(
                            csv_writer,
                            artikel=artikel,
                            stroj=stroj,
                            postaja=postaja,
                            del_id=del_id,
                            sarza=trenutna.sarza,
                            event_type="INFO",
                            message=f"Skipped, difference={difference:.2f} == 0"
                        )

        self.stdout.write(self.style.SUCCESS(f"Production data synced for {day_date}, see '{log_file_path}'."))

    def sync_inbound_data(self, day_date):

        """
        Similar approach for inbound data from ZalogaSarza.
        We get cumulative inbound totals for each (del_id, sarza).
        Insert incremental InboundTransactions or InboundVirtualBatchAllocation if blocked.
        Update CumulativeCount.

        """
        # inbound_data = (ZalogaSarza.objects.using('external_db')
        #                 .filter(datum_dobave=day_date)
        #                 .all())
        
        inbound_data = (ZalogaSarza.objects
                .filter(datum_dobave=day_date)
                .all())

        # For inbound, we assume ZalogaSarza gives us a cumulative 'zaloga' for each (del_id, sarza) for the day.
        # We'll treat each inbound record as cumulative total stock received for that del_id, sarza combination at day_date.
        # We'll need default stroj/postaja (e.g., WAREHOUSE/INBOUND_AREA) or logic to find them.
        
        # If part.is_inbound_blocked = True, we create InboundVirtualBatchAllocation instead of InboundTransaction.
        stroj = "WAREHOUSE"
        postaja = "INBOUND_AREA"

        for zd in inbound_data:
            part, _ = Part.objects.get_or_create(del_id=zd.del_id, defaults={'description': zd.del_opis})
            batch, _ = Batch.objects.get_or_create(part=part, sarza=zd.sarza, defaults={'datum_dobave': zd.datum_dobave})
            
            new_cumulative = zd.zaloga
            old_cumulative = self.get_old_cumulative(
                artikel="",  # Inbound may not have artikel directly. If needed, store a placeholder or find artikel if known.
                stroj=stroj,
                postaja=postaja,
                del_id=zd.del_id,
                sarza=zd.sarza
            )
            
            difference = new_cumulative - old_cumulative
            if difference > 0:
                # Check if inbound is blocked
                if part.is_inbound_blocked:
                    # Create InboundVirtualBatchAllocation instead of InboundTransaction
                    InboundVirtualBatchAllocation.objects.create(
                        part=part,
                        original_batch=batch,
                        stroj=stroj,
                        postaja=postaja,
                        total_inbound_quantity=difference
                    )
                else:
                    # Create InboundTransaction
                    InboundTransaction.objects.create(
                        part=part,
                        batch=batch,
                        stroj=stroj,
                        postaja=postaja,
                        quantity_added=difference,
                        day_date=day_date
                    )

                # Update cumulative count
                self.save_new_cumulative(
                    artikel="",
                    stroj=stroj,
                    postaja=postaja,
                    del_id=zd.del_id,
                    sarza=zd.sarza,
                    new_cumulative=new_cumulative
                )

    def get_old_cumulative(self, artikel, stroj, postaja, del_id, sarza):
        try:
            cc = CumulativeCount.objects.get(
                artikel=artikel,
                stroj=stroj,
                postaja=postaja,
                del_id=del_id,
                sarza=sarza
            )
            return cc.cumulative_count
        except CumulativeCount.DoesNotExist:
            return Decimal('0.0')

    def save_new_cumulative(self, artikel, stroj, postaja, del_id, sarza, new_cumulative):
        CumulativeCount.objects.update_or_create(
            artikel=artikel,
            stroj=stroj,
            postaja=postaja,
            del_id=del_id,
            sarza=sarza,
            defaults={'cumulative_count': new_cumulative}
        )
