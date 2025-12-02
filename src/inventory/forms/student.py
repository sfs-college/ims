# ims/src/inventory/forms/student.py
from django import forms
from inventory.models import Issue
from config.mixins import form_mixin
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

class IssueReportForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    """
    Form for students to report issues using only their college email.
    The email is required and must belong to @sfscollege.in domain.
    """
    email = forms.EmailField(max_length=255, required=True, label="College Email (must end with @sfscollege.in)")

    class Meta:
        model = Issue
        fields = ['email', 'subject', 'description', 'room']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Validate standard email format first
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")

        # Enforce institutional domain
        if not email.lower().endswith('@sfscollege.in'):
            raise ValidationError("Email must belong to the @sfscollege.in domain.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        if not room:
            raise forms.ValidationError("Please select the room/department where the issue belongs.")
        return cleaned_data
