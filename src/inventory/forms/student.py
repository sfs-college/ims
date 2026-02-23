# ims/src/inventory/forms/student.py
from django import forms
from inventory.models import Issue
from config.mixins import form_mixin
from django.core.exceptions import ValidationError

class IssueReportForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    """
    Form for students to report issues.
    The email is handled automatically via Google Auth in the view logic.
    """

    class Meta:
        model = Issue
        fields = ['subject', 'description', 'room']

    def clean(self):
        """
        Custom validation to ensure a room is selected.
        """
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        
        if not room:
            raise forms.ValidationError("Please select the room/department where the issue belongs.")
            
        return cleaned_data