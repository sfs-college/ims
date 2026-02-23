import os
import json
from pathlib import Path
from environ import Env
import firebase_admin
from firebase_admin import auth, credentials

env = Env()
Env.read_env()

ENVIRONMENT = env('ENVIRONMENT', default="development")

# Set the timezone to IST
TIME_ZONE = 'Asia/Kolkata'

# Ensure that Django uses timezone-aware datetimes
USE_TZ = True

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

LOGIN_URL = '/core/login'

AUTH_USER_MODEL = 'core.User'
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

if ENVIRONMENT == 'development':
    DEBUG = True
else:
    DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default="secret_key")

ALLOWED_EMAIL_DOMAIN = "sfscollege.in"


ALLOWED_HOSTS = env('ALLOWED_HOSTS', default='example.com').split(',')

SITE_URL = env('SITE_URL', default='http://localhost:8000/')



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'inventory.apps.InventoryConfig',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
]

SITE_ID = env.int('SITE_ID', default=1)
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Google Login settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}


SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

ACCOUNT_ADAPTER = 'core.adapters.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'core.adapters.SocialAccountAdapter'
SOCIALACCOUNT_EMAIL_VERIFICATION = "none" 
SOCIALACCOUNT_EMAIL_REQUIRED = True

LOGIN_REDIRECT_URL = '/inventory/report_issue/'
LOGOUT_REDIRECT_URL = '/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ALLOW_USER_REGISTRATION = False

MAINTENANCE_MODE = False


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.firebase_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if ENVIRONMENT == 'development':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'blixtro_db',
            'USER': 'blixtro_user',
            'PASSWORD': 'blixtro_pass',
            'HOST': 'blixtro_postgres',
            'PORT': 5432,
        }
    }
    
else:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(env('DATABASE_URL', default='postgresql://'))
    }



CSRF_TRUSTED_ORIGINS = [
    url.strip() for url in env('CSRF_TRUSTED_ORIGINS', default='https://example.com').split(',')
]


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

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


if ENVIRONMENT == 'development':
    STATIC_URL = '/static/'
    STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
    STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
else:
    # DigitalOcean Spaces Configuration
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default="aws_access_key")
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default="aws_secret_access_key")
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default="aws_storage_bucket_name")
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL', default="aws_s3_endpoint_url")
    AWS_S3_CUSTOM_DOMAIN = f"{env('AWS_S3_CUSTOM_DOMAIN', default='aws_s3_custom_domain')}/{AWS_STORAGE_BUCKET_NAME}"

    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }

    # Static Files
    STATIC_URL = f"{AWS_S3_CUSTOM_DOMAIN}/{AWS_STORAGE_BUCKET_NAME}/static/"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "static"),
    ]

    # Media Files
    MEDIA_URL = f"{AWS_S3_CUSTOM_DOMAIN}/{AWS_STORAGE_BUCKET_NAME}/media/"
    STATICFILES_STORAGE = "config.storages.StaticStorage"
    DEFAULT_FILE_STORAGE = "config.storages.MediaStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if ENVIRONMENT == 'development':
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', default='in-v3.mailjet.com')
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')
    EMAIL_TIMEOUT = 10

COLLEGE_CODE = env("COLLEGE_CODE")
STUDENT_API_KEY = env("STUDENT_API_KEY")
STUDENT_API_SECRET_KEY = env("STUDENT_API_SECRET_KEY")



if not DEBUG:
    # Logging (Docker-safe: stdout only)
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {name} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': True,
            },
            'core': {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
             },
            'inventory': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
            },
            'services': {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': False,
            },
        },
    }

# =========================
# ISSUE ESCALATION SETTINGS
# =========================

DEFAULT_TAT_HOURS = 48

CRON_SECRET = env(
    "CRON_SECRET",
    default="local-dev-cron-secret"
)

# ── Firebase Client Config (passed to templates via context processor) ────────
# These values power the Firebase JS SDK in the browser. They are NOT secret —
# Firebase scopes them with Security Rules + the hd domain restriction.
# Stored in env vars so they never appear hardcoded in source or HTML.
FIREBASE_CLIENT_CONFIG = {
    "apiKey":            env('FIREBASE_API_KEY'),
    "authDomain":        env('FIREBASE_AUTH_DOMAIN'),
    "projectId":         env('FIREBASE_PROJECT_ID'),
    "storageBucket":     env('FIREBASE_STORAGE_BUCKET'),
    "messagingSenderId": env('FIREBASE_MESSAGING_SENDER_ID'),
    "appId":             env('FIREBASE_APP_ID'),
}

# ── Firebase Admin SDK Initialization ────────────────────────────────────────
# Priority 1: FIREBASE_ADMIN_CREDENTIALS_JSON env var (Railway + local .env).
#             Paste the full service-account JSON as one line — no outer quotes.
# Priority 2: Local file fallback at src/core/firebase_key.json.
#             Must be in .gitignore, never committed.
if not firebase_admin._apps:
    _firebase_creds_json = env('FIREBASE_ADMIN_CREDENTIALS_JSON', default='')

    if _firebase_creds_json:
        try:
            _cred_dict = json.loads(_firebase_creds_json)
            # django-environ may store \n as literal \\n in the env value.
            # Firebase needs real newline characters inside the private key.
            if 'private_key' in _cred_dict:
                _cred_dict['private_key'] = _cred_dict['private_key'].replace('\\n', '\n')
            firebase_admin.initialize_app(credentials.Certificate(_cred_dict))
        except json.JSONDecodeError as e:
            import logging
            logging.getLogger('django').error(
                f"Firebase: FIREBASE_ADMIN_CREDENTIALS_JSON is not valid JSON: {e}"
            )
        except Exception as e:
            import logging
            logging.getLogger('django').error(f"Firebase Admin init error: {e}")
    else:
        # Fallback: local key file (dev convenience only, not for production)
        _key_path = os.path.join(BASE_DIR, 'core', 'firebase_key.json')
        if os.path.exists(_key_path):
            try:
                firebase_admin.initialize_app(credentials.Certificate(_key_path))
            except Exception as e:
                import logging
                logging.getLogger('django').error(f"Firebase Admin init error (file): {e}")
        else:
            print(
                "WARNING: Firebase Admin SDK not initialized.\n"
                "Set FIREBASE_ADMIN_CREDENTIALS_JSON in your .env, "
                f"or place firebase_key.json at {_key_path}"
            )