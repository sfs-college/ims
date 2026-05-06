from django.urls import path
from core import views

app_name = 'core'

urlpatterns = [
     path('login/', views.LoginView.as_view(), name='login'),
     path('register/', views.UserRegisterView.as_view(), name='register'),
     path('logout/', views.LogoutView.as_view(), name='logout'),
     path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
     path('reset-password/', views.ResetPasswordView.as_view(), name='reset_password'),
     path('done-password-reset/', views.DonePasswordResetView.as_view(),
          name='done_password_reset'),
     path('confirm-password-reset/<uidb64>/<token>/',
          views.ConfirmPasswordResetView.as_view(), name='confirm_password_reset'),
     path('complete-password-reset/', views.CompletePasswordResetView.as_view(),
          name='complete_password_reset'),
     path("book-room/", views.room_booking_view, name="room_booking"),
     # admin-book-room removed — admin booking is now at central_admin:sub_admin_book_venue (session-authenticated)
     # Keep these URLs as redirects so old bookmarks and the existing template don't 404
     path("admin-book-room/", views.admin_room_booking_redirect, name="admin_room_booking"),
     path("admin-book-room/verify/", views.admin_room_booking_redirect, name="verify_admin_booking_credentials"),
     path("app/", views.app_home_view, name="app_home"),
     path("app-auth-callback/", views.app_auth_callback_view, name="app_auth_callback"),
     path('api/rooms-by-category/', views.rooms_by_category, name='rooms_by_category'),
     path("aura/import-creds/", views.import_booking_credentials, name="import_booking_credentials"),
     path("aura/create-cred/", views.create_booking_credentials, name="create_booking_credentials"),
     path("aura/delete-cred/<int:pk>/", views.delete_booking_credential, name="delete_cred"),
     path('access-denied/', views.TemplateView.as_view(template_name='core/access_denied.html'), name='access_denied'),
     path('firebase-login/', views.firebase_login_callback, name='firebase_login'),
     path('auth-status/', views.auth_status_view, name='auth_status'),
     path('booking/get-bookings/', views.get_bookings_by_email, name='get_bookings_by_email'),
     path('booking/cancel/', views.submit_cancellation_request, name='submit_cancellation_request'),
     path('booking-status/', views.get_booking_status, name='get_booking_status'),
     path('check-document-name/', views.check_document_name, name='check_document_name'),
]