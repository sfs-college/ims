"""
Middleware for Capacitor / mobile app authentication flow.

When the Capacitor app starts the Google OAuth flow, it opens:
    /accounts/google/login/?process=login&app=1

Google then redirects the user through several pages (consent screen,
callback) and the ?app=1 query parameter is lost.  This middleware
intercepts the initial OAuth request and saves the flag in the session
so that the AccountAdapter.get_login_redirect_url() can later detect
it and redirect to the deep-link callback page.
"""


class CapacitorAuthMiddleware:
    """
    Captures ``?app=1`` on any ``/accounts/`` request (the allauth OAuth
    entry-point) and stores ``session['capacitor_auth'] = True`` so
    downstream adapters can redirect back to the native app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Detect Capacitor flag on allauth OAuth entry requests
        if request.path.startswith('/accounts/') and request.GET.get('app') == '1':
            request.session['capacitor_auth'] = True
            # Force session save so the flag persists through the redirect chain
            request.session.modified = True

        response = self.get_response(request)
        return response
