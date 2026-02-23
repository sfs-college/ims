from django.contrib import sitemaps
from django.urls import reverse

class StaticViewSitemap(sitemaps.Sitemap):
    priority = 1.0  # High priority for the landing page
    changefreq = 'daily'

    def items(self):
        return ['landing_page', 'login', 'register']

    def location(self, item):
        return reverse(item)