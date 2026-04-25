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
    # Filter out washrooms and officerooms from booking categories
    BOOKING_CATEGORIES = [
        (cat, label) for cat, label in Room.ROOM_CATEGORIES 
        if cat not in ['washrooms', 'officerooms']
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

        selected_rooms = sort_rooms_iterable(selected_rooms)
        self.selected_rooms = selected_rooms
        cleaned_data['selected_rooms'] = selected_rooms
        cleaned_data['room'] = selected_rooms[0]

        if start and end:
            conflict_ids = set(
                RoomBooking.objects.filter(
                    Q(room__in=selected_rooms) | Q(rooms__in=selected_rooms),
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).values_list('room_id', flat=True)
            )
            conflict_ids.update(
                RoomBooking.objects.filter(
                    rooms__in=selected_rooms,
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).values_list('rooms__id', flat=True)
            )
            pending_ids = set(
                RoomBookingRequest.objects.filter(
                    Q(room__in=selected_rooms) | Q(rooms__in=selected_rooms),
                    status__in=['pending', 'recommended'],
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).values_list('room_id', flat=True)
            )
            pending_ids.update(
                RoomBookingRequest.objects.filter(
                    rooms__in=selected_rooms,
                    status__in=['pending', 'recommended'],
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).values_list('rooms__id', flat=True)
            )

            blocked_ids = {room_id for room_id in conflict_ids.union(pending_ids) if room_id}
            if blocked_ids:
                blocked_rooms = sort_rooms_iterable([room for room in selected_rooms if room.id in blocked_ids])
                labels = ", ".join(getattr(room, 'label', '') or room.room_name for room in blocked_rooms)
                self.add_error('room_ids', f'These rooms are unavailable for the selected time slot: {labels}.')
        return cleaned_data


class RoomBookingEditForm(forms.ModelForm):
    """
    Form for editing a confirmed room booking.
    Pre-fills with original booking data and allows faculty to make changes.
    """
    room_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text="Comma-separated room IDs"
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        }),
        required=True,
        help_text="Enter your password to authorize this edit request"
    )
    
    requirements_type = forms.ChoiceField(
        choices=[
            ('na', 'No Additional Requirements'),
            ('text', 'Type Requirements'),
            ('doc', 'Upload Document')
        ],
        initial='na',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=False
    )
    
    requirements_text_input = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter your requirements here...'
        }),
        required=False
    )
    
    requirements_doc_upload = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.doc,.docx,.pdf'
        }),
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['doc', 'docx', 'pdf'])]
    )

    class Meta:
        model = RoomBookingRequest
        fields = ['faculty_name', 'faculty_email', 'start_datetime', 'end_datetime', 
                 'purpose', 'department']
        widgets = {
            'faculty_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'faculty_email': forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
            'start_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.original_booking = kwargs.pop('original_booking', None)
        super().__init__(*args, **kwargs)
        
        # Pre-fill form with original booking data
        if self.original_booking:
            self.fields['faculty_name'].initial = self.original_booking.faculty_name
            self.fields['faculty_email'].initial = self.original_booking.faculty_email
            self.fields['start_datetime'].initial = self.original_booking.start_datetime
            self.fields['end_datetime'].initial = self.original_booking.end_datetime
            self.fields['purpose'].initial = self.original_booking.purpose
            self.fields['department'].initial = self.original_booking.department
            
            # Set room IDs
            original_rooms = list(self.original_booking.rooms.all() if self.original_booking.rooms.exists() else [self.original_booking.room])
            room_ids = ','.join(str(room.id) for room in original_rooms)
            self.fields['room_ids'].initial = room_ids

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('faculty_email', '').strip().lower()
        password = cleaned_data.get('password', '').strip()
        room_ids = cleaned_data.get('room_ids', '').strip()

        # Timezone-aware datetimes
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')
        if start and timezone.is_naive(start):
            cleaned_data['start_datetime'] = timezone.make_aware(start)
        if end and timezone.is_naive(end):
            cleaned_data['end_datetime'] = timezone.make_aware(end)

        # Validate credentials
        if email and password:
            try:
                cred = RoomBookingCredentials.objects.get(email=email)
                if cred.password != password:
                    self.add_error('password', 'Incorrect password for this email.')
            except RoomBookingCredentials.DoesNotExist:
                self.add_error('faculty_email', 'This email is not authorised to edit bookings.')

        # Parse and validate rooms
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

        selected_rooms = sort_rooms_iterable(selected_rooms)
        self.selected_rooms = selected_rooms
        cleaned_data['selected_rooms'] = selected_rooms

        # Check for conflicts (exclude current booking)
        if start and end and self.original_booking:
            conflict_ids = set(
                RoomBooking.objects.filter(
                    Q(room__in=selected_rooms) | Q(rooms__in=selected_rooms),
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).exclude(pk=self.original_booking.pk).values_list('room_id', flat=True)
            )
            conflict_ids.update(
                RoomBooking.objects.filter(
                    rooms__in=selected_rooms,
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).exclude(pk=self.original_booking.pk).values_list('rooms__id', flat=True)
            )
            
            pending_ids = set(
                RoomBookingRequest.objects.filter(
                    Q(room__in=selected_rooms) | Q(rooms__in=selected_rooms),
                    status__in=['pending', 'recommended'],
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).values_list('room_id', flat=True)
            )
            pending_ids.update(
                RoomBookingRequest.objects.filter(
                    rooms__in=selected_rooms,
                    status__in=['pending', 'recommended'],
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                ).values_list('rooms__id', flat=True)
            )

            blocked_ids = {room_id for room_id in conflict_ids.union(pending_ids) if room_id}
            if blocked_ids:
                blocked_rooms = sort_rooms_iterable([room for room in selected_rooms if room.id in blocked_ids])
                labels = ", ".join(getattr(room, 'label', '') or room.room_name for room in blocked_rooms)
                self.add_error('room_ids', f'These rooms are unavailable for the selected time slot: {labels}.')

        # Handle requirements
        req_type = cleaned_data.get('requirements_type', 'na')
        if req_type == 'text':
            req_text = cleaned_data.get('requirements_text_input', '').strip()
            if not req_text:
                self.add_error('requirements_text_input', 'Please enter requirements text.')
            cleaned_data['requirements_text'] = req_text
        elif req_type == 'doc':
            req_doc = cleaned_data.get('requirements_doc_upload')
            if not req_doc:
                self.add_error('requirements_doc_upload', 'Please upload a requirements document.')
            cleaned_data['requirements_doc'] = req_doc
        else:
            cleaned_data['requirements_text'] = None
            cleaned_data['requirements_doc'] = None

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
