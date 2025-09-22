from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.conf import settings
from config.mixins import form_mixin

User = get_user_model()

# Read allowed domain from settings (if present) otherwise default to sfscollege.in
ALLOWED_EMAIL_DOMAIN = getattr(settings, "ALLOWED_EMAIL_DOMAIN", "sfscollege.in")


class CustomAuthenticationForm(form_mixin.BootstrapFormMixin, AuthenticationForm):
    """
    Login form that requires college email domain.
    We keep the field name 'username' because Django's AuthenticationForm expects it,
    but we use an EmailField widget so value is validated as an email.
    """
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={'required': True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'required': True})
    )

    def __init__(self, *args, **kwargs):
        super(CustomAuthenticationForm, self).__init__(*args, **kwargs)
        self.label_suffix = ''

        # add bootstrap class
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})

    def clean_username(self):
        """
        Ensure the email used to login belongs to the allowed college domain.
        Normalize to lowercase for authentication lookup.
        """
        email = self.cleaned_data.get('username')
        if not email:
            return email

        try:
            domain = email.split('@')[1]
        except IndexError:
            # EmailField should already prevent this, but be defensive.
            raise ValidationError("Enter a valid email address.")

        if domain.lower() != ALLOWED_EMAIL_DOMAIN.lower():
            raise ValidationError(
                f"Login is restricted to college emails (use an @{ALLOWED_EMAIL_DOMAIN} address)."
            )
        return email.lower()


class UserRegisterForm(form_mixin.BootstrapFormMixin, UserCreationForm):
    """
    User creation (registration) form that enforces college email domain.
    """
    org_name = forms.CharField(max_length=200, required=True, label='Organisation name')
    first_name = forms.CharField(max_length=200, required=True)
    last_name = forms.CharField(max_length=200, required=True)

    class Meta:
        model = User
        # keep same fields as before; password fields are provided by UserCreationForm
        fields = ['org_name', 'first_name', 'last_name', 'email',]

    def clean_email(self):
        """
        Ensure email belongs to the allowed college domain and is unique.
        Return normalized (lowercased) email.
        """
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email is required.")

        try:
            domain = email.split('@')[1]
        except IndexError:
            raise ValidationError("Enter a valid email address.")

        if domain.lower() != ALLOWED_EMAIL_DOMAIN.lower():
            raise ValidationError(
                f"Registration is restricted to college emails (please use an @{ALLOWED_EMAIL_DOMAIN} address)."
            )

        # ensure uniqueness (case-insensitive)
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")

        return email.lower()

    def save(self, commit=True):
        """
        Ensure saved user's email is normalized to lowercase.
        """
        user = super().save(commit=False)
        # set normalized email
        email = self.cleaned_data.get('email')
        if email:
            user.email = email.lower()
        if commit:
            user.save()
        return user
