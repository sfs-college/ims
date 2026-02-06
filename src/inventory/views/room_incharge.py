from django.forms import ValidationError
from django.shortcuts import redirect, get_object_or_404, render, reverse
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView, DeleteView, TemplateView, CreateView, View
from inventory.models import Category, Vendor, Purchase, Room, Brand, Item, System, SystemComponent, Issue, ItemGroup, ItemGroupItem, RoomSettings, EditRequest # Import RoomSettings
from inventory.forms.room_incharge import CategoryForm, BrandForm, ItemForm, ItemPurchaseForm, PurchaseForm, PurchaseUpdateForm, SystemForm, SystemComponentForm, ItemGroupForm, ItemGroupItemForm, RoomSettingsForm, ExcelUploadForm, ItemEditRequestForm  # Import RoomSettingsForm
from django.contrib import messages
from django.views.generic.edit import FormView
from inventory.forms.room_incharge import SystemComponentArchiveForm, ItemArchiveForm, RoomUpdateForm
from inventory.models import Archive
from inventory.forms.room_incharge import PurchaseCompleteForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import pandas as pd
import io
from django.utils import timezone
from datetime import datetime, date
from openpyxl.utils import datetime as xl_datetime
from decimal import Decimal, InvalidOperation
from django.forms.models import model_to_dict
from django.http import HttpResponseForbidden
# from ..models import Issue

class CategoryListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/category_list.html'
    model = Category
    context_object_name = 'categories'

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        # Only allow access to rooms where the user is incharge
        room = get_object_or_404(Room, slug=room_slug, incharge=self.request.user.profile)
        return super().get_queryset().filter(room=room, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'], incharge=self.request.user.profile)
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    template_name = 'room_incharge/category_update.html'
    form_class = CategoryForm
    success_url = reverse_lazy('room_incharge:category_list')
    slug_field = 'slug'
    slug_url_kwarg = 'category_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:category_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        category = form.save(commit=False)
        category.organisation = self.request.user.profile.org
        category.room = Room.objects.get(slug=self.kwargs['room_slug'])
        category.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'room_incharge/category_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'category_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:category_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    template_name = 'room_incharge/category_create.html'
    form_class = CategoryForm
    success_url = reverse_lazy('room_incharge:category_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:category_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        category = form.save(commit=False)
        category.organisation = self.request.user.profile.org
        category.room = Room.objects.get(slug=self.kwargs['room_slug'])
        category.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['room'] = Room.objects.get(slug=self.kwargs['room_slug'])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class RoomDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'room_incharge/room_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room_slug = self.kwargs['room_slug']
        room = get_object_or_404(Room, slug=room_slug, incharge=self.request.user.profile)
        context['room'] = room
        context['room_slug'] = room_slug
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class RoomUpdateView(LoginRequiredMixin, UpdateView):
    model = Room
    template_name = 'room_incharge/room_update.html'
    form_class = RoomUpdateForm
    slug_field = 'slug'
    slug_url_kwarg = 'room_slug'

    def get_object(self, queryset=None):
        return get_object_or_404(Room, slug=self.kwargs['room_slug'], incharge=self.request.user.profile)

    def get_success_url(self):
        return reverse_lazy('room_incharge:room_dashboard', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        room = form.save(commit=False)
        room.organisation = self.request.user.profile.org
        room.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.get_object()
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class BrandListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/brand_list.html'
    model = Brand
    context_object_name = 'brands'

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class BrandCreateView(LoginRequiredMixin, CreateView):
    model = Brand
    template_name = 'room_incharge/brand_create.html'
    form_class = BrandForm
    success_url = reverse_lazy('room_incharge:brand_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:brand_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        brand = form.save(commit=False)
        brand.organisation = self.request.user.profile.org
        brand.room = Room.objects.get(slug=self.kwargs['room_slug'])
        brand.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['room'] = Room.objects.get(slug=self.kwargs['room_slug'])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class BrandUpdateView(LoginRequiredMixin, UpdateView):
    model = Brand
    template_name = 'room_incharge/brand_update.html'
    form_class = BrandForm
    success_url = reverse_lazy('room_incharge:brand_list')
    slug_field = 'slug'
    slug_url_kwarg = 'brand_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:brand_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        brand = form.save(commit=False)
        brand.organisation = self.request.user.profile.org
        brand.room = Room.objects.get(slug=self.kwargs['room_slug'])
        brand.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class BrandDeleteView(LoginRequiredMixin, DeleteView):
    model = Brand
    template_name = 'room_incharge/brand_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'brand_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:brand_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

class ItemListView(LoginRequiredMixin, ListView):
    model = Item
    template_name = 'room_incharge/item_list.html'
    context_object_name = 'items'
    # probably have paginate_by, etc.

    def get_queryset(self):
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        return Item.objects.filter(room=room).order_by('item_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        context['room'] = room
        context['room_slug'] = self.kwargs['room_slug']
        # ensure RoomSettings exists and is available to the template
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    template_name = 'room_incharge/item_create.html'
    form_class = ItemForm
    success_url = reverse_lazy('room_incharge:item_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_list', kwargs={'room_slug': self.kwargs['room_slug']})
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        form.fields['category'].queryset = Category.objects.filter(room=room)
        form.fields['brand'].queryset = Brand.objects.filter(room=room)
        return form

    def form_valid(self, form):
        obj = form.save(commit=False)
        profile = getattr(self.request.user, "profile", None)

        if profile:
            obj.organisation = profile.org
            obj.created_by = profile

        # 🔒 Lock the item immediately after creation
        obj.is_edit_lock = True  
        obj.room = Room.objects.get(slug=self.kwargs['room_slug'])
        obj.save()

        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['room'] = Room.objects.get(slug=self.kwargs['room_slug'])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class RequestEditView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        room = get_object_or_404(Room, slug=kwargs['room_slug'])
        item = get_object_or_404(Item, slug=kwargs['item_slug'], room=room)

        from django.db.utils import ProgrammingError

        try:
            has_pending_request = EditRequest.objects.filter(
                item=item,
                status="pending"
            ).exists()
        except ProgrammingError:
            # EditRequest table not yet created (migration-safe fallback)
            has_pending_request = False

        if has_pending_request:
            messages.error(request, "An edit request is already pending.")
            return redirect(self.get_success_url())


        EditRequest.objects.create(
            item=item,
            room=room,
            requested_by=request.user.profile,
            status="pending",
        )
        item.is_edit_lock = True
        item.save()  # FIXED

        messages.success(request, "Edit request submitted successfully.")
        return redirect('room_incharge:item_list', room_slug=room.slug)


class ItemUpdateView(LoginRequiredMixin, View):
    """
    Room Incharge can only request edits.
    Direct item updates are not allowed.
    """

    template_name = "room_incharge/item_edit_request.html"
    form_class = ItemEditRequestForm

    def get(self, request, *args, **kwargs):
        item = self.get_item()
        form = self.form_class(initial={
            "item_name": item.item_name,
            "item_description": item.item_description,
            "total_count": item.total_count,
            "available_count": item.available_count,
            "in_use": item.in_use,
        })

        return self.render(form, item)

    def post(self, request, *args, **kwargs):
        item = self.get_item()
        form = self.form_class(request.POST)

        if form.is_valid():
            user_profile = request.user.profile

            # Admins are not allowed to raise edit requests
            if user_profile.is_sub_admin or user_profile.is_central_admin:
                messages.error(
                    request,
                    "Admins cannot edit items. They only approve edit requests."
                )
                return redirect(self.get_success_url())

            # Prevent duplicate edit requests
            if item.is_edit_lock:
                messages.error(
                    request,
                    "An edit request is already pending for this item."
                )
                return redirect(self.get_success_url())

            form.save(item=item, requested_by=user_profile)

            messages.success(
                request,
                "Edit request submitted successfully for approval."
            )
            return redirect(self.get_success_url())

        return self.render(form, item)

    def get_item(self):
        return get_object_or_404(
            Item,
            slug=self.kwargs["item_slug"],
            room__slug=self.kwargs["room_slug"],
        )

    def get_success_url(self):
        return reverse_lazy(
            "room_incharge:item_list",
            kwargs={"room_slug": self.kwargs["room_slug"]},
        )

    def render(self, form, item):
        room = item.room

        context = {
            "form": form,
            "item": item,
            "room": room,
            "room_slug": room.slug,
            "room_name": room.room_name,
            "current_room": room,
            "room_settings": RoomSettings.objects.get_or_create(room=room)[0],
        }

        return render(self.request, self.template_name, context)


class IssueBulkDeleteView(LoginRequiredMixin, View):
    """
    Allows Room Incharge to bulk-delete selected issues.
    Only deletes issues:
      - belonging to the user's organisation
      - belonging to the same room
      - escalation_level == 0   (not escalated)
    """

    def post(self, request, room_slug, *args, **kwargs):
        ids = request.POST.getlist('selected_issues')

        if not ids:
            messages.error(request, "No issues selected.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        profile = getattr(request.user, 'profile', None)
        room = get_object_or_404(Room, slug=room_slug)

        issues = Issue.objects.filter(id__in=ids, room=room)

        allowed = []
        for issue in issues:
            if (
                profile and profile.org and
                issue.organisation == profile.org and
                issue.escalation_level == 0
            ):
                allowed.append(issue.pk)

        if allowed:
            Issue.objects.filter(pk__in=allowed).delete()
            messages.success(request, f"Deleted {len(allowed)} issue(s).")
        else:
            messages.error(request, "No permitted issues to delete.")

        return redirect(request.META.get('HTTP_REFERER', '/'))
    
    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")


class ItemDeleteView(LoginRequiredMixin, DeleteView):
    model = Item
    template_name = 'room_incharge/item_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'item_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context
    
    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is not allowed to delete items (restricted permanently)
        return HttpResponseForbidden("Delete action is not permitted.")


class ItemArchiveView(LoginRequiredMixin, FormView):
    template_name = 'room_incharge/item_archive.html'
    form_class = ItemArchiveForm

    def get_success_url(self):
        return reverse_lazy(
            'room_incharge:item_list',
            kwargs={'room_slug': self.kwargs['room_slug']}
        )

    def form_valid(self, form):
        item = get_object_or_404(Item, slug=self.kwargs['item_slug'])
        count = form.cleaned_data['count']

        if count <= 0:
            form.add_error("count", "Count must be positive.")
            return self.form_invalid(form)

        if item.available_count < count:
            form.add_error("count", "Available count is lower than the number to archive.")
            return self.form_invalid(form)

        Archive.objects.create(
            organisation=item.organisation,
            department=item.department,
            room=item.room,
            item=item,
            count=count,
            archive_type=form.cleaned_data["archive_type"],
            remark=form.cleaned_data["remark"]
        )

        # FIXED — USE CORRECT FIELD
        item.available_count -= count
        item.archived_count += count
        item.save(update_fields=["available_count", "archived_count", "updated_on"])

        messages.success(self.request, "Item archived successfully.")
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['item_slug'] = self.kwargs['item_slug']
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/system_list.html'
    model = System
    context_object_name = 'systems'

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemCreateView(LoginRequiredMixin, CreateView):
    model = System
    template_name = 'room_incharge/system_create.html'
    form_class = SystemForm
    success_url = reverse_lazy('room_incharge:system_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:system_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        system = form.save(commit=False)
        system.organisation = self.request.user.profile.org
        system.room = Room.objects.get(slug=self.kwargs['room_slug'])
        system.department = system.room.department  # Set the department field
        system.save()
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['room'] = Room.objects.get(slug=self.kwargs['room_slug'])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemUpdateView(LoginRequiredMixin, UpdateView):
    model = System
    template_name = 'room_incharge/system_update.html'
    form_class = SystemForm
    success_url = reverse_lazy('room_incharge:system_list')
    slug_field = 'slug'
    slug_url_kwarg = 'system_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:system_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        system = form.save(commit=False)
        system.organisation = self.request.user.profile.org
        system.room = Room.objects.get(slug=self.kwargs['room_slug'])
        system.department = system.room.department  # Set the department field
        system.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemDeleteView(LoginRequiredMixin, DeleteView):
    model = System
    template_name = 'room_incharge/system_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'system_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:system_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context
    
    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

class SystemComponentListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/system_component_list.html'
    model = SystemComponent
    context_object_name = 'components'

    def get_queryset(self):
        system_slug = self.kwargs['system_slug']
        return super().get_queryset().filter(system__slug=system_slug, system__organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['system_slug'] = self.kwargs['system_slug']
        context['room_slug'] = self.kwargs['room_slug']
        context['system'] = get_object_or_404(System, slug=self.kwargs['system_slug'])
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemComponentCreateView(LoginRequiredMixin, CreateView):
    model = SystemComponent
    template_name = 'room_incharge/system_component_create.html'
    form_class = SystemComponentForm
    success_url = reverse_lazy('room_incharge:system_component_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:system_component_list', kwargs={'room_slug': self.kwargs['room_slug'], 'system_slug': self.kwargs['system_slug']})
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        form.fields['component_item'].queryset = Item.objects.filter(room=room)
        return form

    def form_valid(self, form):
        component = form.save(commit=False)
        component.system = System.objects.get(slug=self.kwargs['system_slug'])
        try:
            component.save()
        except ValueError as e:
            form.add_error(None, str(e))
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        
        # Adjust the available_count and in_use count of the associated Item
        item = component.component_item
        item.available_count -= 1
        item.in_use += 1
        item.save()
        
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['system'] = System.objects.get(slug=self.kwargs['system_slug'])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['system_slug'] = self.kwargs['system_slug']
        context['room_slug'] = self.kwargs['room_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemComponentUpdateView(LoginRequiredMixin, UpdateView):
    model = SystemComponent
    template_name = 'room_incharge/system_component_update.html'
    form_class = SystemComponentForm
    success_url = reverse_lazy('room_incharge:system_component_list')
    slug_field = 'slug'
    slug_url_kwarg = 'component_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:system_component_list', kwargs={'room_slug': self.kwargs['room_slug'], 'system_slug': self.kwargs['system_slug']})

    def form_valid(self, form):
        component = form.save(commit=False)
        component.system = System.objects.get(slug=self.kwargs['system_slug'])
        
        # Get the old component item before saving the new one
        old_component = SystemComponent.objects.get(pk=component.pk)
        old_item = old_component.component_item
        
        try:
            component.save()
        except ValueError as e:
            form.add_error(None, str(e))
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        
        # Adjust the counts if the item has changed
        new_item = component.component_item
        if old_item != new_item:
            old_item.available_count += 1
            old_item.in_use -= 1
            old_item.save()
            
            new_item.available_count -= 1
            new_item.in_use += 1
            new_item.save()
        
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['system_slug'] = self.kwargs['system_slug']
        context['room_slug'] = self.kwargs['room_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class SystemComponentDeleteView(LoginRequiredMixin, DeleteView):
    model = SystemComponent
    template_name = 'room_incharge/system_component_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'component_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:system_component_list', kwargs={'room_slug': self.kwargs['room_slug'], 'system_slug': self.kwargs['system_slug']})

    def get_queryset(self):
        system_slug = self.kwargs['system_slug']
        return super().get_queryset().filter(system__slug=system_slug, system__organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['system_slug'] = self.kwargs['system_slug']
        context['room_slug'] = self.kwargs['room_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

class SystemComponentArchiveView(LoginRequiredMixin, FormView):
    template_name = 'room_incharge/system_component_archive.html'
    form_class = SystemComponentArchiveForm

    def get_success_url(self):
        return reverse_lazy(
            'room_incharge:system_component_list',
            kwargs={'room_slug': self.kwargs['room_slug'], 'system_slug': self.kwargs['system_slug']}
        )

    def form_valid(self, form):
        component = get_object_or_404(SystemComponent, slug=self.kwargs["component_slug"])
        item = component.component_item

        Archive.objects.create(
            organisation=item.organisation,
            department=item.department,
            room=item.room,
            item=item,
            count=1,
            archive_type=form.cleaned_data["archive_type"],
            remark=form.cleaned_data["remark"]
        )

        # FIXED
        item.in_use -= 1
        if item.in_use < 0:
            item.in_use = 0

        item.archived_count += 1
        item.save(update_fields=["in_use", "archived_count", "updated_on"])

        component.delete()

        messages.success(self.request, "Component archived successfully.")
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['component_slug'] = self.kwargs['component_slug']
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['system_slug'] = self.kwargs['system_slug']
        context['room_slug'] = self.kwargs['room_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ArchiveListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/archive_list.html'
    model = Archive
    context_object_name = 'archives'

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class PurchaseListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/purchase_list.html'
    model = Purchase
    context_object_name = 'purchases'

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class PurchaseCreateView(LoginRequiredMixin, CreateView):
    model = Purchase
    template_name = 'room_incharge/purchase_create.html'
    form_class = PurchaseForm

    def get_success_url(self):
        return reverse_lazy('room_incharge:purchase_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        org = self.request.user.profile.org

        purchase = form.save(commit=False)

        # 🔒 HARD GUARANTEES
        purchase.organisation = org
        purchase.room = room
        purchase.status = "requested"

        if not purchase.vendor:
            form.add_error("vendor", "Vendor is required")
            return self.form_invalid(form)

        if not purchase.purchase_date:
            purchase.purchase_date = timezone.now().date()

        # Update stock
        if purchase.item:
            item = purchase.item
            item.total_count += int(purchase.quantity)
            item.save(update_fields=["total_count", "updated_on"])

        purchase.save()
        return redirect(self.get_success_url())


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class PurchaseUpdateView(LoginRequiredMixin, UpdateView):
    model = Purchase
    template_name = 'room_incharge/purchase_update.html'
    form_class = PurchaseUpdateForm
    success_url = reverse_lazy('room_incharge:purchase_list')
    slug_field = 'slug'
    slug_url_kwarg = 'purchase_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:purchase_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        purchase = form.save(commit=False)
        if purchase.status != 'requested':
            purchase.status = 'requested'  # Set status to requested if not already
        purchase.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class PurchaseNewItemCreateView(LoginRequiredMixin, CreateView):
    model = Purchase
    template_name = 'room_incharge/purchase_new_item_create.html'
    form_class = ItemPurchaseForm

    def get_success_url(self):
        return reverse_lazy('room_incharge:purchase_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        org = self.request.user.profile.org

        category = form.cleaned_data['category']
        brand = form.cleaned_data['brand']
        vendor = form.cleaned_data['vendor']
        qty = form.cleaned_data['quantity']
        unit = form.cleaned_data['unit_of_measure']

        # 1️⃣ CREATE ITEM
        item = Item.objects.create(
            organisation=org,
            department=room.department,
            room=room,
            category=category,
            brand=brand,
            item_name=form.cleaned_data['item_name'],
            item_description=form.cleaned_data.get('item_description', ''),
            serial_number=form.cleaned_data.get('serial_number', ''),
            purchase_model_code=form.cleaned_data.get('purchase_model_code', ''),
            vendor=vendor,
            total_count=int(qty),
            in_use=0,
            archived_count=0,
            is_listed=True
        )

        # 2️⃣ SAFE PURCHASE DATE (🔥 FIX)
        purchase_date = form.cleaned_data.get('purchase_date') or timezone.now().date()

        # 3️⃣ CREATE PURCHASE
        if not vendor:
            form.add_error("vendor", "Vendor is required")
            return self.form_invalid(form)

        purchase = Purchase.objects.create(
            organisation=org,
            room=room,
            item=item,
            vendor=vendor,
            quantity=qty,
            unit_of_measure=unit,
            cost=form.cleaned_data.get("cost"),
            cost_per_unit=form.cleaned_data.get("cost_per_unit"),
            invoice_number=form.cleaned_data.get("invoice_number"),
            purchase_date=form.cleaned_data.get("purchase_date") or timezone.now().date(),
            item_description=form.cleaned_data.get("item_description", item.item_name),
            remarks=form.cleaned_data.get("remarks", ""),
            status="requested",
        )

        # 4️⃣ TOTAL COST CALC (SAFE DECIMAL)
        if purchase.cost_per_unit and purchase.quantity:
            purchase.total_cost = purchase.cost_per_unit * Decimal(str(purchase.quantity))
            purchase.save(update_fields=['total_cost'])

        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context


class PurchaseDeleteView(LoginRequiredMixin, DeleteView):
    model = Purchase
    template_name = 'room_incharge/purchase_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'purchase_slug'
    success_url = reverse_lazy('room_incharge:purchase_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:purchase_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

# ============================
# Excel Expected Column Formats
# ============================

ITEMS_EXPECTED_COLS = [
    "Sl No",
    "Date of Entry",
    "Item Description",
    "Category",
    "Opening Stock Qty",
    "Arrival / Receipts",
    "Total",
    "Consumed Stock/Issues Qty",
    "Closing / Balance Qty",
    "Unit of Measure",
    "Remarks"
]

PURCHASES_EXPECTED_COLS = [
    "Sl No",
    "Date of Purchase/Entry",
    "Item Description",
    "Category",
    "Purchase ID/Model Code",
    "Serial No",
    "Quantity",
    "Unit of Measure",
    "Status",
    "Vendor",
    "Remarks"
]

# ----------------------------------------
# ---------- Import view: upload + preview ----------
class PurchaseImportView(LoginRequiredMixin, FormView):
    """
    Upload an Excel file and preview the parsed Items and Purchases.
    Validates headers and rows, then renders a preview page where the
    user can re-upload the same file to confirm and commit the import.
    """
    template_name = 'room_incharge/purchase_import_upload.html'
    form_class = ExcelUploadForm

    def get_success_url(self):
        # After upload/preview we route back to the same upload page
        return reverse('room_incharge:purchase_import', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        upload_file = form.cleaned_data['file']
        # try to parse the uploaded Excel file
        try:
            excel = pd.ExcelFile(upload_file)
        except Exception as e:
            form.add_error('file', f'Invalid Excel file: {e}')
            return self.form_invalid(form)

        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        org = self.request.user.profile.org

        preview = {'items': [], 'purchases': [], 'errors': []}

        # ---------- Items sheet ----------
        if 'Items' in excel.sheet_names:
            try:
                df_items = excel.parse('Items')
            except Exception as e:
                preview['errors'].append(f"Could not read 'Items' sheet: {e}")
                df_items = None

            if df_items is not None:
                # Normalize columns (strip whitespace)
                df_items.columns = [str(c).strip() for c in df_items.columns]
                missing = [c for c in ITEMS_EXPECTED_COLS if c not in df_items.columns]
                if missing:
                    preview['errors'].append(f"'Items' sheet missing columns: {missing}")
                else:
                    # Validate rows and prepare sanitized preview row dicts
                    for idx, row in df_items.iterrows():
                        rownum = idx + 2  # Excel-like numbering
                        row_errors = []

                        # required minimal mapping
                        item_desc = str(row.get('Item Description', '')).strip()
                        category_name = str(row.get('Category', '')).strip()

                        if not item_desc:
                            row_errors.append('Item Description is empty.')
                        if not category_name:
                            row_errors.append('Category is empty.')

                        # numeric checks (gracefully collect errors)
                        try:
                            opening = float(row.get('Opening Stock Qty', 0) or 0)
                        except Exception:
                            opening = None
                            row_errors.append('Opening Stock Qty not a number.')
                        try:
                            arrival = float(row.get('Arrival / Receipts', 0) or 0)
                        except Exception:
                            arrival = None
                            row_errors.append('Arrival / Receipts not a number.')
                        try:
                            closing = float(row.get('Closing / Balance Qty', 0) or 0)
                        except Exception:
                            closing = None
                            row_errors.append('Closing / Balance Qty not a number.')

                        # sanitized mapping (keys without spaces for templates)
                        sanitized = {
                            'item_description': item_desc,
                            'category': category_name,
                            'opening': opening,
                            'arrival': arrival,
                            'total': row.get('Total', ''),
                            'closing': closing,
                            'uom': row.get('Unit of Measure', ''),
                            'remarks': row.get('Remarks', ''),
                        }

                        preview['items'].append({
                            'rownum': rownum,
                            'raw': row.to_dict(),
                            'sanitized': sanitized,
                            'errors': row_errors
                        })

        # ---------- Purchases sheet ----------
        if 'Purchases' in excel.sheet_names:
            try:
                df_pur = excel.parse('Purchases')
            except Exception as e:
                preview['errors'].append(f"Could not read 'Purchases' sheet: {e}")
                df_pur = None

            if df_pur is not None:
                df_pur.columns = [str(c).strip() for c in df_pur.columns]
                missing = [c for c in PURCHASES_EXPECTED_COLS if c not in df_pur.columns]
                if missing:
                    preview['errors'].append(f"'Purchases' sheet missing columns: {missing}")
                else:
                    for idx, row in df_pur.iterrows():
                        rownum = idx + 2
                        row_errors = []
                        item_desc = str(row.get('Item Description', '')).strip()
                        qty_val = row.get('Quantity', None)
                        if not item_desc:
                            row_errors.append('Item Description is empty.')
                        # numeric check for quantity
                        try:
                            qty = float(qty_val)
                        except Exception:
                            qty = None
                            row_errors.append('Quantity not a number.')

                        # Vendor (optional) - just pass through
                        vendor_name = str(row.get('Vendor', '')).strip()

                        sanitized = {
                            'date': row.get('Date of Purchase/Entry', ''),
                            'item_description': item_desc,
                            'category': row.get('Category', ''),
                            'model_code': row.get('Purchase ID/Model Code', ''),
                            'serial_no': row.get('Serial No', ''),
                            'quantity': qty,
                            'uom': row.get('Unit of Measure', ''),
                            'vendor': vendor_name,
                            'remarks': row.get('Remarks', ''),
                        }

                        preview['purchases'].append({
                            'rownum': rownum,
                            'raw': row.to_dict(),
                            'sanitized': sanitized,
                            'errors': row_errors
                        })

        # Save preview meta in session for reference (not raw file bytes)
        self.request.session['import_preview_meta'] = {
            'room_slug': self.kwargs['room_slug'],
            'has_errors': bool(preview['errors'] or any(r['errors'] for r in preview['items']) or any(r['errors'] for r in preview['purchases']))
        }

        # Render preview template
        room = get_object_or_404(Room, slug=self.kwargs['room_slug'])
        room_settings = RoomSettings.objects.get_or_create(room=room)[0]

        # Final return for preview page
        return render(
            self.request,
            "room_incharge/purchase_import_preview.html",
            {
                "room_slug": self.kwargs['room_slug'],
                "preview": preview,
                "has_errors": self.request.session['import_preview_meta']['has_errors'],

                # 👇 REQUIRED for sidebar (prevents the room_settings error)
                "room_settings": room_settings,
            }
        )

    def get_context_data(self, **kwargs):
        # Add room-related context (this avoids KeyError in templates)
        context = super().get_context_data(**kwargs)
        room_slug = self.kwargs['room_slug']
        
        room = get_object_or_404(Room, slug=room_slug)
        room_settings, _ = RoomSettings.objects.get_or_create(room=room)
        
        context['room_slug'] = room_slug
        context["room_settings"] = room_settings
        return context

# ---------- Confirm import view: commit to DB ----------
class PurchaseImportConfirmView(LoginRequiredMixin, FormView):
    """
    CONFIRM IMPORT VIEW
    -------------------
    User re-uploads the same Excel file.
    We re-parse + validate + commit into ALL sheets:
        Summary (optional)
        Categories
        Brands
        Items
        Systems
        Item Groups
        Purchases
        Issues

    Only necessary fixes have been applied:
      ✔ robust date parsing
      ✔ all sheet support
      ✔ room_settings always passed
      ✔ clean comments
      ✔ no layout break
    """

    template_name = "room_incharge/purchase_import_preview.html"
    form_class = ExcelUploadForm

    # ---------------------------------------------------------------------
    # UNIVERSAL DATE PARSER  (fixes “Oct. 06, 2025” issue)
    # ---------------------------------------------------------------------
    def parse_excel_date(self, val):
        """
        Converts ANY Excel date format (string or Excel timestamp) into python.date.
        Returns None if empty.
        Raises ValueError if format unknown.
        """
        if val in (None, "", float("nan")):
            return None

        # Excel datetime
        if isinstance(val, (datetime, date)):
            return val.date() if isinstance(val, datetime) else val

        # Convert using pandas (handles 99% of human formats)
        parsed = pd.to_datetime(str(val), errors="coerce")
        if pd.isna(parsed):
            raise ValueError(f"Invalid date format: {val}")

        return parsed.date()

    # ---------------------------------------------------------------------
    #                          MAIN CONFIRM LOGIC
    # ---------------------------------------------------------------------
    def form_valid(self, form):
        upload_file = form.cleaned_data["file"]

        try:
            excel = pd.ExcelFile(upload_file)
        except Exception as e:
            form.add_error("file", f"Invalid Excel file: {e}")
            return self.form_invalid(form)

        room = get_object_or_404(Room, slug=self.kwargs["room_slug"])
        org = self.request.user.profile.org

        # Always available for commit summary
        room_settings = RoomSettings.objects.get_or_create(room=room)[0]

        commit_errors = []

        # Generic brand fallback
        generic_brand, _ = Brand.objects.get_or_create(
            organisation=org, room=room, brand_name="Generic"
        )

        # Helper: get or create category -----------------------------------
        def get_or_create_category(name):
            name = str(name).strip()
            if not name:
                return None
            cat, _ = Category.objects.get_or_create(
                organisation=org,
                room=room,
                category_name=name
            )
            return cat

        # ---------------------------------------------------------------------
        # 1️⃣ SUMMARY SHEET (optional — no DB write required)
        # ---------------------------------------------------------------------
        if "Summary" in excel.sheet_names:
            try:
                df_summary = excel.parse("Summary")
            except Exception as e:
                commit_errors.append(f"Could not read 'Summary' sheet: {e}")

        # ---------------------------------------------------------------------
        # 2️⃣ CATEGORIES SHEET
        # ---------------------------------------------------------------------
        if "Categories" in excel.sheet_names:
            try:
                df_cat = excel.parse("Categories")
                df_cat.columns = [c.strip() for c in df_cat.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Categories' sheet: {e}")
                df_cat = None

            if df_cat is not None:
                for idx, row in df_cat.iterrows():
                    name = str(row.get("Category Name", "")).strip()
                    if not name:
                        commit_errors.append(
                            f"Categories row {idx+2}: Category Name missing."
                        )
                        continue
                    Category.objects.get_or_create(
                        organisation=org, room=room, category_name=name
                    )

        # ---------------------------------------------------------------------
        # 3️⃣ BRANDS SHEET
        # ---------------------------------------------------------------------
        if "Brands" in excel.sheet_names:
            try:
                df_brand = excel.parse("Brands")
                df_brand.columns = [c.strip() for c in df_brand.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Brands' sheet: {e}")
                df_brand = None

            if df_brand is not None:
                for idx, row in df_brand.iterrows():
                    name = str(row.get("Brand Name", "")).strip()
                    if not name:
                        commit_errors.append(f"Brands row {idx+2}: Brand Name missing.")
                        continue

                    Brand.objects.get_or_create(
                        organisation=org, room=room, brand_name=name
                    )

        # ---------------------------------------------------------------------
        # 4️⃣ ITEMS SHEET
        # ---------------------------------------------------------------------
        if "Items" in excel.sheet_names:
            try:
                df_items = excel.parse("Items")
                df_items.columns = [c.strip() for c in df_items.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Items' sheet: {e}")
                df_items = None

            if df_items is not None:
                for idx, row in df_items.iterrows():

                    item_desc = str(row.get("Item Description", "")).strip()
                    category_name = str(row.get("Category", "")).strip()

                    if not item_desc:
                        commit_errors.append(f"Items row {idx+2}: Missing Item Description.")
                        continue

                    arrival = int(row.get("Arrival / Receipts", 0) or 0)
                    closing = int(row.get("Closing / Balance Qty", arrival))

                    # Check if exists
                    item_qs = Item.objects.filter(
                        organisation=org, room=room,
                        item_name__iexact=item_desc
                    )

                    if item_qs.exists():
                        item = item_qs.first()
                    else:
                        cat = get_or_create_category(category_name)
                        if not cat:
                            commit_errors.append(f"Items row {idx+2}: Missing category.")
                            continue

                        Item.objects.create(
                            organisation=org,
                            department=room.department,
                            room=room,
                            category=cat,
                            brand=generic_brand,
                            item_name=item_desc[:255],
                            item_description=item_desc,
                            serial_number=str(row.get("Serial Number", ""))[:100],
                            purchase_model_code=str(row.get("Purchase Model Code", ""))[:100],
                            total_count=arrival,
                            available_count=closing,
                            is_listed=True
                        )

        # ---------------------------------------------------------------------
        # 5️⃣ SYSTEMS SHEET
        # ---------------------------------------------------------------------
        if "Systems" in excel.sheet_names:
            try:
                df_sys = excel.parse("Systems")
                df_sys.columns = [c.strip() for c in df_sys.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Systems' sheet: {e}")
                df_sys = None

            if df_sys is not None:
                for idx, row in df_sys.iterrows():
                    name = str(row.get("System Name", "")).strip()
                    status = str(row.get("Status", "")).strip()

                    if not name:
                        commit_errors.append(f"Systems row {idx+2}: Missing System Name.")
                        continue

                    System.objects.get_or_create(
                        organisation=org,
                        room=room,
                        system_name=name,
                        defaults={"status": status}
                    )

        # ---------------------------------------------------------------------
        # 6️⃣ ITEM GROUPS SHEET
        # ---------------------------------------------------------------------
        if "Item Groups" in excel.sheet_names:
            try:
                df_ig = excel.parse("Item Groups")
                df_ig.columns = [c.strip() for c in df_ig.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Item Groups' sheet: {e}")
                df_ig = None

            if df_ig is not None:
                for idx, row in df_ig.iterrows():
                    name = str(row.get("Item Group Name", "")).strip()
                    if not name:
                        commit_errors.append(f"Item Groups row {idx+2}: Missing name.")
                        continue

                    ItemGroup.objects.get_or_create(
                        organisation=org, room=room, item_group_name=name
                    )

        # ---------------------------------------------------------------------
        # 7️⃣ PURCHASES SHEET (with **robust date parser**)
        # ---------------------------------------------------------------------
        if "Purchases" in excel.sheet_names:
            try:
                df_pur = excel.parse("Purchases")
                df_pur.columns = [c.strip() for c in df_pur.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Purchases' sheet: {e}")
                df_pur = None

            if df_pur is not None:
                for idx, row in df_pur.iterrows():

                    item_desc = str(row.get("Item Description", "")).strip()
                    if not item_desc:
                        commit_errors.append(f"Purchases row {idx+2}: Missing item.")
                        continue

                    qty = float(row.get("Quantity", 0) or 0)
                    vendor_name = str(row.get("Vendor", "")).strip()

                    try:
                        purchase_date = self.parse_excel_date(row.get("Date of Purchase/Entry"))
                    except Exception as e:
                        commit_errors.append(f"Purchases row {idx+2}: Invalid date ({e}).")
                        continue

                    # Get item
                    item = Item.objects.filter(
                        organisation=org, room=room,
                        item_name__iexact=item_desc
                    ).first()

                    if not item:
                        cat = get_or_create_category(row.get("Category", "Uncategorized"))
                        item = Item.objects.create(
                            organisation=org,
                            department=room.department,
                            room=room,
                            category=cat,
                            brand=generic_brand,
                            item_name=item_desc[:255],
                            item_description=item_desc,
                            total_count=qty,
                            available_count=qty,
                            is_listed=True
                        )

                    # Vendor
                    vendor = Vendor.objects.filter(
                        organisation=org
                    ).first()

                    if not vendor:
                        raise ValidationError("At least one vendor must exist")
                    

                    Purchase.objects.create(
                        organisation=org,
                        room=room,
                        item=item,
                        quantity=qty,
                        unit_of_measure=row.get("Unit of Measure", "units"),
                        vendor=vendor,
                        purchase_date=purchase_date,
                        remarks=str(row.get("Remarks", "")),
                        status="requested"
                    )

        # ---------------------------------------------------------------------
        # 8️⃣ ISSUES SHEET
        # ---------------------------------------------------------------------
        if "Issues" in excel.sheet_names:
            try:
                df_iss = excel.parse("Issues")
                df_iss.columns = [c.strip() for c in df_iss.columns]
            except Exception as e:
                commit_errors.append(f"Could not read 'Issues' sheet: {e}")
                df_iss = None

            if df_iss is not None:
                for idx, row in df_iss.iterrows():
                    subject = str(row.get("Subject", "")).strip()
                    description = str(row.get("Description", "")).strip()

                    if not subject:
                        commit_errors.append(f"Issues row {idx+2}: Missing Subject.")
                        continue

                    Issue.objects.create(
                        organisation=org,
                        room=room,
                        subject=subject,
                        description=description,
                        resolved=bool(row.get("Resolved", False))
                    )

        # ---------------------------------------------------------------------
        # FINAL: SHOW ERRORS OR SUCCESS
        # ---------------------------------------------------------------------
        if commit_errors:
            messages.error(self.request, "Some rows failed to import.")
            return render(
                self.request,
                "room_incharge/purchase_import_preview.html",
                {
                    "room_slug": room.slug,
                    "preview": {"items": [], "purchases": [], "errors": commit_errors},
                    "has_errors": True,
                    "room_settings": room_settings,   # FIX: always passed
                },
            )

        messages.success(self.request, "Import completed successfully.")
        return redirect("room_incharge:purchase_list", room_slug=room.slug)

    # -------------------------------------------------------------------------
    # REQUIRED: room_settings in get_context_data to avoid sidebar crash
    # -------------------------------------------------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = get_object_or_404(Room, slug=self.kwargs["room_slug"])
        context["room_slug"] = room.slug
        context["room_settings"] = RoomSettings.objects.get_or_create(room=room)[0]
        return context



class PurchaseCompleteView(LoginRequiredMixin, FormView):
    template_name = 'room_incharge/purchase_complete.html'
    form_class = PurchaseCompleteForm
    success_url = reverse_lazy('room_incharge:purchase_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:purchase_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        purchase = Purchase.objects.get(slug=self.kwargs['purchase_slug'])
        receipt = form.save(commit=False)
        receipt.purchase = purchase
        receipt.org = self.request.user.profile.org
        receipt.save()
        purchase.status = 'completed'
        purchase.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['purchase_slug'] = self.kwargs['purchase_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class PurchaseAddToStockView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        purchase = get_object_or_404(Purchase, slug=self.kwargs['purchase_slug'])
        if purchase.status == 'completed' and not purchase.added_to_stock:
            item = purchase.item
            item.total_count += purchase.quantity
            item.available_count += purchase.quantity
            if not item.is_listed:
                item.is_listed = True
            item.save()
            purchase.added_to_stock = True
            purchase.save()
            messages.success(request, f"Added {purchase.quantity} {purchase.unit_of_measure} to {item.item_name} stock.")
        return redirect('room_incharge:purchase_list', room_slug=self.kwargs['room_slug'])


from django.core.exceptions import PermissionDenied

class IssueListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/issue_list.html'
    model = Issue
    context_object_name = 'issues'
    paginate_by = 50

    def get_room(self):
        room = get_object_or_404(Room, slug=self.kwargs["room_slug"])
        profile = self.request.user.profile

        # Allow if:
        # 1. Same organisation
        # 2. User is the room incharge
        # 3. User is sub admin / central admin
        if (
            room.organisation == profile.org
            or room.incharge == profile
            or profile.is_sub_admin
            or profile.is_central_admin
        ):
            return room

        raise PermissionDenied("You do not have access to this room")


    def get_queryset(self):
        room = self.get_room()
        return Issue.objects.filter(
            room=room
        ).order_by('-created_on')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.get_room()

        room_settings, _ = RoomSettings.objects.get_or_create(room=room)

        context.update({
            'room': room,
            'room_slug': room.slug,
            'room_settings': room_settings,
        })
        return context


# ---- action views (POST-only) ----
class MarkInProgressView(LoginRequiredMixin, View):
    def post(self, request, room_slug, pk):
        profile = request.user.profile

        # Ensure room exists & user is incharge
        room = get_object_or_404(Room, slug=room_slug, organisation=profile.org)
        if room.incharge != profile:
            return HttpResponseForbidden("You are not allowed to update this issue.")

        # Get issue belonging to this room
        issue = get_object_or_404(Issue, pk=pk, room=room)

        # Update status
        issue.status = "in_progress"
        issue.resolved = False
        issue.escalation_level = 0
        issue.updated_on = timezone.now()

        issue.save(update_fields=["status", "resolved", "escalation_level", "updated_on"])

        messages.success(request, f"Issue {issue.ticket_id} marked as IN PROGRESS.")
        return redirect("room_incharge:issue_list", room_slug=room.slug)


class MarkResolvedView(LoginRequiredMixin, View):
    """
    POST: mark issue as resolved/closed.
    """
    def post(self, request, room_slug, pk):
        room = get_object_or_404(Room, slug=room_slug, organisation=request.user.profile.org)
        issue = get_object_or_404(Issue, pk=pk, room=room)

        issue.status = "closed"
        issue.resolved = True
        issue.save(update_fields=["status", "resolved", "updated_on"])
        return redirect('room_incharge:issue_list', room_slug=room.slug)


class MarkUnresolvedView(LoginRequiredMixin, View):
    """
    POST: reopen the issue (set to open and unresolved).
    """
    def post(self, request, room_slug, pk):
        room = get_object_or_404(Room, slug=room_slug, organisation=request.user.profile.org)
        issue = get_object_or_404(Issue, pk=pk, room=room)

        issue.status = "open"
        issue.resolved = False
        issue.save(update_fields=["status", "resolved", "updated_on"])
        return redirect('room_incharge:issue_list', room_slug=room.slug)

class ItemGroupListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/item_group_list.html'
    model = ItemGroup
    context_object_name = 'item_groups'

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ItemGroupCreateView(LoginRequiredMixin, CreateView):
    model = ItemGroup
    template_name = 'room_incharge/item_group_create.html'
    form_class = ItemGroupForm
    success_url = reverse_lazy('room_incharge:item_group_list')

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_group_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        item_group = form.save(commit=False)
        item_group.organisation = self.request.user.profile.org
        item_group.room = Room.objects.get(slug=self.kwargs['room_slug'])
        item_group.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ItemGroupItemCreateView(LoginRequiredMixin, CreateView):
    model = ItemGroupItem
    template_name = 'room_incharge/item_group_item_create.html'
    form_class = ItemGroupItemForm

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_group_item_list', kwargs={'room_slug': self.kwargs['room_slug'], 'item_group_slug': self.kwargs['item_group_slug']})
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        form.fields['item'].queryset = Item.objects.filter(room=room)
        return form

    def form_valid(self, form):
        item_group_item = form.save(commit=False)
        item_group_item.item_group = ItemGroup.objects.get(slug=self.kwargs['item_group_slug'])
        item = item_group_item.item

        # Adjust the available_count and in_use count of the associated Item
        item.available_count -= item_group_item.qty
        item.in_use += item_group_item.qty

        try:
            item_group_item.save()
            item.save()
        except ValueError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['room_slug'] = self.kwargs['room_slug']
        context['item_group_slug'] = self.kwargs['item_group_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ItemGroupItemListView(LoginRequiredMixin, ListView):
    template_name = 'room_incharge/item_group_item_list.html'
    model = ItemGroupItem
    context_object_name = 'item_group_items'

    def get_queryset(self):
        item_group_slug = self.kwargs['item_group_slug']
        return super().get_queryset().filter(item_group__slug=item_group_slug, item_group__organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['room_slug'] = self.kwargs['room_slug']
        context['item_group_slug'] = self.kwargs['item_group_slug']
        context['item_group'] = get_object_or_404(ItemGroup, slug=self.kwargs['item_group_slug'])
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ItemGroupUpdateView(LoginRequiredMixin, UpdateView):
    model = ItemGroup
    template_name = 'room_incharge/item_group_update.html'
    form_class = ItemGroupForm
    success_url = reverse_lazy('room_incharge:item_group_list')
    slug_field = 'slug'
    slug_url_kwarg = 'item_group_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_group_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def form_valid(self, form):
        item_group = form.save(commit=False)
        item_group.organisation = self.request.user.profile.org
        item_group.room = Room.objects.get(slug=self.kwargs['room_slug'])
        item_group.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

class ItemGroupDeleteView(LoginRequiredMixin, DeleteView):
    model = ItemGroup
    template_name = 'room_incharge/item_group_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'item_group_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_group_list', kwargs={'room_slug': self.kwargs['room_slug']})

    def get_queryset(self):
        room_slug = self.kwargs['room_slug']
        return super().get_queryset().filter(room__slug=room_slug, organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_slug'] = self.kwargs['room_slug']
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

class ItemGroupItemUpdateView(LoginRequiredMixin, UpdateView):
    model = ItemGroupItem
    template_name = 'room_incharge/item_group_item_update.html'
    form_class = ItemGroupItemForm
    slug_field = 'slug'
    slug_url_kwarg = 'item_group_item_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_group_item_list', kwargs={'room_slug': self.kwargs['room_slug'], 'item_group_slug': self.kwargs['item_group_slug']})

    def form_valid(self, form):
        item_group_item = form.save(commit=False)
        item = item_group_item.item
        old_qty = ItemGroupItem.objects.get(pk=item_group_item.pk).qty

        # Adjust the available_count and in_use count of the associated Item
        item.available_count += old_qty - item_group_item.qty
        item.in_use -= old_qty - item_group_item.qty
        item.save()

        item_group_item.save()
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['room_slug'] = self.kwargs['room_slug']
        context['item_group_slug'] = self.kwargs['item_group_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context


class ItemGroupItemDeleteView(LoginRequiredMixin, DeleteView):
    model = ItemGroupItem
    template_name = 'room_incharge/item_group_item_delete_confirm.html'
    slug_field = 'slug'
    slug_url_kwarg = 'item_group_item_slug'

    def get_success_url(self):
        return reverse_lazy('room_incharge:item_group_item_list', kwargs={'room_slug': self.kwargs['room_slug'], 'item_group_slug': self.kwargs['item_group_slug']})

    def get_queryset(self):
        return super().get_queryset().filter(item_group__slug=self.kwargs['item_group_slug'], item_group__organisation=self.request.user.profile.org)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['room_slug'] = self.kwargs['room_slug']
        context['item_group_slug'] = self.kwargs['item_group_slug']
        room = Room.objects.get(slug=self.kwargs['room_slug'])
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0]
        return context

    def dispatch(self, request, *args, **kwargs):
    # Room Incharge is permanently restricted from delete operations
        return HttpResponseForbidden("Delete operation is not allowed.")

class RoomSettingsView(LoginRequiredMixin, UpdateView):
    model = RoomSettings 
    template_name = 'room_incharge/room_settings.html' 
    form_class = RoomSettingsForm 
    success_url = reverse_lazy('room_incharge:room_dashboard') 
    
    def get_object(self): 
        room = get_object_or_404(Room, slug=self.kwargs['room_slug']) 
        return RoomSettings.objects.get_or_create(room=room)[0] 
    
    def get_success_url(self): 
        return reverse_lazy('room_incharge:room_settings', kwargs={'room_slug': self.kwargs['room_slug']}) 
    
    def get_context_data(self, **kwargs): 
        context = super().get_context_data(**kwargs) 
        context['room_slug'] = self.kwargs['room_slug'] 
        room = Room.objects.get(slug=self.kwargs['room_slug']) 
        context['room_settings'] = RoomSettings.objects.get_or_create(room=room)[0] 
        return context

class RoomReportView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        room_slug = self.kwargs['room_slug']
        room = get_object_or_404(Room, slug=room_slug)
        room_settings = RoomSettings.objects.get_or_create(room=room)[0]
        format_type = request.GET.get('format', 'pdf')  # dropdown choice

        # ---------------------------
        # Helper functions
        # ---------------------------
        def fmt_datetime(dt):
            """Format datetime similar to PDF's visual style."""
            if not dt:
                return ''
            if isinstance(dt, date) and not isinstance(dt, datetime):
                return dt.strftime('%b. %d, %Y')
            try:
                dt_local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
            except Exception:
                dt_local = dt
            hour = dt_local.strftime('%I').lstrip('0') or '0'
            minute = dt_local.strftime('%M')
            ampm = dt_local.strftime('%p')
            ampm = 'a.m.' if ampm == 'AM' else 'p.m.'
            return f"{dt_local.strftime('%b. %d, %Y')}, {hour}:{minute} {ampm}"

        def safe_str(value):
            if value is None:
                return ''
            try:
                return str(value)
            except Exception:
                return ''

        # ---------------------------
        # Build context
        # ---------------------------
        context = {
            'room': room,
            'room_settings': room_settings,
            'categories': Category.objects.filter(room=room) if room_settings.categories_tab else None,
            'brands': Brand.objects.filter(room=room) if room_settings.brands_tab else None,
            'items': Item.objects.filter(room=room) if room_settings.items_tab else None,
            'systems': System.objects.filter(room=room) if room_settings.systems_tab else None,
            'item_groups': ItemGroup.objects.filter(room=room) if room_settings.item_groups_tab else None,
            'system_components': SystemComponent.objects.filter(system__room=room) if room_settings.systems_tab else None,
            'purchases': Purchase.objects.filter(room=room),
            'issues': Issue.objects.filter(room=room),
        }

        # ---------------------------
        # Excel Generation
        # ---------------------------
        if format_type == 'excel':
            excel_buffer = io.BytesIO()

            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                #  1) Summary Sheet
                summary_rows = [{
                    'Room Name': room.room_name,
                    'Incharge': f"{room.incharge.first_name} {room.incharge.last_name}" if getattr(room, 'incharge', None) else '',
                    'Department': getattr(room.department, 'department_name', '') if getattr(room, 'department', None) else '',
                    'Created On': fmt_datetime(getattr(room, 'created_on', None)),
                    'Updated On': fmt_datetime(getattr(room, 'updated_on', None)),
                }]
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Summary', index=False)

                #  2) Categories
                if context['categories'] is not None and context['categories'].exists():
                    rows = [{
                        'Category Name': c.category_name,
                        'Created On': fmt_datetime(c.created_on),
                        'Updated On': fmt_datetime(c.updated_on)
                    } for c in context['categories']]
                    pd.DataFrame(rows).to_excel(writer, sheet_name='Categories', index=False)

                #  3) Brands
                if context['brands'] is not None and context['brands'].exists():
                    rows = [{
                        'Brand Name': b.brand_name,
                        'Created On': fmt_datetime(b.created_on),
                        'Updated On': fmt_datetime(b.updated_on)
                    } for b in context['brands']]
                    pd.DataFrame(rows).to_excel(writer, sheet_name='Brands', index=False)

                # --------------------------------------------------------------
                # 🧾 4) ITEMS SHEET  — matches stock register format exactly
                # --------------------------------------------------------------
                if context['items'] is not None and context['items'].exists():
                    item_rows = []
                    for i, item in enumerate(context['items'], start=1):
                        opening_stock = max(item.total_count - item.available_count, 0)
                        arrival = getattr(item, 'arrival_receipts', 0)
                        consumed = getattr(item, 'consumed_stock_qty', 0)
                        closing = item.available_count
                        total = opening_stock + arrival
                        item_rows.append({
                            'Sl No': i,
                            'Date of Entry': fmt_datetime(item.created_on),
                            'Item Description': item.item_description or item.item_name,
                            'Category': safe_str(getattr(item.category, 'category_name', '')),
                            'Opening Stock Qty': opening_stock,
                            'Arrival / Receipts': arrival,
                            'Total': total,
                            'Consumed Stock/Issues Qty': consumed,
                            'Closing / Balance Qty': closing,
                            'Unit of Measure': getattr(item, 'unit_of_measure', 'Units'),
                            'Remarks': getattr(item, 'remarks', ''),
                        })
                    pd.DataFrame(item_rows).to_excel(writer, sheet_name='Items', index=False)

                #  5) Systems
                if context['systems'] is not None and context['systems'].exists():
                    rows = [{
                        'System Name': s.system_name,
                        'Status': s.status,
                        'Created On': fmt_datetime(s.created_on),
                        'Updated On': fmt_datetime(s.updated_on)
                    } for s in context['systems']]
                    pd.DataFrame(rows).to_excel(writer, sheet_name='Systems', index=False)

                #  6) System Components
                if context['system_components'] is not None and context['system_components'].exists():
                    rows = [{
                        'System': safe_str(c.system),
                        'Component Type': c.component_type,
                        'Component Item': safe_str(c.component_item),
                        'Serial Number': getattr(c, 'serial_number', ''),
                        'Created On': fmt_datetime(c.created_on),
                        'Updated On': fmt_datetime(c.updated_on),
                    } for c in context['system_components']]
                    pd.DataFrame(rows).to_excel(writer, sheet_name='System Components', index=False)

                # 7) Item Groups
                if context['item_groups'] is not None and context['item_groups'].exists():
                    rows = [{
                        'Item Group Name': g.item_group_name,
                        'Created On': fmt_datetime(g.created_on),
                        'Updated On': fmt_datetime(g.updated_on)
                    } for g in context['item_groups']]
                    pd.DataFrame(rows).to_excel(writer, sheet_name='Item Groups', index=False)

                # --------------------------------------------------------------
                # 💰 8) PURCHASES SHEET — matches purchase register format exactly
                # --------------------------------------------------------------
                if context['purchases'] is not None and context['purchases'].exists():
                    purchase_rows = []
                    for i, p in enumerate(context['purchases'], start=1):
                        purchase_rows.append({
                            'Sl No': i,
                            'Date of Purchase/Entry': fmt_datetime(p.purchase_date) or fmt_datetime(p.date_of_entry),
                            'Item Description': safe_str(getattr(p.item, 'item_description', p.item_description)),
                            'Category': safe_str(getattr(p.item.category, 'category_name', '')) if getattr(p, 'item', None) else '',
                            'Purchase ID/Model Code': p.purchase_id or safe_str(getattr(p.item, 'purchase_model_code', '')),
                            'Serial No': safe_str(getattr(p.item, 'serial_number', '')),
                            'Quantity': p.quantity,
                            'Unit of Measure': p.unit_of_measure,
                            'Status': p.status,
                            'Vendor': safe_str(getattr(p.vendor, 'vendor_name', '')) if p.vendor else '',
                            'Remarks': safe_str(p.remarks),
                        })
                    pd.DataFrame(purchase_rows).to_excel(writer, sheet_name='Purchases', index=False)

                # 9) Issues
                if context['issues'] is not None and context['issues'].exists():
                    rows = [{
                        'Subject': iss.subject,
                        'Description': iss.description,
                        'Resolved': 'Resolved' if iss.resolved else 'Unresolved',
                        'Created On': fmt_datetime(iss.created_on),
                        'Updated On': fmt_datetime(iss.updated_on)
                    } for iss in context['issues']]
                    pd.DataFrame(rows).to_excel(writer, sheet_name='Issues', index=False)

            excel_buffer.seek(0)
            response = HttpResponse(
                excel_buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{room.room_name}_report.xlsx"'
            return response

        # ---------------------------
        # Default PDF generation
        # ---------------------------
        html_string = render_to_string('room_incharge/room_report.html', context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{room.room_name}_report.pdf"'
        return response
