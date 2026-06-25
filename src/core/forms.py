import os
from django.db.models import Q
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.conf import settings
from config.mixins import form_mixin
from inventory.models import RoomBooking, RoomBookingRequest, Room, Department, RoomBookingCredentials
from django.utils import timezone
from inventory.booking_utils import sort_rooms_iterable

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
    # Filter out washrooms, officerooms, and staffrooms from booking categories
    BOOKING_CATEGORIES = [
        (cat, label) for cat, label in Room.ROOM_CATEGORIES 
        if cat not in ['washrooms', 'officerooms', 'staffrooms']
    ]
    
    category = forms.ChoiceField(
        choices=BOOKING_CATEGORIES,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_category'}),
        required=True,
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your booking password',
            'id': 'id_password',
        }),
        required=True,
    )
    room_ids = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'id_room_ids'}),
        required=True,
    )

    class Meta:
        model = RoomBookingRequest
        fields = [
            'faculty_name', 'faculty_email', 'purpose',
            'start_datetime', 'end_datetime', 'department', 'room',
            'requirements_doc', 'alternative_slots',
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
            'requirements_doc': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.png,.jpg,.jpeg,.heic,.heif,.webp,.gif,.bmp,.tiff,.tif'}),
            'alternative_slots': forms.HiddenInput(attrs={'id': 'id_alternative_slots'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all required fields mandatory
        self.fields['faculty_name'].required = True
        self.fields['faculty_email'].required = True
        self.fields['purpose'].required = True
        self.fields['start_datetime'].required = True
        self.fields['end_datetime'].required = True
        self.fields['department'].required = True
        self.fields['room'].required = False
        # requirements_doc remains optional
        self.fields['requirements_doc'].required = False
        self.fields['requirements_doc'].max_length = 255
        self.fields['alternative_slots'].required = False
        # Sort departments alphabetically (A to Z)
        self.fields['department'].queryset = Department.objects.all().order_by('department_name')
        self.selected_rooms = []

    def clean_faculty_email(self):
        email = self.cleaned_data.get('faculty_email', '').strip().lower()
        if not email.endswith('@sfscollege.in'):
            raise ValidationError('Only @sfscollege.in email addresses are allowed.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        email    = cleaned_data.get('faculty_email', '').strip().lower()
        password = cleaned_data.get('password', '').strip()
        room_ids = cleaned_data.get('room_ids', '').strip()

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

        parsed_room_ids = []
        for value in room_ids.split(','):
            value = value.strip()
            if not value:
                continue
            if value.isdigit():
                parsed_room_ids.append(int(value))

        parsed_room_ids = list(dict.fromkeys(parsed_room_ids))
        if not parsed_room_ids:
            self.add_error('room_ids', 'Please select at least one room.')
            return cleaned_data

        selected_rooms = list(Room.objects.filter(id__in=parsed_room_ids))
        if len(selected_rooms) != len(parsed_room_ids):
            self.add_error('room_ids', 'One or more selected rooms could not be found.')
            return cleaned_data

        # Double-check room availability / conflicts for all selected rooms
        if start and end and selected_rooms:
            alt_slots_json = cleaned_data.get('alternative_slots', '[]') or '[]'
            slots = [(cleaned_data['start_datetime'], cleaned_data['end_datetime'])]
            try:
                import json
                from django.utils.dateparse import parse_datetime
                extra = json.loads(alt_slots_json)
                for slot in extra:
                    s_dt = parse_datetime(slot['start'])
                    e_dt = parse_datetime(slot['end'])
                    if s_dt and e_dt:
                        if timezone.is_naive(s_dt):
                            s_dt = timezone.make_aware(s_dt)
                        if timezone.is_naive(e_dt):
                            e_dt = timezone.make_aware(e_dt)
                        slots.append((s_dt, e_dt))
            except Exception:
                pass

            from inventory.booking_utils import check_slots_conflict
            exclude_booking_pk = None
            exclude_request_pk = None
            if self.instance and self.instance.pk:
                if isinstance(self.instance, RoomBookingRequest):
                    exclude_request_pk = self.instance.pk
                elif isinstance(self.instance, RoomBooking):
                    exclude_booking_pk = self.instance.pk

            conflict_msg = check_slots_conflict(
                selected_rooms,
                slots,
                exclude_booking_pk=exclude_booking_pk,
                exclude_request_pk=exclude_request_pk
            )
            if conflict_msg:
                self.add_error('room_ids', conflict_msg)
                return cleaned_data

        cleaned_data['selected_rooms'] = selected_rooms
        return cleaned_data


class AdminRoomBookingForm(RoomBookingForm):
    """
    Variant of RoomBookingForm for sub-admin / central-admin direct bookings.
    - Skips RoomBookingCredentials validation (admin uses Django login credentials).
    - Password field is not required (admin credentials are passed separately).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = False

    def clean(self):
        cleaned_data = super(RoomBookingForm, self).clean()  # skip RoomBookingForm.clean entirely
        room_ids = self.data.get('room_ids', '').strip()

        # Timezone-aware datetimes
        start = cleaned_data.get('start_datetime')
        end   = cleaned_data.get('end_datetime')
        if start and timezone.is_naive(start):
            cleaned_data['start_datetime'] = timezone.make_aware(start)
        if end and timezone.is_naive(end):
            cleaned_data['end_datetime'] = timezone.make_aware(end)

        # Room IDs
        parsed_room_ids = []
        for value in room_ids.split(','):
            value = value.strip()
            if not value:
                continue
            if value.isdigit():
                parsed_room_ids.append(int(value))

        parsed_room_ids = list(dict.fromkeys(parsed_room_ids))
        if not parsed_room_ids:
            self.add_error(None, 'Please select at least one room.')
            return cleaned_data

        selected_rooms = list(Room.objects.filter(id__in=parsed_room_ids))
        if len(selected_rooms) != len(parsed_room_ids):
            self.add_error(None, 'One or more selected rooms could not be found.')
            return cleaned_data

        # Double-check room availability / conflicts for all selected rooms
        if start and end and selected_rooms:
            alt_slots_json = cleaned_data.get('alternative_slots', '[]') or '[]'
            slots = [(cleaned_data['start_datetime'], cleaned_data['end_datetime'])]
            try:
                import json
                from django.utils.dateparse import parse_datetime
                extra = json.loads(alt_slots_json)
                for slot in extra:
                    s_dt = parse_datetime(slot['start'])
                    e_dt = parse_datetime(slot['end'])
                    if s_dt and e_dt:
                        if timezone.is_naive(s_dt):
                            s_dt = timezone.make_aware(s_dt)
                        if timezone.is_naive(e_dt):
                            e_dt = timezone.make_aware(e_dt)
                        slots.append((s_dt, e_dt))
            except Exception:
                pass

            from inventory.booking_utils import check_slots_conflict
            exclude_booking_pk = None
            exclude_request_pk = None
            if self.instance and self.instance.pk:
                if isinstance(self.instance, RoomBookingRequest):
                    exclude_request_pk = self.instance.pk
                elif isinstance(self.instance, RoomBooking):
                    exclude_booking_pk = self.instance.pk

            conflict_msg = check_slots_conflict(
                selected_rooms,
                slots,
                exclude_booking_pk=exclude_booking_pk,
                exclude_request_pk=exclude_request_pk
            )
            if conflict_msg:
                self.add_error(None, conflict_msg)
                return cleaned_data

        cleaned_data['room_ids'] = room_ids
        cleaned_data['selected_rooms'] = selected_rooms
        return cleaned_data


class CustomPasswordResetForm(PasswordResetForm):
    """
    Custom password reset form that ensures proper email validation
    and handles college email domain restrictions.
    """
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError('Email is required.')
        
        # Check if user exists with this email
        User = get_user_model()
        if not User.objects.filter(email=email).exists():
            raise ValidationError('No account found with this email address.')
            
        return email

    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.html",
        use_https=False,
        token_generator=None,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        """
        Generate a one-time use-link for resetting a password and send it to the user
        using safe_send_mail to prevent any connection or SMTP errors.
        """
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.urls import reverse
        from django.conf import settings
        from inventory.email import safe_send_mail
        
        email = self.cleaned_data.get("email")
        if not email:
            return
            
        token_generator = token_generator or default_token_generator
        
        active_users = User.objects.filter(email__iexact=email, is_active=True)
        for user in active_users:
            token = token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            domain = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            if domain.endswith('/'):
                domain = domain.rstrip('/')
            
            reset_link = f"{domain}{reverse('core:confirm_password_reset', kwargs={'uidb64': uid, 'token': token})}"
            
            subject = "Reset Your Blixtro Password"
            message = (
                "Hi,\n\n"
                "We received a request to reset the password for your account on the SFS College Inventory Management System (Blixtro IMS):\n\n"
                f"{reset_link}\n\n"
                "If you did not request this change, you can safely ignore this email.\n\n"
                "Best regards,\nSFS IMS Team"
            )
            
            # Send using our production-safe Mailjet API sender
            success = safe_send_mail(
                subject=subject,
                message=message,
                recipient_list=[user.email],
                from_email=from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sfscollege.in'),
                fail_silently=False,
            )
            if not success:
                raise Exception("Email delivery failed via Mailjet API. Please verify the mail settings or contact system administrator.")
