from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import TemplateView, CreateView
from django.db import transaction, connection
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, 
    PasswordResetCompleteView, PasswordResetConfirmView, 
    PasswordResetDoneView, PasswordResetView
    )
from django.contrib.auth import login, get_user_model
from django.urls import reverse_lazy
from . forms import CustomAuthenticationForm, UserRegisterForm, CustomPasswordResetForm
from core.models import UserProfile, Organisation
from config.mixins.access_mixins import RedirectLoggedInUsersMixin
from django.contrib import messages
from core.forms import RoomBookingForm, RoomBookingEditForm
from inventory.models import Room, RoomBooking, RoomBookingRequest, RoomCancellationRequest, RoomBookingCredentials, RoomBookingEditRequest
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from django.utils import timezone
import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
import os
from pathlib import Path
import pandas as pd
from datetime import date, timedelta
from inventory.booking_utils import format_booking_details as build_booking_details, format_room_list, sort_rooms_iterable
from inventory.email import build_email_shell

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _safe_mail(subject, message, recipient_list, fail_silently=True, html_message=None):
    """Wrapper around safe_send_mail — imported lazily to avoid circular imports."""
    try:
        from inventory.email import safe_send_mail
        safe_send_mail(
            subject=subject,
            message=message,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=fail_silently,
        )
    except Exception as _e:
        print(f"[_safe_mail] {_e}", flush=True)


def _admin_emails():
    """Return email addresses for all central & sub admins."""
    return list(
        UserProfile.objects.filter(
            Q(is_central_admin=True) | Q(is_sub_admin=True)
        ).values_list('user__email', flat=True)
    )


def _sub_admin_emails():
    """
    Return email addresses for sub-admins only.
    Falls back to central admins if no sub-admins exist.
    """
    emails = list(
        UserProfile.objects.filter(is_sub_admin=True)
        .values_list('user__email', flat=True)
    )
    if not emails:
        # Fallback: if no sub-admins are configured, notify central admins
        emails = list(
            UserProfile.objects.filter(is_central_admin=True, is_sub_admin=False)
            .values_list('user__email', flat=True)
        )
    return emails


def _central_admin_only_emails():
    """Return email addresses for central admins only (not sub-admins)."""
    return list(
        UserProfile.objects.filter(is_central_admin=True, is_sub_admin=False)
        .values_list('user__email', flat=True)
    )


def _format_booking_details(rooms_or_instance, faculty_name, start_dt, end_dt, purpose, department=None):
    """Utility: format a readable booking-detail block for email bodies."""
    return build_booking_details(rooms_or_instance, faculty_name, start_dt, end_dt, purpose, department)


def _booking_email_sections(rooms_or_instance, faculty_name, faculty_email, start_dt, end_dt, purpose, department=None):
    from django.utils import timezone as _tz

    sl = _tz.localtime(start_dt)
    el = _tz.localtime(end_dt)
    return [
        {
            "title": "Booking Details",
            "rows": [
                {"label": "Room(s)", "value": format_room_list(rooms_or_instance)},
                {"label": "Faculty", "value": faculty_name},
                {"label": "Email", "value": faculty_email},
                {"label": "Date", "value": sl.strftime('%A, %d %B %Y')},
                {"label": "Time", "value": f"{sl.strftime('%I:%M %p')} to {el.strftime('%I:%M %p')}"},
                {"label": "Purpose", "value": purpose or '—'},
                {"label": "Department", "value": str(department) if department else '—'},
            ],
        }
    ]


# ─────────────────────────────────────────────────────────────────────


class LandingPageView(RedirectLoggedInUsersMixin, TemplateView):
    template_name = 'landing_page.html'
    
    
class LoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'core/login.html'

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)

        profile = getattr(user, "profile", None)

        # CENTRAL ADMIN
        if profile and profile.is_central_admin:
            return redirect("central_admin:dashboard")

        # SUB ADMIN
        if profile and profile.is_sub_admin:
            return redirect("central_admin:dashboard")

        # ROOM INCHARGE
        if profile and profile.is_incharge:
            assigned_room = profile.rooms_incharge.first()
            if assigned_room:
                return redirect("room_incharge:room_dashboard", room_slug=assigned_room.slug)
            else:
                messages.error(self.request, "No room is assigned to your account.")
                return redirect("core:login")

        # DEFAULT
        return redirect("landing_page")

    

class UserRegisterView(CreateView):
    model = User
    form_class = UserRegisterForm
    template_name = 'core/register.html'
    success_url = reverse_lazy('core:login')

    def _central_admin_exists(self):
        """Return True if at least one central admin account already exists."""
        return UserProfile.objects.filter(is_central_admin=True).exists()

    def dispatch(self, request, *args, **kwargs):
        """
        If a central admin already exists, skip normal dispatch entirely
        and render the locked page immediately — for both GET and POST.
        """
        if self._central_admin_exists():
            return render(request, self.template_name, {'registration_locked': True})
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        # Double-check at commit time in case of a race condition
        if self._central_admin_exists():
            return render(self.request, self.template_name, {'registration_locked': True})

        user = form.save()

        org_name = form.cleaned_data.get('org_name')
        org = Organisation.objects.create(
            name=org_name,
        )

        # Create user profile
        first_name = form.cleaned_data.get('first_name')
        last_name = form.cleaned_data.get('last_name')
        UserProfile.objects.create(
            user=user,
            org=org,
            first_name=first_name,
            last_name=last_name,
            is_central_admin=True
        )

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('landing_page')
    

class LogoutView(LogoutView):
    template_name = 'core/logout.html'


class ChangePasswordView(PasswordChangeView):
    template_name = 'core/change_password.html'
    success_url = reverse_lazy('landing_page')


class ResetPasswordView(PasswordResetView):
    form_class = CustomPasswordResetForm
    email_template_name = 'core/password_reset/password_reset_email.html'
    html_email_template_name = 'core/password_reset/password_reset_email.html'
    subject_template_name = 'core/password_reset/password_reset_subject.txt'
    success_url = reverse_lazy('core:done_password_reset')
    template_name = 'core/password_reset/password_reset_form.html'


class DonePasswordResetView(PasswordResetDoneView):
    template_name = 'core/password_reset/password_reset_done.html'


class ConfirmPasswordResetView(PasswordResetConfirmView):
    success_url = reverse_lazy('core:complete_password_reset')
    template_name = 'core/password_reset/password_reset_confirm.html'


class CompletePasswordResetView(PasswordResetCompleteView):
    template_name = 'core/password_reset/password_reset_complete.html'
    


def _roombooking_has_datetime_columns():
    """
    Checks once per request whether the roombooking table
    actually has start_datetime and end_datetime columns.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'inventory_roombooking'
        """)
        columns = {row[0] for row in cursor.fetchall()}

    return {'start_datetime', 'end_datetime'}.issubset(columns)


def _is_booking_too_soon(dt):
    """
    Returns True if the booking date is today, tomorrow, or in the past.
    Minimum allowed booking date is today + 2 days (day after tomorrow).
    """
    from django.utils import timezone as _tz
    local_dt = _tz.localtime(dt) if _tz.is_aware(dt) else dt
    booking_date = local_dt.date()
    today = date.today()
    return booking_date <= today + timedelta(days=1)


def room_booking_view(request):
    # Run TAT expiry check on every booking page load
    try:
        process_booking_tat_reminders_and_expiry()
    except Exception as _e:
        print(f"[room_booking_view] TAT check failed: {_e}", flush=True)

    form = RoomBookingForm()

    if request.method == "POST":
        form = RoomBookingForm(request.POST, request.FILES)
        if form.is_valid():
            import uuid as _uuid
            import os as _os
            booking_req = form.save(commit=False)
            selected_rooms = form.cleaned_data.get('selected_rooms', [])
            booking_req.status = 'pending'
            booking_req.workflow_stage = 'sub_admin'

            # ── Same-day / next-day / previous-day block ────────────────────────
            if booking_req.start_datetime and _is_booking_too_soon(booking_req.start_datetime):
                messages.error(
                    request,
                    "Bookings cannot be made for today, tomorrow, or a previous date. "
                    "Please select a date at least 2 days in advance."
                )
                return render(request, "booking/room_booking.html", {"form": form})

            # ── Inline requirements text ─────────────────────────────────────
            req_type = request.POST.get('requirements_type', 'na')
            if req_type == 'text':
                booking_req.requirements_text = request.POST.get('requirements_text_input', '').strip() or None

            # Ensure each uploaded document gets a unique storage name
            if booking_req.requirements_doc:
                orig_name = _os.path.basename(booking_req.requirements_doc.name)
                name_root, ext = _os.path.splitext(orig_name)
                unique_name = f"{name_root}_{_uuid.uuid4().hex[:8]}{ext}"
                booking_req.requirements_doc.name = _os.path.join(
                    _os.path.dirname(booking_req.requirements_doc.name), unique_name
                )
            # Dynamic TAT: if event is within 48hrs, give only 12hrs for approval
            from django.utils import timezone as _tz
            now = _tz.now()
            hours_until_event = (booking_req.start_datetime - now).total_seconds() / 3600
            if hours_until_event <= 48:
                booking_req.tat_deadline = now + timezone.timedelta(hours=12)
            else:
                booking_req.tat_deadline = now + timezone.timedelta(hours=48)
            booking_req.save()
            if selected_rooms:
                booking_req.rooms.set(selected_rooms)

            # ── Notify faculty: request received ────────────────────────────
            details = _format_booking_details(
                selected_rooms or booking_req,
                booking_req.faculty_name,
                booking_req.start_datetime,
                booking_req.end_datetime,
                booking_req.purpose,
                booking_req.department,
            )
            booking_sections = _booking_email_sections(
                selected_rooms or booking_req,
                booking_req.faculty_name,
                booking_req.faculty_email,
                booking_req.start_datetime,
                booking_req.end_datetime,
                booking_req.purpose,
                booking_req.department,
            )
            _safe_mail(
                subject="[Blixtro] Room Booking Request Received",
                message=(
                    f"Dear {booking_req.faculty_name},\n\n"
                    "Your room booking request has been submitted successfully.\n"
                    f"{details}\n\n"
                    "Your request is currently under review by the sub-admin. "
                    "You will receive an email once it is recommended for final approval.\n\n"
                    "Best regards,\nBlixtro — SFS College Inventory & Booking System"
                ),
                recipient_list=[booking_req.faculty_email],
                html_message=build_email_shell(
                    title="Booking Request Received",
                    intro_html=(
                        f"Dear <strong>{booking_req.faculty_name}</strong>, your room booking request has been submitted "
                        "successfully and is currently awaiting sub-admin review."
                    ),
                    sections=booking_sections,
                    outro_html="You will receive another email as soon as the request is recommended, approved, or rejected.",
                ),
            )

            # ── Notify SUB-ADMINS ONLY: new booking request pending ──────────
            # (Central admins are notified only after sub-admin recommends)
            sub_admin_emails = _sub_admin_emails()
            if sub_admin_emails:
                _safe_mail(
                    subject=f"[Blixtro] New Room Booking Request — {format_room_list(selected_rooms or booking_req)}",
                    message=(
                        f"A new room booking request requires your review.\n"
                        f"{details}\n\n"
                        f"Please log in to the admin dashboard and either Recommend or Reject this request.\n\n"
                        f"Note: This request will be auto-cancelled if not acted upon within "
                        f"{'12' if hours_until_event <= 48 else '48'} hours "
                        f"(TAT deadline: {booking_req.tat_deadline.strftime('%d %b %Y, %H:%M')}).\n\n"
                        "Blixtro — SFS College Inventory & Booking System"
                    ),
                    recipient_list=sub_admin_emails,
                    html_message=build_email_shell(
                        title="Booking Review Required",
                        intro_html=(
                            "A faculty booking request is waiting in the Approval Hub. "
                            "Please review it and add your recommendation remark if you want to share guidance."
                        ),
                        sections=booking_sections + [
                            {
                                "title": "Workflow",
                                "rows": [
                                    {"label": "Current Stage", "value": "Sub-admin review"},
                                    {"label": "TAT Deadline", "value": booking_req.tat_deadline.strftime('%d %b %Y, %H:%M')},
                                ],
                            }
                        ],
                        outro_html="Open Blixtro IMS and recommend or reject the request from the Approval Hub.",
                    ),
                )

            return render(request, "booking/booking_success.html", {
                "booking": booking_req,
                "pending": True,
            })
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "booking/room_booking.html", {"form": form})


def edit_booking_view(request, booking_id):
    """
    Handle edit booking requests for confirmed bookings.
    Shows a pre-filled form with original booking data and allows faculty to make changes.
    """
    # Get the original booking
    try:
        original_booking = RoomBooking.objects.get(id=booking_id)
    except RoomBooking.DoesNotExist:
        messages.error(request, "Booking not found.")
        return redirect('room_booking')
    
    # Check if booking is in the future (can only edit upcoming bookings)
    if original_booking.start_datetime <= timezone.now():
        messages.error(request, "Cannot edit bookings that have already started or passed.")
        return redirect('room_booking')
    
    form = RoomBookingEditForm(original_booking=original_booking)
    
    if request.method == "POST":
        form = RoomBookingEditForm(request.POST, request.FILES, original_booking=original_booking)
        if form.is_valid():
            import uuid as _uuid
            import os as _os
            
            # Create edit request
            edit_req = RoomBookingEditRequest()
            edit_req.original_booking = original_booking
            edit_req.faculty_email = original_booking.faculty_email
            
            # Store original values
            edit_req.original_start_datetime = original_booking.start_datetime
            edit_req.original_end_datetime = original_booking.end_datetime
            edit_req.original_purpose = original_booking.purpose
            edit_req.original_department = original_booking.department
            
            # Store new values from form
            edit_req.new_start_datetime = form.cleaned_data['start_datetime']
            edit_req.new_end_datetime = form.cleaned_data['end_datetime']
            edit_req.new_purpose = form.cleaned_data['purpose']
            edit_req.new_department = form.cleaned_data['department']
            
            # Handle requirements
            req_type = request.POST.get('requirements_type', 'na')
            if req_type == 'text':
                edit_req.new_requirements_text = form.cleaned_data.get('requirements_text_input', '').strip() or None
            elif req_type == 'doc' and form.cleaned_data.get('requirements_doc_upload'):
                requirements_doc = form.cleaned_data['requirements_doc_upload']
                # Ensure unique filename
                orig_name = _os.path.basename(requirements_doc.name)
                name_root, ext = _os.path.splitext(orig_name)
                unique_name = f"{name_root}_{_uuid.uuid4().hex[:8]}{ext}"
                requirements_doc.name = _os.path.join(_os.path.dirname(requirements_doc.name), unique_name)
                edit_req.new_requirements_doc = requirements_doc
            
            # Set TAT deadline
            from django.utils import timezone as _tz
            now = _tz.now()
            hours_until_event = (edit_req.new_start_datetime - now).total_seconds() / 3600
            if hours_until_event <= 48:
                edit_req.tat_deadline = now + timezone.timedelta(hours=12)
            else:
                edit_req.tat_deadline = now + timezone.timedelta(hours=48)
            
            edit_req.save()
            
            # Set many-to-many relationships
            selected_rooms = form.selected_rooms
            edit_req.new_rooms.set(selected_rooms)
            edit_req.original_rooms.set(
                original_booking.rooms.all() if original_booking.rooms.exists() else [original_booking.room]
            )
            
            # Send email notification to faculty
            details = _format_booking_details(
                selected_rooms or original_booking,
                original_booking.faculty_name,
                edit_req.new_start_datetime,
                edit_req.new_end_datetime,
                edit_req.new_purpose,
                edit_req.new_department,
            )
            
            _safe_mail(
                subject="[Blixtro] Room Booking Edit Request Submitted",
                message=(
                    f"Dear {original_booking.faculty_name},\n\n"
                    "Your room booking edit request has been submitted successfully and is awaiting admin review.\n"
                    f"{details}\n\n"
                    "You will receive another email as soon as the request is reviewed.\n\n"
                    "Best regards,\nBlixtro — SFS College Inventory & Booking System"
                ),
                recipient_list=[original_booking.faculty_email],
            )
            
            # Send email notification to admins
            admin_emails = _admin_emails()
            if admin_emails:
                _safe_mail(
                    subject=f"[Blixtro] Room Booking Edit Request — {format_room_list(selected_rooms or original_booking)}",
                    message=(
                        f"A faculty member has requested to edit a confirmed booking.\n"
                        f"Original Booking: {original_booking.room.room_name} | {timezone.localtime(original_booking.start_datetime).strftime('%d %b %Y, %H:%M')}\n"
                        f"Requested Changes: {format_room_list(selected_rooms or original_booking)} | {timezone.localtime(edit_req.new_start_datetime).strftime('%d %b %Y, %H:%M')}\n"
                        f"Faculty: {original_booking.faculty_name} ({original_booking.faculty_email})\n\n"
                        "Please log in to the admin dashboard to review this edit request.\n\n"
                        "Blixtro — SFS College Inventory & Booking System"
                    ),
                    recipient_list=admin_emails,
                )
            
            return render(request, "booking/booking_success.html", {
                "booking": original_booking,
                "edit_request": True,
                "pending": True,
            })
        else:
            messages.error(request, "Please correct the errors below.")
    
    return render(request, "booking/edit_booking.html", {
        "form": form,
        "original_booking": original_booking,
    })


def get_bookings_by_email(request):
    """
    AJAX GET — returns the faculty's upcoming confirmed bookings AND pending
    booking requests for the cancellation modal.  Validates email + password first.
    """
    email    = request.GET.get('email', '').strip().lower()
    password = request.GET.get('password', '').strip()

    if not email or not password:
        return JsonResponse({'error': 'Email and password are required.'}, status=400)

    # Validate credentials
    try:
        cred = RoomBookingCredentials.objects.get(email=email)
        if cred.password != password:
            return JsonResponse({'error': 'Incorrect password.'}, status=403)
    except RoomBookingCredentials.DoesNotExist:
        return JsonResponse({'error': 'This email is not authorised.'}, status=403)

    data = []

    # 1. Confirmed (RoomBooking) records that are still upcoming
    confirmed_bookings = RoomBooking.objects.filter(
        faculty_email=email,
        end_datetime__gte=timezone.now()
    ).select_related('room').prefetch_related('rooms').order_by('start_datetime')

    for b in confirmed_bookings:
        has_pending_cancel = b.cancellation_requests.filter(status='pending').exists()
        start_local = timezone.localtime(b.start_datetime)
        end_local   = timezone.localtime(b.end_datetime)
        
        # Check if booking can be edited (not within 24 hours and no pending edits)
        hours_until_booking = (b.start_datetime - timezone.now()).total_seconds() / 3600
        has_pending_edit = b.edit_requests.filter(status='pending').exists()
        can_edit = hours_until_booking > 24 and not has_pending_cancel
        
        data.append({
            'id':                b.id,
            'booking_type':      'confirmed',
            'room_name':         format_room_list(b),
            'start':             start_local.strftime('%d %b %Y, %H:%M'),
            'end':               end_local.strftime('%H:%M'),
            # ISO timestamp so JS can calculate 24hr window for cancel button
            'start_raw':         b.start_datetime.isoformat(),
            'has_pending_cancel': has_pending_cancel,
            'can_edit':          can_edit,
        })

    # 2. Pending booking requests (not yet approved / rejected / expired)
    pending_requests = RoomBookingRequest.objects.filter(
        faculty_email=email,
        status__in=['pending', 'recommended'],
        end_datetime__gte=timezone.now()
    ).select_related('room').prefetch_related('rooms').order_by('start_datetime')

    for r in pending_requests:
        start_local = timezone.localtime(r.start_datetime)
        end_local   = timezone.localtime(r.end_datetime)
        status_label = 'Recommended' if r.status == 'recommended' else 'Pending Approval'
        data.append({
            'id':                r.id,
            'booking_type':      'request',
            'room_name':         format_room_list(r),
            'start':             start_local.strftime('%d %b %Y, %H:%M'),
            'end':               end_local.strftime('%H:%M'),
            'start_raw':         r.start_datetime.isoformat(),
            'has_pending_cancel': False,
            'status_label':      status_label,
        })

    return JsonResponse({'bookings': data})


def get_booking_status(request):
    """
    AJAX GET — faculty enters email + password to view the status of all
    their booking requests AND cancellation requests.
    Validates against RoomBookingCredentials (Faculty Manager).
    """
    email    = request.GET.get('email', '').strip().lower()
    password = request.GET.get('password', '').strip()

    if not email or not password:
        return JsonResponse({'error': 'Email and password are required.'}, status=400)

    # Validate credentials against Faculty Manager
    try:
        cred = RoomBookingCredentials.objects.get(email=email)
        if cred.password != password:
            return JsonResponse({'error': 'Incorrect password.'}, status=403)
    except RoomBookingCredentials.DoesNotExist:
        return JsonResponse({'error': 'This email is not registered in the Faculty Manager.'}, status=403)

    results = []

    # Booking requests for this faculty
    booking_reqs = RoomBookingRequest.objects.filter(
        faculty_email=email
    ).select_related('room', 'recommended_by', 'approved_by').prefetch_related('rooms').order_by('-created_on')

    for req in booking_reqs:
        start_local = timezone.localtime(req.start_datetime)
        end_local   = timezone.localtime(req.end_datetime)
        review_note = req.review_note or ''
        if req.status == 'recommended' and getattr(req, 'recommended_by', None):
            recommender = f"{req.recommended_by.first_name} {req.recommended_by.last_name}".strip() or str(req.recommended_by)
            review_note = f"Recommended by {recommender}"
            if getattr(req, 'recommended_note', ''):
                review_note += f" — {req.recommended_note}"
        elif req.status == 'approved' and getattr(req, 'approved_by', None):
            approver = f"{req.approved_by.first_name} {req.approved_by.last_name}".strip() or str(req.approved_by)
            review_note = f"Approved by {approver}"
            if getattr(req, 'approved_note', ''):
                review_note += f" — {req.approved_note}"
        results.append({
            'type':        'Booking Request',
            'room':        format_room_list(req),
            'from':        start_local.strftime('%d %b %Y, %H:%M'),
            'to':          end_local.strftime('%H:%M'),
            'purpose':     req.purpose or '—',
            'status':      req.status,      # pending / recommended / approved / rejected / expired
            'review_note': review_note,
            'submitted':   req.created_on.strftime('%d %b %Y'),
        })

    # Cancellation requests for this faculty's confirmed bookings
    cancel_reqs = RoomCancellationRequest.objects.filter(
        faculty_email=email
    ).select_related('booking', 'booking__room').order_by('-created_on')

    for req in cancel_reqs:
        room_name = format_room_list(req.booking) if req.booking else '—'
        if req.booking:
            b_start = timezone.localtime(req.booking.start_datetime).strftime('%d %b %Y, %H:%M')
            b_end   = timezone.localtime(req.booking.end_datetime).strftime('%H:%M')
        else:
            b_start = '—'
            b_end   = '—'
        results.append({
            'type':        'Cancellation Request',
            'room':        format_room_list(req.booking) if req.booking else room_name,
            'from':        b_start,
            'to':          b_end,
            'purpose':     req.reason,
            'status':      req.status,
            'review_note': '',
            'submitted':   req.created_on.strftime('%d %b %Y'),
        })

    return JsonResponse({'requests': results})


def submit_cancellation_request(request):
    """
    Handles both:
      - Withdrawal of a pending RoomBookingRequest (no admin approval needed, done instantly)
      - Cancellation request for a confirmed RoomBooking (needs admin approval)

    Emails are sent in both cases:
      - For pending-request withdrawal: only faculty receives email.
      - For confirmed booking cancellation: faculty + admins receive emails.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)

    email        = request.POST.get('email', '').strip().lower()
    password     = request.POST.get('password', '').strip()
    booking_id   = request.POST.get('booking_id', '').strip()
    reason       = request.POST.get('reason', '').strip()
    booking_type = request.POST.get('booking_type', 'confirmed')   # 'request' | 'confirmed'

    if not all([email, password, booking_id, reason]):
        return JsonResponse({'error': 'All fields are required.'}, status=400)

    # Validate credentials
    try:
        cred = RoomBookingCredentials.objects.get(email=email)
        if cred.password != password:
            return JsonResponse({'error': 'Incorrect password.'}, status=403)
    except RoomBookingCredentials.DoesNotExist:
        return JsonResponse({'error': 'This email is not authorised.'}, status=403)

    # ── Case 1: Withdraw a PENDING/RECOMMENDED booking request (instant, no approval) ──
    if booking_type == 'request':
        try:
            booking_req = RoomBookingRequest.objects.get(
                id=booking_id,
                faculty_email=email,
                status__in=['pending', 'recommended']
            )
        except RoomBookingRequest.DoesNotExist:
            return JsonResponse({'error': 'Pending request not found or already processed.'}, status=404)

        booking_req.status = 'rejected'
        booking_req.review_note = f"Withdrawn by faculty: {reason}"
        booking_req.save(update_fields=['status', 'review_note', 'updated_on'])

        # Email only to faculty
        details = _format_booking_details(
            booking_req,
            booking_req.faculty_name,
            booking_req.start_datetime,
            booking_req.end_datetime,
            booking_req.purpose,
            booking_req.department,
        )
        _safe_mail(
            subject="[Blixtro] Room Booking Request Withdrawn",
            message=(
                f"Dear {booking_req.faculty_name},\n\n"
                "Your room booking request has been successfully withdrawn.\n"
                f"{details}\n\n"
                "Reason provided: {reason}\n\n"
                "You are welcome to submit a new request at any time.\n\n"
                "Best regards,\nBlixtro — SFS College Inventory & Booking System"
            ).format(reason=reason),
            recipient_list=[email],
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Your booking request has been withdrawn successfully.',
        })

    # ── Case 2: Request cancellation for a CONFIRMED booking ───────────────
    try:
        booking = RoomBooking.objects.get(id=booking_id, faculty_email=email)
    except RoomBooking.DoesNotExist:
        return JsonResponse({'error': 'Booking not found.'}, status=404)

    # ── 24-hour cancellation window check ──────────────────────────────────
    from django.utils import timezone as _tz
    hours_until = (booking.start_datetime - _tz.now()).total_seconds() / 3600
    if hours_until < 24:
        return JsonResponse({
            'error': 'Cancellation requests cannot be submitted within 24 hours of the booking date.'
        }, status=400)

    # Prevent a duplicate pending cancellation request
    if booking.cancellation_requests.filter(status='pending').exists():
        return JsonResponse(
            {'error': 'A cancellation request is already pending for this booking.'},
            status=400
        )

    RoomCancellationRequest.objects.create(
        booking=booking,
        faculty_email=email,
        reason=reason,
        status='pending',
    )

    details = _format_booking_details(
        booking,
        booking.faculty_name,
        booking.start_datetime,
        booking.end_datetime,
        booking.purpose,
        booking.department,
    )

    # Email to faculty
    _safe_mail(
        subject="[Blixtro] Room Booking Cancellation Request Submitted",
        message=(
            f"Dear {booking.faculty_name},\n\n"
            "Your cancellation request has been submitted and is awaiting admin review.\n"
            f"{details}\n\n"
            "Reason: {reason}\n\n"
            "You will be notified once a decision is made.\n\n"
            "Best regards,\nBlixtro — SFS College Inventory & Booking System"
        ).format(reason=reason),
        recipient_list=[email],
    )

    # Email to admins
    admin_emails = _admin_emails()
    if admin_emails:
        _safe_mail(
            subject=f"[Blixtro] Cancellation Request — {format_room_list(booking)}",
            message=(
                f"A faculty member has requested cancellation of a confirmed booking.\n"
                f"{details}\n\n"
                f"Reason: {reason}\n\n"
                "Please log in to the admin dashboard to approve or reject this request.\n\n"
                "Blixtro — SFS College Inventory & Booking System"
            ),
            recipient_list=admin_emails,
        )

    return JsonResponse({
        'status': 'success',
        'message': 'Cancellation request submitted. Awaiting admin approval.',
    })


def rooms_by_category(request):
    category = request.GET.get("category")
    start    = request.GET.get("start")
    end      = request.GET.get("end")

    # Exclude washrooms and officerooms from booking categories
    rooms = list(
        Room.objects.filter(room_category=category)
        .exclude(room_category__in=['washrooms', 'officerooms'])
    )
    rooms = sort_rooms_iterable(rooms)
    start_dt = parse_datetime(start) if start else None
    end_dt   = parse_datetime(end)   if end   else None

    if start_dt and timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt)
    if end_dt and timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt)

    # Use the safe check to see if the table is ready for datetime queries
    can_check_availability = _roombooking_has_datetime_columns()

    # Pre-fetch overlapping confirmed bookings and pending requests in bulk
    confirmed_booked_ids = set()
    pending_ids          = set()

    if can_check_availability and start_dt and end_dt:
        try:
            confirmed_booked_ids = set(
                RoomBooking.objects.filter(
                    Q(room__in=rooms) | Q(rooms__in=rooms),
                    start_datetime__lt=end_dt,
                    end_datetime__gt=start_dt,
                ).values_list('room_id', flat=True)
            )
            confirmed_booked_ids.update(
                RoomBooking.objects.filter(
                    rooms__in=rooms,
                    start_datetime__lt=end_dt,
                    end_datetime__gt=start_dt,
                ).values_list('rooms__id', flat=True)
            )
        except Exception:
            confirmed_booked_ids = set()

        try:
            pending_ids = set(
                RoomBookingRequest.objects.filter(
                    Q(room__in=rooms) | Q(rooms__in=rooms),
                    status__in=['pending', 'recommended'],
                    start_datetime__lt=end_dt,
                    end_datetime__gt=start_dt,
                ).values_list('room_id', flat=True)
            )
            pending_ids.update(
                RoomBookingRequest.objects.filter(
                    rooms__in=rooms,
                    status__in=['pending', 'recommended'],
                    start_datetime__lt=end_dt,
                    end_datetime__gt=start_dt,
                ).values_list('rooms__id', flat=True)
            )
        except Exception:
            pending_ids = set()

    data = []
    for room in rooms:
        is_confirmed_booked = room.id in confirmed_booked_ids
        is_pending          = room.id in pending_ids

        data.append({
            "id":          room.id,
            "name":        room.room_name,
            "label":       room.label,
            "category":    room.room_category,
            "capacity":    getattr(room, 'capacity', 40),
            "available":   not is_confirmed_booked and not is_pending,
            "is_booked":   is_confirmed_booked,
            "has_pending": is_pending,
        })
    return JsonResponse(data, safe=False)


def firebase_login_callback(request):
    if request.method != "POST":
        return redirect('student:portal_login')

    id_token = request.POST.get('id_token', '').strip()
    if not id_token:
        return redirect('student:portal_login')

    try:
        if not firebase_admin._apps:
            creds_json = os.environ.get('FIREBASE_ADMIN_CREDENTIALS_JSON', '')
            if creds_json:
                import json as _json
                cred_dict = _json.loads(creds_json)
                if 'private_key' in cred_dict:
                    cred_dict['private_key'] = cred_dict['private_key'].replace('\\n', '\n')
                firebase_admin.initialize_app(credentials.Certificate(cred_dict))
            else:
                print("[firebase_login] CRITICAL: No Firebase credentials available", flush=True)
                return redirect('student:portal_login')

        decoded_token = auth.verify_id_token(id_token, clock_skew_seconds=10)

    except Exception as e:
        print(f"[firebase_login] Token verification failed: {e}", flush=True)
        return redirect('student:portal_login')

    email = (decoded_token.get('email') or '').strip().lower()
    name  = (decoded_token.get('name') or '').strip()

    if not email:
        print("[firebase_login] No email in token payload", flush=True)
        return redirect('student:portal_login')

    allowed_domain = getattr(settings, 'ALLOWED_EMAIL_DOMAIN', 'sfscollege.in')
    if not email.endswith(f'@{allowed_domain}'):
        print(f"[firebase_login] Rejected domain: {email}", flush=True)
        return redirect('student:portal_login')

    try:
        user = User.objects.get(email=email)
        update_fields = []
        if not user.first_name and name:
            user.first_name = name.split()[0]
            update_fields.append('first_name')
        if not user.last_name and name and len(name.split()) > 1:
            user.last_name = ' '.join(name.split()[1:])
            update_fields.append('last_name')
        if update_fields:
            user.save(update_fields=update_fields)

    except User.DoesNotExist:
        parts      = name.split() if name else []
        first_name = parts[0]                   if parts else ''
        last_name  = ' '.join(parts[1:])        if len(parts) > 1 else ''
        user = User(
            email      = email,
            first_name = first_name,
            last_name  = last_name,
            is_active  = True,
            is_staff   = False,
        )
        user.set_unusable_password()
        user.save()

    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    storage = messages.get_messages(request)
    storage.used = True

    print(f"[firebase_login] Logged in successfully: {email}", flush=True)
    return redirect('student:report_issue')


def import_credentials(request):
    if request.method == "POST" and request.FILES.get('excel_file'):
        try:
            df = pd.read_excel(request.FILES['excel_file'])
            df.columns = df.columns.str.strip().str.lower()
            required_cols = {'email', 'password'}
            missing = required_cols - set(df.columns)
            if missing:
                messages.error(request, f"Excel file is missing required columns: {', '.join(missing)}")
                return redirect('central_admin:aura_dashboard')
            for _, row in df.iterrows():
                RoomBookingCredentials.objects.update_or_create(
                    email=str(row['email']).strip().lower(),
                    defaults={
                        'password':    str(row['password']),
                        'designation': str(row['designation']) if 'designation' in df.columns else 'Faculty'
                    }
                )
            messages.success(request, "Credentials imported successfully.")
        except Exception as e:
            messages.error(request, f"Import failed: {e}")
    return redirect('central_admin:aura_dashboard')


def import_booking_credentials(request):
    if request.method == "POST" and request.FILES.get('excel_file'):
        try:
            df = pd.read_excel(request.FILES['excel_file'])
            df.columns = df.columns.str.strip().str.lower()
            required_cols = {'email', 'password', 'designation'}
            missing = required_cols - set(df.columns)
            if missing:
                err_msg = f"Excel file is missing required columns: {', '.join(missing)}"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': err_msg}, status=400)
                messages.error(request, err_msg)
                return redirect('central_admin:aura_dashboard')
            for _, row in df.iterrows():
                RoomBookingCredentials.objects.update_or_create(
                    email=str(row['email']).strip().lower(),
                    defaults={
                        'password':    str(row['password']),
                        'designation': str(row['designation'])
                    }
                )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Credentials imported successfully.'})
            messages.success(request, "Faculty credentials imported successfully.")
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            messages.error(request, f"Import failed: {e}")
    return redirect('central_admin:aura_dashboard')


def delete_booking_credential(request, pk):
    if request.user.userprofile.role == 'subadmin':
        messages.error(request, "Unauthorized access.")
    else:
        get_object_or_404(RoomBookingCredentials, pk=pk).delete()
        messages.success(request, "Credential deleted.")
    return redirect('central_admin:aura_dashboard')


def create_booking_credentials(request):
    """Create a new faculty credential manually via AJAX."""
    import json
    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            designation = data.get('designation', '').strip()
            password = data.get('password', '').strip()
            
            if not email or not designation or not password:
                return JsonResponse({'status': 'error', 'message': 'All fields are required.'}, status=400)
            
            if RoomBookingCredentials.objects.filter(email=email).exists():
                return JsonResponse({'status': 'error', 'message': 'Email already exists.'}, status=400)
            
            RoomBookingCredentials.objects.create(
                email=email,
                designation=designation,
                password=password
            )
            return JsonResponse({'status': 'success', 'message': 'Credential created successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


def check_document_name(request):
    """
    AJAX GET — checks whether the given filename already exists in
    RoomBookingRequest or RoomBooking requirements_doc fields.
    Returns {'is_unique': True/False}
    """
    filename = request.GET.get('filename', '').strip()
    if not filename:
        return JsonResponse({'is_unique': True})

    import os as _os
    basename = _os.path.basename(filename).lower()

    from inventory.models import RoomBookingRequest as _RBR
    exists_in_requests = _RBR.objects.filter(
        requirements_doc__iendswith=basename
    ).exists()

    from inventory.models import RoomBooking as _RB
    exists_in_bookings = _RB.objects.filter(
        requirements_doc__iendswith=basename
    ).exists()

    is_unique = not (exists_in_requests or exists_in_bookings)
    return JsonResponse({'is_unique': is_unique})


# ─────────────────────────────────────────────────────────────────────
# AUTOMATED BOOKING TAT TASK
# ─────────────────────────────────────────────────────────────────────

def process_booking_tat_reminders_and_expiry():
    """
    For EACH pending/recommended booking request:
      - Detect TAT type (12h or 48h) from (tat_deadline - created_on).
      - 48h TAT → 24h reminder then 12h reminder.
      - 12h TAT → 6h reminder then 3h reminder.
      - Auto-cancel when TAT deadline passes.

    Also sends a day-before reminder to faculty for confirmed bookings.
    """
    from django.utils import timezone as _tz

    now = _tz.now()

    pending_reqs = RoomBookingRequest.objects.filter(
        status__in=['pending', 'recommended']
    ).select_related('room')

    for req in pending_reqs:
        if not req.tat_deadline:
            continue

        details = _format_booking_details(
            req,
            req.faculty_name,
            req.start_datetime,
            req.end_datetime,
            req.purpose,
            req.department,
        )
        time_left = req.tat_deadline - now

        tat_duration = req.tat_deadline - req.created_on
        is_12h_tat = tat_duration <= timezone.timedelta(hours=14)

        # Determine who to remind based on stage
        if req.workflow_stage == 'central_admin':
            reminder_emails = _central_admin_only_emails()
        else:
            reminder_emails = _sub_admin_emails()

        if is_12h_tat:
            if (not req.reminder_24h_sent and
                    timezone.timedelta(hours=3) < time_left <= timezone.timedelta(hours=6)):
                if reminder_emails:
                    _safe_mail(
                        subject=f"[Blixtro] ⏳ 6h Approval Reminder (Fast-Track) — {format_room_list(req)}",
                        message=(
                            "A fast-track room booking request has 6 hours or less remaining "
                            "on its 12-hour approval window.\n"
                            f"{details}\n\n"
                            "Please approve or reject this request promptly, or it will be "
                            "automatically cancelled.\n\n"
                            "Blixtro — SFS College Inventory & Booking System"
                        ),
                        recipient_list=reminder_emails,
                    )
                req.reminder_24h_sent = True
                req.save(update_fields=['reminder_24h_sent'])

            if (not req.reminder_12h_sent and
                    timezone.timedelta(hours=0) < time_left <= timezone.timedelta(hours=3)):
                if reminder_emails:
                    _safe_mail(
                        subject=f"[Blixtro] 🚨 3h Final Reminder (Fast-Track) — {format_room_list(req)}",
                        message=(
                            "URGENT: A fast-track room booking request has less than 3 hours "
                            "remaining before automatic cancellation.\n"
                            f"{details}\n\n"
                            "Please take immediate action in the admin dashboard.\n\n"
                            "Blixtro — SFS College Inventory & Booking System"
                        ),
                        recipient_list=reminder_emails,
                    )
                req.reminder_12h_sent = True
                req.save(update_fields=['reminder_12h_sent'])

        else:
            if (not req.reminder_24h_sent and
                    timezone.timedelta(hours=12) < time_left <= timezone.timedelta(hours=24)):
                if reminder_emails:
                    _safe_mail(
                        subject=f"[Blixtro] ⚠ 24h Approval Reminder — {format_room_list(req)}",
                        message=(
                            "A room booking request has not been approved yet and the 48-hour "
                            "TAT deadline is approaching (less than 24 hours remaining).\n"
                            f"{details}\n\n"
                            "Please approve or reject this request before the deadline, or it "
                            "will be automatically cancelled.\n\n"
                            "Blixtro — SFS College Inventory & Booking System"
                        ),
                        recipient_list=reminder_emails,
                    )
                req.reminder_24h_sent = True
                req.save(update_fields=['reminder_24h_sent'])

            if (not req.reminder_12h_sent and
                    timezone.timedelta(hours=0) < time_left <= timezone.timedelta(hours=12)):
                if reminder_emails:
                    _safe_mail(
                        subject=f"[Blixtro] 🚨 12h Final Reminder — {format_room_list(req)}",
                        message=(
                            "URGENT: A room booking request has less than 12 hours remaining "
                            "before automatic cancellation.\n"
                            f"{details}\n\n"
                            "Please take immediate action in the admin dashboard.\n\n"
                            "Blixtro — SFS College Inventory & Booking System"
                        ),
                        recipient_list=reminder_emails,
                    )
                req.reminder_12h_sent = True
                req.save(update_fields=['reminder_12h_sent'])

        # ── Auto-expiry ─────────────────────────────────────────────────────
        if time_left <= timezone.timedelta(0):
            tat_label = '12' if is_12h_tat else '48'
            req.status = 'expired'
            req.review_note = f'Auto-cancelled: Approval TAT of {tat_label} hours exceeded.'
            req.save(update_fields=['status', 'review_note', 'updated_on'])

            _safe_mail(
                subject=f"[Blixtro] Room Booking Request Auto-Cancelled — {format_room_list(req)}",
                message=(
                    f"Dear {req.faculty_name},\n\n"
                    "Unfortunately, your room booking request was not reviewed within the "
                    f"required {tat_label}-hour approval window and has been automatically cancelled.\n"
                    f"{details}\n\n"
                    "Please submit a new booking request if you still need the room.\n\n"
                    "Best regards,\nBlixtro — SFS College Inventory & Booking System"
                ),
                recipient_list=[req.faculty_email],
                fail_silently=False,
            )

            all_admin_emails = _admin_emails()
            if all_admin_emails:
                _safe_mail(
                    subject=f"[Blixtro] Booking Request Auto-Cancelled — {format_room_list(req)}",
                    message=(
                        "A room booking request was automatically cancelled because the "
                        f"{tat_label}-hour approval TAT was exceeded without action.\n"
                        f"{details}\n\n"
                        "The request has been removed from the pending queue.\n\n"
                        "Blixtro — SFS College Inventory & Booking System"
                    ),
                    recipient_list=all_admin_emails,
                )

    # ── Day-before confirmed booking reminder to faculty ──────────────────────
    tomorrow_start = _tz.now().replace(hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(days=1)
    tomorrow_end   = tomorrow_start + timezone.timedelta(days=1)

    tomorrow_bookings = RoomBooking.objects.filter(
        start_datetime__gte=tomorrow_start,
        start_datetime__lt=tomorrow_end,
        reminder_sent=False,
    ).select_related('room')

    for booking in tomorrow_bookings:
        details = _format_booking_details(
            booking,
            booking.faculty_name,
            booking.start_datetime,
            booking.end_datetime,
            booking.purpose,
            booking.department,
        )
        _safe_mail(
            subject=f"[Blixtro] Reminder: Your Room Booking is Tomorrow — {format_room_list(booking)}",
            message=(
                f"Dear {booking.faculty_name},\n\n"
                "This is a friendly reminder that you have a confirmed room booking tomorrow.\n"
                f"{details}\n\n"
                "Please visit the office to verify your booking details, or cancel your booking "
                "through the booking portal if you no longer require the room.\n\n"
                "Best regards,\nBlixtro — SFS College Inventory & Booking System"
            ),
            recipient_list=[booking.faculty_email],
        )
        booking.reminder_sent = True
        booking.save(update_fields=['reminder_sent'])
