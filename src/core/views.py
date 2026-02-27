from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import TemplateView
from django.db import transaction, connection
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, 
    PasswordResetCompleteView, PasswordResetConfirmView, 
    PasswordResetDoneView, PasswordResetView
    )
from django.contrib.auth import login
from django.urls import reverse_lazy
from . forms import CustomAuthenticationForm, UserRegisterForm
from django.views.generic import CreateView
from core.models import UserProfile, Organisation
from django.contrib.auth import get_user_model
from config.mixins.access_mixins import RedirectLoggedInUsersMixin
from django.contrib import messages
from core.forms import RoomBookingForm
from inventory.models import Room, RoomBooking, RoomBookingRequest, RoomCancellationRequest, RoomBookingCredentials
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

User = get_user_model()


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
    
    @transaction.atomic
    def form_valid(self, form):
        user = form.save()
        
        org_name = form.cleaned_data.get('org_name')
        org = Organisation.objects.create(
            name = org_name,
        )
        
        # Create user profile
        first_name = form.cleaned_data.get('first_name')
        last_name = form.cleaned_data.get('last_name')
        UserProfile.objects.create(
            user=user, 
            org = org,
            first_name=first_name, 
            last_name=last_name, 
            is_central_admin=True
            )
        
        login(self.request, user)
        return redirect('landing_page')
    

class LogoutView(LogoutView):
    template_name = 'core/logout.html'


class ChangePasswordView(PasswordChangeView):
    template_name = 'core/change_password.html'
    success_url = reverse_lazy('landing_page')


class ResetPasswordView(PasswordResetView):
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

def room_booking_view(request):
    form = RoomBookingForm()

    if request.method == "POST":
        form = RoomBookingForm(request.POST, request.FILES)
        if form.is_valid():
            import uuid as _uuid
            import os as _os
            booking_req = form.save(commit=False)
            booking_req.status = 'pending'
            # Ensure each uploaded document gets a unique storage name
            if booking_req.requirements_doc:
                orig_name = _os.path.basename(booking_req.requirements_doc.name)
                name_root, ext = _os.path.splitext(orig_name)
                unique_name = f"{name_root}_{_uuid.uuid4().hex[:8]}{ext}"
                booking_req.requirements_doc.name = _os.path.join(
                    _os.path.dirname(booking_req.requirements_doc.name), unique_name
                )
            booking_req.save()
            return render(request, "booking/booking_success.html", {
                "booking": booking_req,
                "pending": True,
            })
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "booking/room_booking.html", {"form": form})


def get_bookings_by_email(request):
    """
    AJAX GET — returns the faculty's upcoming confirmed bookings for the
    cancellation modal.  Validates email + password first.
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

    # Return only confirmed (RoomBooking) records that are still upcoming
    bookings = RoomBooking.objects.filter(
        faculty_email=email,
        end_datetime__gte=timezone.now()
    ).select_related('room').order_by('start_datetime')

    data = []
    for b in bookings:
        has_pending_cancel = b.cancellation_requests.filter(status='pending').exists()
        # Convert to local timezone before formatting so displayed times match
        # what the faculty originally entered (stored as UTC in the database).
        start_local = timezone.localtime(b.start_datetime)
        end_local   = timezone.localtime(b.end_datetime)
        data.append({
            'id': b.id,
            'room_name': b.room.room_name,
            'start': start_local.strftime('%d %b %Y, %H:%M'),
            'end':   end_local.strftime('%H:%M'),
            'has_pending_cancel': has_pending_cancel,
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
    ).select_related('room').order_by('-created_on')

    for req in booking_reqs:
        start_local = timezone.localtime(req.start_datetime)
        end_local   = timezone.localtime(req.end_datetime)
        results.append({
            'type':        'Booking Request',
            'room':        req.room.room_name,
            'from':        start_local.strftime('%d %b %Y, %H:%M'),
            'to':          end_local.strftime('%H:%M'),
            'purpose':     req.purpose or '—',
            'status':      req.status,      # pending / approved / rejected
            'review_note': req.review_note or '',
            'submitted':   req.created_on.strftime('%d %b %Y'),
        })

    # Cancellation requests for this faculty's confirmed bookings
    cancel_reqs = RoomCancellationRequest.objects.filter(
        faculty_email=email
    ).select_related('booking', 'booking__room').order_by('-created_on')

    for req in cancel_reqs:
        room_name = req.booking.room.room_name if req.booking else '—'
        if req.booking:
            b_start = timezone.localtime(req.booking.start_datetime).strftime('%d %b %Y, %H:%M')
            b_end   = timezone.localtime(req.booking.end_datetime).strftime('%H:%M')
        else:
            b_start = '—'
            b_end   = '—'
        results.append({
            'type':        'Cancellation Request',
            'room':        room_name,
            'from':        b_start,
            'to':          b_end,
            'purpose':     req.reason,
            'status':      req.status,
            'review_note': '',
            'submitted':   req.created_on.strftime('%d %b %Y'),
        })

    return JsonResponse({'requests': results})


def submit_cancellation_request(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)

    email      = request.POST.get('email', '').strip().lower()
    password   = request.POST.get('password', '').strip()
    booking_id = request.POST.get('booking_id', '').strip()
    reason     = request.POST.get('reason', '').strip()

    if not all([email, password, booking_id, reason]):
        return JsonResponse({'error': 'All fields are required.'}, status=400)

    # Validate credentials
    try:
        cred = RoomBookingCredentials.objects.get(email=email)
        if cred.password != password:
            return JsonResponse({'error': 'Incorrect password.'}, status=403)
    except RoomBookingCredentials.DoesNotExist:
        return JsonResponse({'error': 'This email is not authorised.'}, status=403)

    # Find the booking — must belong to this email
    try:
        booking = RoomBooking.objects.get(id=booking_id, faculty_email=email)
    except RoomBooking.DoesNotExist:
        return JsonResponse({'error': 'Booking not found.'}, status=404)

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
    return JsonResponse({
        'status': 'success',
        'message': 'Cancellation request submitted. Awaiting admin approval.',
    })

def rooms_by_category(request):
    category = request.GET.get("category")
    start    = request.GET.get("start")
    end      = request.GET.get("end")

    rooms    = Room.objects.filter(room_category=category)
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
                    room__in=rooms,
                    start_datetime__lt=end_dt,
                    end_datetime__gt=start_dt,
                ).values_list('room_id', flat=True)
            )
        except Exception:
            confirmed_booked_ids = set()

        try:
            # Rooms with a PENDING booking request for this slot are treated
            # as unavailable — shown as "Waiting for Approval" on the UI.
            # Rejected requests do NOT block the room.
            pending_ids = set(
                RoomBookingRequest.objects.filter(
                    room__in=rooms,
                    status='pending',
                    start_datetime__lt=end_dt,
                    end_datetime__gt=start_dt,
                ).values_list('room_id', flat=True)
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
            "category":    room.room_category,
            "capacity":    getattr(room, 'capacity', 40),
            "available":   not is_confirmed_booked and not is_pending,
            "is_booked":   is_confirmed_booked,   # confirmed/approved booking
            "has_pending": is_pending,             # waiting for admin approval
        })
    return JsonResponse(data, safe=False)

def firebase_login_callback(request):
    if request.method != "POST":
        return redirect('student:portal_login')

    id_token = request.POST.get('id_token', '').strip()
    if not id_token:
        return redirect('student:portal_login')

    # ── Step 1: Verify Firebase token ────────────────────────────────────────
    try:
        if not firebase_admin._apps:
            # This should never happen if settings.py initialized correctly,
            # but kept as a safety net
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

    # ── Step 2: Extract and validate email ────────────────────────────────
    email = (decoded_token.get('email') or '').strip().lower()
    name  = (decoded_token.get('name') or '').strip()

    if not email:
        print("[firebase_login] No email in token payload", flush=True)
        return redirect('student:portal_login')

    allowed_domain = getattr(settings, 'ALLOWED_EMAIL_DOMAIN', 'sfscollege.in')
    if not email.endswith(f'@{allowed_domain}'):
        print(f"[firebase_login] Rejected domain: {email}", flush=True)
        return redirect('student:portal_login')

    # ── Step 3: Get or create Django User ─────────────────────────────────
    # This is an email-based User model (no username field) so we look up
    # and create using email only.
    try:
        user = User.objects.get(email=email)
        # Sync name if blank (handles users created before this fix)
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

    # ── Step 4: Log into Django session and redirect ───────────────────────
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    # Clear any stale error messages from previous failed login attempts
    # so they don't bleed through onto the report_issue page
    storage = messages.get_messages(request)
    storage.used = True

    print(f"[firebase_login] Logged in successfully: {email}", flush=True)
    return redirect('student:report_issue')

def import_credentials(request):
    if request.method == "POST" and request.FILES.get('excel_file'):
        try:
            df = pd.read_excel(request.FILES['excel_file'])
            # Normalise column names to lowercase to handle varied casing
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
            # Normalise column names to lowercase to handle varied casing
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


def check_document_name(request):
    """
    AJAX GET — checks whether the given filename already exists in
    RoomBookingRequest or RoomBooking requirements_doc fields.
    Returns {'is_unique': True/False}
    """
    filename = request.GET.get('filename', '').strip()
    if not filename:
        return JsonResponse({'is_unique': True})

    # Normalise: just the basename, case-insensitive
    import os as _os
    basename = _os.path.basename(filename).lower()

    # Check RoomBookingRequest (pending)
    from inventory.models import RoomBookingRequest as _RBR
    exists_in_requests = _RBR.objects.filter(
        requirements_doc__iendswith=basename
    ).exists()

    # Check confirmed RoomBooking
    from inventory.models import RoomBooking as _RB
    exists_in_bookings = _RB.objects.filter(
        requirements_doc__iendswith=basename
    ).exists()

    is_unique = not (exists_in_requests or exists_in_bookings)
    return JsonResponse({'is_unique': is_unique})