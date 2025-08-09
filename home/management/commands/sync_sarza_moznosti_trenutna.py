from django.core.management.base import BaseCommand
from django.db import transaction, connections
from decimal import Decimal
from django.db import models
from django.db.models import F, IntegerField
from django.db.models.functions import Cast
from vgradni_deli.models import (
    StrojArtikelSarzaMoznosti,
    StrojArtikelSarzaTrenutno,
    Part,
    PostajeStrojevTisna0104Montaza,
    TiBOMKosovnica,
    PreteklostZamenjavSarzTisna1160,
)

import pandas as pd

class Command(BaseCommand):
    help = 'Populate StrojArtikelSarzaMoznosti and StrojArtikelSarzaTrenutno tables.'

    def handle(self, *args, **options):
        missing_entries = []  # To track missing data

        # Step 1: Fetch all montaza machines and postaja from PostajeStrojevTisna0104Montaza
        montaza_data = self.fetch_montaza_data()

        # Step 2: Process each montaza entry
        for montaza in montaza_data:
            stroj = montaza['stroj']

            # Step 3: Bulk fetch all Artikel and Nalog for the given Stroj
            all_products = self.fetch_all_products(stroj)
            if not all_products:
                print(f"No products found for stroj: {stroj}")
                missing_entries.append({"stroj": stroj, "artikel": None, "nalog": None, "missing_type": "products"})
                continue

            # Group the fetched products by Artikel
            artikli_to_nalogi = {}
            for product in all_products:
                artikel = product['Artikel']
                nalog = product['Nalog']
                if artikel not in artikli_to_nalogi:
                    artikli_to_nalogi[artikel] = set()
                artikli_to_nalogi[artikel].add(nalog)

            # Step 4: Process each Artikel and its associated Nalogi
            for artikel, nalogi in artikli_to_nalogi.items():
                # print(f"Processing Artikel: {artikel}")

                # Fetch vgradni deli (parts) from tibom1110_kosovnica
                parts = self.fetch_parts(artikel)
                if not parts:
                    # print(f"No parts found for artikel: {artikel}")
                    missing_entries.append({"stroj": stroj, "artikel": artikel, "nalog": None, "missing_type": "parts"})
                    continue

                for part in parts:
                    del_id = part['del_id']

                    # Step 5: Process each Nalog for the current Artikel
                    for nalog in nalogi:
                        # print(f"Processing Nalog: {nalog} for Artikel: {artikel}")

                        # Fetch all sarzas from preteklost_zamenjav_sarz_tisna1160
                        sarzas = self.fetch_sarzas(nalog, del_id)
                        if not sarzas:
                            # print(f"No sarzas found for Nalog: {nalog}, Del_ID: {del_id}")
                            missing_entries.append({"stroj": stroj, "artikel": artikel, "nalog": nalog, "missing_type": "sarzas"})
                            continue

                        for sarza in sarzas:
                            # Populate StrojArtikelSarzaMoznosti
                            self.populate_sarza_moznosti(stroj, artikel, sarza, del_id, nalog)

                    # Populate StrojArtikelSarzaTrenutno (only once per part)
                    self.populate_sarza_trenutno(stroj, artikel, del_id)

        # Save missing entries to CSV and Excel
        self.save_missing_entries(missing_entries)
        self.stdout.write(self.style.SUCCESS('StrojArtikelSarzaMoznosti and StrojArtikelSarzaTrenutno tables populated successfully.'))

    def save_missing_entries(self, missing_entries):
        """
        Save missing entries into CSV and Excel files.
        """
        if not missing_entries:
            print("No missing entries to save.")
            return

        # Convert to DataFrame
        df = pd.DataFrame(missing_entries)

        # Save to CSV and Excel
        csv_file_path = "missing_entries.csv"
        excel_file_path = "missing_entries.xlsx"
        df.to_csv(csv_file_path, index=False)
        df.to_excel(excel_file_path, index=False)

        print(f"Missing entries have been saved to {csv_file_path} and {excel_file_path}")
        
    def fetch_montaza_data(self):
        """
        Fetch all records from the PostajeStrojevTisna0104Montaza table using raw SQL.
        """
        query = """
            SELECT 
                stroj,
                opis_stroja,
                postaja_stroja,
                opis_postaje,
                delovno_mesto,
                opis_delovnega_mesta,
                postaje_v_zaporedju,
                paralel,
                obmocje,
                rocna_montaza,
                zalogovnik
            FROM public.postaje_strojev_tisna0104_montaza
        """
        with connections['default'].cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]  # Fetch column names
            rows = cursor.fetchall()  # Fetch all rows

        # Convert the results into a list of dictionaries for easier usage
        return [dict(zip(columns, row)) for row in rows]

    def fetch_all_products(self, stroj):
        """
        Fetch distinct Artikel and Nalog for the given Stroj across all Postaja.
        """
        with connections['external_db'].cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT p."Artikel", n."Nalog"
                FROM "realizacija_proizvodnje_postaje_opravila" p
                LEFT JOIN "zadnji_nalog" n
                ON p."Artikel" = n."Artikel" AND p."Stroj" = n."Stroj"
                WHERE p."Stroj" = %s
                ORDER BY p."Artikel", n."Nalog"
            """, [stroj])

            column_names = [desc[0] for desc in cursor.description]
            return [dict(zip(column_names, row)) for row in cursor.fetchall()]



    def fetch_parts(self, artikel):
        """
        Fetch parts for the given artikel using raw SQL.
        """
        query = """
            SELECT "del_id", "kolicina"
            FROM public.tibom1110_kosovnica
            WHERE "artikel" = %s
        """
        with connections['external_db'].cursor() as cursor:
            cursor.execute(query, [artikel])
            column_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

        # Convert the results into a list of dictionaries
        return [dict(zip(column_names, row)) for row in rows]


    def fetch_sarzas(self, nalog, del_id):
        """
        Fetch sarzas for the given nalog and del_id using raw SQL.
        """
        query = """
            SELECT "sarza"
            FROM public.preteklost_zamenjav_sarz_tisna1160
            WHERE "nalog" = %s AND "del_id" = %s
        """
        with connections['external_db'].cursor() as cursor:
            cursor.execute(query, [nalog, del_id])
            column_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

        # Convert the results into a list of dictionaries
        return [dict(zip(column_names, row)) for row in rows]


    def populate_sarza_moznosti(self, stroj, artikel, sarza, del_id, nalog):
        """
        Populate StrojArtikelSarzaMoznosti.
        """
        StrojArtikelSarzaMoznosti.objects.update_or_create(
            stroj=stroj,
            artikel=artikel,
            sarza=sarza['sarza'],
            del_id=del_id,
            nalog=nalog
        )

    def populate_sarza_trenutno(self, stroj, artikel, del_id):
        """
        Create or update entries in StrojArtikelSarzaTrenutno only for combinations
        of stroj-artikel-del_id that don't already exist. Use the sarza with the highest value.
        """
        # Get all sarza options for this combination from StrojArtikelSarzaMoznosti
        possible_sarzas = (
            StrojArtikelSarzaMoznosti.objects.filter(stroj=stroj, artikel=artikel, del_id=del_id)
            .order_by('-sarza')  # Sort directly as strings
        )

        # If there are no possible sarzas, skip
        if not possible_sarzas.exists():
            return

        # Get the sarza with the highest string value
        highest_sarza = possible_sarzas.first()

        # Check if this combination already exists in StrojArtikelSarzaTrenutno
        if not StrojArtikelSarzaTrenutno.objects.filter(stroj=stroj, artikel=artikel, del_id=del_id).exists():
            # Create a new entry in StrojArtikelSarzaTrenutno
            StrojArtikelSarzaTrenutno.objects.create(
                stroj=stroj,
                artikel=artikel,
                del_id=del_id,
                sarza=highest_sarza.sarza
            )

