from django.shortcuts import redirect, render
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
from inventory.models import Room, RoomBooking
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from django.utils import timezone

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
    
def room_booking_view(request):
    name="room_booking"
    form = RoomBookingForm()

    if request.method == "POST":
        form = RoomBookingForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "booking/booking_success.html")

    return render(request, "booking/room_booking.html", {"form": form})


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


def rooms_by_category(request):
    category = request.GET.get("category")
    start = request.GET.get("start")
    end = request.GET.get("end")

    rooms = Room.objects.filter(room_category=category)

    start_dt = parse_datetime(start) if start else None
    end_dt = parse_datetime(end) if end else None

    if start_dt and timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt)

    if end_dt and timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt)

    # 🔒 SAFE SCHEMA CHECK
    can_check_availability = _roombooking_has_datetime_columns()

    data = []
    for room in rooms:
        is_booked = False

        if can_check_availability and start_dt and end_dt:
            is_booked = RoomBooking.objects.filter(
                room=room,
                start_datetime__lt=end_dt,
                end_datetime__gt=start_dt
            ).exists()

        data.append({
            "id": room.id,
            "name": room.room_name,
            "category": room.room_category,
            "available": not is_booked,
        })

    return JsonResponse(data, safe=False)