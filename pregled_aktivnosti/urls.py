from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('api/task-steps/status', views.update_task_step_status, name='update_task_step_status'),
    path('api/stepper-delete', views.delete_stepper, name='delete_stepper'),
    path('api/stepper-change-assignee', views.change_assignee, name='change_assignee'),
    path('api/task-steps/change-exp-date', views.change_exp_date, name='change_exp_date'),
    path('api/task-steps/actions', views.add_task_action, name='add_task_action'),
    path('api/task-steps', views.add_task_step, name='add_task_step'),
    path('api/get-username', views.get_username, name='get_username'),
    path('api/fetch-steppers/', views.fetch_steppers, name='fetch_steppers'),
    
    path('<str:safe_obrat>/aktivnosti/<str:safe_oddelek>/', views.pregled_akcij, name='pregled_akcij'),
    path('<str:safe_obrat>/aktivnosti/<str:safe_oddelek>/nova_akcija/', views.nova_akcija, name='nova_akcija'),
    path('<str:safe_obrat>/aktivnosti/<str:safe_oddelek>/nova_akcija/post_form/', views.nova_akcija_post_form, name='nova_akcija_post_form'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
