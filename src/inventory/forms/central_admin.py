from django import forms
from django.core.validators import RegexValidator
from core.models import User, UserProfile, Organisation
from inventory.models import Department, Room, Vendor, Purchase, Issue, Category, Brand
from config.mixins import form_mixin
from django.forms import RadioSelect

special_char_validator = RegexValidator(
    regex=r'^[\w\s\-&.\'()]+$',
    message='Department name can only contain letters, numbers, spaces, and these special characters: - & . \' ( )'
)

class DepartmentForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    department_name = forms.CharField(
        max_length=500,
        validators=[special_char_validator]
    )

    class Meta:
        model = Department
        fields = ['department_name']


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['label','room_name','incharge']


class VendorForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['vendor_name','email','contact_number','alternate_number','address']  


class Issues(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['subject','description','resolved']


class Category(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name']


class Brand(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['brand_name']
        
        
class PeopleCreateForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    """
    Clean form: NO organisation field (org is auto-assigned in the view).
    """
    email = forms.EmailField(label="Official Email")
    last_name = forms.CharField(max_length=255, required=False)

    ROLE_CHOICES = (
        ('central_admin', 'Central Admin'),
        ('sub_admin', 'Sub Admin'),
        ('room_incharge', 'Room Incharge'),
    )

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=RadioSelect, label="Select Role", initial='room_incharge')

    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name']  # org removed entirely

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
        return profile


class RoomCreateForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    capacity = forms.IntegerField(required=False)

    class Meta:
        model = Room
        fields = ['label', 'room_name', 'department', 'incharge','room_category', 'capacity']