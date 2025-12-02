from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from django.db import transaction
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
    
    