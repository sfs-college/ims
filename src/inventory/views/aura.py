import json
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from inventory.models import Issue, Item, Room, Category, RoomBooking, Purchase, Vendor, Department
from core.models import UserProfile

class CentralAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        profile = getattr(self.request.user, 'profile', None)
        return profile and profile.is_central_admin and not profile.is_sub_admin

class AuraDashboardView(LoginRequiredMixin, CentralAdminRequiredMixin, TemplateView):
    template_name = 'central_admin/aura_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.request.user.profile.org
        
        # Accurate Global Organizational Counts
        context['total_issues'] = Issue.objects.all().count()
        context['escalated_count'] = Issue.objects.filter(status='escalated').count()
        context['total_items'] = Item.objects.all().count()
        
        # Defensive check for RoomBookings to prevent crashes if columns are missing
        try:
            context['active_bookings'] = RoomBooking.objects.filter(
                room__organisation=org, 
                end_datetime__gte=timezone.now()
            ).count()
        except Exception:
            context['active_bookings'] = 0
            
        return context

def aura_analytics_data(request):
    if not request.user.profile.is_central_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    org = request.user.profile.org
    
    # Live data for Charts
    issue_stats = Issue.objects.all().values('status').annotate(count=Count('id'))
    category_stats = Item.objects.all().values('category__category_name').annotate(count=Count('id'))
    
    total_rooms = Room.objects.all().count()
    booked_today = 0
    
    # Defensive query for Room Utilization
    try:
        booked_today = RoomBooking.objects.filter(
            # room__organisation=org,
            start_datetime__date=timezone.now().date()
        ).values('room').distinct().count()
    except Exception:
        pass 

    return JsonResponse({
        'issue_labels': [s['status'].replace('_', ' ').title() for s in issue_stats],
        'issue_series': [s['count'] for s in issue_stats],
        'cat_labels': [s['category__category_name'] for s in category_stats],
        'cat_series': [s['count'] for s in category_stats],
        'room_util': [booked_today, max(0, total_rooms - booked_today)]
    })

def aura_data_manager(request):
    if not request.user.profile.is_central_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    model_name = request.GET.get('model')
    org = request.user.profile.org
    
    model_map = {
        'issues': Issue, 'items': Item, 'rooms': Room, 
        'bookings': RoomBooking, 'purchases': Purchase,
        'vendors': Vendor, 'departments': Department
    }
    
    model = model_map.get(model_name)
    if not model:
        return JsonResponse({'error': 'Invalid model'}, status=400)
    
    # Corrected filter logic strictly by Organisation
    if model_name == 'rooms':
        qs = model.objects.all()
    elif model_name in ['items', 'bookings']:
        qs = model.objects.all()
    else:
        qs = model.objects.all()
        
    data = []
    for obj in qs.order_by('-id'):
        row = {'id': obj.id, 'label': str(obj)}
        try:
            if model_name == 'bookings':
                row['detail'] = f"Faculty: {obj.faculty_name} | Start: {obj.start_datetime.strftime('%H:%M')}"
            elif model_name == 'issues':
                row['detail'] = f"Status: {obj.status} | {obj.subject}"
            elif model_name == 'items':
                row['detail'] = f"Room: {obj.room.room_name} | Qty: {obj.total_count}"
            else:
                row['detail'] = "General Record"
        except Exception:
            row['detail'] = "N/A (Database Mismatch)"
        data.append(row)
        
    return JsonResponse({'results': data})

def aura_delete_record(request):
    if request.method == 'POST' and request.user.profile.is_central_admin:
        data = json.loads(request.body)
        model_name = data.get('model')
        record_id = data.get('id')
        
        model_map = {'issues': Issue, 'items': Item, 'rooms': Room, 'bookings': RoomBooking}
        model = model_map.get(model_name)
        obj = get_object_or_404(model, id=record_id)
        
        # Ownership check
        is_owner = False
        if model_name == 'rooms' and obj.organisation == request.user.profile.org:
            is_owner = True
        elif hasattr(obj, 'room') and obj.room.organisation == request.user.profile.org:
            is_owner = True
        elif hasattr(obj, 'organisation') and obj.organisation == request.user.profile.org:
            is_owner = True
            
        if is_owner:
            obj.delete()
            return JsonResponse({'status': 'success'})
            
    return JsonResponse({'status': 'error'}, status=403)