from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View
from core.models import User, UserProfile
from inventory.models import Room, Vendor, Purchase, Issue, Department  # Import the Department model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.base_user import BaseUserManager
from django.db import transaction
from inventory.forms.central_admin import PeopleCreateForm, RoomCreateForm, DepartmentForm, VendorForm  # Import the form
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail

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
        try:
            userprofile = form.save(commit=False)

            random_password = BaseUserManager().make_random_password()

            user = User.objects.create_user(
                email=form.cleaned_data.get('email'),
                first_name=userprofile.first_name,
                last_name=userprofile.last_name,
                password=random_password,
            )
            
            userprofile.user = user
            userprofile.org = self.request.user.profile.org
            userprofile.save()
            
            # Generate password reset link
            token_generator = PasswordResetTokenGenerator()
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            reset_link = self.request.build_absolute_uri(
                reverse('core:confirm_password_reset', kwargs={'uidb64': uid, 'token': token})
            )
            
            subject = "Welcome to SFS IMS"
            message = (
                f"Hello,\n\n"
                f"Welcome to our BusNest! You have been added to the system by "
                f"{self.request.user.profile.first_name} {self.request.user.profile.last_name}. "
                f"Please set your password using the link below.\n\n"
                f"{reset_link}\n\n"
                f"Best regards,\nSFS IMS Team"
            )
            recipient_list = [user.email]

            send_mail(
                subject,
                message,
                None,  # Use default from_email in settings
                recipient_list,
                fail_silently=False,
            )
            
            
            return redirect(self.success_url)
        except Exception as e:
            print(self.request, f"An error occurred: {str(e)}")
            return self.form_invalid(form)
        
        
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
    template_name = 'central_admin/issue_list.html'
    model = Issue
    context_object_name = 'issues'
    
    def get_queryset(self):
        return super().get_queryset().filter(organisation=self.request.user.profile.org)


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

