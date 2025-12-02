from django import forms
from inventory.models import Category, Brand, Item, System, SystemComponent, Archive, Room, Purchase, Vendor, Receipt, ItemGroup, ItemGroupItem, RoomSettings, EditRequest, Item  # Import RoomSettings
from config.mixins import form_mixin
from core.models import UserProfile

class CategoryForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name']

class BrandForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['brand_name']

class ItemForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'item_name', 'category', 'brand', 'total_count',
            'item_description', 'serial_number', 'purchase_model_code',
            'vendor', 'cost', 'warranty_expiry'
        ]
        widgets = {
            'item_description': forms.Textarea(attrs={'rows': 3}),
        }

class SystemForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = System
        fields = ['system_name', 'status']

class SystemComponentForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SystemComponent
        fields = ['component_item', 'component_type', 'serial_number']  # Updated field

class SystemComponentArchiveForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Archive
        fields = ['archive_type', 'remark']

class ItemArchiveForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    count = forms.IntegerField(min_value=1)

    class Meta:
        model = Archive
        fields = ['archive_type', 'remark', 'count']

class RoomUpdateForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Room
        fields = ['label', 'room_name', 'department', 'incharge']  # Adjust fields as necessary

class PurchaseForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            'item', 'quantity', 'unit_of_measure', 'vendor',
            'cost', 'cost_per_unit', 'invoice_number', 'purchase_date',
            'item_description', 'remarks'
        ]
        widgets = {
            'item_description': forms.Textarea(attrs={'rows': 3}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
        
        
class PurchaseUpdateForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            'quantity', 'unit_of_measure', 'vendor',
            'cost', 'cost_per_unit', 'invoice_number', 'purchase_date'
        ]

class ItemPurchaseForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    item_name = forms.CharField(max_length=255)
    category = forms.ModelChoiceField(queryset=Category.objects.all())
    brand = forms.ModelChoiceField(queryset=Brand.objects.all())
    quantity = forms.FloatField(min_value=1)
    unit_of_measure = forms.ChoiceField(choices=Purchase.UNIT_CHOICES)
    vendor = forms.ModelChoiceField(queryset=Vendor.objects.all())
    cost = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    cost_per_unit = forms.DecimalField(max_digits=12, decimal_places=2, required=False)
    invoice_number = forms.CharField(max_length=100, required=False)
    purchase_date = forms.DateField(required=False)

    item_description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    serial_number = forms.CharField(max_length=100, required=False)
    purchase_model_code = forms.CharField(max_length=100, required=False)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    class Meta:
        model = Purchase
        fields = [
            'item_name', 'category', 'brand', 'quantity', 'unit_of_measure',
            'vendor', 'cost', 'cost_per_unit', 'invoice_number', 'purchase_date',
            'item_description', 'serial_number', 'purchase_model_code', 'remarks'
        ]

class PurchaseCompleteForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ['receipt', 'remarks']

class ItemGroupForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemGroup
        fields = ['item_group_name']  # Include necessary fields

class ItemGroupItemForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemGroupItem
        fields = ['item', 'qty']  # Include necessary fields

class RoomSettingsForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    items_tab = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), required=False)
    item_groups_tab = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), required=False)
    systems_tab = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), required=False)
    categories_tab = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), required=False)
    brands_tab = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), required=False)

    class Meta:
        model = RoomSettings
        fields = ['items_tab', 'item_groups_tab', 'systems_tab', 'categories_tab', 'brands_tab']
        
# Add to inventory/forms/room_incharge.py (near other form classes)

class ExcelUploadForm(forms.Form):
    """
    Simple form for uploading the import Excel file.
    """
    file = forms.FileField(
        required=True,
        help_text="Upload an .xlsx file exported by the system (sheets: 'Items' and/or 'Purchases')."
    )

class ItemEditRequestForm(form_mixin.BootstrapFormMixin, forms.Form):
    """
    Room Incharge requests item edits.
    Proposed changes stored as JSON.
    """

    item_name = forms.CharField(required=False)
    item_description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    total_count = forms.IntegerField(required=False)
    available_count = forms.IntegerField(required=False)
    in_use = forms.IntegerField(required=False)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)

    def save(self, *, item: Item, requested_by: UserProfile):
        cleaned = self.cleaned_data
        proposed = {}

        for field in ['item_name', 'item_description', 'total_count', 'available_count', 'in_use', 'remarks']:
            if cleaned.get(field) not in [None, '']:
                proposed[field] = cleaned[field]

        edit_request = EditRequest.objects.create(
            item=item,
            room=item.room,
            requested_by=requested_by.user.profile,   # NOW CORRECT TYPE: UserProfile
            proposed_data=proposed,
            reason=cleaned['reason'],
            status="pending"
        )

        # Lock item AFTER request
        item.is_edit_lock = True
        item.save()

        return edit_request

