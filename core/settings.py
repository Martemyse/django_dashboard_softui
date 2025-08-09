import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-prod')

# Env-driven flags
DEVELOPMENT = os.getenv('DEVELOPMENT', 'True') == 'True'
# Determine if we are in development or production
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*'] if DEBUG else os.getenv('ALLOWED_HOSTS', '').split(',')

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost' if DEVELOPMENT else 'rabbitmq')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USERNAME = os.getenv('RABBITMQ_USERNAME', 'guest')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))  # Typically 587 for TLS
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'home',
    'pregled_aktivnosti',
    'signali_strojev',
    'vgradni_deli',
]

AUTH_USER_MODEL = 'home.User'


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'home', 'templates'),
            os.path.join(BASE_DIR, 'pregled_aktivnosti', 'templates'),
            os.path.join(BASE_DIR, 'signali_strojev', 'templates'),  # Add this line
            os.path.join(BASE_DIR, 'vgradni_deli', 'templates'),  # Add this line
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'home.context_processors.current_obrat',
                'home.context_processors.obrat_mapping',
                'home.context_processors.available_users_processor',
                'home.context_processors.user_obrati_oddelki_processor',
                'home.context_processors.client_ip_processor',
                'signali_strojev.context_processors.obrat_oddelek_context',

            ],
            'libraries': {  # Adding this line to register custom tags and filters
                'custom_filters': 'home.custom_filters',
            }
        },
    },
]

if DEBUG:
    AUTHENTICATION_BACKENDS = [
        'home.backends.DevelopmentAuthBackend',
        # 'django.contrib.auth.backends.ModelBackend',
    ]
else:
    AUTHENTICATION_BACKENDS = [
        # 'django.contrib.auth.backends.ModelBackend',
    ]

LOGIN_URL = 'login' if DEBUG else 'django.contrib.auth.views.LoginView'
LOGIN_REDIRECT_URL = 'index'  # If 'index' is the intended page


WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'django_overview_aplikacije'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost' if DEVELOPMENT else 'postgres'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    },
    'external_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('EXTERNAL_DB_NAME', 'external_db'),
        'USER': os.getenv('EXTERNAL_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('EXTERNAL_DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('EXTERNAL_DB_HOST', 'localhost' if DEVELOPMENT else 'postgres'),
        'PORT': os.getenv('EXTERNAL_DB_PORT', '5432'),
    },
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
# settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',  # Ensure this is DEBUG
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',  # General Django logs
            'propagate': True,
        },
        'home': {
            'handlers': ['console'],
            'level': 'DEBUG',  # Set this to DEBUG to see home app logs
            'propagate': False,
        },
    },
}



# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Ljubljana'  # Change from UTC to Europe/Ljubljana
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/django_c/'

# Directory where `collectstatic` will gather all static files for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') if DEVELOPMENT else '/app/static/django_c/'

# Directories Django will search for additional static files during development
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static') if DEVELOPMENT else os.path.join(BASE_DIR, 'static'),
]
# Static files storage backend
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Media file configurations
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Directory for uploaded files
MEDIA_URL = '/media/'  # URL that serves the uploaded files

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'