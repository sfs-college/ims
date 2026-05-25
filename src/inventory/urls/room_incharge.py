from django.urls import path
from inventory.views import room_incharge
from inventory.views import aura as aura_views

app_name = 'room_incharge'

urlpatterns = [
    # Categories URLs
    path('rooms/<slug:room_slug>/categories/', room_incharge.CategoryListView.as_view(), name='category_list'),
    path('rooms/<slug:room_slug>/categories/<slug:category_slug>/update/', room_incharge.CategoryUpdateView.as_view(), name='category_update'),
    path('rooms/<slug:room_slug>/categories/create/', room_incharge.CategoryCreateView.as_view(), name='category_create'),
    
    # Brands URLs
    path('rooms/<slug:room_slug>/brands/', room_incharge.BrandListView.as_view(), name='brand_list'),
    path('rooms/<slug:room_slug>/brands/create/', room_incharge.BrandCreateView.as_view(), name='brand_create'),
    path('rooms/<slug:room_slug>/brands/<slug:brand_slug>/update/', room_incharge.BrandUpdateView.as_view(), name='brand_update'),
    
    # Items URLs
    path('rooms/<slug:room_slug>/items/', room_incharge.ItemListView.as_view(), name='item_list'),
    path('rooms/<slug:room_slug>/items/create/', room_incharge.ItemCreateView.as_view(), name='item_create'),
    path('rooms/<slug:room_slug>/items/<slug:item_slug>/archive/', room_incharge.ItemArchiveView.as_view(), name='item_archive'),
    
    # Item Groups URLs
    path('rooms/<slug:room_slug>/item-groups/', room_incharge.ItemGroupListView.as_view(), name='item_group_list'),
    path('rooms/<slug:room_slug>/item-groups/create/', room_incharge.ItemGroupCreateView.as_view(), name='item_group_create'),
    path('rooms/<slug:room_slug>/item-groups/<slug:item_group_slug>/update/', room_incharge.ItemGroupUpdateView.as_view(), name='item_group_update'),
    path('rooms/<slug:room_slug>/item-groups/<slug:item_group_slug>/items/create/', room_incharge.ItemGroupItemCreateView.as_view(), name='item_group_item_create'),
    path('rooms/<slug:room_slug>/item-groups/<slug:item_group_slug>/items/', room_incharge.ItemGroupItemListView.as_view(), name='item_group_item_list'),
    path('rooms/<slug:room_slug>/item-groups/<slug:item_group_slug>/items/<slug:item_group_item_slug>/update/', room_incharge.ItemGroupItemUpdateView.as_view(), name='item_group_item_update'),
    
    # Systems URLs
    path('rooms/<slug:room_slug>/systems/', room_incharge.SystemListView.as_view(), name='system_list'),
    path('rooms/<slug:room_slug>/systems/create/', room_incharge.SystemCreateView.as_view(), name='system_create'),
    path('rooms/<slug:room_slug>/systems/import/', room_incharge.SystemImportView.as_view(), name='system_import'),
    path('rooms/<slug:room_slug>/systems/import/confirm/', room_incharge.SystemImportConfirmView.as_view(), name='system_import_confirm'),
    path('rooms/<slug:room_slug>/systems/<slug:system_slug>/update/', room_incharge.SystemUpdateView.as_view(), name='system_update'),
    path('rooms/<slug:room_slug>/systems/<slug:system_slug>/components/', room_incharge.SystemComponentListView.as_view(), name='system_component_list'),
    path('rooms/<slug:room_slug>/systems/configuration/', room_incharge.SystemConfigurationView.as_view(), name='system_configuration'),
    path('rooms/<slug:room_slug>/systems/<slug:system_slug>/configuration/', room_incharge.SystemConfigurationDetailView.as_view(), name='system_configuration_detail'),
    path('rooms/<slug:room_slug>/systems/<slug:system_slug>/components/create/', room_incharge.SystemComponentCreateView.as_view(), name='system_component_create'),
    path('rooms/<slug:room_slug>/systems/<slug:system_slug>/components/<slug:component_slug>/update/', room_incharge.SystemComponentUpdateView.as_view(), name='system_component_update'),
    path('rooms/<slug:room_slug>/systems/<slug:system_slug>/components/<slug:component_slug>/archive/', room_incharge.SystemComponentArchiveView.as_view(), name='system_component_archive'),
    
    # Purchases URLs
    path('rooms/<slug:room_slug>/purchases/', room_incharge.PurchaseListView.as_view(), name='purchase_list'),
    path('rooms/<slug:room_slug>/purchases/create/', room_incharge.PurchaseCreateView.as_view(), name='purchase_create'),
    path('rooms/<slug:room_slug>/purchases/<slug:purchase_slug>/update/', room_incharge.PurchaseUpdateView.as_view(), name='purchase_update'),
    path('rooms/<slug:room_slug>/purchases/<slug:purchase_slug>/complete/', room_incharge.PurchaseCompleteView.as_view(), name='purchase_complete'),
    path('rooms/<slug:room_slug>/purchases/<slug:purchase_slug>/add_to_stock/', room_incharge.PurchaseAddToStockView.as_view(), name='purchase_add_to_stock'),
    path('rooms/<slug:room_slug>/purchases/new_item/create/', room_incharge.PurchaseNewItemCreateView.as_view(), name='purchase_new_item_create'),
    
    # Archives URLs
    path('rooms/<slug:room_slug>/archives/', room_incharge.ArchiveListView.as_view(), name='archive_list'),
    path('rooms/<slug:room_slug>/api/archive/<slug:archive_slug>/update-status/', room_incharge.ArchiveStatusUpdateView.as_view(), name='archive_update_status'),

    # Systems Kanban APIs
    path('rooms/<slug:room_slug>/api/systems/assign/', room_incharge.SystemsAssignView.as_view(), name='systems_assign'),
    path('rooms/<slug:room_slug>/api/systems/archive/', room_incharge.SystemsArchiveView.as_view(), name='systems_archive'),
    path('rooms/<slug:room_slug>/api/systems/create-automated/', room_incharge.SystemAutomatedCreateView.as_view(), name='systems_create_automated'),
    path('rooms/<slug:room_slug>/api/systems/<int:pk>/delete/', room_incharge.SystemDeleteView.as_view(), name='systems_delete'),
    path('rooms/<slug:room_slug>/api/systems/components/<int:pk>/revert/', room_incharge.SystemComponentRevertView.as_view(), name='systems_revert_component'),

    # Configurations
    path('rooms/<slug:room_slug>/configurations/', room_incharge.ConfigurationsListView.as_view(), name='configurations_list'),
    path('rooms/<slug:room_slug>/api/configurations/save/', room_incharge.SaveConfigurationView.as_view(), name='save_configuration'),
    path('rooms/<slug:room_slug>/api/configurations/<slug:cfg_slug>/delete/', room_incharge.DeleteConfigurationView.as_view(), name='delete_configuration'),
    path('rooms/<slug:room_slug>/api/item-configurations/', room_incharge.ItemConfigurationsAPIView.as_view(), name='item_configurations'),
        
    # Room Management URLs
    path('rooms/<slug:room_slug>/dashboard/', room_incharge.RoomDashboardView.as_view(), name='room_dashboard'),
    path('rooms/<slug:room_slug>/update/', room_incharge.RoomUpdateView.as_view(), name='room_update'),
    path('rooms/<slug:room_slug>/settings/', room_incharge.RoomSettingsView.as_view(), name='room_settings'),
    path('rooms/<slug:room_slug>/report/', room_incharge.RoomReportView.as_view(), name='room_report'),
    
    # Issues URLs
    # ROOM INCHARGE ISSUE LIST (per-room, kept for in_progress / resolve actions)
    path('rooms/<slug:room_slug>/issues/', 
     room_incharge.IssueListView.as_view(), 
     name='issue_list'),
    # CENTRALISED ISSUES LIST (no room_slug — room filter + count)
    path('room-issues/', 
     room_incharge.CentralIssuesListView.as_view(), 
     name='central_issue_list'),

    # ISSUE ACTION CONTROLS
    path(
    "rooms/<slug:room_slug>/issue/<int:pk>/in-progress/",
    room_incharge.MarkInProgressView.as_view(),
    name='in_progress'
    ),

    path('rooms/<slug:room_slug>/issue/<int:pk>/resolve/', 
     room_incharge.MarkResolvedView.as_view(), 
     name='resolve'),

    path('rooms/<slug:room_slug>/issue/<int:pk>/unresolve/', 
     room_incharge.MarkUnresolvedView.as_view(), 
     name='unresolve'),
    path("issues/<int:issue_id>/request-time-extension/",
        room_incharge.IssueTimeExtensionRequestView.as_view(),
        name="issue_time_extension_request"),
    path('<slug:room_slug>/items/stock-request/', room_incharge.SubmitStockRequestView.as_view(), name='submit_stock_request'),
    path('rooms/<slug:room_slug>/notifications/', room_incharge.RoomInchargeNotificationsView.as_view(), name='notifications'),
    path('<slug:room_slug>/issues/<int:pk>/close/', room_incharge.CloseIssueView.as_view(), name='close_issue'),
    path('rooms/<slug:room_slug>/asset-tags/', room_incharge.get_room_asset_tags, name='get_room_asset_tags'),
    path('rooms/<slug:room_slug>/issue/<int:pk>/remark/', room_incharge.SendIssueRemarkView.as_view(), name='issue_remark'),
    # Master Inventory — view-only for room incharges with granted access
    path('rooms/<slug:room_slug>/master-inventory/', aura_views.RoomInchargeMasterInventoryView.as_view(), name='master_inventory'),
    path('rooms/<slug:room_slug>/master-inventory/import/', aura_views.MasterInventoryImportView.as_view(), name='master_inventory_import'),
    path('rooms/<slug:room_slug>/master-inventory/import/confirm/', aura_views.MasterInventoryImportConfirmView.as_view(), name='master_inventory_import_confirm'),
    path('rooms/<slug:room_slug>/api/master-inventory/manual-create/', aura_views.create_master_inventory_item, name='create_master_inventory_item'),
    path('rooms/<slug:room_slug>/api/save-product-code/', aura_views.save_product_code, name='save_product_code'),
    path('rooms/<slug:room_slug>/api/save-item-edit/', aura_views.save_item_edit, name='save_item_edit'),
    path('rooms/<slug:room_slug>/api/toggle-item-condition/', aura_views.toggle_item_condition, name='toggle_item_condition'),
    # Assign Inventory — for room incharges with granted assign access
    path('rooms/<slug:room_slug>/assign-inventory/', aura_views.RoomInchargeAssignInventoryView.as_view(), name='assign_inventory'),
    path('rooms/<slug:room_slug>/api/assign-inventory/', aura_views.incharge_assign_inventory_api, name='incharge_assign_inventory_api'),
    path('rooms/<slug:room_slug>/api/revert-inventory-data/', aura_views.revert_inventory_data, name='revert_inventory_data'),
    path('rooms/<slug:room_slug>/api/revert-inventory/', aura_views.revert_inventory_api, name='revert_inventory_api'),
]
