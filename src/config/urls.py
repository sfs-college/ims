from django.contrib import admin
from django.urls import path, include
from core.views import LandingPageView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', LandingPageView.as_view(), name="landing_page"),
    path('core/', include('core.urls', namespace='core')),
    path('central_admin/', include('inventory.urls.central_admin', namespace='central_admin')),
    path('sub_admin/', include('inventory.urls.sub_admin', namespace='sub_admin')),
    path('room_incharge/', include('inventory.urls.room_incharge', namespace='room_incharge')),
    path('students/', include('inventory.urls.student', namespace='student')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)