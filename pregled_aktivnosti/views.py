from django.shortcuts import render, get_object_or_404, redirect
from utils.utils import SAFE_URL_OBRAT_MAPPING, URL_TO_RAW_MAPPING, RAW_TO_URL_MAPPING, RAW_TO_URL_MAPPING_APP, URL_TO_RAW_MAPPING_APP
from .models import Stepper
from home.models import ObratiOddelki
from django.db import models
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic.edit import FormView
from django.contrib.auth.decorators import login_required
from home.models import User, UserGroup, ObratiOddelki
from .models import Stepper, TaskStep, Attachment, Action
from .forms import GroupForm, AttachmentForm, TaskStepForm
import json
import logging
from datetime import datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta  # For relative time calculations
from django.utils.dateformat import DateFormat
from django.utils.formats import get_format
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class AttachmentUploadView(FormView):
    form_class = AttachmentForm
    template_name = 'pages/nova_akcija.html'
    success_url = '...'  # Replace with your success URL

    def form_valid(self, form):
        # Handle multiple file uploads
        files = form.cleaned_data['files']
        task_step_id = self.request.POST.get('task_step_id')
        task_step = get_object_or_404(TaskStep, id=task_step_id)

        # Save each file individually
        for f in files:
            Attachment.objects.create(task_step=task_step, file=f)

        # Return response after saving
        return super().form_valid(form)


def map_safe_to_raw(safe_obrat, safe_oddelek):
    # Reverse the mappings
    obrat = {v: k for k, v in SAFE_URL_OBRAT_MAPPING.items()}.get(safe_obrat)
    oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek)
    
    # Debugging: Print the mappings
    print(f"Mapping safe_obrat: {safe_obrat} to obrat: {obrat}")
    # print(f"Mapping safe_app: {safe_app} to app: {app}")
    print(f"Mapping safe_oddelek: {safe_oddelek} to oddelek: {oddelek}")
    
    return obrat, oddelek

@login_required
def nova_akcija(request, safe_obrat, safe_oddelek):
    obrat = {v: k for k, v in SAFE_URL_OBRAT_MAPPING.items()}.get(safe_obrat)
    oddelek = URL_TO_RAW_MAPPING.get(safe_oddelek)
    # aplikacija = URL_TO_RAW_MAPPING_APP.get(safe_app)
    obrat_oddelek = get_object_or_404(ObratiOddelki, obrat=obrat, oddelek=oddelek)

    # Calculate tomorrow's date
    tomorrow = datetime.now() + timedelta(days=1)
    formatted_tomorrow = tomorrow.strftime('%Y-%m-%d')

    form = AttachmentForm()

    context = {
        'obrat': obrat,
        'oddelek': oddelek,
        'safe_obrat': safe_obrat,
        # 'safe_app': safe_app,
        'safe_oddelek': safe_oddelek,
        'form': form,
        'exp_time': formatted_tomorrow,  # Pass tomorrow's date
    }
    return render(request, 'pages/nova_akcija.html', context)

def nova_akcija_post_form(request, safe_obrat, safe_oddelek):
    print("Received POST request for nova_akcija_post_form.")
    
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        form = TaskStepForm(request.POST, request.FILES)
        username = request.POST.get('username')  # Assignee's username

        print(f"Username (Assignee) from form: {username}")

        # Initialize stepper as None
        stepper = None

        # Check if 'createNewStepper' is in POST data
        if 'createNewStepper' in request.POST:
            # Creating a new stepper
            print("Creating a new stepper based on 'createNewStepper' checkbox.")
            project_name = request.POST.get('project', 'Default Project')
            print(f"New Stepper project name: {project_name}")
            obrat_oddelek = get_object_or_404(ObratiOddelki, obrat=safe_obrat, oddelek=safe_oddelek)
            stepper = Stepper.objects.create(
                project=project_name,
                assigner=request.user.username,
                assignee=username,
                assignee_username=username,
                loggedusername=request.user.username,
                obrat_oddelek=obrat_oddelek
            )
            print(f"New Stepper created: {stepper}")
        else:
            # User selected an existing stepper
            stepper_id = request.POST.get('stepper')  # Get the selected stepper ID from the form
            print(f"Stepper ID from form: {stepper_id}")

            if stepper_id:
                print(f"Attempting to fetch Stepper with ID: {stepper_id}")
                try:
                    stepper = Stepper.objects.get(id=stepper_id)
                    print(f"Stepper found: {stepper}")
                except Stepper.DoesNotExist:
                    print(f"Stepper with ID {stepper_id} does not exist.")
                    return JsonResponse({'success': False, 'message': 'Selected stepper does not exist.'})

        if form.is_valid():
            print("Form is valid. Proceeding to create TaskStep.")
            task_step = form.save(commit=False)
            task_step.stepper = stepper

            # Calculate the order based on the number of existing TaskSteps for the related Stepper
            max_order = TaskStep.objects.filter(stepper=stepper).aggregate(max_order=models.Max('order'))['max_order']
            task_step.order = (max_order or 0) + 1  # Set the order to the next available number
            print(f"TaskStep order set to: {task_step.order}")

            task_step.save()
            print(f"TaskStep created: {task_step}")

            # Save file attachments
            attachment_form = AttachmentForm(request.POST, request.FILES)
            print(f"Files uploaded")
            if attachment_form.is_valid():
                attachment_form.save(task_step=task_step, username=request.user.username)  # Pass the username here
                print(f"Attachments created for task_step: {task_step}")
            else:
                print(f"Attachment form errors: {attachment_form.errors}")

            # Handle checkbox states
            notify_email = 'notify_email' in request.POST
            print(f"Notify by email: {notify_email}")

            # Perform actions based on checkbox states
            if notify_email:
                print("Email notification sent.")

            # Return JSON success response
            print("Returning success response.")
            return JsonResponse({'success': True, 'message': 'Action created successfully'})

        else:
            print(f"Form validation failed: {form.errors}")
            # Return JSON error response with form errors
            return JsonResponse({'success': False, 'message': 'Form validation failed', 'errors': form.errors})

    # If the request is not POST, return an error response
    print("Invalid request method. Only POST is allowed.")
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


def fetch_steppers(request):
    username = request.GET.get('username')
    current_user = request.user

    if username:
        steppers = Stepper.objects.filter(assignee_username=username, assigner=current_user)
        return render(request, 'partials/steppers_options_select_dropdown.html', {'steppers': steppers})
    return render(request, 'partials/steppers_options_select_dropdown.html', {'steppers': []})

@login_required
def pregled_akcij(request, safe_obrat, safe_oddelek):
    current_user = request.user
    obrat = request.session.get('current_obrat', '')
    hide_buttons = 'hide_buttons' in request.GET
    my_issued_tasks = request.GET.get('my_issued_tasks', 'off') == 'on'

    # Get filter parameters from the request
    assignee_filter = request.GET.get('assignee', '')
    obrat_oddelek_filter = request.GET.get('obrat_oddelek', '')
    status_filter = request.GET.get('status', '')
    hours_filter = request.GET.get('hours_filter', '24')

    # Base queryset for steppers
    if my_issued_tasks:
        steppers = Stepper.objects.filter(assignee=current_user.username)
    else:
        steppers = Stepper.objects.filter(assigner=current_user.username)

    # Apply assignee filter
    if assignee_filter:
        steppers = steppers.filter(assignee=assignee_filter)

    # Apply obrat_oddelek filter
    if obrat_oddelek_filter:
        steppers = steppers.filter(obrat_oddelek__obrat=obrat_oddelek_filter)

    # Build task steps filter
    task_steps_filter = Q()
    if status_filter:
        task_steps_filter &= Q(status=status_filter)

    try:
        hours_ago = int(hours_filter)
        time_threshold = timezone.now() - relativedelta(hours=hours_ago)
        task_steps_filter &= Q(status_modified_at__gte=time_threshold)
    except ValueError:
        pass  # Ignore invalid hours_filter input

    # Prefetch only the task steps that match the filter criteria
    task_steps_prefetch = Prefetch(
        'steps',
        queryset=TaskStep.objects.filter(task_steps_filter).order_by('order'),
        to_attr='filtered_steps'
    )

    # Fetch steppers with the filtered task steps
    steppers = steppers.prefetch_related(task_steps_prefetch)

    steppers_data = []
    for stepper in steppers:
        filtered_steps = []
        for task_step in getattr(stepper, 'filtered_steps', []):
            actions = []
            for action in task_step.actions.all().order_by('timestamp'):
                actions.append({
                    'ActionName': action.action_name,
                    'TimeStamp': timezone.localtime(action.timestamp).strftime('%Y-%m-%dT%H:%M:%S'),
                    'user': action.user,
                })

            # Get attachments associated with the task step
            attachments = [
                {
                    'id': str(attachment.id),
                    'file_url': request.build_absolute_uri(attachment.file.url) if attachment.file else '',
                    'file_name': os.path.basename(attachment.file.name) if attachment.file else ''
                }
                for attachment in task_step.attachments.all()
            ]

            # Convert status_modified_at to local timezone
            if task_step.status_modified_at:
                status_modified_at_local = timezone.localtime(task_step.status_modified_at)
                status_modified_at_str = status_modified_at_local.strftime('%Y-%m-%dT%H:%M:%S')
            else:
                status_modified_at_str = None

            filtered_steps.append({
                'id': str(task_step.id),
                'TaskStep': task_step.description,
                'ExpTime': timezone.localtime(task_step.exp_time).strftime('%Y-%m-%dT%H:%M:%S'),
                'Order': task_step.order,
                'Actions': actions,
                'Status': task_step.status,
                'Machine': task_step.machine or '',
                'Product': task_step.product or '',
                'ExpDate': timezone.localtime(task_step.exp_time).strftime('%Y-%m-%d'),
                'status_modified_at': status_modified_at_str,
                'Attachments': attachments
            })

        # Include the stepper if it has any matching task steps
        if filtered_steps:
            stepper_data = {
                'id': str(stepper.id),
                'project': stepper.project,
                'assignee': stepper.assignee,
                'assignee_username': stepper.assignee_username,
                'assigner': stepper.assigner,
                'steps': filtered_steps,
                'initialCompletedSteps': [],
                'activeStep': -1,
                'obrat_oddelek': {'obrat': stepper.obrat_oddelek.obrat},
            }
            steppers_data.append(stepper_data)

    # Get unique assignees and obrat_oddelek values for the dropdowns
    unique_assignees = Stepper.objects.filter(assigner=current_user.username).values_list('assignee', flat=True).distinct()
    unique_obrati = Stepper.objects.filter(assigner=current_user.username).values_list('obrat_oddelek__obrat', flat=True).distinct()

    context = {
        'safe_obrat': safe_obrat,
        # 'safe_app': safe_app,
        'safe_oddelek': safe_oddelek,
        'steppers_data': steppers_data,
        'unique_assignees': unique_assignees,
        'unique_obrati': unique_obrati,
        'hide_buttons': hide_buttons,
        'my_issued_tasks': my_issued_tasks,
    }

    # If the request is an HTMX request, render only the steppers part
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'partials/stepper_partial.html', context)

    return render(request, 'pages/pregled_akcij.html', context)


def user_search(request):
    query = request.GET.get('q', '')
    logger.debug(f"Search query received: {query}")
    current_user = request.user

    if len(query) > 2:
        User = get_user_model()
        try:
            user = User.objects.get(username=query)
            user_groups = user.user_groups.all()

            # Determine if the current user can edit the searched user
            can_edit = True
            if current_user == user:
                can_edit = False

            # Check user role hierarchy
            role_hierarchy = {'osnovni': 1, 'vodja': 2, 'admin': 3}
            if role_hierarchy.get(current_user.user_role, 0) <= role_hierarchy.get(user.user_role, 0):
                can_edit = False

            # Check obrat and oddelek permissions
            if current_user.user_role == 'vodja' and can_edit:
                if current_user.obrat_oddelek != user.obrat_oddelek:
                    if current_user.obrat_oddelek.obrat != 'LTH' and current_user.obrat_oddelek != 'LTH':
                        can_edit = False
                    elif current_user.obrat_oddelek.obrat == 'LTH' and current_user.obrat_oddelek.oddelek != user.obrat_oddelek.oddelek:
                        can_edit = False
                    elif current_user.obrat_oddelek.oddelek == 'LTH' and current_user.obrat_oddelek.obrat != user.obrat_oddelek.obrat:
                        can_edit = False

            # Retrieve obrat_oddelek details for debugging
            obrat_oddelek_instance = user.obrat_oddelek
            logger.debug(f"User's obrat_oddelek ID: {user.obrat_oddelek_id}")
            logger.debug(f"User's obrat_oddelek instance: {obrat_oddelek_instance}")

            user_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'user_role': user.user_role,
                'obrat_oddelek': {
                    'id': obrat_oddelek_instance.obrati_oddelki_id if obrat_oddelek_instance else None,
                    'label': f"{obrat_oddelek_instance.obrat} - {obrat_oddelek_instance.oddelek}" if obrat_oddelek_instance else ''
                },
                'groups': [group.name for group in user_groups],
                'can_edit': can_edit
            }
            logger.debug(f"User found: {user_data}")
            return JsonResponse({'users': [user_data]})
        except User.DoesNotExist:
            logger.error("User not found.")
            return JsonResponse({'users': []}, status=404)
        except Exception as e:
            logger.error(f"Error occurred in user_search: {str(e)}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    else:
        logger.error("No valid search query or too short")
        return JsonResponse({'users': []}, status=400)
    
@login_required
def get_username(request):
    # Get the current logged-in user's username
    username = request.user.username
    return JsonResponse({'username': username})


@login_required
@require_POST
def add_task_step(request):
    try:
        print("[DEBUG] Incoming data: ", request.body)
        # Parse the incoming JSON data
        data = json.loads(request.body)
        print("[DEBUG] Parsed data: ", data)
        
        stepper_id = data.get('StepperId')
        print("[DEBUG] Stepper ID: ", stepper_id)
        
        stepper = Stepper.objects.get(pk=stepper_id)  # Assuming Stepper has a primary key as id
        print("[DEBUG] Stepper found: ", stepper)

        # Parse the expiration time from the incoming data format
        try:
            exp_time = timezone.make_aware(datetime.strptime(data['ExpTime'], '%d.%m.%Y %H:%M'))
        except:
            exp_time = timezone.make_aware(datetime.strptime(data['ExpTime'], '%Y-%m-%dT%H:%M:%S'))

        print("[DEBUG] Expiration time: ", exp_time)

        # Create a new TaskStep object
        new_task_step = TaskStep(
            description=data['TaskStep'],
            exp_time=exp_time,
            order=data['Order'],
            machine=data['Machine'],
            product=data['Product'],
            status=data['Status'],
            stepper=stepper
        )

        new_task_step.save()
        print("[DEBUG] Task step saved successfully")

        return JsonResponse({
            "status": "success",
            "message": "Task step added successfully.",
            "ExpTime": new_task_step.exp_time.date().isoformat(),  # Ensure ExpTime is passed as a string in ISO format
            "taskStepId": str(new_task_step.id),
            "CreatedAt": new_task_step.created_at.isoformat()  # Include created_at
        }, status=200)

    except Stepper.DoesNotExist:
        return JsonResponse({'error': 'Stepper not found'}, status=404)
    
    except Exception as e:
        print("[DEBUG] Error: ", str(e))
        return JsonResponse({'error': str(e)}, status=400)    

@require_POST
def add_task_action(request):
    try:
        print("[DEBUG] Starting add_task_action")
        data = json.loads(request.body)
        print(f"[DEBUG] Received request data: {data}")

        action_data = data.get('actionData')
        if not action_data:
            print("[DEBUG] Missing actionData in request")
            return JsonResponse({'error': 'Missing actionData'}, status=400)

        stepper_id = action_data.get('StepperId')
        taskstepid = action_data.get('taskStepId')
        user = action_data.get('user')
        new_status = data.get('newStatus')

        if not stepper_id or not taskstepid:
            print("[DEBUG] Missing StepperId or TaskStepId")
            return JsonResponse({'error': 'Missing StepperId or TaskStepId'}, status=400)

        # Find the stepper and task step
        stepper = Stepper.objects.filter(id=stepper_id).first()
        if not stepper:
            print("[DEBUG] Stepper not found")
            return JsonResponse({'error': 'Stepper not found'}, status=404)

        task_step = TaskStep.objects.filter(stepper_id=stepper.id, id=taskstepid).first()
        if not task_step:
            print("[DEBUG] TaskStep not found")
            return JsonResponse({'error': 'TaskStep not found'}, status=404)

        # Add the new action
        new_action = Action(
            action_name=action_data.get('ActionName'),
            timestamp=datetime.strptime(action_data.get('TimeStamp'), '%Y-%m-%dT%H:%M:%S.%fZ'),
            task_step=task_step,
            user=user
        )
        new_action.save()

        # Update TaskStep status if newStatus is provided
        if new_status:
            task_step.status = new_status
            task_step.save()

        print("[DEBUG] Action added successfully")
        return JsonResponse({"status": "success", "message": "Action added successfully."}, status=200)

    except Exception as e:
        print(f"[DEBUG] Error: {e}")
        return JsonResponse({"error": str(e)}, status=400)

    

@require_POST
def update_task_step_status(request):
    try:
        print("[DEBUG] Starting update_task_step_status")
        data = json.loads(request.body)
        print(f"[DEBUG] Received request data: {data}")

        # Access the StepperId directly from the data
        stepper_id = data.get('StepperId')
        taskstepid = data.get('TaskStepId')
        new_status = data.get('NewStatus')

        print(f"[DEBUG] stepper_id: {stepper_id}, taskstepid: {taskstepid}, new_status: {new_status}")

        # Query the stepper by its ID
        stepper = Stepper.objects.filter(id=stepper_id).first()
        if not stepper:
            print("[DEBUG] Stepper not found")
            return JsonResponse({'error': 'Stepper not found'}, status=404)

        # Query the task step by the stepper's ID and the task step's ID
        task_step = TaskStep.objects.filter(stepper_id=stepper.id, id=taskstepid).first()
        if not task_step:
            print("[DEBUG] TaskStep not found")
            return JsonResponse({'error': 'TaskStep not found'}, status=404)

        # Update the task step status and modified timestamp
        task_step.status = new_status
        task_step.status_modified_at = timezone.localtime(timezone.now())
        task_step.save()

        new_status_modified_at = timezone.localtime(timezone.now())

        print(f"[DEBUG] Task step status updated successfully, status_modified_at: {new_status_modified_at}")

        print("[DEBUG] Task step status updated successfully")
        return JsonResponse({"status": "success", "message": "Task step status updated successfully."}, status=200)

    except Exception as e:
        print(f"[DEBUG] Error occurred: {e}")
        return JsonResponse({"error": str(e)}, status=400)
    
@require_POST
def delete_stepper(request):
    try:
        data = json.loads(request.body)
        stepper_id = data.get('StepperId')

        # Find and delete the stepper
        stepper = Stepper.objects.filter(id=stepper_id).first()
        if stepper:
            stepper.delete()
            return JsonResponse({'message': 'Stepper deleted successfully'}, status=200)
        else:
            return JsonResponse({'error': 'Stepper not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@require_POST
def change_assignee(request):
    try:
        data = json.loads(request.body)
        stepper_id = data.get('StepperId')
        new_assignee_username = data.get('NewAssigneeUsername')

        # Find and update the stepper
        stepper = Stepper.objects.filter(id=stepper_id).first()
        if not stepper:
            return JsonResponse({'error': 'Stepper not found'}, status=404)

        stepper.assignee_username = new_assignee_username
        stepper.save()

        return JsonResponse({"status": "success", "message": "Assignee username updated successfully."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
    
@require_POST
def change_exp_date(request):
    try:
        data = json.loads(request.body)
        stepper_id = data.get('StepperId')
        taskstepid = data.get('TaskStepId')
        new_exp_date = data.get('NewExpDate')

        # Find the stepper and task step
        stepper = Stepper.objects.filter(id=stepper_id).first()
        if not stepper:
            return JsonResponse({'error': 'Stepper not found'}, status=404)

        task_step = TaskStep.objects.filter(stepper_id=stepper.id, id=taskstepid).first()
        if not task_step:
            return JsonResponse({'error': 'TaskStep not found'}, status=404)

        # Update the expiration date
        task_step.exp_time = datetime.strptime(new_exp_date, '%Y-%m-%d')
        task_step.save()

        return JsonResponse({"status": "success", "message": "Expiration date updated successfully."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)