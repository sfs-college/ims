from django.urls import path
from inventory.views import central_admin, aura

app_name = 'central_admin'

urlpatterns = [
    path('', central_admin.DashboardView.as_view(), name='dashboard'),
    path('people/', central_admin.PeopleListView.as_view(), name='people_list'),
    path('people/create/', central_admin.PeopleCreateView.as_view(), name='people_create'),
    path('people/<slug:people_slug>/delete/', central_admin.PeopleDeleteView.as_view(), name='people_delete'),
    path('rooms/', central_admin.RoomListView.as_view(), name='room_list'),
    path('rooms/create/', central_admin.RoomCreateView.as_view(), name='room_create'),
    path('rooms/<slug:room_slug>/delete/', central_admin.RoomDeleteView.as_view(), name='room_delete'),
    path('rooms/<slug:room_slug>/update/', central_admin.RoomUpdateView.as_view(), name='room_update'),
    path('vendors/', central_admin.VendorListView.as_view(), name='vendor_list'),
    path('vendors/create/', central_admin.VendorCreateView.as_view(), name='vendor_create'),
    path('vendors/<slug:vendor_slug>/update/', central_admin.VendorUpdateView.as_view(), name='vendor_update'),
    path('vendors/<slug:vendor_slug>/delete/', central_admin.VendorDeleteView.as_view(), name='vendor_delete'),
    path('purchases/', central_admin.PurchaseListView.as_view(), name='purchase_list'),
    path('purchases/<slug:purchase_slug>/approve/', central_admin.PurchaseApproveView.as_view(), name='purchase_approve'),
    path('purchases/<slug:purchase_slug>/decline/', central_admin.PurchaseDeclineView.as_view(), name='purchase_decline'),
    path('issues/', central_admin.IssueListView.as_view(), name='issue_list'),
    path('departments/', central_admin.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', central_admin.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<slug:department_slug>/delete/', central_admin.DepartmentDeleteView.as_view(), name='department_delete'),
    #Issue Resolving by admin
    path("issues/<int:pk>/resolve/", central_admin.admin_resolve_issue, name="resolve_issue"),
    path("issues/<int:pk>/unresolve/", central_admin.admin_unresolve_issue, name="unresolve_issue"),
    path("issues/<int:pk>/deescalate/",central_admin.admin_deescalate_issue, name="deescalate_issue"),
    
    path(
        "approval-requests/",
        central_admin.ApprovalRequestListView.as_view(),
        name="approval_requests",
    ),

    # Issue time extension approvals
    path(
        "issue-time-extension/<int:pk>/approve/",
        central_admin.ApproveIssueTimeExtensionView.as_view(),
        name="approve_issue_time_extension",
    ),
    path(
        "issue-time-extension/<int:pk>/reject/",
        central_admin.RejectIssueTimeExtensionView.as_view(),
        name="reject_issue_time_extension",
    ),
    path('aura/', aura.AuraDashboardView.as_view(), name='aura_dashboard'),
    path('aura/api/analytics/', aura.aura_analytics_data, name='aura_api_analytics'),
    path('aura/api/data-manager/', aura.aura_data_manager, name='aura_api_data'),
    path('aura/api/delete/', aura.aura_delete_record, name='aura_api_delete'),
    path('aura/api/generate-pdf/', aura.aura_generate_report_pdf, name='aura_api_pdf'),
    path('aura/api/bulk-delete/', aura.aura_bulk_delete, name='aura_api_bulk_delete'),
    
    path('aura/api/generate-excel/', aura.aura_generate_report_excel, name='aura_api_excel'),
    path('master-inventory/import/', aura.MasterInventoryImportView.as_view(), name='master_inventory_import'),
    path('master-inventory/import/confirm/', aura.MasterInventoryImportConfirmView.as_view(), name='master_inventory_import_confirm'),
    path('master-inventory/', aura.MasterInventoryListView.as_view(), name='master_inventory_list'),
    path('api/rooms-by-category/', aura.get_rooms_by_category, name='get_rooms_by_category'),
    path('api/assignment-details/', aura.get_assignment_details, name='get_assignment_details'),
    path('master-inventory/assign/', aura.AssignInventoryView.as_view(), name='assign_inventory'),
    path('api/assign-inventory/', aura.assign_inventory_api, name='assign_inventory_api'),
    path('api/master-items/', aura.get_master_items_api, name='get_master_items_api'),
    
    path('aura/credentials/<int:pk>/delete/', aura.credential_delete, name='credential_delete'),
    path('aura/credentials/<int:pk>/update/', aura.credential_update, name='credential_update'),
    path('approvals/booking-request/<int:pk>/approve/', central_admin.ApproveRoomBookingRequestView.as_view(), name='approve_room_booking_request'),
    path('approvals/booking-request/<int:pk>/reject/',  central_admin.RejectRoomBookingRequestView.as_view(),  name='reject_room_booking_request'),
    path('approvals/cancel-request/<int:pk>/approve/',  central_admin.ApproveCancellationRequestView.as_view(), name='approve_cancellation_request'),
    path('approvals/cancel-request/<int:pk>/reject/',   central_admin.RejectCancellationRequestView.as_view(),  name='reject_cancellation_request'),
    path('aura/booking-status/', aura.get_booking_status, name='booking_status'),
    path('aura/confirmed-booking-files/', aura.confirmed_booking_files, name='confirmed_booking_files'),
    path('approve/stock/<int:pk>/', central_admin.ApproveStockRequestView.as_view(), name='approve_stock_request'),
    path('reject/stock/<int:pk>/',  central_admin.RejectStockRequestView.as_view(),  name='reject_stock_request'),
    path('notifications/', central_admin.AdminNotificationsView.as_view(), name='admin_notifications'),
    path('notification-counts/', central_admin.admin_notification_counts, name='admin_notification_counts'),
    path('booking-doc/<int:booking_id>/download/', aura.download_booking_doc, name='download_booking_doc'),
    path('api/room-inventory/', aura.get_room_inventory, name='get_room_inventory'),
    path('purchases/create/', central_admin.PurchaseCreateView.as_view(), name='purchase_create'),
    
    path('booking-doc-text/<int:booking_id>/', aura.get_booking_doc_text, name='get_booking_doc_text'),
    path('booking-doc-pdf/<int:booking_id>/',  aura.download_booking_doc_as_pdf, name='download_booking_doc_as_pdf'),
    
    path('booking-delete/<int:booking_id>/', aura.delete_confirmed_booking,    name='delete_confirmed_booking'),
    path('booking-bulk-delete/', aura.bulk_delete_confirmed_bookings, name='bulk_delete_confirmed_bookings'),

    
]
