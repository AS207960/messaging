"""
Django settings for as207960_messaging project.

Generated by 'django-admin startproject' using Django 3.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

import json
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.getenv("HOST", "messaging.as207960.net").split(",")


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_keycloak_auth',
    'rest_framework',
    'messaging',
    'gbc'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_keycloak_auth.middleware.OIDCMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'as207960_messaging.urls'

AUTHENTICATION_BACKENDS = ["django_keycloak_auth.auth.KeycloakAuthorization"]

LOGIN_URL = "oidc_login"
LOGOUT_REDIRECT_URL = "oidc_login"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
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

WSGI_APPLICATION = 'as207960_messaging.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        "ENGINE": "django_cockroachdb",
        "HOST": os.getenv("DB_HOST", "localhost"),
        "NAME": os.getenv("DB_NAME", "messaging"),
        "USER": os.getenv("DB_USER", "messaging"),
        "PASSWORD": os.getenv("DB_PASS"),
        "PORT": '26257',
        "OPTIONS": {
            "application_name": os.getenv("APP_NAME", "messaging")
        }
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

EXTERNAL_URL_BASE = os.getenv("EXTERNAL_URL", f"https://{ALLOWED_HOSTS[0]}")

STATIC_URL = f"{EXTERNAL_URL_BASE}/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = f"{EXTERNAL_URL_BASE}/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
OIDC_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
OIDC_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")
OIDC_SCOPES = os.getenv("KEYCLOAK_SCOPES")

GBM_SERVICE_ACCOUNT_FILE = os.getenv("BM_SA_LOCATION")
GBC_PARTNER_KEY = os.getenv("BM_PARTNER_KEY")

PAT_URL = os.getenv("PAT_URL")

CELERY_RESULT_BACKEND = "rpc://"
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser'
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'as207960_utils.api.auth.BearerAuthentication',
        'as207960_utils.api.auth.PATAuthentication',
        'as207960_utils.api.auth.SessionAuthentication',
    ] if PAT_URL else [
        'as207960_utils.api.auth.BearerAuthentication',
        'as207960_utils.api.auth.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 25
}