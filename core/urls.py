from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('vgradni_deli.urls')),
    path('', include('signali_strojev.urls')),
    path('', include('pregled_aktivnosti.urls')),  # Remove the prefix to match URLs directly
    path('', include('home.urls')),
    path("admin/", admin.site.urls),
    path("", include('admin_soft.urls')),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)