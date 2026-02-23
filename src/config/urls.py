from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from core.views import LandingPageView
from django.conf import settings
from django.conf.urls.static import static
from inventory.views.escalation import run_escalation
from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap


sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', LandingPageView.as_view(), name="landing_page"),
    path('core/', include('core.urls', namespace='core')),
    path('central_admin/', include('inventory.urls.central_admin', namespace='central_admin')),
    path('room_incharge/', include('inventory.urls.room_incharge', namespace='room_incharge')),
    path('students/', include('inventory.urls.student', namespace='student')),
    path("internal/escalate/", run_escalation, name="run_escalation"),
    path('accounts/', include('allauth.urls')),
    path('googlea9164186443e93d5.html', TemplateView.as_view(template_name="googlea9164186443e93d5.html", content_type='text/html')),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)