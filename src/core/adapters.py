from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False

    def get_login_redirect_url(self, request):
        """
        After a successful social login (Google), redirect Capacitor app users
        to a dedicated deep-link callback page instead of the normal student portal.

        Detection: The Capacitor app passes ?app=1 when starting the OAuth flow.
        We store this flag in the session so it persists through the Google redirect chain.
        """
        is_capacitor = request.session.pop('capacitor_auth', False)
        if is_capacitor:
            return '/core/app-auth-callback/'
        return super().get_login_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter.

    Key responsibility beyond open-for-signup:
    - Enforces @sfscollege.in domain restriction for all Google logins
    - Syncs email from social account payload so request.user.email is never blank
    """

    def is_open_for_signup(self, request, sociallogin):
        """
        Allow signup only for @sfscollege.in email addresses.
        This enforces the domain restriction for the allauth Google login path
        (used by Capacitor system-browser auth flow).
        """
        allowed_domain = getattr(settings, 'ALLOWED_EMAIL_DOMAIN', 'sfscollege.in')
        email = ''
        try:
            extra = sociallogin.account.extra_data or {}
            email = (
                extra.get('email') or
                extra.get('emailAddress') or
                getattr(sociallogin.user, 'email', '') or
                ''
            ).strip().lower()
        except Exception:
            pass

        if not email:
            return False

        return email.endswith(f'@{allowed_domain}')

    def pre_social_login(self, request, sociallogin):
        """
        Called right before the social login is completed.
        Preserve the Capacitor flag that was set in the session during the
        initial OAuth redirect (via the allauth middleware).
        """
        super().pre_social_login(request, sociallogin)

    def populate_user(self, request, sociallogin, data):
        """
        Called by allauth when creating/updating the User record from the
        social login payload.  We make sure the email field is always synced
        from the Google account data so request.user.email is never blank.
        """
        user = super().populate_user(request, sociallogin, data)

        # If allauth didn't set an email, pull it from extra_data directly
        if not user.email:
            extra = sociallogin.account.extra_data or {}
            email = extra.get("email") or extra.get("emailAddress") or ""
            user.email = email

        return user

    def save_user(self, request, sociallogin, form=None):
        """
        Ensure User.email is persisted after every login, not just on
        account creation.  This handles the case where a user was created
        before this fix was deployed and their User.email is blank.
        """
        user = super().save_user(request, sociallogin, form)

        if not user.email:
            extra = sociallogin.account.extra_data or {}
            email = extra.get("email") or extra.get("emailAddress") or ""
            if email:
                user.email = email
                user.save(update_fields=["email"])

        return user