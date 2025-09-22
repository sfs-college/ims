from django import forms
from inventory.models import Category, Brand, Item, System, SystemComponent, Archive, Room, Purchase, Vendor, Receipt, ItemGroup, ItemGroupItem, RoomSettings  # Import RoomSettings
from config.mixins import form_mixin

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
        fields = ['item_name', 'category', 'brand', 'total_count']  # Include necessary fields

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
        fields = ['item', 'quantity', 'unit_of_measure', 'vendor', 'cost']  # Include necessary fields #added cost
        
        
class PurchaseUpdateForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['quantity', 'unit_of_measure', 'vendor', 'cost']  # Include necessary fields #added cost

class ItemPurchaseForm(form_mixin.BootstrapFormMixin, forms.ModelForm):
    item_name = forms.CharField(max_length=255)
    category = forms.ModelChoiceField(queryset=Category.objects.all())
    brand = forms.ModelChoiceField(queryset=Brand.objects.all())
    quantity = forms.FloatField(min_value=1)
    unit_of_measure = forms.ChoiceField(choices=Purchase.UNIT_CHOICES)
    vendor = forms.ModelChoiceField(queryset=Vendor.objects.all())
    cost = forms.DecimalField(max_digits=10, decimal_places=2, required=False)  # ✅ NEW

    class Meta:
        model = Purchase
        fields = ['item_name', 'category', 'brand', 'quantity', 'unit_of_measure', 'vendor', 'cost'] #added cost

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