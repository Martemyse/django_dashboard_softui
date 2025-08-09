from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from .views import TimConfigViewSet, TimDefinitionViewSet, StrojEntryViewSet, get_distinct_team_labels

router = DefaultRouter()
router.register(r'timconfigs', TimConfigViewSet)
router.register(r'timdefinitions', TimDefinitionViewSet)
router.register(r'strojentries', StrojEntryViewSet)

urlpatterns = [
    # Konfiguracija URL comes first
    path('<str:safe_obrat>/signali_strojev/<str:safe_oddelek>/konfiguracija/', views.konfiguracija_lean_teami, name='konfiguracija_lean_teami'),
    
    # Team label view and others follow
    path('<str:safe_obrat>/signali_strojev/<str:safe_oddelek>/', views.pregled, name='pregled'),
    path('<str:safe_obrat>/signali_strojev/<str:safe_oddelek>/<slug:team_label_slug>/', views.team_label_view, name='team_label_view'),
    path('<str:safe_obrat>/signali_strojev/<str:safe_oddelek>/<slug:team_label_slug>/<slug:team_name_slug>/rom/',
    views.terminali_overview,
    name='terminali_overview'
    ),

    path(
        '<str:safe_obrat>/signali_strojev/<str:safe_oddelek>/<slug:team_label_slug>/<slug:team_name_slug>/',
        views.tim_detail,
        name='tim_detail'
    ),

    path('tim/<slug:team_name_slug>/', views.tim_detail, name='tim_detail'),
    path('api/get-ag-grid-data/<slug:team_name_slug>/', views.get_ag_grid_data, name='get_ag_grid_data'),
    path('api/update-opomba/', views.update_opomba, name='update_opomba'),
    
    # API and other paths
    path('api/', include(router.urls)),
    path('api/team-labels/', get_distinct_team_labels, name='team-labels'),

    path('terminals/<int:terminal_id>/manage-limits/', views.manage_limits, name='manage_limits'),
    path('limits/<int:limit_id>/delete/', views.delete_limit, name='delete_limit'),
]
