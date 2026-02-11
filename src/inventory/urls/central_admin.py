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
    # Item editing approvals request
    path("edit-requests/", central_admin.EditRequestListView.as_view(), name="edit_request_list"),
    path("edit-requests/<int:pk>/approve/", central_admin.ApproveEditRequestView.as_view(), name="approve_edit_request"),
    path("edit-requests/<int:pk>/reject/", central_admin.RejectEditRequestView.as_view(), name="reject_edit_request"),
    #Issue Resolving by admin
    path("issues/<int:pk>/resolve/", central_admin.admin_resolve_issue, name="resolve_issue"),
    path("issues/<int:pk>/unresolve/", central_admin.admin_unresolve_issue, name="unresolve_issue"),
    path("issues/<int:pk>/deescalate/",central_admin.admin_deescalate_issue, name="deescalate_issue"),
    
    path(
        "approval-requests/",
        central_admin.ApprovalRequestListView.as_view(),
        name="approval_requests",
    ),

    # Issue Time Extension approvals
    path(
        "edit-requests/<int:pk>/approve/",
        central_admin.ApproveEditRequestView.as_view(),
        name="approve_edit_request",
    ),
    path(
        "edit-requests/<int:pk>/reject/",
        central_admin.RejectEditRequestView.as_view(),
        name="reject_edit_request",
    ),

    # Issue time extension approvals (NEW, SAME PAGE)
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
    
]
