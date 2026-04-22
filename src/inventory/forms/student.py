# ims/src/inventory/forms/student.py
from django import forms
from inventory.models import Issue, Room
from config.mixins import form_mixin
from django.core.exceptions import ValidationError

class IssueReportForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    """
    Form for students to report issues.
    The email is handled automatically via Google Auth in the view logic.
    All fields are mandatory to ensure complete issue reporting.
    """

    subject = forms.CharField(
        required=True, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter issue subject'
        })
    )
    description = forms.CharField(
        required=True, 
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4,
            'placeholder': 'Describe the issue in detail'
        })
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(), 
        required=True, 
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Select room/department'
        })
    )

    class Meta:
        model = Issue
        fields = ['subject', 'description', 'room']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize room choices to show both label and room name
        self.fields['room'].queryset = Room.objects.all().order_by('label', 'room_name')
        self.fields['room'].label_from_instance = lambda obj: f"{obj.label} - {obj.room_name}"

    def clean(self):
        """
        Custom validation to ensure a room is selected.
        """
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        
        if not room:
            raise forms.ValidationError("Please select the room/department where the issue belongs.")
            
        return cleaned_data