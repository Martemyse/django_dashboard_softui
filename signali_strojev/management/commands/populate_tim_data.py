from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.core.management import call_command
from signali_strojev.models import TimConfig, TimDefinition, StrojEntry

class Command(BaseCommand):
    help = 'Populates the database with default TimConfig, TimDefinition, StrojEntry data.'

    def handle(self, *args, **options):
        # Run migrations for the 'signali_strojev' app
        self.stdout.write(self.style.SUCCESS('Running migrations for signali_strojev app...'))
        call_command('makemigrations', 'signali_strojev')
        call_command('migrate', 'signali_strojev')
        self.stdout.write(self.style.SUCCESS('Migrations completed.'))

        self.stdout.write('Starting to populate default TIM data...')
        clear_existing_data()
        populate_default_tim_data()
        self.stdout.write(self.style.SUCCESS('Successfully populated default TIM data.'))

def clear_existing_data():
    """Delete all existing records in a safe transaction."""
    with transaction.atomic():
        StrojEntry.objects.all().delete()
        TimDefinition.objects.all().delete()
        TimConfig.objects.all().delete()

def populate_default_tim_data():
    """Populate the database with the default TimConfig, TimDefinition, StrojEntry data."""
    # Data for TimConfig
    tim_configs_data = [
        {'team_label':'Lean Team','team_name': 'HEAT Obdelava', 'vodja': 'Srebernak Matej', 'ad_username': 'matejsr', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'HEAT Soba', 'vodja': 'Serec Natalija', 'ad_username': 'natalijas', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'STGH I. II. + HAG', 'vodja': 'Ovniček Klemen', 'ad_username': 'klemeno', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'BOSCH + AUDI', 'vodja': 'Tabaković Ervin', 'ad_username': 'ervint', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'MOPF', 'vodja': 'Tabaković Ervin', 'ad_username': 'ervint', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'TIM 4', 'vodja': 'Pašalić Goran', 'ad_username': 'goranp', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'TIM 5', 'vodja': 'Klobasa Marjan', 'ad_username': 'marjank', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'TIM 8', 'vodja': 'Pašalić Goran', 'ad_username': 'goranp', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'Stellantis', 'vodja': 'Šek Matej', 'ad_username': 'matejse', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Lean Team','team_name': 'Onebox', 'vodja': 'Bizjak Ivan', 'ad_username': 'ivanb', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Delovodje','team_name': 'Litostroj', 'vodja': 'Kruno', 'ad_username': 'krunom', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'Mojstri','team_name': 'STGH', 'vodja': 'Alis', 'ad_username': 'alisb', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
        {'team_label':'ROM Celice','team_name': 'ROM', 'vodja': 'Jenko Simon', 'ad_username': 'simonje', 'oddelek': 'Obdelava', 'obrat': 'Ljubljana'},
    ]

    # Create TimConfig instances
    tim_configs = {}
    for config_data in tim_configs_data:
        config, created = TimConfig.objects.get_or_create(**config_data)
        tim_configs[config.team_name] = config

    # Data for TimDefinitions and associated entries
    tim_definitions_data = {
        'HEAT Obdelava': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['TA120', 'TA121', 'TA122', 'TA123', 'TA203', 'TA206', 'TA207', 'TA208', 'T0237', 'T0238', 'TA401', 'TA129'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': [],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TG901'],
                    
                },
            ]
        },
        'HEAT Soba': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['T2806', 'T3101'],
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['TE101', 'TD101'],
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TE701', 'TD201', 'TD901'],
                    
                },
                {
                    'ime_tabele': 'Montaža',
                    'operacija': 70,
                    'stroj_entries': [],
                },
                {
                    'ime_tabele': 'Pregledovanje',
                    'operacija': 80,
                    'stroj_entries': ['TGB01', 'TG701', 'TD802'],
                },
            ]
        },
        'STGH I. II. + HAG': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['TA110', 'TA111', 'TA112', 'TA113', 'TA114', 'TA115', 'TA116', 'TA117', 'TP401'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': [],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TP301', 'TP501', 'TP601', 'TR301', 'TR302', 'TR303'],
                    
                },
            ]
        },
        'BOSCH + AUDI': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['TA204', 'TA205'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['T3102', 'T2401', 'T2403'],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TD601', 'TF101', 'PN901'],
                    
                },
                {
                    'ime_tabele': 'Pregledovanje',
                    'operacija': 80,
                    'stroj_entries': ['S10'],
                    
                },
            ]
        },
        'MOPF': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['TA124', 'TA125', 'TA126', 'TA127', 'TA128', 'TA401', 'TA402', 'TA403', 'TA404', 'TA405'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['T2808', 'T2902', 'T2903'],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TF301', 'TG401', 'TG601'],
                    
                },
            ]
        },
        'TIM 4': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['T0223', 'T0224', 'T0225', 'T0226', 'T0227', 'T0228', 'TR101', 'TR102', 'TR103'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['T2802'],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['T6401', 'TD501', 'TF801', 'TL501'],
                    
                },
            ]
        },
        'TIM 5': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['T0215', 'T0216', 'TR601', 'TR602', 'TR603', 'TR604', 'TR605', 'TR606', 'TR607'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['T2601', 'T2603'],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TB301', 'TF701'],
                    
                },
            ]
        },
        'TIM 8': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['T0301', 'T0302', 'T0303', 'T0304', 'T0401', 'T0402', 'T0403', 'T0404', 'T0505', 'TR201', 'TR202'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['T2901'],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TF401', 'TL401', 'TL402'],
                    
                },
            ]
        },
        'ROM Celice': {
            'definitions': [
                {
                    'ime_tabele': 'Obdelava',
                    'operacija': 30,
                    'stroj_entries': ['T0301', 'T0302', 'T0303', 'T0304', 'T0401', 'T0402', 'T0403', 'T0404', 'T0505', 'TR201', 'TR202'],
                    
                },
                {
                    'ime_tabele': 'Pranje',
                    'operacija': 50,
                    'stroj_entries': ['T2901'],
                    
                },
                {
                    'ime_tabele': 'Preizkus tesnosti',
                    'operacija': 70,
                    'stroj_entries': ['TF401', 'TL401', 'TL402'],
                    
                },
            ]
        },

        # Add similar definitions for TIM 4, TIM 5, TIM 8, Stellantis, and Onebox if needed
    }

    # Create TimDefinitions and associated entries
    for tim_name, data in tim_definitions_data.items():
        tim_config = tim_configs.get(tim_name)
        if not tim_config:
            continue

        for def_data in data['definitions']:
            tim_definition = TimDefinition.objects.create(
                tim_config=tim_config,
                ime_tabele=def_data['ime_tabele'],
                operacija=def_data.get('operacija'),
                opravilo=def_data.get('opravilo')
            )

            # Create StrojEntries
            for stroj in def_data.get('stroj_entries', []):
                StrojEntry.objects.create(
                    tim_definition=tim_definition,
                    stroj=stroj,
                    postaja='',
                    is_delovno_mesto=False,
                    
                )
