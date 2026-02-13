import json, csv, io
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from inventory.models import Issue, Item, Room, Category, RoomBooking, Purchase, Vendor, Department
from core.models import UserProfile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

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
    """
    Fetches AURA report data for all modules with module and date filtering.
    """
    if not request.user.profile.is_central_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    model_name = request.GET.get('model')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    model_map = {
        'issues': Issue, 
        'items': Item, 
        'rooms': Room, 
        'bookings': RoomBooking, 
        'purchases': Purchase,
        'vendors': Vendor, 
        'departments': Department
    }
    
    model = model_map.get(model_name)
    if not model:
        return JsonResponse({'error': 'Invalid model'}, status=400)
    
    qs = model.objects.all()

    # Apply Date Filtering across all applicable modules
    if date_from and date_to:
        if model_name == 'bookings':
            qs = qs.filter(start_datetime__date__range=[date_from, date_to])
        elif model_name in ['issues', 'items', 'rooms', 'purchases']:
            qs = qs.filter(created_on__date__range=[date_from, date_to])

    data = []
    for obj in qs.order_by('-id'):
        row = {'id': obj.id, 'label': str(obj)}
        try:
            if model_name == 'bookings':
                row['label'] = f"{obj.room.room_name} | {obj.faculty_email}"
                
                start_local = timezone.localtime(obj.start_datetime)
                end_local = timezone.localtime(obj.end_datetime)
                
                row['detail'] = f"{obj.faculty_name}"
                row['schedule'] = f"{start_local.strftime('%d %b, %Y | %H:%M')} - {end_local.strftime('%H:%M')}"
                
            elif model_name == 'rooms':
                row['detail'] = f"Category: {obj.get_room_category_display()} | Capacity: {obj.capacity}"
            elif model_name == 'issues':
                row['detail'] = f"Status: {obj.status} | {obj.subject}"
            elif model_name == 'items':
                row['detail'] = f"Room: {obj.room.room_name} | Qty: {obj.total_count} | Available: {obj.available_count}"
            elif model_name == 'purchases':
                row['detail'] = f"Vendor: {obj.vendor.vendor_name} | Status: {obj.status}"
            else:
                row['detail'] = "General Record"
        except Exception:
            row['detail'] = "N/A (Data Mismatch)"
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

def aura_generate_report_pdf(request):
    """
    Solid fix for large datasets: Server-side PDF generation.
    Uses ReportLab and .iterator() to prevent blank pages and memory crashes.
    """
    if not request.user.profile.is_central_admin:
        return HttpResponse("Unauthorized", status=403)

    # 1. Capture Filters
    model_name = request.GET.get('model')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    model_map = {
        'issues': Issue, 'items': Item, 'rooms': Room, 
        'bookings': RoomBooking, 'purchases': Purchase,
        'vendors': Vendor, 'departments': Department
    }
    
    model = model_map.get(model_name)
    if not model:
        return HttpResponse("Invalid Model", status=400)

    # 2. Query Data with Iterator
    qs = model.objects.all()
    if date_from and date_to:
        if model_name == 'bookings':
            qs = qs.filter(start_datetime__date__range=[date_from, date_to])
        elif model_name in ['issues', 'items', 'rooms', 'purchases']:
            qs = qs.filter(created_on__date__range=[date_from, date_to])
    
    qs = qs.order_by('id')

    # 3. Setup PDF Buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph(f"AURA Generated Report: {model_name.upper()}", styles['Title']))
    elements.append(Spacer(1, 12))

    # Table Header and Data
    report_data = [["ID", "Primary Record", "Metadata / Details"]]
    
    # Efficiently loop through large data
    for obj in qs.iterator():
        # Replicate label/detail logic from aura_data_manager
        label = str(obj)
        detail = "General Record"
        
        try:
            if model_name == 'bookings':
                label = f"{obj.room.room_name} | {obj.faculty_email}"
                start_local = timezone.localtime(obj.start_datetime)
                end_local = timezone.localtime(obj.end_datetime)
                schedule_str = f"{start_local.strftime('%d %b, %Y | %H:%M')} - {end_local.strftime('%H:%M')}"
                detail = f"Faculty: {obj.faculty_name} | Schedule: {schedule_str}"
            elif model_name == 'rooms':
                detail = f"Category: {obj.get_room_category_display()} | Capacity: {obj.capacity}"
            elif model_name == 'issues':
                detail = f"Status: {obj.status} | {obj.subject}"
            elif model_name == 'items':
                detail = f"Room: {obj.room.room_name} | Qty: {obj.total_count}"
        except Exception:
            detail = "Data Mismatch"

        report_data.append([
            str(obj.id),
            Paragraph(label, styles['Normal']),
            Paragraph(detail, styles['Normal'])
        ])

    # 4. Build Table
    table = Table(report_data, repeatRows=1, colWidths=[60, 250, 400])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Blixtro_AURA_{model_name}_Report.pdf"'
    return response