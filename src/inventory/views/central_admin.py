from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View
from core.models import User, UserProfile
from inventory.models import Room, Vendor, Purchase, Issue, Department, Item, EditRequest  # Import the Department model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.base_user import BaseUserManager
from django.db import transaction
from inventory.forms.central_admin import PeopleCreateForm, RoomCreateForm, DepartmentForm, VendorForm  # Import the form
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from inventory.email import safe_send_mail
from django.utils import timezone
from django.views.decorators.http import require_POST

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'central_admin/dashboard.html'
    
    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PeopleListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/people_list.html'
    model = UserProfile
    context_object_name = 'people'
    
    def get_qeryset(self):
        return super().get_queryset().filter(organisation=self.request.user.organisation)
    

class PeopleCreateView(LoginRequiredMixin, CreateView):
    model = UserProfile
    template_name = 'central_admin/people_create.html'
    form_class = PeopleCreateForm
    success_url = reverse_lazy('central_admin:people_list')

    @transaction.atomic
    def form_valid(self, form):
        current_profile = getattr(self.request.user, "profile", None)
        role = form.cleaned_data.get('role')
        email = form.cleaned_data.get('email')

        # Prevent Sub Admin from creating Central Admin
        if current_profile and current_profile.is_sub_admin and role == 'central_admin':
            form.add_error('role', "Sub Admin cannot create a Central Admin account.")
            return self.form_invalid(form)

        # Create Django User
        random_password = BaseUserManager().make_random_password()

        user = User.objects.create_user(
            email=email,
            first_name=form.cleaned_data.get('first_name'),
            last_name=form.cleaned_data.get('last_name'),
            password=random_password,
        )
        user.is_active = True
        user.is_staff = True
        user.save()

        # Create UserProfile
        userprofile = form.save(commit=False)
        userprofile.user = user

        if current_profile:
            userprofile.org = current_profile.org

        # Reset role flags
        userprofile.is_central_admin = False
        userprofile.is_sub_admin = False
        userprofile.is_incharge = False

        if role == 'central_admin':
            userprofile.is_central_admin = True
        elif role == 'sub_admin':
            userprofile.is_sub_admin = True
        elif role == 'room_incharge':
            userprofile.is_incharge = True

        userprofile.save()

        # Create password reset link
        token_generator = PasswordResetTokenGenerator()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)

        reset_link = self.request.build_absolute_uri(
            reverse('core:confirm_password_reset', kwargs={'uidb64': uid, 'token': token})
        )

        subject = "Your Blixtro account has been created"
        message = (
            "Hi,\n\n"
            "An account has been created for you on the SFS IMS system.\n\n"
            "Please click the link below to set your password:\n"
            f"{reset_link}\n\n"
            "Best regards,\nSFS IMS Team"
        )

        # Use safe_send_mail to avoid worker crash if SMTP fails
        try:
            safe_send_mail(
                subject,
                message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[user.email],
                fail_silently=True
            )
        except Exception as e:
            # defensive: safe_send_mail should not raise, but log unexpected errors
            print(f"[central_admin] safe_send_mail unexpected error: {e}", flush=True)

        return redirect(self.success_url)


class PeopleDeleteView(LoginRequiredMixin, DeleteView):
    model = UserProfile
    template_name = 'central_admin/people_delete_confirm.html'
    slug_field = 'slug'  # Changed from 'people_slug' to 'slug'
    slug_url_kwarg = 'people_slug'
    success_url = reverse_lazy('central_admin:people_list')
    

class RoomListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/room_list.html'
    model = Room
    context_object_name = 'rooms'

    def get_queryset(self):
        return Room.objects.filter(organisation=self.request.user.profile.org)
    
    
class RoomCreateView(LoginRequiredMixin, CreateView):
    model = Room
    template_name = 'central_admin/room_create.html'
    form_class = RoomCreateForm
    success_url = reverse_lazy('central_admin:room_list')

    def form_valid(self, form):
        room = form.save(commit=False)
        room.organisation = self.request.user.profile.org
        room.save()
        return redirect(self.success_url)
    
    
class RoomDeleteView(LoginRequiredMixin, DeleteView):
    model = Room
    template_name = 'central_admin/room_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'room_slug'
    success_url = reverse_lazy('central_admin:room_list')


class RoomUpdateView(LoginRequiredMixin, UpdateView):
    model = Room
    template_name = 'central_admin/room_update.html'
    form_class = RoomCreateForm
    success_url = reverse_lazy('central_admin:room_list')
    slug_field = 'slug'
    slug_url_kwarg = 'room_slug'

    def form_valid(self, form):
        room = form.save(commit=False)
        room.organisation = self.request.user.profile.org
        room.save()
        return redirect(self.success_url)


class VendorListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/vendor_list.html'
    model = Vendor
    context_object_name = 'vendors'
    
    def get_queryset(self):
        return super().get_queryset().filter(organisation=self.request.user.profile.org)


class VendorCreateView(LoginRequiredMixin, CreateView):
    model = Vendor
    template_name = 'central_admin/vendor_create.html'
    form_class = VendorForm
    success_url = reverse_lazy('central_admin:vendor_list')

    def form_valid(self, form):
        vendor = form.save(commit=False)
        vendor.organisation = self.request.user.profile.org
        vendor.save()
        return redirect(self.success_url)


class VendorUpdateView(LoginRequiredMixin, UpdateView):
    model = Vendor
    template_name = 'central_admin/vendor_update.html'
    form_class = VendorForm
    success_url = reverse_lazy('central_admin:vendor_list')
    slug_field = 'slug'
    slug_url_kwarg = 'vendor_slug'

    def form_valid(self, form):
        vendor = form.save(commit=False)
        vendor.organisation = self.request.user.profile.org
        vendor.save()
        return redirect(self.success_url)


class VendorDeleteView(LoginRequiredMixin, DeleteView):
    model = Vendor
    template_name = 'central_admin/vendor_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'vendor_slug'
    success_url = reverse_lazy('central_admin:vendor_list')


class PurchaseListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/purchase_list.html'
    model = Purchase
    context_object_name = 'purchases'
    
    def get_queryset(self):
        return super().get_queryset().filter(organisation=self.request.user.profile.org)


class IssueListView(LoginRequiredMixin, ListView):
    """
    [IssueTab] Show all issues for the current organisation to Central Admin / Sub Admin.
    """
    template_name = 'central_admin/issue_list.html'
    model = Issue
    context_object_name = 'issues'

    # --- Replace the get_queryset method inside IssueListView with this full method ---
def get_queryset(self):
    """
    Return issues visible to the central/sub admin view.

    Rules:
      - Show issues belonging to the admin's organisation (profile.org)
      - OR issues specifically assigned to the current user's profile (assigned_to)
      - Superuser sees everything
      - If the user has no org and not superuser, and there's only one org in DB, show issues for that org
      - Otherwise fallback to qs.none() to avoid cross-org leaks
    """
    qs = super().get_queryset()
    profile = getattr(self.request.user, "profile", None)

    # If the user has a profile and an organisation, show issues either belonging to that organisation
    # OR those assigned directly to the user (this ensures escalated issues assigned to a user are visible).
    if profile and getattr(profile, "org", None):
        from django.db.models import Q
        qs = qs.filter(Q(organisation=profile.org) | Q(assigned_to=profile))

    elif self.request.user.is_superuser:
        # Superusers see everything
        qs = qs

    else:
        # If only one organisation exists, show that org's issues
        from inventory.models import Organisation
        org_count = Organisation.objects.count()
        if org_count == 1:
            org = Organisation.objects.first()
            qs = qs.filter(organisation=org)
        else:
            # Fallback: avoid cross-organisation leakage
            qs = qs.none()

    # Use select_related for efficiency and order newest first
    return qs.select_related('room', 'assigned_to').order_by('-created_on')





class DepartmentListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/department_list.html'
    model = Department
    context_object_name = 'departments'

    def get_queryset(self):
        return super().get_queryset().filter(organisation=self.request.user.profile.org)


class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    template_name = 'central_admin/department_create.html'
    form_class = DepartmentForm
    success_url = reverse_lazy('central_admin:department_list')

    def form_valid(self, form):
        department = form.save(commit=False)
        department.organisation = self.request.user.profile.org
        department.save()
        return redirect(self.success_url)


class DepartmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Department
    template_name = 'central_admin/department_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'department_slug'
    success_url = reverse_lazy('central_admin:department_list')


class PurchaseApproveView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        purchase = get_object_or_404(Purchase, slug=self.kwargs['purchase_slug'])
        if purchase.status == 'requested':
            purchase.status = 'approved'
            purchase.save()
        return redirect('central_admin:purchase_list')

class PurchaseDeclineView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        purchase = get_object_or_404(Purchase, slug=self.kwargs['purchase_slug'])
        if purchase.status == 'requested':
            purchase.status = 'rejected'
            purchase.save()
        return redirect('central_admin:purchase_list')
    
class ItemListView(LoginRequiredMixin, ListView):
    model = Item
    template_name = 'central_admin/item_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        profile = self.request.user.profile

        if profile.is_sub_admin:
            # SubAdmin sees EVERYTHING from room-incharges
            return Item.objects.filter(
                organisation=profile.org
            ).select_related('room', 'category', 'brand')

        if profile.is_central_admin:
            # CentralAdmin sees only items NOT created by incharge
            return Item.objects.filter(
                organisation=profile.org,
                created_by__is_incharge=False
            ).select_related('room', 'category', 'brand')

        return Item.objects.none()

class EditRequestListView(ListView):
    model = EditRequest
    template_name = "central_admin/edit_request_list.html"
    context_object_name = "edit_requests"

    def get_queryset(self):
        return EditRequest.objects.filter(status="pending").order_by("-created_on")

class ApproveEditRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        er = get_object_or_404(EditRequest, pk=pk)
        item = er.item

        # STEP 1 — Mark request as approved
        er.status = "approved"
        er.reviewed_by = request.user.profile
        er.save()

        # STEP 2 — Unlock item so room incharge can edit it
        item.is_edit_lock = False
        item.save()

        messages.success(request, "Edit request approved. Item is now unlocked for editing.")
        return redirect('central_admin:edit_request_list')


class RejectEditRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        er = get_object_or_404(EditRequest, pk=pk)
        er.status = 'rejected'
        er.save()
        messages.info(request, "Edit request rejected.")
        return redirect('central_admin:edit_request_list')

# added this for admin issue actions

@require_POST
def admin_resolve_issue(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    issue.resolved = True
    issue.status = "closed"
    issue.save(update_fields=["resolved", "status", "updated_on"])
    messages.success(request, f"Issue {issue.ticket_id} marked as resolved.")
    return redirect("central_admin:issue_list")


@require_POST
def admin_unresolve_issue(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    issue.resolved = False
    issue.status = "open"   # keep simple — not touching workflow
    issue.save(update_fields=["resolved", "status", "updated_on"])
    messages.info(request, f"Issue {issue.ticket_id} marked as unresolved.")
    return redirect("central_admin:issue_list")


@require_POST
def admin_deescalate_issue(request, pk):
    issue = get_object_or_404(Issue, pk=pk)

    # Only de-escalate if above room incharge
    if issue.escalation_level > 0:
        issue.escalation_level = 0
        issue.status = "open"
        issue.resolved = False

        # send back to room incharge
        issue.assigned_to = issue.room.incharge

        issue.save(update_fields=[
            "escalation_level", "assigned_to", "status",
            "resolved", "updated_on"
        ])

        messages.warning(request, f"Issue {issue.ticket_id} de-escalated to room incharge.")
    else:
        messages.error(request, "Issue is already at the lowest escalation level.")

    return redirect("central_admin:issue_list")