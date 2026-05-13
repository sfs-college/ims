"""
Test settings for the audit test suite.
Patches WeasyPrint (requires GTK native libs not available on Windows dev machines).
"""
import sys
from unittest.mock import MagicMock

# Patch weasyprint before any Django app imports it
_weasyprint_mock = MagicMock()
_weasyprint_mock.HTML = MagicMock(return_value=MagicMock(write_pdf=MagicMock(return_value=b'%PDF-mock')))
sys.modules['weasyprint'] = _weasyprint_mock

from .settings import *  # noqa: E402, F401, F403

# Test database — in-memory SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Static files
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

DEBUG = False

# Disable email sending in tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
