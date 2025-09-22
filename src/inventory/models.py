from django.db import models
from django.forms import ValidationError
from core.models import Organisation, UserProfile, Department
from django.utils.text import slugify
from config.utils import generate_unique_slug, generate_unique_code
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Room(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=20)
    room_name = models.CharField(max_length=255)
    incharge = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='rooms_incharge')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.room_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.room_name
    

class RoomSettings(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE)
    items_tab = models.BooleanField(default=True)
    item_groups_tab = models.BooleanField(default=True)
    systems_tab = models.BooleanField(default=True)
    categories_tab = models.BooleanField(default=True)
    brands_tab = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.room.room_name} settings"


class Activity(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.action)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.action


class Vendor(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    vendor_name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_number = models.CharField(max_length=15)
    alternate_number = models.CharField(max_length=15)
    address = models.CharField(max_length=255)
    vendor_id = models.CharField(max_length=8, unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.vendor_id:
            self.vendor_id = generate_unique_code(self, 8, 'vendor_id')
        if not self.slug:
            base_slug = slugify(self.vendor_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.vendor_name


class Purchase(models.Model):
    UNIT_CHOICES = [
        ('kilogram', 'Kilogram'),
        ('liters', 'Liters'),
        ('units', 'Units'),
    ]
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    purchase_id = models.CharField(max_length=8, unique=True)
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE)
    quantity = models.FloatField()
    unit_of_measure = models.CharField(max_length=10, choices=UNIT_CHOICES)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # ✅ NEW field
    created_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    added_to_stock = models.BooleanField(default=False)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.purchase_id:
            self.purchase_id = generate_unique_code(self, 8, 'purchase_id')
        if not self.slug:
            base_slug = slugify(self.purchase_id)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.purchase_id} {self.room}"

@receiver(post_delete, sender=Purchase)
def delete_related_item(sender, instance, **kwargs):
    item = instance.item
    if not item.is_listed:
        item.delete()


class Issue(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    created_by = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    description = models.TextField()
    resolved = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.subject)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.subject


class Category(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    category_name = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.category_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.category_name


class Brand(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    brand_name = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.brand_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.brand_name

class Item(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    total_count = models.IntegerField()
    available_count = models.IntegerField()
    in_use = models.IntegerField(default=0)
    achived_count = models.IntegerField(default=0)  # Set default value
    is_listed = models.BooleanField(default=True)  # New field
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.item_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.item_name
    

class ItemGroup(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    item_group_name = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.item_group_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.item_group_name
    

class ItemGroupItem(models.Model):
    item_group = models.ForeignKey(ItemGroup, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    qty = models.IntegerField()
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    class Meta:
        unique_together = [('item_group', 'item')]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.item.item_name)
            self.slug = generate_unique_slug(self, base_slug)
        # validate unique together
        if ItemGroupItem.objects.filter(item_group=self.item_group, item=self.item).exclude(pk=self.pk).exists():
            raise ValueError("The combination of item group and item must be unique.")
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.item.item_name

@receiver(post_delete, sender=ItemGroupItem)
def restore_item_count(sender, instance, **kwargs):
    item = instance.item
    item.available_count += instance.qty
    item.in_use -= instance.qty
    item.save()


class System(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('under_maintenance', 'Under Maintenance'),
        ('disposed', 'Disposed'),
    ]
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True) 
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    system_name = models.CharField(max_length=255)
    status = models.CharField(max_length=255, choices=STATUS_CHOICES)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.system_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.system_name


class SystemComponent(models.Model):
    COMPONENT_TYPES = [
        ('mouse', 'Mouse'),
        ('keyboard', 'Keyboard'),
        ('monitor', 'Monitor'),
        ('cpu', 'CPU'),
        ('ups', 'UPS'),
        ('printer', 'Printer'),
        ('scanner', 'Scanner'),
        ('projector', 'Projector'),
        ('router', 'Router'),
        ('switch', 'Switch'),
        ('firewall', 'Firewall'),
        ('server', 'Server'),
        ('storage', 'Storage'),
        ('network', 'Network'),
        ('other', 'Other'),
    ]
    system = models.ForeignKey(System, on_delete=models.CASCADE)
    component_item = models.ForeignKey(Item, on_delete=models.CASCADE)  # Updated field
    component_type = models.CharField(max_length=255, choices=COMPONENT_TYPES)
    serial_number = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    class Meta:
        unique_together = [('system', 'component_type', 'serial_number')]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.component_item.item_name)  # Updated field
            self.slug = generate_unique_slug(self, base_slug)
        # validate unique together
        if SystemComponent.objects.filter(system=self.system, component_type=self.component_type, serial_number=self.serial_number).exclude(pk=self.pk).exists():
            raise ValueError("The combination of system, component type, and serial number must be unique.")
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.component_item.item_name  # Updated field


@receiver(post_delete, sender=SystemComponent)
def restore_item_count_on_component_delete(sender, instance, **kwargs):
    """Restore item counts when a system component is deleted."""
    item = instance.component_item
    item.available_count += 1
    item.in_use -= 1
    item.save()


@receiver(post_delete, sender=System)
def restore_item_counts_on_system_delete(sender, instance, **kwargs):
    """Restore item counts when a system is deleted (cascades to components)."""
    # Note: This signal fires after SystemComponents are already deleted
    # due to CASCADE, so we need to handle this differently
    # This signal is mainly for cleanup, the SystemComponent signal above
    # handles the individual component count restoration
    pass


class Archive(models.Model):
    ARCHIVE_TYPES = [
        ('consumption', 'Consumption'),
        ('depreciation', 'Depreciation'),
    ]
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    count = models.IntegerField()
    archive_type = models.CharField(max_length=20, choices=ARCHIVE_TYPES)
    remark = models.TextField()
    archived_on = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True, max_length=255)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.item.item_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.item.item_name


class Receipt(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    purchase = models.OneToOneField(Purchase, on_delete=models.CASCADE, related_name='receipt')
    receipt = models.FileField(upload_to='receipts/')
    remarks = models.TextField()
    completed_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt for {self.purchase.purchase_id}"

