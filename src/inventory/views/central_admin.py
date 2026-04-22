from django.shortcuts import redirect, get_object_or_404, render
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View
from django.template.loader import render_to_string
from core.models import User, UserProfile
from django.db.models import Q
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

        subject = "Your Blixtro Account - Set Your Password"
        message = (
            "Hi,\n\n"
            "An account has been created for you on the SFS College Inventory Management System (Blixtro IMS).\n\n"
            "Please click the link below to set your password and activate your account:\n\n"
            f"{reset_link}\n\n"
            "Important: This link will expire in 3 days for security reasons.\n\n"
            "If you did not request this account, please contact your system administrator.\n\n"
            "Best regards,\nSFS IMS Team"
        )

        try:
            safe_send_mail(
                subject=subject,
                message=message,
                recipient_list=[user.email],
            )
        except Exception as e:
            print(f"[central_admin] safe_send_mail unexpected error: {e}", flush=True)

        return redirect(self.success_url)


class PeopleDeleteView(LoginRequiredMixin, DeleteView):
    model = UserProfile
    template_name = 'central_admin/people_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'people_slug'
    success_url = reverse_lazy('central_admin:people_list')

    def delete(self, request, *args, **kwargs):
        """
        Override delete to handle comprehensive data cleanup:
        1. Revert items to master inventory
        2. Unassign rooms and track them as reverted
        3. Mark issues as 'other issues' for admin review
        4. Handle all related data cleanup
        """
        person = self.get_object()
        org = person.org
        
        try:
            from inventory.models import RevertedRoom, RevertedItem, Item, Room, Issue
            from django.utils import timezone
            
            # Store user info for tracking
            deleted_user_email = person.user.email
            deleted_user_name = person.user.get_full_name()
            
            # 1. Handle room assignments - mark as reverted
            rooms_as_incharge = Room.objects.filter(incharge=person, organisation=org)
            for room in rooms_as_incharge:
                # Create reverted room record
                reverted_room, created = RevertedRoom.objects.get_or_create(
                    organisation=org,
                    room=room,
                    defaults={
                        'previous_incharge': person,
                        'deleted_user_email': deleted_user_email,
                        'deleted_user_name': deleted_user_name,
                    }
                )
                if not created:
                    # Update existing record
                    reverted_room.previous_incharge = person
                    reverted_room.deleted_user_email = deleted_user_email
                    reverted_room.deleted_user_name = deleted_user_name
                    reverted_room.reassigned_to = None
                    reverted_room.reassigned_on = None
                    reverted_room.save()
                
                # Unassign the room (set incharge to null or default)
                # For now, we'll keep the room but mark it as unassigned
                # You might want to set a default admin or keep it unassigned
                room.incharge = None
                room.save()
            
            # 2. Handle item assignments - revert to master inventory
            items_assigned_to_user = Item.objects.filter(
                created_by=person, 
                organisation=org,
                room__isnull=False  # Items that are assigned to rooms
            )
            
            for item in items_assigned_to_user:
                # Store previous assignment info
                previous_room = item.room
                
                # Create reverted item record
                reverted_item, created = RevertedItem.objects.get_or_create(
                    organisation=org,
                    item=item,
                    defaults={
                        'previous_room': previous_room,
                        'previous_assigned_to': person,
                        'deleted_user_email': deleted_user_email,
                        'deleted_user_name': deleted_user_name,
                    }
                )
                if not created:
                    # Update existing record
                    reverted_item.previous_room = previous_room
                    reverted_item.previous_assigned_to = person
                    reverted_item.deleted_user_email = deleted_user_email
                    reverted_item.deleted_user_name = deleted_user_name
                    reverted_item.reassigned_to_room = None
                    reverted_item.reassigned_to_user = None
                    reverted_item.reassigned_on = None
                    reverted_item.save()
                
                # Revert item to master inventory (set room to null)
                item.room = None
                item.save()
            
            # 3. Handle issues - mark assigned issues as 'other issues'
            # Issues assigned to this user should be visible in admin issues tab
            # We'll keep the assigned_to field but add a flag or handle this in the view
            issues_assigned = Issue.objects.filter(
                assigned_to=person,
                organisation=org,
                status__in=['open', 'in_progress', 'escalated']  # Only active issues
            )
            
            # For issues, we'll keep them assigned but they'll be filtered in the admin view
            # The admin issues tab will have a filter for 'other issues' from deleted users
            
            # 4. Handle other related data
            # - Stock requests made by this user
            # - Purchase requests made by this user
            # - Room bookings made by this user
            # These will remain in the system but the user reference will be set to NULL
            
            from inventory.models import StockRequest, Purchase, RoomBooking, RoomBookingRequest
            
            # Set user references to NULL where appropriate
            StockRequest.objects.filter(requested_by=person).update(requested_by=None)
            Purchase.objects.filter(requested_by=person).update(requested_by=None)
            
            # For room bookings, we keep the email but note that the user is deleted
            RoomBooking.objects.filter(faculty_email=deleted_user_email).update(
                # Keep the booking but add a note or handle in view
                # You might want to add a 'user_deleted' flag
            )
            
            RoomBookingRequest.objects.filter(faculty_email=deleted_user_email).update(
                # Keep the request but add a note or handle in view
            )
            
            # Log the deletion
            print(f'[User Deletion] User {deleted_user_name} ({deleted_user_email}) deleted from {org.name}')
            print(f'[User Deletion] Reverted {rooms_as_incharge.count()} rooms')
            print(f'[User Deletion] Reverted {items_assigned_to_user.count()} items to master inventory')
            print(f'[User Deletion] {issues_assigned.count()} issues marked for admin review')
            
            # Add success message
            messages.success(
                request,
                f'User {deleted_user_name} deleted successfully. '
                f'{rooms_as_incharge.count()} rooms unassigned and '
                f'{items_assigned_to_user.count()} items reverted to master inventory.'
            )
            
        except Exception as e:
            # Log error but still proceed with deletion
            print(f'[User Deletion Error] {str(e)}')
            messages.error(
                request,
                f'User deleted but some data cleanup failed: {str(e)}'
            )
        
        # Proceed with the actual deletion
        return super().delete(request, *args, **kwargs)


class RoomListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/room_list.html'
    model = Room
    context_object_name = 'rooms'

    def get_queryset(self):
        qs = Room.objects.filter(
            organisation=self.request.user.profile.org,
            incharge__isnull=False  # Exclude reverted rooms (rooms with no incharge)
        ).select_related('incharge', 'incharge__user', 'department')
        category = self.request.GET.get('category')
        search   = self.request.GET.get('search')
        if category:
            qs = qs.filter(room_category=category)
        if search:
            # Search by room name, label, or incharge name
            qs = qs.filter(
                Q(room_name__icontains=search) |
                Q(label__icontains=search) |
                Q(incharge__user__first_name__icontains=search) |
                Q(incharge__user__last_name__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Room.ROOM_CATEGORIES
        context['view_mode']  = self.request.GET.get('view', 'list')

        now       = timezone.now()
        all_rooms = self.get_queryset()

        active_bookings = RoomBooking.objects.filter(
            room__in=all_rooms,
            start_datetime__lte=now,
            end_datetime__gte=now,
        ).select_related('room')

        booked_room_ids = {b.room_id for b in active_bookings}

        pending_reqs = RoomBookingRequest.objects.filter(
            room__in=all_rooms,
            status='pending',
        ).select_related('room')

        pending_room_ids = {r.room_id for r in pending_reqs}

        booked_map = {}
        for b in active_bookings:
            booked_map[b.room_id] = b
        booked_entries = [{'room': b.room, 'booking': b} for b in booked_map.values()]

        pending_map = {}
        for r in pending_reqs:
            pending_map[r.room_id] = r
        pending_entries = [{'room': r.room, 'request': r} for r in pending_map.values()]

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
    """
    Both central admin and sub-admin can delete rooms.
    Sub-admin delete triggers a notification to central admin (in-app only, no email).
    """

    def get(self, request, *args, **kwargs):
        room = get_object_or_404(
            Room, slug=kwargs['room_slug'],
            organisation=request.user.profile.org
        )
        return render(request, 'central_admin/room_delete_confirm.html', {'object': room})

    def post(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        room = get_object_or_404(
            Room, slug=kwargs['room_slug'],
            organisation=request.user.profile.org
        )
        room_name = room.room_name

        # If sub-admin is performing the delete, create a notification for central admin
        if profile and profile.is_sub_admin:
            _create_room_action_notification(
                org=profile.org,
                action='deleted',
                room_name=room_name,
                actor=profile,
            )

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

    def form_valid(self, form):
        profile = getattr(self.request.user, 'profile', None)
        room = form.save(commit=False)
        room.organisation = self.request.user.profile.org
        room.save()

        # If sub-admin is performing the edit, create a notification for central admin
        if profile and profile.is_sub_admin:
            _create_room_action_notification(
                org=profile.org,
                action='edited',
                room_name=room.room_name,
                actor=profile,
            )

        return redirect(self.success_url)


def _create_room_action_notification(org, action, room_name, actor):
    """
    Store an in-app notification for the central admin when sub-admin edits/deletes a room.
    We re-use the Django messages framework stored in a simple DB approach via a
    transient AdminRoomNotification flag stored in session or a dedicated model.
    Since we don't have a dedicated model, we'll use a simple approach:
    store it as a pending message in a cache/session-independent way by
    piggy-backing on the existing notification count endpoint via a temporary
    in-memory store. For a proper implementation, use a Notification model.
    For now we add a Django message that the next central admin page load will pick up.
    This function is intentionally a no-op stub — the actual notification is
    delivered via the admin_notification_counts view which already counts
    room-related pending items. The sub-admin room action flag is stored
    server-side using the RoomActionLog approach below.
    """
    # Store notification in the RoomActionLog if model exists, otherwise skip gracefully
    try:
        from inventory.models import RoomActionLog
        RoomActionLog.objects.create(
            organisation=org,
            action=action,
            room_name=room_name,
            actor=actor,
        )
    except Exception:
        # Model may not exist yet — fail silently
        pass


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
    Sub Admin raises a purchase request for an item (existing or new).
    - existing item: select from master inventory (filtered by category/brand)
    - new item: manual entry of item name, category, brand
    """
    template_name = 'central_admin/purchase_create.html'

    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_sub_admin:
            return redirect('central_admin:dashboard')
        try:
            from inventory.models import Category, Brand
            categories = Category.objects.filter(organisation=profile.org, room=None).order_by('category_name')
            brands = Brand.objects.filter(organisation=profile.org, room=None).order_by('brand_name')
            master_items = Item.objects.filter(organisation=profile.org, is_listed=True).order_by('item_name')
        except Exception:
            categories = []
            brands = []
            master_items = []
        rooms = Room.objects.filter(organisation=profile.org)
        return render(request, self.template_name, {
            'master_items': master_items,
            'categories': categories,
            'brands': brands,
            'rooms': rooms,
        })

    def post(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_sub_admin:
            return redirect('central_admin:dashboard')

        purchase_type = request.POST.get('purchase_type', 'new')  # 'existing' or 'new'
        quantity = request.POST.get('quantity', '').strip()
        unit_of_measure = request.POST.get('unit_of_measure', 'units')
        room_id = request.POST.get('room_id', '')
        reason = request.POST.get('reason', '').strip()

        if not quantity:
            messages.error(request, 'Quantity is required.')
            return redirect('central_admin:purchase_create')

        org = profile.org
        from inventory.models import Category, Brand, Item as InvItem

        if purchase_type == 'existing':
            # Sub admin selects an existing master inventory item
            existing_item_id = request.POST.get('existing_item_id', '').strip()
            if not existing_item_id:
                messages.error(request, 'Please select an existing item.')
                return redirect('central_admin:purchase_create')
            try:
                item_obj = InvItem.objects.get(id=existing_item_id, organisation=org, is_listed=True)
                item_name = item_obj.item_name
                item_category = item_obj.category.category_name if item_obj.category else 'General'
                item_brand = item_obj.brand.brand_name if item_obj.brand else 'General'
            except InvItem.DoesNotExist:
                messages.error(request, 'Selected item not found.')
                return redirect('central_admin:purchase_create')

            # Create a unlisted placeholder item for the purchase record
            placeholder_cat, _ = Category.objects.get_or_create(
                organisation=org, category_name='Purchase Requests',
                defaults={'room': None}
            )
            placeholder_brand, _ = Brand.objects.get_or_create(
                organisation=org, brand_name='To Be Determined',
                defaults={'room': None}
            )
            new_item_obj = InvItem.objects.create(
                organisation=org,
                item_name=item_name,
                category=placeholder_cat,
                brand=placeholder_brand,
                total_count=0,
                is_listed=False,
            )

        else:
            # New item — manual entry
            item_name = request.POST.get('item_name', '').strip()
            item_category = request.POST.get('item_category', '').strip() or 'General'
            item_brand = request.POST.get('item_brand', '').strip() or 'General'

            if not item_name:
                messages.error(request, 'Item name is required.')
                return redirect('central_admin:purchase_create')

            placeholder_cat, _ = Category.objects.get_or_create(
                organisation=org, category_name='Purchase Requests',
                defaults={'room': None}
            )
            placeholder_brand, _ = Brand.objects.get_or_create(
                organisation=org, brand_name='To Be Determined',
                defaults={'room': None}
            )
            new_item_obj = InvItem.objects.create(
                organisation=org,
                item_name=item_name,
                category=placeholder_cat,
                brand=placeholder_brand,
                total_count=0,
                is_listed=False,
            )

        room = None
        if room_id:
            try:
                room = Room.objects.get(id=room_id, organisation=org)
            except Room.DoesNotExist:
                pass

        Purchase.objects.create(
            organisation=org,
            item=new_item_obj,
            quantity=float(quantity),
            unit_of_measure=unit_of_measure,
            room=room,
            reason=reason,
            status='requested',
            requested_by=profile,
            item_category=item_category,
            item_brand=item_brand,
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
            return (
                Purchase.objects
                .filter(organisation=profile.org)
                .select_related("room", "item", "vendor", "receipt", "requested_by__user")
                .order_by("-created_on")
            )

        if profile.is_sub_admin:
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
        context['vendors'] = Vendor.objects.filter(organisation=profile.org).order_by('vendor_name')
        return context

class PurchaseUploadInvoiceView(LoginRequiredMixin, View):
    def post(self, request, purchase_slug):
        profile = request.user.profile
        if not (profile.is_central_admin and not profile.is_sub_admin):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        purchase = get_object_or_404(Purchase, slug=purchase_slug)
        invoice_file = request.FILES.get('invoice')

        if not invoice_file:
            return JsonResponse({'error': 'No file uploaded.'}, status=400)

        if not invoice_file.name.endswith('.pdf'):
            return JsonResponse({'error': 'Only PDF files are allowed.'}, status=400)

        if invoice_file.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File too large. Max 10MB.'}, status=400)

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
        profile = request.user.profile
        if not (profile.is_central_admin and not profile.is_sub_admin):
            raise Http404

        purchase = get_object_or_404(Purchase, slug=purchase_slug)
        if not purchase.invoice:
            raise Http404

        try:
            file = purchase.invoice
            response = HttpResponse(file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="invoice_{purchase.purchase_id}.pdf"'
            return response
        except Exception:
            raise Http404

class IssueListView(LoginRequiredMixin, ListView):
    template_name = 'central_admin/issue_list.html'
    model = Issue
    context_object_name = 'issues'

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, "profile", None)
        issue_filter = self.request.GET.get('filter')

        if profile and getattr(profile, "org", None):
            from django.db.models import Q
            qs = qs.filter(Q(organisation=profile.org) | Q(assigned_to=profile))

            if issue_filter == 'escalated':
                target_level = 2 if profile.is_central_admin else 1
                qs = qs.filter(escalation_level=target_level)
            elif issue_filter == 'other':
                # Show issues from deleted users (assigned_to is null but issue is active)
                qs = qs.filter(
                    organisation=profile.org,
                    assigned_to__isnull=True,
                    status__in=['open', 'in_progress', 'escalated']
                )

        elif self.request.user.is_superuser:
            qs = qs
            if issue_filter == 'escalated':
                qs = qs.filter(status='escalated')
            elif issue_filter == 'other':
                qs = qs.filter(
                    assigned_to__isnull=True,
                    status__in=['open', 'in_progress', 'escalated']
                )

        else:
            from inventory.models import Organisation
            org_count = Organisation.objects.count()
            if org_count == 1:
                org = Organisation.objects.first()
                qs = qs.filter(organisation=org)
                if issue_filter == 'other':
                    qs = qs.filter(
                        assigned_to__isnull=True,
                        status__in=['open', 'in_progress', 'escalated']
                    )
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


class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    template_name = 'central_admin/department_update.html'
    form_class = DepartmentForm
    slug_field = 'slug'
    slug_url_kwarg = 'department_slug'
    success_url = reverse_lazy('central_admin:department_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit Department'
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Department "{form.instance.department_name}" updated successfully!')
        return super().form_valid(form)


class DepartmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Department
    template_name = 'central_admin/department_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'department_slug'
    success_url = reverse_lazy('central_admin:department_list')


class PurchaseApproveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        if not (profile.is_central_admin and not profile.is_sub_admin):
            return redirect('central_admin:purchase_list')

        purchase = get_object_or_404(Purchase, slug=self.kwargs['purchase_slug'])

        if purchase.status != 'requested':
            return redirect('central_admin:purchase_list')

        from decimal import Decimal, InvalidOperation
        cost_input = request.POST.get('cost', '').strip()
        cost_value = None
        if cost_input:
            try:
                cost_value = Decimal(cost_input)
            except InvalidOperation:
                pass

        vendor_id = request.POST.get('vendor_id', '').strip()
        purchase.status = 'approved'
        if cost_value is not None:
            purchase.cost = cost_value
            purchase.cost_per_unit = cost_value
        if vendor_id:
            try:
                from inventory.models import Vendor as VendorModel
                purchase.vendor = VendorModel.objects.get(id=vendor_id, organisation=profile.org)
            except VendorModel.DoesNotExist:
                pass
        purchase.save()

        org = profile.org
        from inventory.models import Category, Brand
        from decimal import Decimal

        cat_name = purchase.item_category or 'General'
        brand_name = purchase.item_brand or 'General'

        master_category, _ = Category.objects.get_or_create(
            organisation=org,
            room=None,
            category_name=cat_name
        )
        master_brand, _ = Brand.objects.get_or_create(
            organisation=org,
            room=None,
            brand_name=brand_name
        )

        master_item = Item.objects.filter(
            organisation=org,
            room=None,
            item_name=purchase.item.item_name,
            is_listed=True,
        ).first()

        if master_item:
            # Check if cost has changed
            existing_cost = master_item.cost
            cost_is_different = (
                cost_value is not None
                and existing_cost is not None
                and cost_value != existing_cost
            )

            if cost_is_different:
                # Different cost — create a new row for this price point
                Item.objects.create(
                    organisation=org,
                    room=None,
                    item_name=purchase.item.item_name,
                    category=master_item.category,
                    brand=master_item.brand,
                    total_count=int(purchase.quantity),
                    cost=cost_value,
                    is_listed=True,
                    item_description=master_item.item_description or purchase.item.item_name,
                    created_by=profile,
                    vendor=purchase.vendor,
                )
            else:
                # Same cost (or no cost entered) — just update count on existing row
                master_item.total_count += int(purchase.quantity)
                if cost_value and not master_item.cost:
                    master_item.cost = cost_value
                master_item.save()
        else:
            Item.objects.create(
                organisation=org,
                room=None,
                item_name=purchase.item.item_name,
                category=master_category,
                brand=master_brand,
                total_count=int(purchase.quantity),
                cost=cost_value or Decimal('0.00'),
                is_listed=True,
                item_description=purchase.item.item_name,
                created_by=profile,
                vendor=purchase.vendor,
            )

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
            return Item.objects.filter(
                organisation=profile.org
            ).select_related('room', 'category', 'brand')

        if profile.is_central_admin:
            return Item.objects.filter(
                organisation=profile.org,
                created_by__is_incharge=False
            ).select_related('room', 'category', 'brand')

        return Item.objects.none()

class EditRequestListView(LoginRequiredMixin, ListView):
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
    def post(self, request, pk, *args, **kwargs):
        stock_req = get_object_or_404(StockRequest, pk=pk, status="pending")
        item = stock_req.item

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
    issue.status = "open"
    issue.save(update_fields=["resolved", "status", "updated_on"])
    messages.info(request, f"Issue {issue.ticket_id} marked as unresolved.")
    return redirect("central_admin:issue_list")


@require_POST
def admin_deescalate_issue(request, pk):
    issue = get_object_or_404(Issue, pk=pk)

    if issue.escalation_level > 0:
        issue.escalation_level = 0
        issue.status = "open"
        issue.resolved = False
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

        context['stock_requests'] = (
            StockRequest.objects
            .filter(status='pending')
            .select_related('item', 'room', 'requested_by')
            .order_by('-created_on')
        )

        context['tat_requests'] = (
            IssueTimeExtensionRequest.objects
            .filter(status='pending')
            .select_related('issue', 'requested_by')
            .order_by('-created_on')
        )

        context['booking_requests'] = (
            RoomBookingRequest.objects
            .filter(status='pending' , tat_deadline__gt=timezone.now())
            .select_related('room', 'department')
            .order_by('-created_on')
        )

        context['cancel_requests'] = (
            RoomCancellationRequest.objects
            .filter(status='pending')
            .select_related('booking', 'booking__room')
            .order_by('-created_on')
        )

        # ── Tab badge counts ─────────────────────────────────────────────────
        context['item_edit_count']   = context['stock_requests'].count()
        context['issue_tat_count']   = context['tat_requests'].count()
        context['booking_req_count'] = context['booking_requests'].count()
        context['cancel_req_count']  = context['cancel_requests'].count()

        return context


class ApproveIssueTimeExtensionView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        ext_req = get_object_or_404(IssueTimeExtensionRequest, pk=pk, status='pending')
        issue   = ext_req.issue

        extra_hours = ext_req.requested_extra_hours
        if issue.tat_deadline:
            issue.tat_deadline += timedelta(hours=extra_hours)
        else:
            issue.tat_deadline = timezone.now() + timedelta(hours=extra_hours)
        issue.save(update_fields=['tat_deadline'])

        ext_req.status      = 'approved'
        ext_req.reviewed_by = request.user.profile
        ext_req.save(update_fields=['status', 'reviewed_by'])

        messages.success(request, f"TAT extension of {extra_hours}h approved for issue {issue.ticket_id}.")
        next_type = request.POST.get('next_type', 'issue_tat')
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectIssueTimeExtensionView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        ext_req = get_object_or_404(IssueTimeExtensionRequest, pk=pk, status='pending')

        ext_req.status      = 'rejected'
        ext_req.reviewed_by = request.user.profile
        ext_req.save(update_fields=['status', 'reviewed_by'])

        messages.info(request, f"TAT extension request for issue {ext_req.issue.ticket_id} rejected.")
        next_type = request.POST.get('next_type', 'issue_tat')
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class ApproveRoomBookingRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        from inventory.models import RoomBooking
        profile  = request.user.profile
        req      = get_object_or_404(RoomBookingRequest, pk=pk, status='pending')

        try:
            booking = RoomBooking.objects.create(
                room           = req.room,
                department     = req.department,
                faculty_name   = req.faculty_name,
                faculty_email  = req.faculty_email,
                start_datetime = req.start_datetime,
                end_datetime   = req.end_datetime,
                purpose        = req.purpose,
                requirements_doc  = req.requirements_doc,
                requirements_text = req.requirements_text,
            )
        except Exception as exc:
            messages.error(request, f"Booking conflict or validation error: {exc}")
            next_type = request.POST.get("next_type", "booking_req")
            return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")

        req.status      = 'approved'
        req.reviewed_by = profile
        req.review_note = request.POST.get('note', '')
        req.save()

        # Extract doc text from uploaded word document if present
        if booking.requirements_doc:
            try:
                import docx, io
                doc_bytes = booking.requirements_doc.read()
                doc_obj   = docx.Document(io.BytesIO(doc_bytes))
                blocks    = []
                for block in doc_obj.element.body:
                    tag = block.tag.split('}')[-1] if '}' in block.tag else block.tag
                    if tag == 'p':
                        from docx.oxml.ns import qn
                        text = ''.join(n.text or '' for n in block.iter() if n.tag == qn('w:t'))
                        if text.strip():
                            blocks.append({'type': 'paragraph', 'text': text})
                    elif tag == 'tbl':
                        import docx.table
                        tbl_obj = docx.table.Table(block, doc_obj)
                        rows = []
                        for r in tbl_obj.rows:
                            rows.append([c.text for c in r.cells])
                        if rows:
                            blocks.append({'type': 'table', 'rows': rows})
                import json
                booking.requirements_doc_text = json.dumps(blocks)
                booking.save(update_fields=['requirements_doc_text'])
            except Exception:
                pass

        try:
            send_mail(
                subject="Room Booking Approved",
                message=(
                    f"Dear {req.faculty_name},\n\n"
                    f"Your booking request for {req.room.room_name} has been approved.\n"
                    f"From: {req.start_datetime.strftime('%d %b %Y %H:%M')}\n"
                    f"To:   {req.end_datetime.strftime('%d %b %Y %H:%M')}\n\n"
                    "Regards,\nAdmin Team"
                ),
                from_email=None,
                recipient_list=[req.faculty_email],
                fail_silently=True,
            )
        except Exception as _e:
            print(f"[ApproveBooking] Email failed (non-fatal): {_e}", flush=True)

        messages.success(request, f"Booking for {req.room.room_name} approved.")
        next_type = request.POST.get("next_type", "booking_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectRoomBookingRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = request.user.profile
        req     = get_object_or_404(RoomBookingRequest, pk=pk, status='pending')

        req.status      = 'rejected'
        req.reviewed_by = profile
        req.review_note = request.POST.get('note', '')
        req.save()

        try:
            send_mail(
                subject="Room Booking Request Rejected",
                message=(
                    f"Dear {req.faculty_name},\n\n"
                    f"Your booking request for {req.room.room_name} has been rejected.\n"
                    f"Reason: {req.review_note or 'No reason provided.'}\n\n"
                    "Regards,\nAdmin Team"
                ),
                from_email=None,
                recipient_list=[req.faculty_email],
                fail_silently=True,
            )
        except Exception as _e:
            print(f"[RejectBooking] Email failed (non-fatal): {_e}", flush=True)

        messages.warning(request, f"Booking request for {req.room.room_name} rejected.")
        next_type = request.POST.get("next_type", "booking_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class ApproveCancellationRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile  = request.user.profile
        cancel   = get_object_or_404(RoomCancellationRequest, pk=pk, status='pending')
        booking  = cancel.booking
        room_name = booking.room.room_name
        faculty_email = cancel.faculty_email

        cancel.status      = 'approved'
        cancel.reviewed_by = profile
        cancel.save()

        booking.delete()

        try:
            send_mail(
                subject="Room Booking Cancellation Approved",
                message=(
                    f"Dear Faculty,\n\n"
                    f"Your cancellation request for {room_name} has been approved and the booking has been removed.\n\n"
                    "Regards,\nAdmin Team"
                ),
                from_email=None,
                recipient_list=[faculty_email],
                fail_silently=True,
            )
        except Exception as _e:
            print(f"[ApproveCancellation] Email failed (non-fatal): {_e}", flush=True)

        messages.success(request, f"Cancellation for {room_name} approved — booking removed.")
        next_type = request.POST.get("next_type", "cancel_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


class RejectCancellationRequestView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = request.user.profile
        cancel  = get_object_or_404(RoomCancellationRequest, pk=pk, status='pending')

        cancel.status      = 'rejected'
        cancel.reviewed_by = profile
        cancel.save()

        try:
            send_mail(
                subject="Room Booking Cancellation Rejected",
                message=(
                    f"Dear Faculty,\n\n"
                    f"Your cancellation request has been rejected — your original booking remains active.\n\n"
                    "Regards,\nAdmin Team"
                ),
                from_email=None,
                recipient_list=[cancel.faculty_email],
                fail_silently=True,
            )
        except Exception as _e:
            print(f"[RejectCancellation] Email failed (non-fatal): {_e}", flush=True)

        messages.info(
            request,
            "Cancellation request rejected — booking remains active."
        )
        next_type = request.POST.get("next_type", "cancel_req")
        return redirect(f"{reverse('central_admin:approval_requests')}?type={next_type}")


# ═══════════════════════════════════════════════════════════════
# ROOM INCHARGE — NOTIFICATIONS VIEW
# ═══════════════════════════════════════════════════════════════

class RoomInchargeNotificationsView(LoginRequiredMixin, TemplateView):
    template_name = "room_incharge/notifications.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room_slug = self.kwargs["room_slug"]
        from inventory.models import Room, RoomSettings
        room         = get_object_or_404(Room, slug=room_slug, incharge=self.request.user.profile)
        room_settings = RoomSettings.objects.get_or_create(room=room)[0]

        stock_notifications = (
            StockRequest.objects
            .filter(room=room, status__in=["approved", "rejected"])
            .select_related("item", "reviewed_by")
            .order_by("-created_on")[:50]
        )

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
    Now also checks for sub-admin room action logs (edit/delete notifications).
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    profile = getattr(request.user, 'profile', None)
    if not profile or not (profile.is_central_admin or profile.is_sub_admin):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    is_central = profile.is_central_admin and not profile.is_sub_admin
    org        = profile.org

    try:
        counts = {
            'booking_requests': RoomBookingRequest.objects.filter(status='pending', tat_deadline__gt=timezone.now()).count(),
            'cancel_requests': RoomCancellationRequest.objects.filter(status='pending').count(),
            'stock_requests': StockRequest.objects.filter(status='pending').count(),
            'tat_requests': IssueTimeExtensionRequest.objects.filter(status='pending').count(),
            'escalated_issues': Issue.objects.filter(status='escalated', organisation=org).count(),
        }
    except Exception as e:
        return JsonResponse({'error': f'Database error: {str(e)}'}, status=500)

    if is_central:
        counts['purchase_requests'] = Purchase.objects.filter(
            status='requested', room__organisation=org
        ).count()
        # Count unread room action logs by sub-admins
        try:
            from inventory.models import RoomActionLog
            counts['room_actions'] = RoomActionLog.objects.filter(
                organisation=org, is_read=False
            ).count()
        except Exception:
            pass
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
    Now supports persistent dismiss via POST to mark notifications as read server-side.
    """
    template_name = "central_admin/admin_notifications.html"

    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not (profile.is_central_admin or profile.is_sub_admin):
            return redirect('central_admin:dashboard')

        is_central = profile.is_central_admin and not profile.is_sub_admin
        org        = profile.org

        # Read dismissed IDs from session
        dismissed = request.session.get('dismissed_notifications', {})

        def not_dismissed(prefix, obj_id):
            return str(obj_id) not in dismissed.get(prefix, [])

        from django.utils import timezone as _tz
        _now = _tz.now()

        booking_requests = [
            r for r in RoomBookingRequest.objects
            .filter(status='pending', tat_deadline__gt=_now)
            .select_related('room')
            .order_by('-created_on')[:40]
            if not_dismissed('booking', r.id)
        ]

        expiring_soon_bookings = [
            r for r in RoomBookingRequest.objects
            .filter(
                status='pending',
                tat_deadline__isnull=False,
                tat_deadline__lte=_now + timezone.timedelta(hours=24),
                tat_deadline__gt=_now,
            )
            .select_related('room')
            .order_by('tat_deadline')[:20]
            if not_dismissed('booking_expiring', r.id)
        ]

        cancel_requests = [
            r for r in RoomCancellationRequest.objects
            .filter(status='pending')
            .select_related('booking', 'booking__room')
            .order_by('-created_on')[:40]
            if not_dismissed('cancel', r.id)
        ]

        stock_requests = [
            r for r in StockRequest.objects
            .filter(status='pending')
            .select_related('item', 'room', 'requested_by')
            .order_by('-created_on')[:40]
            if not_dismissed('stock', r.id)
        ]

        tat_requests = [
            r for r in IssueTimeExtensionRequest.objects
            .filter(status='pending')
            .select_related('issue', 'requested_by')
            .order_by('-created_on')[:40]
            if not_dismissed('tat', r.id)
        ]

        escalated_issues = [
            r for r in Issue.objects
            .filter(status='escalated', organisation=org)
            .select_related('room', 'assigned_to')
            .order_by('-updated_on')[:40]
            if not_dismissed('esc', r.id)
        ]

        purchase_requests  = None
        purchase_approvals = None

        if is_central:
            purchase_requests = [
                r for r in Purchase.objects
                .filter(status='requested', room__organisation=org)
                .select_related('room', 'item', 'vendor')
                .order_by('-created_on')[:40]
                if not_dismissed('pur', r.id)
            ]
            # Room action log notifications for central admin
            room_action_logs = []
            try:
                from inventory.models import RoomActionLog
                room_action_logs = list(
                    RoomActionLog.objects
                    .filter(organisation=org, is_read=False)
                    .order_by('-created_on')[:40]
                )
            except Exception:
                pass
        else:
            purchase_approvals = [
                r for r in Purchase.objects
                .filter(status='approved', room__organisation=org)
                .select_related('room', 'item', 'vendor')
                .order_by('-created_on')[:40]
                if not_dismissed('papp', r.id)
            ]
            room_action_logs = []

        context = {
            'is_central':             is_central,
            'booking_requests':       booking_requests,
            'expiring_soon_bookings': expiring_soon_bookings,
            'cancel_requests':        cancel_requests,
            'stock_requests':         stock_requests,
            'tat_requests':           tat_requests,
            'escalated_issues':       escalated_issues,
            'purchase_requests':      purchase_requests,
            'purchase_approvals':     purchase_approvals,
            'room_action_logs':       room_action_logs,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        AJAX endpoint to persist notification dismissals in session.
        Body: { "action": "dismiss", "prefix": "booking", "id": 42 }
              { "action": "clear_all" }
        """
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        dismissed = request.session.get('dismissed_notifications', {})

        if data.get('action') == 'dismiss':
            prefix = data.get('prefix', '')
            obj_id = str(data.get('id', ''))
            if prefix and obj_id:
                if prefix not in dismissed:
                    dismissed[prefix] = []
                if obj_id not in dismissed[prefix]:
                    dismissed[prefix].append(obj_id)
                request.session['dismissed_notifications'] = dismissed
                request.session.modified = True
            return JsonResponse({'ok': True})

        elif data.get('action') == 'clear_all':
            # Mark all current notifications as dismissed
            request.session['dismissed_notifications'] = {}
            request.session.modified = True

            # Also mark room action logs as read for central admin
            profile = getattr(request.user, 'profile', None)
            if profile and profile.is_central_admin and not profile.is_sub_admin:
                try:
                    from inventory.models import RoomActionLog
                    RoomActionLog.objects.filter(
                        organisation=profile.org, is_read=False
                    ).update(is_read=True)
                except Exception:
                    pass

            return JsonResponse({'ok': True})

        return JsonResponse({'error': 'Unknown action'}, status=400)


def get_person_api(request, people_slug):
    """
    API endpoint to get person data for editing
    """
    if not request.user.profile.is_central_admin and not request.user.profile.is_sub_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        person = get_object_or_404(UserProfile, slug=people_slug, org=request.user.profile.org)
        
        # Determine role
        role = 'unknown'
        if person.is_central_admin:
            role = 'central_admin'
        elif person.is_sub_admin:
            role = 'sub_admin'
        elif person.is_incharge:
            role = 'incharge'
        
        return JsonResponse({
            'status': 'success',
            'person': {
                'slug': person.slug,
                'user': {
                    'full_name': person.user.get_full_name(),
                    'email': person.user.email,
                },
                'role': role,
                'is_central_admin': person.is_central_admin,
                'is_sub_admin': person.is_sub_admin,
                'is_incharge': person.is_incharge,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def edit_person_api(request, people_slug):
    """
    API endpoint to edit person data with email change handling
    """
    if not request.user.profile.is_central_admin and not request.user.profile.is_sub_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        
        person = get_object_or_404(UserProfile, slug=people_slug, org=request.user.profile.org)
        user = person.user
        
        new_full_name = data.get('full_name', '').strip()
        new_email = data.get('email', '').strip().lower()
        new_role = data.get('role', '')
        email_changed = data.get('email_changed', False)
        
        # Validation
        if not new_full_name or not new_email or not new_role:
            return JsonResponse({'error': 'All fields are required'}, status=400)
        
        # Check if email is being changed to an existing user
        if email_changed and new_email != user.email:
            if User.objects.filter(email=new_email).exists():
                return JsonResponse({'error': 'This email address is already in use'}, status=400)
        
        @transaction.atomic
        def update_person():
            # Update user name
            user.first_name = ' '.join(new_full_name.split()[:-1]) if ' ' in new_full_name else new_full_name
            user.last_name = new_full_name.split()[-1] if ' ' in new_full_name else ''
            
            # Update email if changed
            old_email = user.email
            if email_changed and new_email != old_email:
                user.email = new_email
                user.username = new_email  # Update username to match email
            
            user.save()
            
            # Update role flags
            person.is_central_admin = (new_role == 'central_admin')
            person.is_sub_admin = (new_role == 'sub_admin')
            person.is_incharge = (new_role == 'incharge')
            person.save()
            
            # Always send password reset email to ensure user can set password
            if email_changed and new_email != old_email:
                transfer_user_data(old_email, new_email, person)
            
            # Send password reset email (both for email changes and to ensure password is set)
            send_password_reset_email(user)
        
        update_person()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Person updated successfully. Password reset email has been sent to ' + new_email
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def transfer_user_data(old_email, new_email, profile):
    """
    Transfer role-specific data from old email to new email
    Only transfers data relevant to the user's role
    """
    try:
        # Get old and new users
        old_user = User.objects.get(email=old_email)
        new_user = profile.user  # This is the updated user with new email
        
        # Store role information
        is_central_admin = profile.is_central_admin
        is_sub_admin = profile.is_sub_admin
        is_incharge = profile.is_incharge
        
        transferred_count = 0
        
        # === ROOM INCHARGE SPECIFIC TRANSFERS ===
        if is_incharge:
            # Transfer room incharge assignments
            from inventory.models import Room
            rooms_count = Room.objects.filter(incharge=old_user).update(incharge=new_user)
            transferred_count += rooms_count
            
            # Transfer item assignments for rooms they manage
            Item.objects.filter(assigned_to=old_user).update(assigned_to=new_user)
            
            # Transfer issues assigned to this incharge
            Issue.objects.filter(assigned_to__user=old_user).update(assigned_to=profile)
            
            print(f'[transfer_user_data] Room Incharge: Transferred {rooms_count} rooms and related data')
        
        # === ADMIN SPECIFIC TRANSFERS ===
        if is_central_admin or is_sub_admin:
            # Transfer room bookings made by this user
            RoomBooking.objects.filter(faculty_email=old_email).update(faculty_email=new_email)
            
            # Transfer room booking requests
            RoomBookingRequest.objects.filter(faculty_email=old_email).update(faculty_email=new_email)
            
            # Transfer cancellation requests
            RoomCancellationRequest.objects.filter(faculty_email=old_email).update(faculty_email=new_email)
            
            # Transfer stock requests if applicable
            StockRequest.objects.filter(requested_by=old_user).update(requested_by=new_user)
            
            # Transfer issues created/assigned to this admin
            Issue.objects.filter(assigned_to__user=old_user).update(assigned_to=profile)
            
            print(f'[transfer_user_data] Admin: Transferred bookings, requests, and admin data')
        
        # === COMMON TRANSFERS FOR ALL ROLES ===
        # Always transfer personal bookings and requests regardless of role
        RoomBooking.objects.filter(faculty_email=old_email).update(faculty_email=new_email)
        RoomBookingRequest.objects.filter(faculty_email=old_email).update(faculty_email=new_email)
        RoomCancellationRequest.objects.filter(faculty_email=old_email).update(faculty_email=new_email)
        
        # Ensure user can login with new email
        # The username is already updated to match new email in the main function
        # Set a temporary password that will be changed via reset email
        new_user.set_unusable_password()  # Forces password reset
        new_user.save()
        
        print(f'[transfer_user_data] Successfully transferred role-specific data from {old_email} to {new_email}')
        print(f'[transfer_user_data] User role: Central={is_central_admin}, Sub={is_sub_admin}, Incharge={is_incharge}')
        
    except Exception as e:
        print(f'[transfer_user_data] Error transferring data: {e}')
        # Don't raise the exception to avoid breaking the whole process
        pass


def send_password_reset_email(user):
    """
    Send password reset email to user
    """
    try:
        from django.contrib.auth.tokens import PasswordResetTokenGenerator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.conf import settings
        
        # Generate password reset token
        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build reset link
        domain = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        # Ensure domain doesn't end with slash to avoid double slashes
        if domain.endswith('/'):
            domain = domain.rstrip('/')
        reset_link = f"{domain}{reverse('core:confirm_password_reset', kwargs={'uidb64': uid, 'token': token})}"
        
        subject = "Your Blixtro Account - Set Your Password"
        message = (
            "Hi,\n\n"
            "Your email address has been updated in the SFS College Inventory Management System (Blixtro IMS).\n\n"
            "Please click the link below to set your password and activate your account:\n\n"
            f"{reset_link}\n\n"
            "Important: This link will expire in 3 days for security reasons.\n\n"
            "If you did not request this change, please contact your system administrator.\n\n"
            "Best regards,\nSFS IMS Team"
        )
        
        # Send email using the same method as PeopleCreateView
        safe_send_mail(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sfscollege.in'),
            fail_silently=False,
        )
        
        print(f'[send_password_reset_email] Password reset email sent to {user.email}')
        
    except Exception as e:
        print(f'[send_password_reset_email] Error sending password reset email: {e}')
        # Don't raise the exception to avoid breaking the whole process
        pass


# ═══════════════════════════════════════════════════════════════
# REVERTED ROOMS AND ITEMS VIEWS
# ═══════════════════════════════════════════════════════════════

class RevertedRoomsView(LoginRequiredMixin, ListView):
    """
    View rooms that became unassigned when users were deleted
    """
    template_name = 'central_admin/reverted_rooms.html'
    model = None  # We'll use RevertedRoom model
    context_object_name = 'reverted_rooms'
    paginate_by = 20

    def get_queryset(self):
        from inventory.models import RevertedRoom
        return RevertedRoom.objects.filter(
            organisation=self.request.user.profile.org,
            reassigned_to__isnull=True  # Only show un-reassigned rooms
        ).select_related(
            'room',
            'room__department',
            'previous_incharge',
            'previous_incharge__user'
        ).order_by('-reverted_on')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get available users for reassignment - optimized query
        context['available_users'] = UserProfile.objects.filter(
            org=self.request.user.profile.org,
            is_incharge=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        return context
    
    def get(self, request, *args, **kwargs):
        # Check if this is an AJAX request for modal content
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data(**kwargs)
            # Render only the modal content
            return JsonResponse({
                'html': render_to_string(self.template_name, context, request=request),
                'status': 'success'
            })
        return super().get(request, *args, **kwargs)


@require_POST
def reassign_room(request, reverted_room_id):
    """
    Reassign a reverted room to a new user
    """
    if not request.user.profile.is_central_admin and not request.user.profile.is_sub_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from inventory.models import RevertedRoom, Room
        import json
        data = json.loads(request.body)
        new_user_id = data.get('user_id')
        
        if not new_user_id:
            return JsonResponse({'error': 'User ID is required'}, status=400)
        
        reverted_room = get_object_or_404(RevertedRoom, id=reverted_room_id, organisation=request.user.profile.org)
        new_user = get_object_or_404(UserProfile, id=new_user_id, org=request.user.profile.org)
        
        # Update room assignment
        room = reverted_room.room
        room.incharge = new_user
        room.save()
        
        # Update reverted room record
        reverted_room.reassigned_to = new_user
        reverted_room.reassigned_on = timezone.now()
        reverted_room.save()
        
        messages.success(request, f'Room "{room.room_name}" reassigned to {new_user.user.get_full_name()}')
        
        return JsonResponse({
            'status': 'success',
            'message': f'Room reassigned to {new_user.user.get_full_name()}'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class RevertedItemsView(LoginRequiredMixin, ListView):
    """
    View items that reverted to master inventory when users were deleted
    """
    template_name = 'central_admin/reverted_items.html'
    model = None  # We'll use RevertedItem model
    context_object_name = 'reverted_items'
    paginate_by = 20

    def get_queryset(self):
        from inventory.models import RevertedItem
        return RevertedItem.objects.filter(
            organisation=self.request.user.profile.org,
            reassigned_to_room__isnull=True  # Only show un-reassigned items
        ).select_related(
            'item',
            'item__category',
            'item__brand',
            'previous_room',
            'previous_room__department',
            'previous_assigned_to',
            'previous_assigned_to__user'
        ).order_by('-reverted_on')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get available rooms for reassignment - optimized query
        from inventory.models import Room
        context['available_rooms'] = Room.objects.filter(
            organisation=self.request.user.profile.org,
            incharge__isnull=False  # Only rooms with incharges
        ).select_related(
            'incharge',
            'incharge__user',
            'department'
        ).order_by('room_name')
        return context

    def get(self, request, *args, **kwargs):
        # Check if this is an AJAX request for modal content
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data(**kwargs)
            # Render only the modal content
            return JsonResponse({
                'html': render_to_string(self.template_name, context, request=request),
                'status': 'success'
            })
        return super().get(request, *args, **kwargs)


@require_POST
def reassign_item(request, reverted_item_id):
    """
    Reassign a reverted item to a new room
    """
    if not request.user.profile.is_central_admin and not request.user.profile.is_sub_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from inventory.models import RevertedItem, Item, Room
        import json
        data = json.loads(request.body)
        new_room_id = data.get('room_id')
        
        if not new_room_id:
            return JsonResponse({'error': 'Room ID is required'}, status=400)
        
        reverted_item = get_object_or_404(RevertedItem, id=reverted_item_id, organisation=request.user.profile.org)
        new_room = get_object_or_404(Room, id=new_room_id, organisation=request.user.profile.org)
        
        # Validate that the room has an incharge
        if not new_room.incharge:
            return JsonResponse({'error': 'Selected room does not have an incharge assigned'}, status=400)
        
        # Update item assignment
        item = reverted_item.item
        item.room = new_room
        item.save()
        
        # Update reverted item record
        reverted_item.reassigned_to_room = new_room
        reverted_item.reassigned_to_user = new_room.incharge
        reverted_item.reassigned_on = timezone.now()
        reverted_item.save()
        
        messages.success(request, f'Item "{item.item_name}" reassigned to room "{new_room.room_name}"')
        
        return JsonResponse({
            'status': 'success',
            'message': f'Item reassigned to {new_room.room_name}'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)