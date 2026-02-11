import os
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.conf import settings
from config.mixins import form_mixin
from inventory.models import RoomBooking, Room, Department
from django.utils import timezone

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
    
ALLOWED_EMAILS = [
    email.strip().lower()
    for email in os.getenv("ALLOWED_FACULTY_EMAILS", "").split(",")
    if email.strip()
]

class RoomBookingForm(forms.ModelForm):
    category = forms.ChoiceField(choices=Room.ROOM_CATEGORIES)

    class Meta:
        model = RoomBooking
        fields = ['faculty_name', 'faculty_email', 'purpose', 'start_datetime', 'end_datetime', 'department', 'room']
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter the purpose of booking...', 'class': 'form-control rounded-4'}),
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

    def clean_faculty_email(self):
        email = self.cleaned_data['faculty_email'].lower()

        if not email.endswith("@sfscollege.in"):
            raise ValidationError("Only @sfscollege.in emails are allowed.")

        if email not in ALLOWED_EMAILS:
            raise ValidationError("You are not authorized to book rooms.")

        return email
    
    def clean(self):
        cleaned_data = super().clean()

        start = cleaned_data.get("start_datetime")
        end = cleaned_data.get("end_datetime")

        if start and timezone.is_naive(start):
            cleaned_data["start_datetime"] = timezone.make_aware(start)

        if end and timezone.is_naive(end):
            cleaned_data["end_datetime"] = timezone.make_aware(end)

        return cleaned_data

    # CHANGE: Faculty email validation using environment variable allowlist