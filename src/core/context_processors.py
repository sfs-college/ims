from django.conf import settings


def firebase_config(request):
    """
    Injects FIREBASE_CLIENT_CONFIG from settings into every template context.
    This lets portal_login.html use {{ firebase_config.apiKey }} etc.
    without hardcoding any values in the HTML.
    """
    return {
        'firebase_config': getattr(settings, 'FIREBASE_CLIENT_CONFIG', {})
    }