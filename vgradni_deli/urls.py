from django.urls import path, include
from rest_framework import routers
from . import views
from .views import (
    PartViewSet, BatchViewSet, CurrentStockViewSet,
    InboundTransactionViewSet, ProductionTransactionViewSet, AdjustmentTransactionViewSet,
    StrojArtikelSarzaMoznostiViewSet, StrojArtikelSarzaTrenutnoViewSet,
    InboundVirtualBatchAllocationViewSet
)

# Register API routes
router = routers.DefaultRouter()
router.register(r'parts', PartViewSet)
router.register(r'batches', BatchViewSet)
router.register(r'currentstock', CurrentStockViewSet)
router.register(r'inboundtransactions', InboundTransactionViewSet)
router.register(r'productiontransactions', ProductionTransactionViewSet)
router.register(r'adjustments', AdjustmentTransactionViewSet)
router.register(r'sarza_moznosti', StrojArtikelSarzaMoznostiViewSet)
router.register(r'sarza_trenutno', StrojArtikelSarzaTrenutnoViewSet)
router.register(r'inbound_virtual_allocations', InboundVirtualBatchAllocationViewSet)

# Define URL patterns
urlpatterns = [
    path('<str:safe_obrat>/vgradni_deli/<str:safe_oddelek>/konfiguracija_vgradni_deli/', views.konfiguracija_vgradni_deli, name='konfiguracija_vgradni_deli'),
    path('<str:safe_obrat>/vgradni_deli/<str:safe_oddelek>/', views.pregled_vgradni_deli, name='pregled_vgradni_deli'),
    path('update_montaza_cell/', views.update_montaza_cell, name='update_montaza_cell'),
    path('api/', include(router.urls)),
]
