import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import connections
from vgradni_deli.models import (
    StrojArtikelSarzaMoznosti,
    StrojArtikelSarzaTrenutno,
)

LOG_FILE = "populate_tables_log.csv"

def initialize_log_file(file_path):
    """
    Initialize or overwrite the log file with headers.
    """
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        # Write headers
        writer.writerow([
            "timestamp", "stroj", "artikel", "sarza", "del_id", "nalog", "table", "event_type", "message"
        ])

def log_event(file_path, stroj, artikel, sarza, del_id, nalog, table, event_type, message):
    """
    Log an event to the CSV file.

    :param file_path: Path to the CSV log file
    """
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow([
            timestamp, stroj or "", artikel or "", sarza or "", del_id or "", nalog or "",
            table, event_type, message
        ])

class Command(BaseCommand):
    help = 'Populate StrojArtikelSarzaMoznosti and StrojArtikelSarzaTrenutno tables.'

    def handle(self, *args, **options):
        initialize_log_file(LOG_FILE)

        # Step 1: Fetch all montaza machines
        montaza_data = self.fetch_montaza_data()

        # Step 2: Fetch all distinct combinations of Artikel, Nalog, and Stroj
        products_data = self.fetch_all_products(montaza_data)

        # Step 3: Populate StrojArtikelSarzaMoznosti and StrojArtikelSarzaTrenutno
        self.populate_tables(products_data)

        self.stdout.write(self.style.SUCCESS('StrojArtikelSarzaMoznosti and StrojArtikelSarzaTrenutno tables populated successfully.'))

    def fetch_montaza_data(self):
        """
        Fetch all records from the PostajeStrojevTisna0104Montaza table using raw SQL.
        """
        query = """
            SELECT stroj
            FROM public.postaje_strojev_tisna0104_montaza
        """
        with connections['default'].cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        montaza_stroj_list = [row[0] for row in rows]
        for stroj in montaza_stroj_list:
            log_event(LOG_FILE, stroj, None, None, None, None, "fetch_montaza_data", "INFO", "Fetched montaza machine")
        return montaza_stroj_list

    def fetch_all_products(self, montaza_data):
        """
        Fetch all distinct combinations of Artikel, Nalog, and Stroj by joining zadnji_nalog and preteklost_zamenjav_sarz_tisna1160.
        """
        query = """
            SELECT DISTINCT
                z."Stroj",
                z."Artikel",
                p."sarza",
                p."del_id",
                z."Nalog"
            FROM "zadnji_nalog" z
            LEFT JOIN "preteklost_zamenjav_sarz_tisna1160" p
            ON z."Nalog" = p."nalog"::text
            WHERE z."Stroj" = %s
        """
        products_data = []

        with connections['external_db'].cursor() as cursor:
            for stroj in montaza_data:
                cursor.execute(query, [stroj])
                rows = cursor.fetchall()
                for row in rows:
                    product = {
                        'stroj': row[0],
                        'artikel': row[1],
                        'sarza': row[2],
                        'del_id': row[3],
                        'nalog': row[4],
                    }
                    products_data.append(product)
                    log_event(LOG_FILE, **product, table="fetch_all_products", event_type="INFO", message="Fetched product data")

        return products_data

    def populate_tables(self, products_data):
        """
        Populate StrojArtikelSarzaMoznosti and StrojArtikelSarzaTrenutno tables from the fetched product data.
        """
        for product in products_data:
            stroj = product['stroj']
            artikel = product['artikel']
            sarza = product['sarza']
            del_id = product['del_id']
            nalog = product['nalog']

            if sarza and del_id and nalog:
                # Populate StrojArtikelSarzaMoznosti
                moznosti_obj, created = StrojArtikelSarzaMoznosti.objects.update_or_create(
                    stroj=stroj,
                    artikel=artikel,
                    sarza=sarza,
                    del_id=del_id,
                    nalog=nalog
                )
                if created:
                    log_event(LOG_FILE, stroj, artikel, sarza, del_id, nalog, "StrojArtikelSarzaMoznosti", "INFO", "Created new record")
                else:
                    log_event(LOG_FILE, stroj, artikel, sarza, del_id, nalog, "StrojArtikelSarzaMoznosti", "INFO", "Updated existing record")

            # Populate StrojArtikelSarzaTrenutno (only for the highest sarza)
            highest_sarza = (
                StrojArtikelSarzaMoznosti.objects.filter(stroj=stroj, artikel=artikel, del_id=del_id)
                .order_by('-sarza')
                .first()
            )

            if highest_sarza and not StrojArtikelSarzaTrenutno.objects.filter(stroj=stroj, artikel=artikel, del_id=del_id).exists():
                StrojArtikelSarzaTrenutno.objects.create(
                    stroj=stroj,
                    artikel=artikel,
                    del_id=del_id,
                    sarza=highest_sarza.sarza
                )
                log_event(LOG_FILE, stroj, artikel, highest_sarza.sarza, del_id, None, "StrojArtikelSarzaTrenutno", "INFO", "Created new record")
            else:
                log_event(LOG_FILE, stroj, artikel, sarza, del_id, None, "StrojArtikelSarzaTrenutno", "INFO", "Skipped due to existing record")
