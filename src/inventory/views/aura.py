import json, csv, io
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
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
    
    qs = model.objects.all().order_by('-id')

    # Apply Date Filtering across all applicable modules
    if date_from and date_to:
        if model_name == 'bookings':
            qs = qs.filter(start_datetime__date__range=[date_from, date_to])
        elif model_name in ['issues', 'items', 'rooms', 'purchases']:
            qs = qs.filter(created_on__date__range=[date_from, date_to])

    data = []
    for obj in qs:
        row = {'id': obj.id}
        try:
            if model_name == 'rooms':
                row['label_head'] = "Room"
                row['label'] = f"{obj.room_name}<br><small>Incharge: {obj.incharge}</small>"
                row['detail_head'] = "Metadata"
                row['detail'] = f"Category: {obj.get_room_category_display()} | Capacity: {obj.capacity}"
            elif model_name == 'bookings':
                # Report Generator Fields (Multi-line)
                row['label_head'] = "Room Booked"
                row['label'] = f"{obj.faculty_name}<br><small>{obj.faculty_email}</small>"
                row['detail_head'] = "Metadata"
                start_local = timezone.localtime(obj.start_datetime)
                row['detail'] = f"Room: {obj.room.room_name}<br>Date: {start_local.strftime('%d %b, %Y')}<br>Time: {start_local.strftime('%H:%M')}"
                
                # SPECIFIC KEYS FOR ROOM BOOKING MANAGER MODAL
                row['room_name'] = obj.room.room_name
                row['faculty_name'] = obj.faculty_name
                row['faculty_email'] = obj.faculty_email
                row['schedule'] = f"{start_local.strftime('%d %b, %Y')} | {start_local.strftime('%H:%M')}"
            elif model_name == 'issues':
                row['label_head'] = "Issue"
                row['label'] = f"{obj.subject}"
                row['detail_head'] = "Metadata"
                assigned = obj.assigned_to.user.get_full_name() if obj.assigned_to else "N/A"
                row['detail'] = f"Email: {obj.reporter_email}<br>Ticket ID: {obj.ticket_id}<br>Status: {obj.status}<br>Room: {obj.room.room_name}<br>Assigned: {assigned}"
            elif model_name == 'items':
                row['label_head'] = "Items"
                row['label'] = f"{obj.item_name}"
                row['detail_head'] = "Metadata"
                row['detail'] = f"Room: {obj.room.room_name}<br>Qty: {obj.total_count}<br>Available: {obj.available_count}<br>In Use: {obj.in_use}"
            elif model_name == 'purchases':
                row['label_head'] = "Purchase ID"
                row['label'] = f"{obj.purchase_id or 'N/A'}<br>Room: {obj.room.room_name}"
                row['detail_head'] = "Metadata"
                row['detail'] = f"Vendor: {obj.vendor.vendor_name if obj.vendor else 'N/A'}<br>Status: {obj.status}"
            elif model_name == 'vendors':
                row['label_head'] = "Vendors"
                row['label'] = f"{obj.vendor_name}"
                row['detail_head'] = "Metadata"
                row['detail'] = f"Email: {obj.email}<br>Contact: {obj.contact_number}"
            elif model_name == 'departments':
                row['label_head'] = "Department/Cell/Office"
                row['label'] = f"{obj.department_name}"
                row['detail_head'] = "Metadata"
                room_count = Room.objects.filter(department=obj).count()
                row['detail'] = f"Total Rooms: {room_count}"
            else:
                row['label_head'] = "Primary Record"
                row['label'] = str(obj)
                row['detail_head'] = "Metadata / Details"
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
    qs = model.objects.all().order_by('id')
    if date_from and date_to:
        if model_name == 'bookings':
            qs = qs.filter(start_datetime__date__range=[date_from, date_to])
        elif model_name in ['issues', 'items', 'rooms', 'purchases']:
            qs = qs.filter(created_on__date__range=[date_from, date_to])
    

    # 3. Setup PDF Buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph(f"Blixtro - Aura Generated Report: {model_name.upper()}", styles['Title']))
    elements.append(Spacer(1, 12))

    # Dynamic Headers
    headers = ["ID", "Record", "Metadata"]
    if model_name == 'rooms': headers = ["ID", "Room", "Metadata"]
    elif model_name == 'bookings': headers = ["ID", "Room Booked", "Metadata"]
    elif model_name == 'issues': headers = ["ID", "Issue", "Metadata"]
    elif model_name == 'items': headers = ["ID", "Items", "Metadata"]
    elif model_name == 'purchases': headers = ["ID", "Purchase ID", "Metadata"]
    elif model_name == 'vendors': headers = ["ID", "Vendors", "Metadata"]
    elif model_name == 'departments': headers = ["ID", "Department/Cell/Office", "Metadata"]
    
    report_data = [headers]
    
    # Efficiently loop through large data
    for obj in qs.iterator():
        # Replicate label/detail logic from aura_data_manager
        label = str(obj)
        detail = "General Record"
        
        try:
            if model_name == 'rooms':
                label = f"{obj.room_name}<br/>Incharge: {obj.incharge}"
                detail = f"Category: {obj.get_room_category_display()}<br/>Capacity: {obj.capacity}"
            elif model_name == 'bookings':
                label = f"{obj.faculty_name}<br/>{obj.faculty_email}"
                start_local = timezone.localtime(obj.start_datetime)
                detail = f"Room: {obj.room.room_name}<br/>Date: {start_local.strftime('%d %b, %Y')}<br/>Time: {start_local.strftime('%H:%M')}"
            elif model_name == 'issues':
                label = f"{obj.subject}"
                assigned = obj.assigned_to.user.get_full_name() if obj.assigned_to else "N/A"
                detail = f"Email: {obj.reporter_email}<br/>Ticket ID: {obj.ticket_id}<br/>Status: {obj.status}<br/>Room: {obj.room.room_name}<br/>Assigned: {assigned}"
            elif model_name == 'items':
                label = f"{obj.item_name}"
                detail = f"Room: {obj.room.room_name}<br/>Qty: {obj.total_count}<br/>Available: {obj.available_count}<br/>In Use: {obj.in_use}"
            elif model_name == 'purchases':
                label = f"{obj.purchase_id or 'N/A'}<br/>Room: {obj.room.room_name}"
                detail = f"Vendor: {obj.vendor.vendor_name if obj.vendor else 'N/A'}<br/>Status: {obj.status}"
            elif model_name == 'vendors':
                label = f"{obj.vendor_name}"
                detail = f"Email: {obj.email}<br/>Contact: {obj.contact_number}"
            elif model_name == 'departments':
                label = f"{obj.department_name}"
                room_count = Room.objects.filter(department=obj).count()
                detail = f"Total Rooms: {room_count}"
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

@require_POST
def aura_bulk_delete(request):
    """
    Bulk delete records for a specific model based on a list of IDs.
    """
    if not request.user.profile.is_central_admin:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        model_name = data.get('model')
        record_ids = data.get('ids', []) # Expects a list of IDs
        
        model_map = {
            'issues': Issue, 
            'items': Item, 
            'rooms': Room, 
            'bookings': RoomBooking,
            'purchases': Purchase
        }
        
        model = model_map.get(model_name)
        if not model or not record_ids:
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
            
        # Filter records belonging to the user's organization and delete
        if model_name == 'rooms':
            qs = model.objects.filter(id__in=record_ids, organisation=request.user.profile.org)
        elif hasattr(model, 'room'):
            qs = model.objects.filter(id__in=record_ids, room__organisation=request.user.profile.org)
        else:
            qs = model.objects.filter(id__in=record_ids, organisation=request.user.profile.org)
            
        count = qs.count()
        qs.delete()
        
        return JsonResponse({'status': 'success', 'deleted_count': count})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)