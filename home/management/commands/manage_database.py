from django.core.management.base import BaseCommand, CommandError
import os
from django.db import connection, transaction, IntegrityError
from django.core.management import call_command
import psycopg2
import random
from django.utils import timezone
from django.conf import settings
from psycopg2 import sql
from home.models import (
    ObratiOddelki, User, RoleGroup, RoleGroupMapping, AplikacijeObratiOddelki, UserAppRole, UserGroup, ObratOddelekGroup, Notification, NotificationStatus, Terminal, ClientToken, TerminalMachine
)
from utils.utils import SAFE_URL_OBRAT_MAPPING, RAW_TO_URL_MAPPING
import pandas as pd
from django.db.models import F

DEVELOPMENT = settings.DEVELOPMENT

def populate_terminal_data():
    # Consolidated terminal data
    # Example demo terminals (sanitized IPs)
    terminal_data = [
        ["TS251PC", "LAN", "10.0.0.11"],
        ["TS103PC", "LAN", "10.0.0.12"],
        ["TS240PC", "LAN", "10.0.0.13"],
        ["TS404PC", "WIFI", None],
        ["TS114PC", "LAN", "10.0.0.14"],
        ["TS98PC", "LAN", "10.0.0.15"],
        ["TS118PC", "LAN", "10.0.0.16"],
        ["TS275PC", "LAN", "10.0.0.17"],
        ["TS176PC", "LAN", "10.0.0.18"],
        ["TS117PC", "LAN", "10.0.0.19"],
    ]

    # Additional fields for compatibility with the model
    extra_fields = [None] * 8  # To match the remaining model fields
    complete_terminal_data = [entry + extra_fields for entry in terminal_data]

    # Field names for the model
    field_names = [
        "terminal_hostname",
        "network_type",
        "ip_address",
        "label_rom",
        "roboservice_url",
        "opis",
        "is_rom",
        "delovno_mesto",
        "postaja",
    ]

    # Populate data into the Terminal model
    for data in complete_terminal_data:
        terminal_data_dict = dict(zip(field_names, data))

        # Filter out None fields
        filtered_data_dict = {k: v for k, v in terminal_data_dict.items() if v is not None}

        # Update or create the terminal
        Terminal.objects.update_or_create(
            terminal_hostname=terminal_data_dict["terminal_hostname"],
            defaults=filtered_data_dict,
        )

    print("Terminal data populated successfully.")


def populate_stroj_signal_data():
    # Define terminal data with only IP addresses for ip_address field
    stroj_signal_data = [
        ["TS100PC", "ROM1", None, None, [None]],
        ["TS101PC", "ROM2", "10.0.0.21", "http://10.0.0.21:8885/Service@listen:4006", ["TR601"]],
        ["TS102PC", "ROM3", "10.0.0.22", "http://10.0.0.22:8887/Service@listen:4008", ["TR602"]],
        ["TS103PC", "ROM4", "10.0.0.23", "http://10.0.0.23:8883/Service@listen:4003", ["TR603"]],
        ["TS104PC", "ROM5", "10.0.0.24", "http://10.0.0.24:8884/Service@listen:4004", ["TR604"]],
        ["TS105PC", "ROM6", "10.0.0.25", "http://10.0.0.25:8888/Service@listen:4003", ["TR605"]],
        ["TS106PC", "ROM7", "10.0.0.26", "http://10.0.0.26:8886/Service@listen:4007", ["TR606"]],
        ["TS107PC", "ROM8", "10.0.0.27", "http://10.0.0.27:8885/Service@listen:4006", ["TR607"]],
        ["TS108PC", "ROM9", None, None, [None]],
        ["TS109PC", "ROM10", "10.0.0.28", "http://10.0.0.28:8881/Service@listen:4000", ["TR101"]],
        ["TS110PC", "ROM11", "10.0.0.29", "http://10.0.0.29:8882/Service@listen:4005", [None]],
        ["TS111PC", "ROM12", "10.0.0.30", "http://10.0.0.30:8882/Service@listen:4005", ["TR102"]],
        ["TS112PC", "ROM13", "10.0.0.31", "http://10.0.0.31:8883/Service@listen:4002", ["TR103"]],
        ["TS113PC", "ROM14", "10.0.0.32", "http://10.0.0.32:8881/Service@listen:4001", ["TR201"]],
        ["TS114PC", "ROM15", "10.0.0.33", "http://10.0.0.33:8882/Service@listen:4002", ["TR202"]],
        ["TS115PC", "ROM16", "10.0.0.34", "http://10.0.0.34:8888/Service@listen:4000", ["TR301"]],
        ["TS116PC", "ROM17", "10.0.0.35", "http://10.0.0.35:9999/Service@listen:4002", ["TR302"]],
        ["TS117PC", "ROM18", "10.0.0.36", "http://10.0.0.36:8885/Service@listen:4005", ["TR303"]],
        ["TS118PC", "ROM19", "10.0.0.37", "http://10.0.0.37:8881/Service@listen:4001", ["TP301"]],
        ["TS119PC", "ROM20", None, None, [None]],
        ["TS120PC", "ROM21", None, None, [None]],
        ["TS121PC", "ROM22", "192.168.19.110", "http://192.168.19.110:8888/RoboService@listen:4005", ["TP501"]],
        ["TS122PC", "ROM23", None, None, [None]],
        ["TS123PC", "ROM24", "192.168.19.110", "http://192.168.19.110:8888/RoboService@listen:4005", [None]],
        ["TS124PC", "ROM25", "192.168.19.109", "http://192.168.19.109:8886/RoboService@listen:4006", ["TP401"]],
        ["TS125PC", "ROM26", "192.168.19.109", "http://192.168.19.109:8882/RoboService@listen:4002", ["TP401"]],
        ["TS126PC", "ROM27", "10.100.15.10", "http://10.100.15.10:8888/DataBlockExe", ["TP601"]],
        ["TS127PC", "ROM28", "10.100.15.10", "http://10.100.15.10:8888/DataBlockExe", ["TP601"]],
        ["TS128PC", "ROM29", "10.100.15.10", "http://10.100.15.10:8881/DataBlockExe", ["TP601"]],
        ["TS129PC", "ROM30", "10.100.15.10", "http://10.100.15.10:8881/DataBlockExe", ["TP601"]],
        ["TS130PC", "ROM31", "10.100.15.10", "http://10.100.15.10:9999/DataBlockExe", ["TP601"]],
        ["TS131PC", "ROM32", None, None, ["STGH2 Namenski"]],
        ["TS132PC", "ROM33", None, None, [None]],
        ["TS133PC", "ROM34", None, None, [None]],
        ["TS134PC", "ROM35", None, None, [None]],
        ["TS135PC", "ROM36", "10.100.40.200", "http://10.100.40.200:8888/DataBlockExe", ["TA204","TA205"]],
        ["TS136PC", "ROM37", "10.100.41.200", "http://10.100.41.200:8888/DataBlockExe", ["TA120","TA121"]],
        ["TS137PC", "ROM38", "10.100.42.200", "http://10.100.42.200:8888/DataBlockExe", [None]],
        ["TS138PC", "ROM39", None, None, [None]],
        ["TS139PC", "ROM40", "10.100.43.200", "http://10.100.43.200:8888/DataBlockExe", ["TA402","TA403"]],
        ["TS140PC", "ROM41", "10.100.44.200", "http://10.100.44.200:8888/DataBlockExe", ["TA404","TA405"]],
        ["TS141PC", "ROM42", "192.168.24.68", "http://192.168.24.68:8888/RoboService@listen:4000", ["TA631"]],
        ["TS142PC", "ROM43", "192.168.24.49", "http://192.168.24.49:8888/RoboService@listen:4000", ["TA632"]],
    ]
    
    terminal_field_names = ["terminal_hostname", "label_rom", "ip_address", "roboservice_url", "network_type"]

    # Sanitize private IPs and URLs in demo data
    def _sanitize_ip(url_or_ip, idx):
        if not url_or_ip:
            return url_or_ip
        safe_ip = f"10.0.1.{(idx % 200) + 1}"
        if isinstance(url_or_ip, str) and url_or_ip.startswith("http://"):
            # replace host part with safe_ip and generic path
            try:
                parts = url_or_ip.split('//', 1)[1]
                host_and_rest = parts.split('/', 1)
                rest = host_and_rest[1] if len(host_and_rest) > 1 else ''
                return f"http://{safe_ip}/{rest.split('/', 1)[-1]}"
            except Exception:
                return f"http://{safe_ip}"
        return safe_ip

    for i, row in enumerate(stroj_signal_data):
        # row: [hostname, label_rom, ip_address, url, machines]
        if len(row) >= 3 and isinstance(row[2], str):
            row[2] = _sanitize_ip(row[2], i)
        if len(row) >= 4 and isinstance(row[3], str):
            row[3] = _sanitize_ip(row[3], i)

    for data in stroj_signal_data:
        machine_list = data.pop(-1)  # Extract machine list
        terminal_data_dict = dict(zip(terminal_field_names, data))

        # Filter out None fields
        filtered_data_dict = {k: v for k, v in terminal_data_dict.items() if v is not None}
        filtered_data_dict.pop("is_rom", None)  # Remove is_rom explicitly if present

        # Update or create the terminal
        terminal, created = Terminal.objects.update_or_create(
            terminal_hostname=terminal_data_dict["terminal_hostname"],
            defaults=filtered_data_dict,
        )

        # Call save() to apply the is_rom logic in the model
        terminal.save()

        # Handle machines
        if machine_list:
            existing_machines = set(
                TerminalMachine.objects.filter(terminal=terminal)
                .values_list("machine_name", flat=True)
            )
            new_machines = set(machine_list) - existing_machines
            for machine in new_machines:
                if machine:  # Avoid adding None machines
                    TerminalMachine.objects.create(terminal=terminal, machine_name=machine)

    print("Stroj signal data populated successfully.")

    # Fetch all terminal data and convert to pandas DataFrame
    terminals = Terminal.objects.all().values(
        "terminal_hostname",
        "label_rom",
        "ip_address",
        "roboservice_url",
        "opis",
        "is_rom",
        "delovno_mesto",
        "postaja",
        "network_type",
    )
    terminal_df = pd.DataFrame(list(terminals))

    # Save terminal data to Excel
    terminal_df.to_excel("terminal_data.xlsx", index=False)
    print("Terminal data exported to 'terminal_data.xlsx' successfully.")

    # Fetch all terminal machine data and convert to pandas DataFrame
    terminal_machines = TerminalMachine.objects.annotate(
        terminal_hostname=F("terminal__terminal_hostname")
    ).values("terminal_hostname", "machine_name")
    terminal_machines_df = pd.DataFrame(list(terminal_machines))

    # Save terminal machine data to Excel
    terminal_machines_df.to_excel("terminal_machines_data.xlsx", index=False)
    print("Terminal machine data exported to 'terminal_machines_data.xlsx' successfully.")


# Add this function to create realistic notifications
def create_realistic_notifications():
    users = User.objects.filter(username__in=['user01', 'user02', 'user03', 'user04', 'user05'])
    terminals = Terminal.objects.all()  # Fetch all terminals

    # Realistic notification keys and contents for machining department
    notification_contents = [
        'Vzorčna obdelava novega orodja G501 je potrebna. Začetek obdelave takoj.',
        'Zamenjaj rezilni sklop G401, zaradi prekomerne obrabe.',
        'Preveri kvaliteto površine obdelovanca na stroju X210.',
        'Izvedi kalibracijo stroja X305 zaradi odstopanja v tolerancah.',
        'Pripravi vzorce za testno obdelavo na stroju X560.',
        'Zamenjaj hladilno tekočino na stroju G300. Kontrola kvalitete obdelave je potrebna.',
        'Preveri rezalne parametre za orodje T120 na liniji L5.',
        'Nastavi rezkalni stroj G401 za novo serijo obdelovancev.',
        'Opravite pregled kakovosti na končnem izdelku serije Y789.',
        'Obvestilo o nujni menjavi orodja na stroju Z401 zaradi prekomerne obrabe.'
    ]

    reply_contents = [
        'Preverjeno in potrjeno.',
        '',
        'Rezila so zamenjana, obdelava poteka.',
        'Nastavitve popravljene, obdelava ponovno steče.',
        'Stroj kalibriran, odstopanja odpravljena.',
        'Vzorec pripravljen, testna obdelava poteka.',
        'Kontrola kvalitete izvedena, izdelek ustreza zahtevam.',
        '',
        '',
        ''
    ]

    # Loop through each user and create 10 notifications for each
    for user in users:
        for i in range(10):  # Each user creates 10 notifications
            sender = user
            receiver = random.choice(users.exclude(username=sender.username))

            # Only select a terminal if available and decide randomly if to assign
            receiver_terminal = random.choice(terminals) if terminals and random.choice([True, False]) else None
            
            # Use a ClientToken if available, or create one if necessary
            receiver_token = (
                ClientToken.objects.filter(user=receiver, terminal=receiver_terminal, expires_at__gt=timezone.now()).first()
                or ClientToken.objects.create(
                    user=receiver,
                    terminal=receiver_terminal,
                    ip_address=f'10.0.0.{random.randint(1, 254)}',
                    expires_at=timezone.now() + timezone.timedelta(days=7)
                )
            )

            notification_content = notification_contents[i % len(notification_contents)]  # Rotate through contents

            # Create the notification object
            notification = Notification.objects.create(
                key=f'NOTIF-{random.randint(1000, 9999)}',  # Randomized key
                sender_user=sender,
                receiver_user=receiver,
                receiver_token=receiver_token,
                receiver_terminal=receiver_terminal,
                notification_content=notification_content,
                time_sent=timezone.now()
            )

            # Assign a random reply content
            reply_content = random.choice(reply_contents)
            if reply_content:
                notification.reply_content = reply_content
                notification.time_replied = timezone.now() - timezone.timedelta(hours=random.randint(1, 72))  # Random reply time within the last 3 days
                notification.save()  # Save the notification with the reply
                status_choice = 'replied'
            else:
                notification.reply_content = ''
                notification.save()
                # If no reply, choose from 'sent', 'delivered', or 'read'
                status_choice = random.choice(['sent', 'delivered', 'read'])

            # Create NotificationStatus for each notification
            NotificationStatus.objects.create(
                notification=notification,
                status=status_choice
            )

    print("Realistic machining department notifications and statuses created.")


class Command(BaseCommand):
    help = 'Drop and recreate the target database.'

    def handle(self, *args, **options):
        db_params = {
            'dbname': os.getenv('POSTGRES_DB', 'postgres'),  # Connect to 'postgres' database to manage other databases
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
            'host': os.getenv('POSTGRES_HOST', 'localhost' if DEVELOPMENT else 'postgres'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
        }
        
        target_db_name = 'django_overview_aplikacije'
        
        try:
            # Connect to the default 'postgres' database
            conn = psycopg2.connect(**db_params)
            conn.autocommit = True
            cur = conn.cursor()

            # Terminate all active connections to the target database
            cur.execute(sql.SQL(
                "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                "FROM pg_stat_activity "
                "WHERE pg_stat_activity.datname = %s "
                "AND pid <> pg_backend_pid();"
            ), [target_db_name])
            self.stdout.write(self.style.SUCCESS('Terminated active sessions.'))

            # Drop the target database if it exists
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {db_name}")
                        .format(db_name=sql.Identifier(target_db_name)))
            self.stdout.write(self.style.SUCCESS(f'Dropped database {target_db_name}.'))

            # Close the connection and reopen it with a user that has CREATE privileges
            cur.close()
            conn.close()

            # Now use a different user for database creation
            db_params['user'] = os.getenv('POSTGRES_USER', 'postgres')  # User with CREATEDB privileges
            db_params['password'] = os.getenv('POSTGRES_PASSWORD', 'postgres')

            conn = psycopg2.connect(**db_params)
            conn.autocommit = True
            cur = conn.cursor()

            # Create the target database
            cur.execute(sql.SQL("CREATE DATABASE {db_name}")
                        .format(db_name=sql.Identifier(target_db_name)))
            self.stdout.write(self.style.SUCCESS(f'Created database {target_db_name}.'))

            cur.close()
            conn.close()

            # Reconnect Django to the newly created database
            connection.close()

            # Run migrations
            self.stdout.write(self.style.SUCCESS('Running migrations...'))

            # Run migrations with fallback mechanism
            self.run_migrations_with_fallback()

            # Create PostgreSQL trigger
            self.create_postgres_trigger()

            # Populate initial data
            self.stdout.write(self.style.SUCCESS('Populating initial data...'))
            self.populate_initial_data()

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))

    def run_migrations_with_fallback(self):
        """
        Runs migrations with fallback to --fake if migrations fail.
        """
        apps = ['home', 'pregled_aktivnosti', 'signali_strojev', 'vgradni_deli']

        for app in apps:
            try:
                # Ensure migrations are created
                call_command('makemigrations', app)
                # Apply migrations
                call_command('migrate', app)
            except CommandError as ce:
                self.stderr.write(self.style.ERROR(f"Migration error for {app}: {str(ce)}"))
                self.stdout.write(self.style.WARNING(f"Attempting fake migration for {app}..."))
                try:
                    # Fallback to fake migration if migration fails
                    call_command('migrate', app, '--fake')
                except CommandError as fake_ce:
                    self.stderr.write(self.style.ERROR(f"Fake migration failed for {app}: {str(fake_ce)}"))

        # Apply any remaining migrations
        try:
            call_command('migrate')
        except CommandError as e:
            self.stderr.write(self.style.ERROR(f"Error during final migration step: {str(e)}"))
            self.stdout.write(self.style.WARNING("Attempting fake migration for remaining steps..."))
            call_command('migrate', '--fake')

    def create_postgres_trigger(self):
        try:
            # Connect to the database
            conn = psycopg2.connect(
                dbname=os.getenv('POSTGRES_DB', 'django_overview_aplikacije'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
                host=os.getenv('POSTGRES_HOST', 'localhost' if DEVELOPMENT else 'postgres'),
                port=int(os.getenv('POSTGRES_PORT', 5432))
            )
            cur = conn.cursor()

            # Drop the existing trigger if it exists
            self.stdout.write(self.style.SUCCESS('Dropping existing trigger if it exists...'))
            cur.execute("""
                DROP TRIGGER IF EXISTS check_task_expiration ON task_step;
            """)

            # Drop the existing function if it exists
            self.stdout.write(self.style.SUCCESS('Dropping existing function if it exists...'))
            cur.execute("""
                DROP FUNCTION IF EXISTS update_task_status;
            """)

            # Create the function for setting expired statuses
            self.stdout.write(self.style.SUCCESS('Creating PostgreSQL function update_task_status().'))
            cur.execute("""
                CREATE OR REPLACE FUNCTION update_task_status()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NEW.exp_time < now() AND NEW.status NOT IN ('Complete', 'ExpiredComplete') THEN
                        NEW.status := 'Expired';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            # Create the trigger to call the function
            self.stdout.write(self.style.SUCCESS('Creating trigger check_task_expiration on task_step table.'))
            cur.execute("""
                CREATE TRIGGER check_task_expiration
                BEFORE INSERT OR UPDATE ON task_step
                FOR EACH ROW
                EXECUTE FUNCTION update_task_status();
            """)

            # Commit the changes
            conn.commit()

            # Close the cursor and connection
            cur.close()
            conn.close()

            self.stdout.write(self.style.SUCCESS('Trigger and function created successfully.'))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))

    def populate_initial_data(self):
        with transaction.atomic():
            # Add role groups
            role_group_data = [
                {'role_group': 'roles_default'},
                {'role_group': 'roles_sledenje_akcij'},
                {'role_group': 'roles_tehnicna_cistost'},
            ]
            for rg_data in role_group_data:
                RoleGroup.objects.get_or_create(**rg_data)

            # Update to use role_group_id instead of id
            role_group_map = {rg.role_group: rg.role_group_id for rg in RoleGroup.objects.all()}


            # Create a unique list of obrati and oddelki combinations
            default_user_roles = [
                {
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'user01',
            'email': 'user01@example.com',
                    'user_role': 'admin',
                    'obrat': 'LTH',
                    'oddelek': 'LTH',
                },
                {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'username': 'user02',
            'email': 'user02@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
            'first_name': 'Alex',
            'last_name': 'Brown',
            'username': 'user03',
            'email': 'user03@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
            'first_name': 'Taylor',
            'last_name': 'Green',
            'username': 'user04',
            'email': 'user04@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
            'first_name': 'Chris',
            'last_name': 'Taylor',
            'username': 'user05',
            'email': 'user05@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Marjan',
                    'last_name': 'Klobasa',
                    'username': 'marjank',
                    'email': 'user06@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Matej',
                    'last_name': 'Šek',
                    'username': 'matejse',
                    'email': 'user07@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Ivan',
                    'last_name': 'Bizjak',
                    'username': 'ivanb',
                    'email': 'user08@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Krunoslav',
                    'last_name': 'Mijić',
                    'username': 'krunom',
                    'email': 'user09@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Alis',
                    'last_name': 'Bajrić',
                    'username': 'alisb',
                    'email': 'user10@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Natalija',
                    'last_name': 'Serec',
                    'username': 'natalijas',
                    'email': 'user11@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Blaž',
                    'last_name': 'Petek',
                    'username': 'blazp',
                    'email': 'user12@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Tehnologija obdelave'
                },
                {
                    'first_name': 'Blaž',
                    'last_name': 'Škerjanc',
                    'username': 'blazsk',
                    'email': 'user13@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Tehnologija obdelave'
                },
                {
                    'first_name': 'Dominika',
                    'last_name': 'Zorman',
                    'username': 'dominika',
                    'email': 'user14@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Ekologija'
                },
                {
                    'first_name': 'Marjan',
                    'last_name': 'Furdi',
                    'username': 'marjanfu',
                    'email': 'user15@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Ekologija'
                },
                {
                    'first_name': 'Neža',
                    'last_name': 'Gartner',
                    'username': 'nezaga',
                    'email': 'user16@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Škofja Loka',
                    'oddelek': 'Ekologija'
                },
                {
                    'first_name': 'Anže',
                    'last_name': 'Špehar',
                    'username': 'anzes',
                    'email': 'user17@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Varnost'
                },
                {
                    'first_name': 'Petra',
                    'last_name': 'Šketelj',
                    'username': 'petras',
                    'email': 'user18@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Varnost'
                },
                {
                    'first_name': 'Timotej',
                    'last_name': 'Grčar',
                    'username': 'timotejg',
                    'email': 'user19@example.com',
                    'user_role': 'osnovni',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Varnost'
                },
                {
                    'first_name': 'Aleš',
                    'last_name': 'Kranjec',
                    'username': 'aleskr',
                    'email': 'user20@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Kakovost'
                },
                {
                    'first_name': 'Aleš',
                    'last_name': 'Bostič',
                    'username': 'alesbo',
                    'email': 'user21@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Logistika'
                },
                {
                    'first_name': 'Gregor',
                    'last_name': 'Gorše',
                    'username': 'gregorg',
                    'email': 'user22@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Livarna'
                },
                {
                    'first_name': 'Sandi',
                    'last_name': 'Hvala',
                    'username': 'sandih',
                    'email': 'user23@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Orodjarna'
                },
                {
                    'first_name': 'Matija',
                    'last_name': 'Jereb',
                    'username': 'matijaj',
                    'email': 'user24@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Tehnologija livarne'
                },
                {
                    'first_name': 'Primož',
                    'last_name': 'Šušteršič',
                    'username': 'primozsu',
                    'email': 'user25@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Obdelava'
                },
                {
                    'first_name': 'Damjan',
                    'last_name': 'Rožman',
                    'username': 'damjanr',
                    'email': 'user26@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Vzdrževanje'
                },
                {
                    'first_name': 'Miha',
                    'last_name': 'Kumer',
                    'username': 'mihak',
                    'email': 'user27@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Projektna pisarna'
                },
                {
                    'first_name': 'Nada',
                    'last_name': 'Turk',
                    'username': 'nadat',
                    'email': 'user28@example.com',
                    'user_role': 'vodja',
                    'obrat': 'LTH',
                    'oddelek': 'Ekologija'
                },
                {
                    'first_name': 'Izidor',
                    'last_name': 'Šolar',
                    'username': 'izidors',
                    'email': 'user29@example.com',
                    'user_role': 'vodja',
                    'obrat': 'LTH',
                    'oddelek': 'Ekologija'
                },
                {
                    'first_name': 'Vinko',
                    'last_name': 'Drev',
                    'username': 'vinkod',
                    'email': 'user30@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Avtomatizacija'
                },
                {
                    'first_name': 'Blaž',
                    'last_name': 'Žun',
                    'username': 'blazz',
                    'email': 'user31@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'IT'
                },
                {
                    'first_name': 'Mitja',
                    'last_name': 'Bogataj',
                    'username': 'mitjab',
                    'email': 'user32@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Škofja Loka',
                    'oddelek': 'Kontroling'
                },
                {
                    'first_name': 'Anka',
                    'last_name': 'Laketic',
                    'username': 'ankala',
                    'email': 'user33@example.com',
                    'user_role': 'vodja',
                    'obrat': 'Ljubljana',
                    'oddelek': 'Kadrovska služba'
                },
                {
                    'first_name': 'Mladen',
                    'last_name': 'Jurada',
                    'username': 'mladenju',
                    'email': 'user34@example.com',
                    'user_role': 'admin',
                    'obrat': 'LTH',
                    'oddelek': 'LTH'
                },
                {
                    'first_name': 'Denis',
                    'last_name': 'Porenta',
                    'username': 'denisp',
                    'email': 'user35@example.com',
                    'user_role': 'admin',
                    'obrat': 'Ljubljana',
                    'oddelek': 'LTH'
                },
                {
                    'first_name': 'Matjaž',
                    'last_name': 'Turk',
                    'username': 'matjazt',
                    'email': 'user36@example.com',
                    'user_role': 'admin',
                    'obrat':'LTH',
                    'oddelek': 'LTH'
                }
            ]

            locations_data = {
                'Ljubljana': ['Obdelava', 'Livarna', 'Ekologija', 'Varnost', 'Kakovost'],
                'Škofja Loka': ['Obdelava', 'Livarna', 'Ekologija', 'Varnost', 'Kakovost'],
                'Trata': ['Obdelava', 'Livarna', 'Ekologija', 'Razvoj'],
                'Benkovac': ['Obdelava', 'Livarna', 'Ekologija', 'Varnost', 'Kakovost'],
                'Ohrid': ['Obdelava', 'Livarna', 'Ekologija', 'Varnost', 'Kakovost'],
                'Čakovec': ['Obdelava', 'Livarna', 'Ekologija', 'Varnost', 'Kakovost'],
                'LTH': ['Obdelava', 'Livarna', 'Ekologija', 'Varnost', 'Kakovost']
            }

            locations = [{'obrat': obrat, 'oddelek': oddelek} for obrat, oddelki in locations_data.items() for oddelek in oddelki]

            # Create a unique list of obrati and oddelki combinations
            obrati_oddelki_data = [
                {'obrat': user['obrat'], 'oddelek': user['oddelek']}
                for user in default_user_roles
            ] + locations

            obrati_oddelki_data = [dict(t) for t in {tuple(d.items()) for d in obrati_oddelki_data}]

            obrati_oddelki = [ObratiOddelki(**obrat) for obrat in obrati_oddelki_data]
            ObratiOddelki.objects.bulk_create(obrati_oddelki)

            obrati_oddelki_map = {f"{oo.obrat}-{oo.oddelek}": oo.obrati_oddelki_id for oo in ObratiOddelki.objects.all()}

            # Define a mapping for applications to their role groups
            application_role_group_map = {
                'LTH Pregled aktivnosti': 'roles_sledenje_akcij',
                'Tehnična čistost': 'roles_tehnicna_cistost',
                'Sredstva & Energenti': 'roles_default',
                'Urna Produkcija': 'roles_default',
                'Urnik': 'roles_default',
                'Varnostni Pregledi SVD': 'roles_default',
                'Reklamacije': 'roles_default',
                'Signali strojev': 'roles_default',
                'Vgradni deli': 'roles_default',
            }

            # Define a list of data combinations
            obrat_oddelek_aplikacija_combinations = [
                {'obrat': 'Ljubljana', 'oddelki': ['Tehnologija obdelave', 'Kakovost', 'Obdelava', 'Varnost', 'Livarna', 'Vzdrževanje'], 'aplikacija': 'LTH Pregled aktivnosti', 'type': 'režija'},
                {'obrat': 'Škofja Loka', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'LTH Pregled aktivnosti', 'type': 'režija'},
                {'obrat': 'Trata', 'oddelki': ['Razvoj'], 'aplikacija': 'LTH Pregled aktivnosti', 'type': 'režija'},
                {'obrat': 'LTH', 'oddelki': ['LTH'], 'aplikacija': 'LTH Pregled aktivnosti', 'type': 'režija'},

                {'obrat': 'Ljubljana', 'oddelki': ['Ekologija'], 'aplikacija': 'Tehnična čistost', 'type': 'režija'},
                {'obrat': 'Škofja Loka', 'oddelki': ['Ekologija'], 'aplikacija': 'Tehnična čistost', 'type': 'režija'},
                {'obrat': 'Benkovac', 'oddelki': ['Ekologija'], 'aplikacija': 'Tehnična čistost', 'type': 'režija'},
                {'obrat': 'Ohrid', 'oddelki': ['Ekologija'], 'aplikacija': 'Tehnična čistost', 'type': 'režija'},
                {'obrat': 'Čakovec', 'oddelki': ['Ekologija'], 'aplikacija': 'Tehnična čistost', 'type': 'režija'},

                {'obrat': 'Ljubljana', 'oddelki': ['Ekologija'], 'aplikacija': 'Sredstva & Energenti', 'type': 'režija'},
                {'obrat': 'Škofja Loka', 'oddelki': ['Ekologija'], 'aplikacija': 'Sredstva & Energenti', 'type': 'režija'},
                {'obrat': 'Benkovac', 'oddelki': ['Ekologija'], 'aplikacija': 'Sredstva & Energenti', 'type': 'režija'},
                {'obrat': 'Ohrid', 'oddelki': ['Ekologija'], 'aplikacija': 'Sredstva & Energenti', 'type': 'režija'},
                {'obrat': 'Čakovec', 'oddelki': ['Ekologija'], 'aplikacija': 'Sredstva & Energenti', 'type': 'režija'},
                {'obrat': 'LTH', 'oddelki': ['Ekologija'], 'aplikacija': 'Sredstva & Energenti', 'type': 'režija'},

                {'obrat': 'Ljubljana', 'oddelki': ['Varnost'], 'aplikacija': 'Varnostni Pregledi SVD', 'type': 'režija'},
                {'obrat': 'Škofja Loka', 'oddelki': ['Varnost'], 'aplikacija': 'Varnostni Pregledi SVD', 'type': 'režija'},
                {'obrat': 'Benkovac', 'oddelki': ['Varnost'], 'aplikacija': 'Varnostni Pregledi SVD', 'type': 'režija'},
                {'obrat': 'Ohrid', 'oddelki': ['Varnost'], 'aplikacija': 'Varnostni Pregledi SVD', 'type': 'režija'},
                {'obrat': 'Čakovec', 'oddelki': ['Varnost'], 'aplikacija': 'Varnostni Pregledi SVD', 'type': 'režija'},
                {'obrat': 'LTH', 'oddelki': ['Varnost'], 'aplikacija': 'Varnostni Pregledi SVD', 'type': 'režija'},

                {'obrat': 'Ljubljana', 'oddelki': ['Kakovost'], 'aplikacija': 'Reklamacije', 'type': 'režija'},
                {'obrat': 'Škofja Loka', 'oddelki': ['Kakovost'], 'aplikacija': 'Reklamacije', 'type': 'režija'},
                {'obrat': 'Benkovac', 'oddelki': ['Kakovost'], 'aplikacija': 'Reklamacije', 'type': 'režija'},
                {'obrat': 'Ohrid', 'oddelki': ['Kakovost'], 'aplikacija': 'Reklamacije', 'type': 'režija'},
                {'obrat': 'Čakovec', 'oddelki': ['Kakovost'], 'aplikacija': 'Reklamacije', 'type': 'režija'},
                {'obrat': 'LTH', 'oddelki': ['Kakovost'], 'aplikacija': 'Reklamacije', 'type': 'režija'},

                {'obrat': 'Ljubljana', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'Signali strojev', 'type': 'režija'},
                {'obrat': 'Škofja Loka', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'Signali strojev', 'type': 'režija'},
                {'obrat': 'Benkovac', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'Signali strojev', 'type': 'režija'},
                {'obrat': 'Ohrid', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'Signali strojev', 'type': 'režija'},
                {'obrat': 'Čakovec', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'Signali strojev', 'type': 'režija'},
                {'obrat': 'LTH', 'oddelki': ['Obdelava', 'Livarna'], 'aplikacija': 'Signali strojev', 'type': 'režija'},
                {'obrat': 'Ljubljana', 'oddelki': ['Obdelava'], 'aplikacija': 'Vgradni deli', 'type': 'režija'},

                {'obrat': 'Ljubljana', 'oddelki': ['Obdelava','Livarna'], 'aplikacija': 'Urna Produkcija', 'type': 'proizvodnja'},
                {'obrat': 'Ljubljana', 'oddelki': ['Obdelava','Livarna'], 'aplikacija': 'Urnik', 'type': 'proizvodnja'},
            ]

            # Generate the data using list comprehension
            default_obrati_oddelki_data = [
                {
                    'url': f"{SAFE_URL_OBRAT_MAPPING[comb['obrat']]}/{RAW_TO_URL_MAPPING[comb['aplikacija']]}/{RAW_TO_URL_MAPPING[oddelek]}",
                    'obrat': comb['obrat'],
                    'oddelek': oddelek,
                    'type': comb['type'],  # Ensure the type field is populated
                    'aplikacija': comb['aplikacija'],
                    'role_group_id': role_group_map[application_role_group_map[comb['aplikacija']]]
                }
                for comb in obrat_oddelek_aplikacija_combinations
                for oddelek in comb['oddelki']
            ]

            # Create the AplikacijeObratiOddelki objects
            default_aplikacije_obrati_oddelki = [
                AplikacijeObratiOddelki(
                    url=app_data['url'],
                    type=app_data['type'],  # Assign the type here as well
                    aplikacija=app_data['aplikacija'],
                    role_group_id=app_data['role_group_id'],
                    obrat_oddelek_id=obrati_oddelki_map[f"{app_data['obrat']}-{app_data['oddelek']}"]
                )
                for app_data in default_obrati_oddelki_data
            ]

            AplikacijeObratiOddelki.objects.bulk_create(default_aplikacije_obrati_oddelki)


            aplikacije_obrati_oddelki_map = {app.url: app.aplikacije_obrati_oddelki_id for app in AplikacijeObratiOddelki.objects.all()}
            # Add role group mappings
            role_group_mappings_data = [
                {'role_group_id': role_group_map['roles_default'], 'app_role': 'admin', 'user_role_mapping': 'admin'},
                {'role_group_id': role_group_map['roles_default'], 'app_role': 'vodja', 'user_role_mapping': 'vodja'},
                {'role_group_id': role_group_map['roles_default'], 'app_role': 'osnovni', 'user_role_mapping': 'osnovni'},
                {'role_group_id': role_group_map['roles_default'], 'app_role': 'proizvodnja', 'user_role_mapping': 'proizvodnja'},
                {'role_group_id': role_group_map['roles_default'], 'app_role': 'gost', 'user_role_mapping': 'gost'},
                {'role_group_id': role_group_map['roles_default'], 'app_role': 'brez dostopa', 'user_role_mapping': 'brez dostopa'},
                {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'admin', 'user_role_mapping': 'admin'},
                {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'vodja', 'user_role_mapping': 'vodja'},
                {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'osnovni', 'user_role_mapping': 'osnovni'},
                {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'gost', 'user_role_mapping': 'gost'},
                {'role_group_id': role_group_map['roles_sledenje_akcij'], 'app_role': 'brez dostopa', 'user_role_mapping': 'brez dostopa'},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'admin', 'user_role_mapping': 'admin'},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'vodja', 'user_role_mapping': 'vodja'},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'projektni_vodja', 'user_role_mapping': ''},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'vodja_sredstva', 'user_role_mapping': ''},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'tehnolog_cistosti', 'user_role_mapping': ''},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'osnovni', 'user_role_mapping': 'osnovni'},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'gost', 'user_role_mapping': 'gost'},
                {'role_group_id': role_group_map['roles_tehnicna_cistost'], 'app_role': 'brez dostopa', 'user_role_mapping': 'brez dostopa'},
            ]

            role_group_mappings = [RoleGroupMapping(**rgm) for rgm in role_group_mappings_data]
            RoleGroupMapping.objects.bulk_create(role_group_mappings)

            # Add default users
            default_users = []
            for user_data in default_user_roles:
                obrat_oddelek_key = f"{user_data['obrat']}-{user_data['oddelek']}"
                obrat_oddelek_id = obrati_oddelki_map.get(obrat_oddelek_key)

                if obrat_oddelek_id:
                    user = User(
                        username=user_data['username'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        email=user_data['email'],
                        user_role=user_data['user_role'],
                        obrat_oddelek_id=obrat_oddelek_id,
                    )
                    default_users.append(user)

            User.objects.bulk_create(default_users)

            # Automatically assign roles to users for each app
            default_user_app_roles = []

            # Retrieve all applications and users with related data to minimize queries
            applications = AplikacijeObratiOddelki.objects.select_related('obrat_oddelek', 'role_group').all()
            users = User.objects.select_related('obrat_oddelek').all()

            for user in users:
                if user.obrat_oddelek:  # Ensure that user.obrat_oddelek is not None
                    for app in applications:
                        if app.obrat_oddelek:  # Ensure that app.obrat_oddelek is not None
                            # Check if the obrat matches or is 'LTH', then check oddelki
                            if user.obrat_oddelek.obrat == 'LTH' or user.obrat_oddelek.obrat == app.obrat_oddelek.obrat:
                                if user.obrat_oddelek.oddelek == 'LTH' or user.obrat_oddelek.oddelek == app.obrat_oddelek.oddelek:
                                    # Find the corresponding role group mapping
                                    mapped_role = RoleGroupMapping.objects.filter(
                                        role_group=app.role_group,
                                        user_role_mapping=user.user_role
                                    ).first()

                                    role_name = mapped_role.app_role if mapped_role else 'brez dostopa'
                                    default_user_app_roles.append(UserAppRole(
                                        username=user,  # Match field name
                                        app_url_id=app,  # Match field name
                                        role_name=role_name,
                                    ))
                                else:
                                    # Assign 'brez dostopa' role if oddelek does not match
                                    default_user_app_roles.append(UserAppRole(
                                        username=user,  # Match field name
                                        app_url_id=app,  # Match field name
                                        role_name='brez dostopa',
                                    ))
                            else:
                                # Assign 'brez dostopa' role if obrat does not match
                                default_user_app_roles.append(UserAppRole(
                                    username=user,  # Match field name
                                    app_url_id=app,  # Match field name
                                    role_name='brez dostopa',
                                ))
                        else:
                            print(f"App '{app}' or app.obrat_oddelek is None, skipping assignment for user '{user.username}'")
                else:
                    # Assign 'brez dostopa' role if user.obrat_oddelek is None
                    default_user_app_roles.append(UserAppRole(
                        username=user,  # Match field name
                        app_url_id=None,  # Set None explicitly if obrat_oddelek is None
                        role_name='brez dostopa',
                    ))

            # Bulk create the UserAppRole entries
            UserAppRole.objects.bulk_create(default_user_app_roles)

        # Fetch the users
        dominika = User.objects.get(username='dominika')
        nadat = User.objects.get(username='nadat')
        izidors = User.objects.get(username='izidors')
        marjanfu = User.objects.get(username='user04')
        martinmi = User.objects.get(username='user01')

        # Fetch the obrati_oddelki for 'Ljubljana' and 'Obdelava'
        lj_obdelava = ObratiOddelki.objects.get(obrat='Ljubljana', oddelek='Obdelava')

        # Fetch the obrati_oddelki for 'LTH' and 'Ekologija'
        lth_ekologija = ObratiOddelki.objects.get(obrat='LTH', oddelek='Ekologija')

        # Create ObratOddelekGroup 'SIEE' with correct obrat_oddelek
        siee_group, created = ObratOddelekGroup.objects.get_or_create(
            name='SIEE',
            obrat_oddelek=lth_ekologija,  # Correct obrat_oddelek instance
            created_by=dominika  # Use dominika as the created_by user
        )
        siee_group.members.set([dominika, nadat, izidors, marjanfu])

        # Create ObratOddelekGroup 'Lean Team Obdelava LJ'
        lean_team_group, created = ObratOddelekGroup.objects.get_or_create(
            name='Lean Team Obdelava LJ',
            obrat_oddelek=lj_obdelava,
            created_by=dominika
        )
        lean_team_group.members.set([
            User.objects.get(username='matejsr'),
            User.objects.get(username='klemeno'),
            User.objects.get(username='ervint'),
            User.objects.get(username='goranp'),
            User.objects.get(username='marjank'),
            User.objects.get(username='goranp'),
            User.objects.get(username='matejse'),
            User.objects.get(username='ivanb'),
            User.objects.get(username='primozsu'),
            User.objects.get(username='alisb'),
            User.objects.get(username='krunom'),
            User.objects.get(username='natalijas'),
        ])

        # Create UserGroup 'tc lj'
        tc_lj_group, created = UserGroup.objects.get_or_create(
            name='TC Demo',
            created_by=martinmi
        )
        tc_lj_group.members.set([dominika, marjanfu])

        populate_terminal_data()
        populate_stroj_signal_data()
        create_realistic_notifications()

        self.stdout.write(self.style.SUCCESS('Populated initial data.'))

