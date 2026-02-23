from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter.

    Key responsibility beyond open-for-signup:
    social account payload when a student logs in.  Without this,
    request.user.email is empty and the Issue reporter_email field is
    never filled in.
    """

    def is_open_for_signup(self, request, sociallogin):
        # Domain restriction is handled in the Firebase view login logic
        return True

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