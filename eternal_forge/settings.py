"""
Django settings for eternal_forge project.

Eternal Forge - A deck builder and collection manager for Eternal Card Game
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# In production, set DJANGO_SECRET_KEY environment variable
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-tr)3#-j^d%=*jo5ys0gx#74kf&fek684z!0#nli$45&i$kog4v'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,161.35.232.178,workstation.nonagonmedia.net').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'django_htmx',
    # Local apps
    'cards',
    'collection',
    'decks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # HTMX middleware - adds request.htmx attribute
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'eternal_forge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'eternal_forge.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# Uses PostgreSQL - configure via environment variables

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'eternal_forge'),
        'USER': os.environ.get('DB_USER', 'eternal_forge'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'eternal_forge'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (uploaded content)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =============================================================================
# Eternal Forge specific settings
# =============================================================================

# Path to card data JSON file
CARD_DATA_FILE = BASE_DIR / 'data' / 'eternal-cards.json'

# Deck building rules (from Eternal Card Game official rules)
DECK_RULES = {
    'MIN_DECK_SIZE': 75,
    'MAX_DECK_SIZE': 150,
    'MAX_COPIES_PER_CARD': 4,  # Sigils exempt
    'MIN_POWER_RATIO': 1/3,   # At least 1/3 must be power cards
    'MIN_NON_POWER_RATIO': 1/3,  # At least 1/3 must be non-power cards
    'MAX_MARKET_SIZE': 5,
    'MAX_COPIES_IN_MARKET': 1,
    # Sigils can be in both deck and market; Bargain cards too
}

# Card factions/influences
FACTIONS = {
    'F': 'Fire',
    'T': 'Time',
    'J': 'Justice',
    'P': 'Primal',
    'S': 'Shadow',
}

# Card types that count as "power" for deck building rules
POWER_CARD_TYPES = ['Power', 'Sigil']
