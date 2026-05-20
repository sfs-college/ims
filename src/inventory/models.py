from django.db import models
from django.forms import ValidationError
from core.models import Organisation, UserProfile, Department, User
from django.utils.text import slugify
from django.utils import timezone
from config.utils import generate_unique_slug, generate_unique_code
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import send_mail
import pytz, uuid
from django.core.validators import FileExtensionValidator
from inventory.booking_utils import format_room_list

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
    ('others', 'Others'),
]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=20)
    room_name = models.CharField(max_length=255)
    incharge = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='rooms_incharge')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)
    room_category = models.CharField(max_length=20, choices=ROOM_CATEGORIES, default='classrooms')
    capacity = models.PositiveIntegerField(default=0, blank=True, null=True)

    
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
    item_category = models.CharField(max_length=100, blank=True, default='General')
    item_brand = models.CharField(max_length=100, blank=True, default='General')

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
    closure_reason = models.TextField(blank=True, null=True)
    incharge_remark = models.TextField(
        blank=True, null=True,
        help_text="Progress update from room incharge sent to the reporter."
    )
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


class IssueRemark(models.Model):
    """Persistent remark thread for an issue.  Each row is one remark
    added by a specific admin profile (sub-admin or central admin).

    Multiple remarks per issue are allowed and are kept in insertion order.
    The incharge_remark / closure_reason live directly on Issue for backward
    compatibility; this table holds the per-admin remark audit trail.
    """

    class AdminType(models.TextChoices):
        SUB_ADMIN = 'sub_admin', 'Sub Admin'
        CENTRAL_ADMIN = 'central_admin', 'Central Admin'

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='admin_remarks')

    admin_type = models.CharField(max_length=20, choices=AdminType.choices)
    remark_text = models.TextField()

    created_by = models.ForeignKey(
        'core.UserProfile', on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']           # oldest first
        indexes = [models.Index(fields=['issue', 'created_at'])]

    def __str__(self):
        return f"{self.get_admin_type_display()} remark on {self.issue.ticket_id} at {self.created_at:%Y-%m-%d %H:%M}"


class Category(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
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
    product_code = models.CharField(max_length=12, blank=True, null=True)

    # New fields for active/inactive tracking (from Systems kanban)
    active_count = models.IntegerField(default=0)
    inactive_count = models.IntegerField(default=0)
    # Serviceable/unserviceable counts (from Archive assignments)
    serviceable_count = models.IntegerField(default=0)
    unserviceable_count = models.IntegerField(default=0)
    is_serviceable = models.BooleanField(default=True)

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

        used_count = self.active_count + self.inactive_count + self.archived_count
        if used_count > self.total_count:
            raise ValidationError("Available, active, inactive and archived counts cannot exceed total assigned.")

        # AVAILABLE COUNT CALCULATION
        # available = total - active - inactive - archived (serviceable+unserviceable)
        calculated_available = self.total_count - used_count
        self.available_count = max(calculated_available, 0)
        # Keep in_use in sync with active for backward compatibility
        self.in_use = self.active_count

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if update_fields & {"total_count", "active_count", "inactive_count", "archived_count"}:
                update_fields.update({"available_count", "in_use"})
            kwargs["update_fields"] = list(update_fields)

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
    

class RevertedRoom(models.Model):
    """
    Track rooms that became unassigned when a user was deleted
    """
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    previous_incharge = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='reverted_rooms')
    deleted_user_email = models.EmailField()
    deleted_user_name = models.CharField(max_length=255)
    reverted_on = models.DateTimeField(auto_now_add=True)
    reassigned_to = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='reassigned_rooms')
    reassigned_on = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['room', 'organisation']
    
    def __str__(self):
        return f"{self.room.room_name} - reverted from {self.deleted_user_name}"


class RevertedItem(models.Model):
    """
    Track items that reverted to master inventory when a user was deleted
    """
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    previous_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, related_name='reverted_items_previous')
    previous_assigned_to = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='reverted_items')
    deleted_user_email = models.EmailField()
    deleted_user_name = models.CharField(max_length=255)
    reverted_on = models.DateTimeField(auto_now_add=True)
    reassigned_to_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='reverted_items_reassigned')
    reassigned_to_user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='reassigned_items')
    reassigned_on = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['item', 'organisation']
    
    def __str__(self):
        return f"{self.item.item_name} - reverted from {self.deleted_user_name}"


class InventoryRevertHistory(models.Model):
    """
    Audit trail for manual returns from room inventory back to master inventory.
    """
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=255)
    category_name = models.CharField(max_length=255, blank=True, default='')
    brand_name = models.CharField(max_length=255, blank=True, default='')
    quantity = models.PositiveIntegerField()
    reverted_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_reverts',
    )
    room_total_before = models.PositiveIntegerField(default=0)
    room_total_after = models.PositiveIntegerField(default=0)
    master_total_after = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True, default='')
    reverted_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reverted_on']

    def __str__(self):
        room_name = self.room.room_name if self.room else 'Unknown room'
        return f"Returned {self.quantity} x {self.item_name} from {room_name}"


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
    """When an ItemGroupItem is deleted, restore the qty back to available."""
    from django.db.models import F
    Item.objects.filter(pk=instance.item_id).update(
        in_use=F('in_use') - instance.qty,
        available_count=F('available_count') + instance.qty,
    )


class System(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True) 
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    system_name = models.CharField(max_length=255)
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

class SystemConfiguration(models.Model):
    system = models.OneToOneField(System, on_delete=models.CASCADE, related_name='configuration')
    configuration = models.TextField()
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Config for {self.system.system_name}"


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

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('under_maintenance', 'Under Maintenance'),
        ('disposed', 'Disposed'),
    ]

    system = models.ForeignKey(System, on_delete=models.CASCADE)
    component_item = models.ForeignKey(Item, on_delete=models.CASCADE)  # Updated field
    component_type = models.CharField(max_length=255, choices=COMPONENT_TYPES)
    serial_number = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
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
    """
    Restore item counts when a system component is deleted directly
    (not via SystemComponentArchiveView which handles counts manually).
    Only fires for direct deletes not going through the archive flow.
    """
    # The archive view handles count restoration manually before delete.
    # For direct deletes (e.g. cascade), restore active_count → available_count.
    item = instance.component_item
    item.active_count = max(0, item.active_count - 1)
    item.in_use = item.active_count
    item.available_count = max(0, item.total_count - item.active_count - item.inactive_count - item.archived_count)
    item.save(update_fields=["active_count", "in_use", "available_count", "updated_on"])


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
    # Category: was this item serviceable or unserviceable when archived?
    ARCHIVE_CATEGORY_CHOICES = [
        ('serviceable', 'Serviceable'),
        ('unserviceable', 'Unserviceable'),
    ]
    # Status: current state of the archived item
    ARCHIVE_STATUS_CHOICES = [
        ('archived', 'Archived'),
        ('under_maintenance', 'Under Maintenance'),
        ('serviced', 'Serviced'),
        ('not_serviceable', 'Not Serviceable'),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    count = models.IntegerField()
    archive_type = models.CharField(max_length=20, choices=ARCHIVE_TYPES, blank=True, default='consumption')
    # New: serviceable or unserviceable category
    archive_category = models.CharField(
        max_length=20,
        choices=ARCHIVE_CATEGORY_CHOICES,
        default='serviceable',
    )
    # New: current status of this archive entry
    archive_status = models.CharField(
        max_length=20,
        choices=ARCHIVE_STATUS_CHOICES,
        default='archived',
    )
    remark = models.TextField(blank=True, default='')
    archived_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.item.item_name)
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.item.item_name

class AssetTag(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    tag_id = models.CharField(max_length=20, unique=True)
    assigned_room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tag_id


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
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    rooms = models.ManyToManyField(Room, blank=True, related_name='multi_room_bookings')
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    faculty_name = models.CharField(max_length=255)
    faculty_email = models.EmailField()
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    created_on = models.DateTimeField(auto_now_add=True)
    purpose = models.TextField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    cancelled_by = models.ForeignKey('core.UserProfile', null=True, blank=True, on_delete=models.SET_NULL, related_name='cancelled_bookings')
    cancelled_on = models.DateTimeField(null=True, blank=True)
    requirements_doc = models.FileField(
        upload_to='room_bookings/requirements/',
        null=True, 
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'heic', 'heif', 'webp', 'gif', 'bmp', 'tiff', 'tif'])],
        help_text="Upload a PDF or image file, or leave empty if Not Applicable."
    )
    # Inline text requirements (no doc needed)
    requirements_text = models.TextField(
        null=True,
        blank=True,
        help_text="Plain text requirements entered directly by the faculty."
    )
    # Stores the plain-text content extracted from requirements_doc at approval time.
    # This allows admin to view/download the document content without touching
    requirements_doc_text = models.TextField(
        null=True,
        blank=True,
        help_text="Auto-extracted plain text from the uploaded requirements document."
    )
    recommended_by_name = models.CharField(max_length=255, blank=True)
    recommended_note = models.TextField(blank=True)
    approved_by_name = models.CharField(max_length=255, blank=True)
    approved_note = models.TextField(blank=True)
    is_edited = models.BooleanField(default=False, help_text="True if this booking was edited after initial creation.")
    # Internal admin note for extra items added or returned (refreshments only, not emailed)
    add_return_note = models.TextField(
        null=True, blank=True,
        help_text="Internal admin note for extra items added/taken or returned for this booking. Not emailed."
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

    @property
    def room_summary(self):
        return format_room_list(self)


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

# TAT for booking approval (hours). Matches Issue TAT default.
BOOKING_APPROVAL_TAT_HOURS = 48


class RoomBookingRequest(models.Model):
    """
    Pending room booking that requires admin approval before becoming
    a confirmed RoomBooking entry.

    TAT: 48 hours from submission.  Automated reminders at 24h and 12h
    before expiry.  If still pending at deadline the request is auto-cancelled
    and notification emails are sent to both faculty and admins.
    """
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        # Set by the automated expiry task — not by manual admin action.
        ('expired',  'Expired / Auto-Cancelled'),
    ]

    room            = models.ForeignKey(Room, on_delete=models.CASCADE)
    rooms           = models.ManyToManyField(Room, blank=True, related_name='multi_room_booking_requests')
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
                            allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'heic', 'heif', 'webp', 'gif', 'bmp', 'tiff', 'tif']
                        )],
                      )
    # NEW: plain-text requirements typed inline by faculty
    requirements_text = models.TextField(
        null=True,
        blank=True,
        help_text="Plain text requirements typed by faculty (no document upload needed)."
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

    # ── TAT tracking ────────────────────────────────────────────────────────
    # Set automatically on creation to created_on + BOOKING_APPROVAL_TAT_HOURS.
    tat_deadline    = models.DateTimeField(
                        null=True, blank=True,
                        help_text="Deadline by which admin must approve/reject. Auto-cancelled if exceeded."
                      )
    # Tracks whether the 24h and 12h reminder emails have already been sent
    # so the periodic task does not send them twice.
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_12h_sent = models.BooleanField(default=False)

    WORKFLOW_STAGE_CHOICES = [
        ('sub_admin',      'Sub Admin Review'),
        ('central_admin',  'Central Admin Final Approval'),
    ]
 
    # Routing stage — starts at sub_admin, moves to central_admin after recommendation
    workflow_stage   = models.CharField(
        max_length=20,
        choices=WORKFLOW_STAGE_CHOICES,
        default='sub_admin',
    )
 
    # Set when a sub-admin recommends the booking
    recommended_by   = models.ForeignKey(
        'core.UserProfile',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='recommended_bookings',
    )
    recommended_note = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        'core.UserProfile',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_booking_requests',
    )
    approved_note = models.TextField(blank=True)
 

    def save(self, *args, **kwargs):
        # Set TAT deadline on first save
        if not self.pk and not self.tat_deadline:
            self.tat_deadline = timezone.now() + timezone.timedelta(hours=BOOKING_APPROVAL_TAT_HOURS)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"BookingReq [{self.status}]: {self.room} | {self.faculty_email}"

    @property
    def room_summary(self):
        return format_room_list(self)


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


class MasterInventoryAccess(models.Model):
    """
    Tracks which room incharges have been granted access to the Master Inventory.
    - can_view: view-only access (sidebar button visible, read-only page)
    - can_edit: edit access (can edit item fields inline — category, brand, cost, product code)
    Access is granted/revoked by central admin or sub-admin.
    Only one record per incharge (OneToOneField enforced).
    """
    organisation    = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    incharge        = models.OneToOneField(
                        UserProfile,
                        on_delete=models.CASCADE,
                        related_name='master_inventory_access',
                        limit_choices_to={'is_incharge': True},
                    )
    granted_by      = models.ForeignKey(
                        UserProfile,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='master_inventory_grants',
                    )
    can_view        = models.BooleanField(default=True, help_text="Allow view-only access to master inventory")
    can_edit        = models.BooleanField(default=False, help_text="Allow inline editing of master inventory items")
    granted_on      = models.DateTimeField(auto_now_add=True)
    updated_on      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Master Inventory Access'
        verbose_name_plural = 'Master Inventory Accesses'

    def __str__(self):
        perms = []
        if self.can_view: perms.append('view')
        if self.can_edit: perms.append('edit')
        return f"MasterInventoryAccess: {self.incharge} [{', '.join(perms)}]"


class AssignInventoryAccess(models.Model):
    """
    Tracks which room incharges have been granted access to the Assign Inventory page.
    - can_assign: allows the incharge to assign master inventory items to their own room(s)
    Access is granted/revoked by central admin or sub-admin.
    Only one record per incharge (OneToOneField enforced).
    """
    organisation    = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    incharge        = models.OneToOneField(
                        UserProfile,
                        on_delete=models.CASCADE,
                        related_name='assign_inventory_access',
                        limit_choices_to={'is_incharge': True},
                    )
    granted_by      = models.ForeignKey(
                        UserProfile,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='assign_inventory_grants',
                    )
    can_assign      = models.BooleanField(default=True, help_text="Allow incharge to assign master inventory to their rooms")
    granted_on      = models.DateTimeField(auto_now_add=True)
    updated_on      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Assign Inventory Access'
        verbose_name_plural = 'Assign Inventory Accesses'

    def __str__(self):
        return f"AssignInventoryAccess: {self.incharge} [can_assign={self.can_assign}]"


# ─────────────────────────────────────────────────────────────────────
# ITEM CONFIGURATION — Lab-style spec sheets attached to items
# ─────────────────────────────────────────────────────────────────────

class ItemConfiguration(models.Model):
    """
    Stores a named configuration (spec sheet) for one or more items in a room.
    configuration_data: JSON array of {spec, value} objects (same format as SystemConfiguration).
    count: how many of that item are configured with this configuration.
    """
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='configurations')
    configuration_name = models.CharField(max_length=255, blank=True, default='')
    configuration_data = models.TextField(default='[]', help_text='JSON array of {spec, value} objects')
    count = models.PositiveIntegerField(default=1, help_text='How many of this item have this configuration')
    created_by = models.ForeignKey(
        UserProfile,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='item_configurations_created',
    )
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, max_length=255)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.item.item_name}-config")
            self.slug = generate_unique_slug(self, base_slug)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Config: {self.configuration_name or self.item.item_name} ({self.count})"
