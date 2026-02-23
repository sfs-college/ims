import os
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.conf import settings
from config.mixins import form_mixin
from inventory.models import RoomBooking, RoomBookingRequest, Room, Department, RoomBookingCredentials
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
    
class RoomBookingForm(forms.ModelForm):
    """
    Creates a RoomBookingRequest (pending admin approval) rather than
    directly creating a confirmed RoomBooking.
    The password field is used only for validation — never stored.
    """
    category = forms.ChoiceField(
        choices=Room.ROOM_CATEGORIES,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_category'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your booking password',
            'id': 'id_password',
        })
    )

    class Meta:
        model = RoomBookingRequest
        fields = [
            'faculty_name', 'faculty_email', 'purpose',
            'start_datetime', 'end_datetime', 'department', 'room',
            'requirements_doc',
        ]
        widgets = {
            'faculty_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Name',
                'id': 'id_faculty_name',
            }),
            'faculty_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'faculty@sfscollege.in',
                'id': 'id_faculty_email',
            }),
            'purpose': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Enter the purpose of booking...',
                'class': 'form-control rounded-4',
            }),
            'start_datetime': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'id': 'id_start_datetime',
            }),
            'end_datetime': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'id': 'id_end_datetime',
            }),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.HiddenInput(attrs={'id': 'id_room'}),
            'requirements_doc': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_faculty_email(self):
        email = self.cleaned_data.get('faculty_email', '').strip().lower()
        if not email.endswith('@sfscollege.in'):
            raise ValidationError('Only @sfscollege.in email addresses are allowed.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        email    = cleaned_data.get('faculty_email', '').strip().lower()
        password = cleaned_data.get('password', '').strip()

        # Timezone-aware datetimes
        start = cleaned_data.get('start_datetime')
        end   = cleaned_data.get('end_datetime')
        if start and timezone.is_naive(start):
            cleaned_data['start_datetime'] = timezone.make_aware(start)
        if end and timezone.is_naive(end):
            cleaned_data['end_datetime'] = timezone.make_aware(end)

        # Validate credentials against RoomBookingCredentials table
        if email and password:
            try:
                cred = RoomBookingCredentials.objects.get(email=email)
                if cred.password != password:
                    self.add_error('password', 'Incorrect password for this email.')
            except RoomBookingCredentials.DoesNotExist:
                self.add_error('faculty_email', 'This email is not authorised to book rooms.')
        return cleaned_data