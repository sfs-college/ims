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


def home_url(request):
    """
    Injects `home_url` and `is_capacitor` into every template context.
    - Inside the Capacitor app (?app=1 OR Capacitor/WebView UA): /core/app/?app=1
    - In a normal browser: / (landing page)
    Fixes back/home button navigation for login, logout, register, access_denied
    so they never redirect to the web landing page when inside the mobile app.
    """
    ua = request.META.get('HTTP_USER_AGENT', '')
    is_cap = (
        request.GET.get('app') == '1'
        or 'Capacitor' in ua
        or '; wv' in ua
    )
    return {
        'home_url': '/core/app/?app=1' if is_cap else '/',
        'is_capacitor': is_cap,
    }
