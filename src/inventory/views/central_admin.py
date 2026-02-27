from django.shortcuts import redirect, get_object_or_404, render
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View
from core.models import User, UserProfile
from inventory.models import Room, Vendor, Purchase, Issue, Department, Item, StockRequest, IssueTimeExtensionRequest, RoomBooking, RoomBookingRequest, RoomCancellationRequest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.base_user import BaseUserManager
from django.db import transaction, connection
from inventory.forms.central_admin import PeopleCreateForm, RoomCreateForm, DepartmentForm, VendorForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from inventory.email import safe_send_mail
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta
import requests
from django.http import HttpResponse, Http404

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
                subject=subject,
                message=message,
                recipient_list=[user.email],
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
        qs = Room.objects.filter(organisation=self.request.user.profile.org)
        category = self.request.GET.get('category')
        search   = self.request.GET.get('search')
        if category:
            qs = qs.filter(room_category=category)
        if search:
            qs = qs.filter(room_name__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Room.ROOM_CATEGORIES
        context['view_mode']  = self.request.GET.get('view', 'list')

        # ── Booking-status data for the booking view ───────────────────
        now       = timezone.now()
        all_rooms = self.get_queryset()

        # Currently active (confirmed) bookings
        active_bookings = RoomBooking.objects.filter(
            room__in=all_rooms,
            start_datetime__lte=now,
            end_datetime__gte=now,
        ).select_related('room')

        booked_room_ids = {b.room_id for b in active_bookings}

        # Pending booking requests
        pending_reqs = RoomBookingRequest.objects.filter(
            room__in=all_rooms,
            status='pending',
        ).select_related('room')

        pending_room_ids = {r.room_id for r in pending_reqs}

        # One entry per room for booked section
        booked_map = {}
        for b in active_bookings:
            booked_map[b.room_id] = b
        booked_entries = [{'room': b.room, 'booking': b} for b in booked_map.values()]

        # One entry per room for pending section
        pending_map = {}
        for r in pending_reqs:
            pending_map[r.room_id] = r
        pending_entries = [{'room': r.room, 'request': r} for r in pending_map.values()]

        # Available = not booked right now AND no pending request
        available_rooms = [
            r for r in all_rooms
            if r.id not in booked_room_ids and r.id not in pending_room_ids
        ]

        context['booked_rooms']          = booked_entries
        context['pending_booking_rooms'] = pending_entries
        context['available_rooms']       = available_rooms
        return context
    
    
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
    
    
class RoomDeleteView(LoginRequiredMixin, View):
    """Central Admin only — sub-admins are not allowed to delete rooms."""

    def dispatch(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.is_sub_admin:
            messages.error(request, "Sub-admins are not permitted to delete rooms.")
            return redirect('central_admin:room_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        room = get_object_or_404(
            Room, slug=kwargs['room_slug'],
            organisation=request.user.profile.org
        )
        return render(request, 'central_admin/room_delete_confirm.html', {'object': room})

    def post(self, request, *args, **kwargs):
        room = get_object_or_404(
            Room, slug=kwargs['room_slug'],
            organisation=request.user.profile.org
        )
        room_name = room.room_name
        room.delete()
        messages.success(request, f"Room '{room_name}' deleted successfully.")
        return redirect('central_admin:room_list')


class RoomUpdateView(LoginRequiredMixin, UpdateView):
    model = Room
    template_name = 'central_admin/room_update.html'
    form_class = RoomCreateForm
    success_url = reverse_lazy('central_admin:room_list')
    slug_field = 'slug'
    slug_url_kwarg = 'room_slug'

    def dispatch(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.is_sub_admin:
            messages.error(request, "Sub-admins are not permitted to edit rooms.")
            return redirect('central_admin:room_list')
        return super().dispatch(request, *args, **kwargs)

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


class PurchaseCreateView(LoginRequiredMixin, View):
    """
    Sub Admin raises a purchase request for an item (existing or new name).
    They do NOT select a vendor — central admin handles that on approval.
    """
    template_name = 'central_admin/purchase_create.html'

    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_sub_admin:
            return redirect('central_admin:dashboard')
        # Fetch master inventory items for the org to allow selection
        try:
            master_items = Item.objects.filter(organisation=profile.org).order_by('item_name')
        except Exception:
            master_items = []
        rooms = Room.objects.filter(organisation=profile.org)
        return render(request, self.template_name, {
            'master_items': master_items,
            'rooms': rooms,
        })

    def post(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_sub_admin:
            return redirect('central_admin:dashboard')

        item_name = request.POST.get('item_name', '').strip()
        quantity = request.POST.get('quantity', '').strip()
        unit_of_measure = request.POST.get('unit_of_measure', 'units')
        room_id = request.POST.get('room_id', '')
        reason = request.POST.get('reason', '').strip()

        if not item_name or not quantity:
            messages.error(request, 'Item name and quantity are required.')
            return redirect('central_admin:purchase_create')

        org = profile.org

        # Get or create a placeholder item for this purchase request
        from inventory.models import Category, Brand, Item as InvItem
        placeholder_cat, _ = Category.objects.get_or_create(
            organisation=org, category_name='Purchase Requests',
            defaults={'room': None}
        )
        placeholder_brand, _ = Brand.objects.get_or_create(
            organisation=org, brand_name='To Be Determined',
            defaults={'room': None}
        )
        item_obj, _ = InvItem.objects.get_or_create(
            organisation=org,
            item_name=item_name,
            defaults={
                'category': placeholder_cat,
                'brand': placeholder_brand,
                'total_count': 0,
                'is_listed': False,
            }
        )

        room = None
        if room_id:
            try:
                room = Room.objects.get(id=room_id, organisation=org)
            except Room.DoesNotExist:
                pass

        Purchase.objects.create(
            organisation=org,
            item=item_obj,
            quantity=float(quantity),
            unit_of_measure=unit_of_measure,
            room=room,
            reason=reason,
            status='requested',
            requested_by=profile,
        )

        messages.success(request, f'Purchase request for "{item_name}" submitted successfully.')
        return redirect('central_admin:purchase_list')


class PurchaseListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/purchase_list.html'
    model = Purchase
    context_object_name = 'purchases'

    def get_queryset(self):
        profile = self.request.user.profile

        if profile.is_central_admin and not profile.is_sub_admin:
            # Central Admin sees ALL purchase requests from sub-admins
            return (
                Purchase.objects
                .filter(organisation=profile.org)
                .select_related("room", "item", "vendor", "receipt", "requested_by__user")
                .order_by("-created_on")
            )

        if profile.is_sub_admin:
            # Sub Admin sees only their OWN requests
            return (
                Purchase.objects
                .filter(organisation=profile.org, requested_by=profile)
                .select_related("room", "item", "vendor", "receipt", "requested_by__user")
                .order_by("-created_on")
            )

        return Purchase.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        context['is_central_admin'] = profile.is_central_admin and not profile.is_sub_admin
        context['is_sub_admin'] = profile.is_sub_admin
        return context

class PurchaseUploadInvoiceView(LoginRequiredMixin, View):
    def post(self, request, purchase_slug):
        # Only central admin — not sub admin
        profile = request.user.profile
        if not (profile.is_central_admin and not profile.is_sub_admin):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        purchase = get_object_or_404(Purchase, slug=purchase_slug)
        invoice_file = request.FILES.get('invoice')

        if not invoice_file:
            return JsonResponse({'error': 'No file uploaded.'}, status=400)

        if not invoice_file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Only PDF files are allowed.'}, status=400)

        if invoice_file.size > 10 * 1024 * 1024:  # 10MB limit
            return JsonResponse({'error': 'File too large. Max 10MB.'}, status=400)

        # Delete old invoice if exists
        if purchase.invoice:
            purchase.invoice.delete(save=False)

        purchase.invoice = invoice_file
        purchase.save()

        return JsonResponse({
            'success': True,
            'message': 'Invoice uploaded successfully.',
            'has_invoice': True
        })

class PurchaseInvoiceViewView(LoginRequiredMixin, View):
    def get(self, request, purchase_slug):
        # Only central admin
        profile = request.user.profile
        if not (profile.is_central_admin and not profile.is_sub_admin):
            raise Http404

        purchase = get_object_or_404(Purchase, slug=purchase_slug)
        if not purchase.invoice:
            raise Http404

        # Read file and stream it back
        try:
            file = purchase.invoice
            response = HttpResponse(file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="invoice_{purchase.purchase_id}.pdf"'
            return response
        except Exception:
            raise Http404

class IssueListView(LoginRequiredMixin, ListView):
    """
    [IssueTab] Show all issues for the current organisation to Central Admin / Sub Admin.
    """
    template_name = 'central_admin/issue_list.html'
    model = Issue
    context_object_name = 'issues'

    def get_queryset(self):
        """
        Return issues visible to the central/sub admin view.
        Rules:
          - Show issues belonging to the admin's organisation (profile.org)
          - OR issues specifically assigned to the current user's profile (assigned_to)
          - Filters by escalation level if 'filter=escalated' is provided.
        """
        qs = super().get_queryset()
        profile = getattr(self.request.user, "profile", None)
        issue_filter = self.request.GET.get('filter')

        if profile and getattr(profile, "org", None):
            from django.db.models import Q
            # Base logic: Org issues OR directly assigned
            qs = qs.filter(Q(organisation=profile.org) | Q(assigned_to=profile))

            # Filter by escalation level
            if issue_filter == 'escalated':
                # Level 2 for Central Admin, Level 1 for Sub Admin
                target_level = 2 if profile.is_central_admin else 1
                qs = qs.filter(escalation_level=target_level)

        elif self.request.user.is_superuser:
            qs = qs
            if issue_filter == 'escalated':
                qs = qs.filter(status='escalated')

        else:
            from inventory.models import Organisation
            org_count = Organisation.objects.count()
            if org_count == 1:
                org = Organisation.objects.first()
                qs = qs.filter(organisation=org)
            else:
                qs = qs.none()

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

class EditRequestListView(LoginRequiredMixin, ListView):
    """
    Legacy list view — now shows StockRequests.
    The main approval hub is ApprovalRequestListView.
    """
    template_name = "central_admin/edit_request_list.html"
    context_object_name = "stock_requests"

    def get_queryset(self):
        return (
            StockRequest.objects
            .filter(status="pending")
            .select_related("item", "room", "requested_by")
            .order_by("-created_on")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["request_type"] = "item_edit"
        return context


class ApproveStockRequestView(LoginRequiredMixin, View):
    """
    Approving a StockRequest increases the item's total_count and available_count
    by the requested_count, then marks the request as approved.
    """
    def post(self, request, pk, *args, **kwargs):
        stock_req = get_object_or_404(StockRequest, pk=pk, status="pending")
        item = stock_req.item

        # Increase stock
        item.total_count     += stock_req.requested_count
        item.available_count += stock_req.requested_count
        item.save(update_fields=["total_count", "available_count"])

        stock_req.status      = "approved"
        stock_req.reviewed_by = request.user.profile
        stock_req.save(update_fields=["status", "reviewed_by"])

        messages.success(
            request,
            f"Stock request approved — {stock_req.requested_count} units added to '{item.item_name}'."
        )
        next_type = request.POST.get("next_type", "item_edit")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectStockRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        stock_req = get_object_or_404(StockRequest, pk=pk, status="pending")
        stock_req.status      = "rejected"
        stock_req.reviewed_by = request.user.profile
        stock_req.save(update_fields=["status", "reviewed_by"])

        messages.info(request, "Stock request rejected.")
        next_type = request.POST.get("next_type", "item_edit")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


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

class ApprovalRequestListView(LoginRequiredMixin, ListView):
    """
    Central Admin unified approval hub.

    All four request types are fetched in one page-load and rendered into
    four separate HTML panels. The tab switcher is pure client-side JS —
    no page reload when switching tabs.
    """
    template_name       = "central_admin/edit_request_list.html"
    model               = StockRequest 
    context_object_name = "requests"            

    def get_queryset(self):
        return StockRequest.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        VALID_TABS = {'item_edit', 'issue_tat', 'booking_req', 'cancel_req'}
        raw = self.request.GET.get('type', 'item_edit')
        context['active_tab'] = raw if raw in VALID_TABS else 'item_edit'

        # ── Panel 1: Item Stock Requests ──────────────────────────────────
        context['stock_requests'] = (
            StockRequest.objects
            .filter(status='pending')
            .select_related('item', 'room', 'requested_by')
            .order_by('-created_on')
        )

        # ── Panel 2: Issue Time Extension Requests ────────────────────────
        context['tat_requests'] = (
            IssueTimeExtensionRequest.objects
            .filter(status='pending')
            .select_related('issue', 'requested_by')
            .order_by('-created_on')
        )

        # ── Panel 3: Room Booking Requests ────────────────────────────────
        context['booking_requests'] = (
            RoomBookingRequest.objects
            .filter(status='pending')
            .select_related('room')
            .order_by('-created_on')
        )

        # ── Panel 4: Room Cancellation Requests ───────────────────────────
        context['cancel_requests'] = (
            RoomCancellationRequest.objects
            .filter(status='pending')
            .select_related('booking', 'booking__room')
            .order_by('-created_on')
        )

        # ── Badge counts shown on the tab pills ───────────────────────────
        context['item_edit_count']   = context['stock_requests'].count()
        context['issue_tat_count']   = context['tat_requests'].count()
        context['booking_req_count'] = context['booking_requests'].count()
        context['cancel_req_count']  = context['cancel_requests'].count()

        return context


# ================================
# ISSUE TIME EXTENSION APPROVAL
# ================================

class ApproveIssueTimeExtensionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        req = get_object_or_404(
            IssueTimeExtensionRequest,
            pk=pk,
            status="pending"
        )

        issue = req.issue

        # Extend SLA
        if issue.tat_deadline:
            issue.tat_deadline += timedelta(
                hours=req.requested_extra_hours
            )
        else:
            issue.tat_deadline = timezone.now() + timedelta(
                hours=req.requested_extra_hours
            )

        issue.save(update_fields=["tat_deadline"])

        req.status = "approved"
        req.reviewed_by = request.user.profile
        req.save(update_fields=["status", "reviewed_by"])

        messages.success(request, "Issue time extension approved successfully.")
        next_type = request.POST.get("next_type", "issue_tat")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectIssueTimeExtensionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        req = get_object_or_404(
            IssueTimeExtensionRequest,
            pk=pk,
            status="pending"
        )

        req.status = "rejected"
        req.reviewed_by = request.user.profile
        req.save(update_fields=["status", "reviewed_by"])

        messages.info(request, "Issue time extension request rejected.")
        next_type = request.POST.get("next_type", "issue_tat")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")

# ═══════════════════════════════════════════════════════════════
# ROOM BOOKING REQUEST — APPROVE / REJECT
# ═══════════════════════════════════════════════════════════════

class ApproveRoomBookingRequestView(LoginRequiredMixin, View):
    """
    Approving a RoomBookingRequest converts it into a confirmed RoomBooking.
    The duplicate-booking check inside RoomBooking.clean() is still enforced.
    """
    def post(self, request, pk):
        booking_req = get_object_or_404(RoomBookingRequest, pk=pk, status="pending")

        try:
            # ── Extract plain text from the uploaded .docx before saving ────────
            # Uses _extract_docx_structured from aura.py which covers paragraphs,
            # tables, and text boxes.  Failure is non-fatal — text is extracted
            # lazily on first "View Doc" click via get_booking_doc_text.
            doc_text = None
            if booking_req.requirements_doc and booking_req.requirements_doc.name:
                try:
                    import io as _io
                    import traceback as _tb
                    from docx import Document as _DocxDoc
                    from docx.oxml.ns import qn as _qn

                    _storage = booking_req.requirements_doc.storage
                    with _storage.open(booking_req.requirements_doc.name, 'rb') as _f:
                        _raw = _f.read()

                    _doc  = _DocxDoc(_io.BytesIO(_raw))
                    _lines = []
                    _body  = _doc.element.body

                    for _child in _body:
                        _tag = _child.tag.split('}')[-1] if '}' in _child.tag else _child.tag
                        if _tag == 'p':
                            _t = ''.join(n.text or '' for n in _child.iter(_qn('w:t'))).strip()
                            if _t:
                                _lines.append(_t)
                        elif _tag == 'tbl':
                            for _tr in _child.iter(_qn('w:tr')):
                                _cells = []
                                for _tc in _tr.iter(_qn('w:tc')):
                                    _ct = ' '.join(
                                        ''.join(n.text or '' for n in _p.iter(_qn('w:t'))).strip()
                                        for _p in _tc.iter(_qn('w:p'))
                                    ).strip()
                                    _cells.append(_ct)
                                if any(_cells):
                                    _lines.append(' | '.join(_cells))
                        elif _tag == 'txbxContent':
                            _t = ''.join(n.text or '' for n in _child.iter(_qn('w:t'))).strip()
                            if _t:
                                _lines.append(_t)

                    doc_text = '\n'.join(_lines) if _lines else None
                    print(f"[ApproveBooking] docx text extracted OK ({len(doc_text or '')} chars, {len(_lines)} lines)")
                except Exception as _e:
                    import traceback as _tb
                    print(f"[ApproveBooking] docx extraction failed (non-fatal): {_e}\n{_tb.format_exc()}")

            booking = RoomBooking(
                room                  = booking_req.room,
                department            = booking_req.department,
                faculty_name          = booking_req.faculty_name,
                faculty_email         = booking_req.faculty_email,
                start_datetime        = booking_req.start_datetime,
                end_datetime          = booking_req.end_datetime,
                purpose               = booking_req.purpose,
                requirements_doc      = booking_req.requirements_doc,
                requirements_doc_text = doc_text,
            )
            booking.full_clean()  # runs conflict detection
            booking.save()

            booking_req.status      = "approved"
            booking_req.reviewed_by = request.user.profile
            booking_req.save(update_fields=["status", "reviewed_by"])

            # ── Send confirmation email to faculty ──────────────────────────
            try:
                from inventory.email import safe_send_mail as _safe_mail
                from django.utils import timezone as _tz
                _start_local = _tz.localtime(booking.start_datetime)
                _end_local   = _tz.localtime(booking.end_datetime)
                _date_str  = _start_local.strftime("%A, %d %B %Y")
                _start_str = _start_local.strftime("%I:%M %p")
                _end_str   = _end_local.strftime("%I:%M %p")
                _safe_mail(
                    subject=f"[Blixtro] Booking Confirmed — {booking_req.purpose or booking_req.room.room_name}",
                    message=(
                        f"Dear {booking_req.faculty_name},"
                        
                        f"Your room booking request has been approved."
                        
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
                        
                        f"  Room      : {booking.room.room_name}"
                        
                        f"  Date      : {_date_str}"
                        
                        f"  Time      : {_start_str} – {_end_str}"
                        
                        f"  Purpose   : {booking_req.purpose or '—'}"
                        
                        f"  Booking ID: {booking.id}"
                        
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
                        
                        f"Please ensure the room is vacated by the end time."
                        
                        f"Best regards, Blixtro — SFS College Inventory & Booking System"
                    ),
                    recipient_list=[booking_req.faculty_email],
                    fail_silently=True,
                )
                print(f"[ApproveBooking] Confirmation email sent to {booking_req.faculty_email}", flush=True)
            except Exception as _mail_err:
                print(f"[ApproveBooking] Email send failed (non-fatal): {_mail_err}", flush=True)

            messages.success(
                request,
                f"Booking approved — {booking_req.room} confirmed for {booking_req.faculty_name}. A confirmation email has been sent."
            )
        except Exception as e:
            messages.error(request, f"Could not approve booking: {e}")

        next_type = request.POST.get("next_type", "booking_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectRoomBookingRequestView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking_req = get_object_or_404(RoomBookingRequest, pk=pk, status="pending")
        booking_req.status      = "rejected"
        booking_req.review_note = request.POST.get("review_note", "")
        booking_req.reviewed_by = request.user.profile
        booking_req.save(update_fields=["status", "review_note", "reviewed_by"])

        messages.info(request, "Booking request rejected.")
        next_type = request.POST.get("next_type", "booking_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


# ═══════════════════════════════════════════════════════════════
# ROOM CANCELLATION REQUEST — APPROVE / REJECT
# ═══════════════════════════════════════════════════════════════

class ApproveCancellationRequestView(LoginRequiredMixin, View):
    """
    Approving cancellation deletes the confirmed RoomBooking so the
    room becomes available again in the booking manager.
    """
    def post(self, request, pk):
        cancel_req = get_object_or_404(RoomCancellationRequest, pk=pk, status="pending")
        booking    = cancel_req.booking

        # Delete the confirmed booking — room is freed
        booking.delete()

        cancel_req.status      = "approved"
        cancel_req.reviewed_by = request.user.profile
        # booking FK is now null (CASCADE deleted), save only safe fields
        cancel_req.save(update_fields=["status", "reviewed_by"])

        messages.success(
            request,
            "Cancellation approved — booking removed and room is now available."
        )
        next_type = request.POST.get("next_type", "cancel_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectCancellationRequestView(LoginRequiredMixin, View):
    def post(self, request, pk):
        cancel_req = get_object_or_404(RoomCancellationRequest, pk=pk, status="pending")
        cancel_req.status      = "rejected"
        cancel_req.reviewed_by = request.user.profile
        cancel_req.save(update_fields=["status", "reviewed_by"])

        messages.info(
            request,
            "Cancellation request rejected — booking remains active."
        )
        next_type = request.POST.get("next_type", "cancel_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


# ═══════════════════════════════════════════════════════════════
# ROOM INCHARGE — NOTIFICATIONS VIEW
# Used by room_incharge/notifications/ to show stock & issue alerts.
# ═══════════════════════════════════════════════════════════════

class RoomInchargeNotificationsView(LoginRequiredMixin, TemplateView):
    """
    Shows the room incharge their personalised notification feed:
      - Stock requests they raised: approved / rejected
      - Issues assigned to their room: new / escalated
    """
    template_name = "room_incharge/notifications.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room_slug = self.kwargs["room_slug"]
        from inventory.models import Room, RoomSettings
        room         = get_object_or_404(Room, slug=room_slug, incharge=self.request.user.profile)
        room_settings = RoomSettings.objects.get_or_create(room=room)[0]

        # Stock request notifications (approved / rejected only — skip pending)
        # NOTE: StockRequest has no updated_on — order by created_on
        stock_notifications = (
            StockRequest.objects
            .filter(room=room, status__in=["approved", "rejected"])
            .select_related("item", "reviewed_by")
            .order_by("-created_on")[:50]
        )

        # Issue notifications for this room
        issue_notifications = (
            Issue.objects
            .filter(room=room)
            .order_by("-updated_on")[:50]
        )

        context["room"]               = room
        context["room_slug"]          = room_slug
        context["room_settings"]      = room_settings
        context["stock_notifications"] = stock_notifications
        context["issue_notifications"] = issue_notifications
        return context


# ═══════════════════════════════════════════════════════════════
# ADMIN NOTIFICATION COUNTS  (AJAX — navbar bell badge)
# ═══════════════════════════════════════════════════════════════

def admin_notification_counts(request):
    """
    Returns pending/active counts for every notification type relevant to
    the logged-in admin role. Called every 60 s by the navbar bell badge.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    profile = getattr(request.user, 'profile', None)
    if not profile or not (profile.is_central_admin or profile.is_sub_admin):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    is_central = profile.is_central_admin and not profile.is_sub_admin
    org        = profile.org

    counts = {
        'booking_requests': RoomBookingRequest.objects.filter(status='pending').count(),
        'cancel_requests':  RoomCancellationRequest.objects.filter(status='pending').count(),
        'stock_requests':   StockRequest.objects.filter(status='pending').count(),
        'tat_requests':     IssueTimeExtensionRequest.objects.filter(status='pending').count(),
        'escalated_issues': Issue.objects.filter(status='escalated', organisation=org).count(),
    }

    if is_central:
        counts['purchase_requests'] = Purchase.objects.filter(
            status='requested', room__organisation=org
        ).count()
    else:
        counts['purchase_approvals'] = Purchase.objects.filter(
            status='approved', room__organisation=org
        ).count()

    counts['total'] = sum(counts.values())
    return JsonResponse(counts)


# ═══════════════════════════════════════════════════════════════
# ADMIN NOTIFICATIONS PAGE
# ═══════════════════════════════════════════════════════════════

class AdminNotificationsView(LoginRequiredMixin, View):
    """
    Standalone admin notification feed — works for both central admin and sub-admin.

    Central Admin sees:
      room booking requests, cancellation requests, stock requests,
      issue time extension requests, purchase requests, escalated issues.

    Sub Admin sees:
      room booking requests, cancellation requests, stock requests,
      issue time extension requests, purchase approvals (from central admin),
      escalated issues.
    """
    template_name = "central_admin/admin_notifications.html"

    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not (profile.is_central_admin or profile.is_sub_admin):
            return redirect('central_admin:dashboard')

        is_central = profile.is_central_admin and not profile.is_sub_admin
        org        = profile.org

        # ── Shared for both roles ──────────────────────────────────────
        booking_requests = (
            RoomBookingRequest.objects
            .filter(status='pending')
            .select_related('room')
            .order_by('-created_on')[:40]
        )
        cancel_requests = (
            RoomCancellationRequest.objects
            .filter(status='pending')
            .select_related('booking', 'booking__room')
            .order_by('-created_on')[:40]
        )
        stock_requests = (
            StockRequest.objects
            .filter(status='pending')
            .select_related('item', 'room', 'requested_by')
            .order_by('-created_on')[:40]
        )
        tat_requests = (
            IssueTimeExtensionRequest.objects
            .filter(status='pending')
            .select_related('issue', 'requested_by')
            .order_by('-created_on')[:40]
        )
        escalated_issues = (
            Issue.objects
            .filter(status='escalated', organisation=org)
            .select_related('room', 'assigned_to')
            .order_by('-updated_on')[:40]
        )

        # ── Role-specific ──────────────────────────────────────────────
        purchase_requests  = None   # central admin: pending purchase requests
        purchase_approvals = None   # sub-admin: recently approved purchases

        if is_central:
            purchase_requests = (
                Purchase.objects
                .filter(status='requested', room__organisation=org)
                .select_related('room', 'item', 'vendor')
                .order_by('-created_on')[:40]
            )
        else:
            purchase_approvals = (
                Purchase.objects
                .filter(status='approved', room__organisation=org)
                .select_related('room', 'item', 'vendor')
                .order_by('-created_on')[:40]
            )

        context = {
            'is_central':          is_central,
            'booking_requests':    booking_requests,
            'cancel_requests':     cancel_requests,
            'stock_requests':      stock_requests,
            'tat_requests':        tat_requests,
            'escalated_issues':    escalated_issues,
            'purchase_requests':   purchase_requests,
            'purchase_approvals':  purchase_approvals,
        }
        return render(request, self.template_name, context)