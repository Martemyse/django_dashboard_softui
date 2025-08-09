from django.urls import path
from . import views

urlpatterns = [
    # Main and authentication views
    path('', views.index, name='index'),
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('register/', views.register, name='register'),
    path('accounts/profile/', views.profile_view, name='profile'),
    
    # Obrat-related views
    path('set-obrat-ajax/', views.set_obrat_ajax, name='set_obrat_ajax'),
    path('get-obrat-name/', views.get_obrat_name, name='get_obrat_name'),
    path('get-short-obrat-name/', views.get_short_obrat_name, name='get_short_obrat_name'),
    path('login_dynamic_obrati/', views.login_dynamic_obrati_ajax, name='login_dynamic_obrati_ajax'),
    path('navigation_dynamic_obrati/', views.navigation_dynamic_obrati_ajax, name='navigation_dynamic_obrati_ajax'),
    
    # User management views
    path('add_user/', views.add_user, name='add_user'),
    path('user_add_success/', views.user_add_success, name='user_add_success'),
    path('add_user_ajax/', views.add_user_ajax, name='add_user_ajax'),
    path('user_search/', views.user_search, name='user_search'),
    path('update_user_groups/', views.update_user_groups, name='update_user_groups'),
    
    # Permissions management views
    path('manage_permissions/', views.manage_permissions, name='manage_permissions'),
    path('manage_permissions/success/', views.manage_permissions_success, name='manage_permissions_success'),
    path('manage_permissions/failed/', views.manage_permissions_failed, name='manage_permissions_failed'),
    path('manage_permissions/ajax/', views.manage_permissions_ajax, name='manage_permissions_ajax'),
    
    # Group management views
    path('add-group/', views.add_group, name='add_group'),
    path('add-group-ajax/', views.add_group_ajax, name='add_group_ajax'),
    path('manage_groups/', views.manage_groups, name='manage_groups'),
    path('update_group_members/', views.update_group_members, name='update_group_members'),
    
    # Obrat Oddelek Group management views
    path('add-obrat-oddelek-group/', views.add_obrat_oddelek_group, name='add_obrat_oddelek_group'),
    path('add-obrat-oddelek-group-ajax/', views.add_obrat_oddelek_group_ajax, name='add_obrat_oddelek_group_ajax'),
    path('manage_obrat_oddelek_groups/', views.manage_obrat_oddelek_groups, name='manage_obrat_oddelek_groups'),
    path('get-obrat-oddelek-groups/', views.get_obrat_oddelek_groups, name='get_obrat_oddelek_groups'),

    path('pair/', views.pair_terminal, name='pair_terminal'),
    path('create_notification/', views.create_notification, name='create_notification'),
    path('notification_sent/', views.notification_sent, name='notification_sent'),
    path('obvestila/', views.obvestila_view, name='obvestila'),
    path('notifications/<int:notification_id>/', views.notification_detail, name='notification_detail'),
    path('terminal_heartbeat/', views.terminal_heartbeat, name='terminal_heartbeat'),
    path('terminal_sign_out/', views.terminal_sign_out, name='terminal_sign_out'),
    path('terminali_overview/', views.terminali_overview, name='terminali_overview'),

    # Additional utility views
    path('get-oddelki/', views.get_oddelki, name='get_oddelki'),
    path('sidebar_context_ajax/', views.sidebar_context_ajax, name='sidebar_context_ajax'),

    path('api/taskstep-status-data/', views.get_taskstep_status_data, name='get_taskstep_status_data'),
    path('api/taskstep-trend-data/', views.get_taskstep_trend_data, name='get_taskstep_trend_data'),
    path('api/taskstep-status-oddelki-data/', views.get_taskstep_status_oddelki_data, name='get_taskstep_status_oddelki_data'),
]
