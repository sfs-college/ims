from django.db import models
from django.forms import ValidationError
from core.models import Organisation, UserProfile, Department, User
from django.utils.text import slugify
from django.utils import timezone
from config.utils import generate_unique_slug, generate_unique_code
from django.db.models.signals import post_delete
from django.dispatch import receiver
import json
from django.db.models import JSONField
import random, string
from django.conf import settings
from inventory.models import UserProfile
from django.core.mail import send_mail
import pytz, uuid
from django.core.validators import FileExtensionValidator

class Room(models.Model):
    # CHANGE: Added fixed room category support for central admin room management
    ROOM_CATEGORIES = [
    ('classrooms', 'Classrooms'),
    ('labs', 'Labs'),
    ('staffrooms', 'Staffrooms'),
    ('halls', 'Halls'),
    ('outdoors', 'Outdoors'),
    ('washrooms', 'Washrooms'),
    ('officerooms', 'Officerooms'),
]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=20)
    room_name = models.CharField(max_length=255)
    incharge = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='rooms_incharge')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    room_category = models.CharField(max_length=20, choices=ROOM_CATEGORIES, default='classrooms')
    capacity = models.PositiveIntegerField(default=0)

    
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
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True)
    purchase_id = models.CharField(max_length=8, unique=True)
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE)
    quantity = models.FloatField()
    unit_of_measure = models.CharField(max_length=10, choices=UNIT_CHOICES)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True, blank=True)
    requested_by = models.ForeignKey('core.UserProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_requests_made')
    reason = models.TextField(blank=True, help_text="Reason for purchase request")

    # ✅ Excel fields
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField(default=timezone.now)
    invoice_number = models.CharField(max_length=100, blank=True)

    # Stock management
    date_of_entry = models.DateField(default=timezone.now)
    item_description = models.TextField(blank=True)
    opening_stock_qty = models.IntegerField(default=0)
    arrival_receipts = models.FloatField(default=0)
    total_stock = models.FloatField(default=0)
    consumed_stock_qty = models.FloatField(default=0)
    closing_balance_qty = models.FloatField(default=0)
    remarks = models.TextField(blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    added_to_stock = models.BooleanField(default=False)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)

    invoice = models.FileField(
        upload_to='purchase_invoices/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )

    def save(self, *args, **kwargs):
        if not self.purchase_id:
            self.purchase_id = generate_unique_code(self, 8, 'purchase_id')
        if not self.slug:
            base_slug = slugify(self.purchase_id)
            self.slug = generate_unique_slug(self, base_slug)

        # Auto calculations
        if self.item:
            self.item_description = self.item.item_name
            self.opening_stock_qty = self.item.total_count - self.quantity
            self.arrival_receipts = self.quantity
            self.total_stock = self.item.total_count + self.quantity
            self.closing_balance_qty = self.item.available_count + self.quantity

        # Excel-style totals
        from decimal import Decimal, ROUND_HALF_UP

        qty = Decimal(str(self.quantity)).quantize(Decimal("0.01"))

        if self.cost_per_unit is not None:
            self.total_cost = (self.cost_per_unit * qty).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        elif self.cost is not None:
            self.total_cost = (self.cost * qty).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.purchase_id} {self.room}"

@receiver(post_delete, sender=Purchase)
def delete_related_item(sender, instance, **kwargs):
    item = instance.item
    if not item.is_listed:
        item.delete()
        
# Issue model added with ticketing workflow 

class Issue(models.Model):
    """
    Issue/Ticket model with workflow & escalation support.
    Escalation levels:
        0 = room_incharge
        1 = sub_admin
        2 = central_admin
    """

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)

    created_by = models.CharField(max_length=255, blank=True, null = True)
    reporter_email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Reporter college email (@sfscollege.in)"
    )

    ticket_id = models.CharField(max_length=30, unique=True, blank=True, null=True)

    subject = models.CharField(max_length=255)
    description = models.TextField()

    resolved = models.BooleanField(default=False)

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('escalated', 'Escalated'),
        ('closed', 'Closed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    assigned_to = models.ForeignKey(
        'core.UserProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_issues'
    )

    tat_deadline = models.DateTimeField(null=True, blank=True)

    # escalation levels:
    # 0 = room_incharge
    # 1 = sub_admin
    # 2 = central_admin
    escalation_level = models.IntegerField(default=0)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    slug = models.SlugField(unique=True, max_length=255, blank=True)

    # ----------------------------------------------------------------------
    # Utility: Ticket ID generator
    # ----------------------------------------------------------------------
    def generate_ticket_id(self):
        import random, string
        ts = timezone.now().strftime("%y%m%d%H%M%S")
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

        return f"T{self.organisation_id or 0}{ts}{suffix}"

    # ----------------------------------------------------------------------
    # Save override
    # ----------------------------------------------------------------------
    def save(self, *args, **kwargs):
        # slug
        if not self.slug:
            base_slug = slugify(self.subject or "issue")
            self.slug = generate_unique_slug(self, base_slug)

        # ticket id
        if not self.ticket_id:
            self.ticket_id = self.generate_ticket_id()

        super().save(*args, **kwargs)

    # ----------------------------------------------------------------------
    # Escalation Workflow
    # ----------------------------------------------------------------------
    def escalate(self, notify=True):
        """
        Escalation workflow:
            Level 0 → Room Incharge → Sub Admin
            Level 1 → Sub Admin → Central Admin
            Level 2 → Fully Escalated (highest)
        """

        # Do not escalate resolved or closed issues
        if self.resolved or self.status == "closed":
            return {
                "ticket_id": self.ticket_id,
                "escalated": False,
                "from": self.escalation_level,
                "to": self.escalation_level,
                "reason": "Issue is resolved/closed"
            }

        # Already at highest escalation level
        if self.escalation_level >= 2:
            return {
                "ticket_id": self.ticket_id,
                "escalated": False,
                "from": self.escalation_level,
                "to": self.escalation_level,
                "reason": "Already escalated to central admin"
            }

        old_level = self.escalation_level
        next_level = old_level + 1
        candidate = None

        # ----------------------------------------------------
        # VALIDATED FIX: Use actual fields in your UserProfile
        # ----------------------------------------------------
        if next_level == 1:
            # Escalate to Sub Admin
            candidate = UserProfile.objects.filter(
                # org=self.organisation,
                is_sub_admin=True
            ).first()

        elif next_level == 2:
            # Escalate to Central Admin
            candidate = UserProfile.objects.filter(
                # org=self.organisation,
                is_central_admin=True
            ).first()

        # If no user exists at next level → do not escalate
        if not candidate:
            return {
                "ticket_id": self.ticket_id,
                "escalated": False,
                "from": old_level,
                "to": old_level,
                "reason": "No admin available at next escalation level"
            }

        # ----------------------------------------------------
        # APPLY ESCALATION
        # ----------------------------------------------------
        self.escalation_level = next_level
        self.assigned_to = candidate
        self.status = "escalated"

        # Reset TAT deadline for new responsible user
        hours = getattr(settings, "DEFAULT_TAT_HOURS", 48)
        self.tat_deadline = timezone.now() + timezone.timedelta(hours=hours)

        self.save()

        # ----------------------------------------------------
        # OPTIONAL EMAIL (never stops escalation)
        # ----------------------------------------------------
        if notify:
            try:
                user_email = getattr(candidate.user, "email", None)
                if user_email:
                    send_mail(
                        subject=f"Issue Escalated: {self.ticket_id}",
                        message=f"The ticket {self.ticket_id} has been escalated to you.",
                        from_email=None,
                        recipient_list=[user_email],
                        fail_silently=True
                    )
            except Exception:
                pass

        return {
            "ticket_id": self.ticket_id,
            "escalated": True,
            "from": old_level,
            "to": next_level
        }

    # ----------------------------------------------------------------------
    def __str__(self):
        return f"{self.ticket_id or 'TICKET'} - {self.subject}"


class Category(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True)
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
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True)
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
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='items_created'
    )

    item_description = models.TextField(blank=True, default='')
    serial_number = models.CharField(max_length=100, blank=True, default='')
    purchase_model_code = models.CharField(max_length=100, blank=True, default='')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)

    total_count = models.IntegerField()
    available_count = models.IntegerField(default=0)
    in_use = models.IntegerField(default=0)

    # ✔ FIXED SPELLING
    archived_count = models.IntegerField(default=0)

    is_listed = models.BooleanField(default=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)


    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.item_name)
            self.slug = generate_unique_slug(self, base_slug)

        if not self.item_description:
            self.item_description = f"{self.brand.brand_name} {self.item_name} - {self.category.category_name}"

        # AVAILABLE COUNT CALCULATION
        calculated_available = self.total_count - self.in_use - self.archived_count
        self.available_count = max(calculated_available, 0)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.item_name

    # Helpful safe increment
    def increment_archived(self, delta=1):
        new_val = max(0, self.archived_count + int(delta))
        self.archived_count = new_val
        self.save(update_fields=["archived_count", "updated_on"])
    
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

class StockRequest(models.Model):
    """
    Room Incharge requests additional stock for an item.
    Admin approves → item.total_count and item.available_count are increased.
    """
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    item            = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_requests")
    room            = models.ForeignKey(Room, on_delete=models.CASCADE)
    requested_by    = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="stock_requests_made")
    requested_count = models.PositiveIntegerField(default=1)
    reason          = models.TextField()
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_by     = models.ForeignKey(
                        UserProfile, on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name="reviewed_stock_requests"
                      )
    created_on      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StockReq: {self.item.item_name} +{self.requested_count} ({self.status})"



class RoomBooking(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    faculty_name = models.CharField(max_length=255)
    faculty_email = models.EmailField()
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    created_on = models.DateTimeField(auto_now_add=True)
    purpose = models.TextField(null=True, blank=True)
    requirements_doc = models.FileField(
        upload_to='room_bookings/requirements/',
        null=True, 
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['doc', 'docx'])],
        help_text="Upload a Word document or leave empty if Not Applicable."
    )
    # Stores the plain-text content extracted from requirements_doc at approval time.
    # This allows admin to view/download the document content without touching
    requirements_doc_text = models.TextField(
        null=True,
        blank=True,
        help_text="Auto-extracted plain text from the uploaded requirements document."
    )
    
    slug = models.SlugField(unique=True, max_length=255, blank=True, null=True)

    def clean(self):
        tz = pytz.timezone(settings.TIME_ZONE)
        
        if self.start_datetime and timezone.is_naive(self.start_datetime):
            self.start_datetime = timezone.make_aware(self.start_datetime, tz)
        elif self.start_datetime:
            self.start_datetime = self.start_datetime.astimezone(tz)

        if self.end_datetime and timezone.is_naive(self.end_datetime):
            self.end_datetime = timezone.make_aware(self.end_datetime, tz)
        elif self.end_datetime:
            self.end_datetime = self.end_datetime.astimezone(tz)

        # 2. Basic Validation
        if self.start_datetime and self.end_datetime:
            if self.start_datetime >= self.end_datetime:
                raise ValidationError("End time must be after start time.")

            # 3. Conflict Detection logic
            overlapping = RoomBooking.objects.filter(
                room=self.room,
                start_datetime__lt=self.end_datetime,
                end_datetime__gt=self.start_datetime
            )

            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)

            if overlapping.exists():
                raise ValidationError("Room is already booked for this time slot.")

    def save(self, *args, **kwargs):
        # Generate slug based on faculty name and timestamp if it doesn't exist
        if not self.slug:
            unique_id = str(uuid.uuid4())[:8]
            self.slug = slugify(f"{self.faculty_name}-{unique_id}")

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.room.room_name} | {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"


class RoomBookingCredentials(models.Model):
    """
    Stores authorized emails and passwords for room booking validation.
    """
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    designation = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class IssueTimeExtensionRequest(models.Model):
    """
    Request raised by Room Incharge to extend Issue TAT.
    """

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    issue = models.ForeignKey(
        "Issue",
        on_delete=models.CASCADE,
        related_name="time_extension_requests"
    )

    requested_by = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE
    )

    current_tat_hours = models.PositiveIntegerField()
    requested_extra_hours = models.PositiveIntegerField()

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    reviewed_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_time_extensions"
    )

    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Issue #{self.issue.id} – {self.status}"


# ─────────────────────────────────────────────────────────────────────
# ROOM BOOKING APPROVAL WORKFLOW MODELS
# ─────────────────────────────────────────────────────────────────────

class RoomBookingRequest(models.Model):
    """
    Pending room booking that requires admin approval before becoming
    a confirmed RoomBooking entry.
    """
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    room            = models.ForeignKey(Room, on_delete=models.CASCADE)
    department      = models.ForeignKey(
                        'core.Department', null=True, blank=True, on_delete=models.SET_NULL
                      )
    faculty_name    = models.CharField(max_length=255)
    faculty_email   = models.EmailField()
    start_datetime  = models.DateTimeField()
    end_datetime    = models.DateTimeField()
    purpose         = models.TextField(null=True, blank=True)
    requirements_doc = models.FileField(
                        upload_to='room_booking_requests/requirements/',
                        null=True, blank=True,
                        validators=[FileExtensionValidator(
                            allowed_extensions=['doc', 'docx', 'pdf']
                        )],
                      )
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by     = models.ForeignKey(
                        UserProfile, on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='reviewed_booking_requests'
                      )
    review_note     = models.TextField(blank=True)
    created_on      = models.DateTimeField(auto_now_add=True)
    updated_on      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BookingReq [{self.status}]: {self.room} | {self.faculty_email}"


class RoomCancellationRequest(models.Model):
    """
    Faculty-raised request to cancel an existing confirmed RoomBooking.
    On approval  → the linked RoomBooking is deleted (room freed).
    On rejection → booking stays active.
    """
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    booking         = models.ForeignKey(
                        RoomBooking, on_delete=models.CASCADE,
                        related_name='cancellation_requests'
                      )
    faculty_email   = models.EmailField()
    reason          = models.TextField()
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by     = models.ForeignKey(
                        UserProfile, on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='reviewed_cancellation_requests'
                      )
    created_on      = models.DateTimeField(auto_now_add=True)
    updated_on      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CancelReq [{self.status}]: {self.booking}"