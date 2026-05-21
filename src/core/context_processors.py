from django.conf import settings
from django.urls import reverse


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


def dashboard_url(request):
    """
    Injects `dashboard_url` into every template context.
    Returns the correct dashboard URL based on the logged-in user's role:
    - Central Admin / Sub Admin → central_admin:dashboard
    - Room Incharge → room_incharge:room_dashboard (for their first room)
    - Fallback → '/'
    Used by the universal back button in sidebar_base.html.
    """
    url = '/'
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
        except Exception:
            return {'dashboard_url': url}

        if profile.is_central_admin or profile.is_sub_admin:
            url = reverse('central_admin:dashboard')
        elif profile.is_incharge:
            # Try to get the room slug from the current URL kwargs first
            if hasattr(request, 'resolver_match') and request.resolver_match:
                room_slug = request.resolver_match.kwargs.get('room_slug')
                if room_slug:
                    url = reverse('room_incharge:room_dashboard', kwargs={'room_slug': room_slug})
                else:
                    # Fall back to the first room assigned to this incharge
                    first_room = profile.rooms_incharge.first()
                    if first_room:
                        url = reverse('room_incharge:room_dashboard', kwargs={'room_slug': first_room.slug})
            else:
                first_room = profile.rooms_incharge.first()
                if first_room:
                    url = reverse('room_incharge:room_dashboard', kwargs={'room_slug': first_room.slug})

    return {'dashboard_url': url}
