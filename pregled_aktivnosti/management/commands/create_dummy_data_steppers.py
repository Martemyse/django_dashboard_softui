from django.core.management.base import BaseCommand
from django.utils import timezone
from pregled_aktivnosti.models import Stepper, TaskStep, Action, Attachment
from home.models import User, ObratiOddelki, UserGroup
import random
import string
import os
import glob
from django.conf import settings  # Import settings
from dateutil.relativedelta import relativedelta
import calendar

def generate_random_project_name():
    def random_letter():
        return random.choice(string.ascii_uppercase)
    
    def random_number():
        return str(random.randint(0, 9))
    
    # Example: "Project A12 - B34"
    return f"Project {random_letter()}{random_number()}{random_number()} - {random_letter()}{random_number()}{random_number()}"

# Define some dummy descriptions, actions, and priorities
dummy_descriptions = [
    "Inspect machine X123",
    "Check product quality for Y456",
    "Ensure compliance with safety protocols",
    "Review production report",
    "Prepare documentation for Z789"
]

dummy_actions = [
    "Started task",
    "Verified component A",
    "Fixed issue with machine",
    "Updated the report",
    "Task completed"
]

# Define the statuses for the steps
statuses = ["Queued", "Active", "Complete", "Expired", "ExpiredComplete"]

# Define projects and priorities
dummy_projects = ["Project A", "Project B", "Project C"]
priority_choices = [1, 2, 3]  # Nizka, Srednja, Visoka

class Command(BaseCommand):
    help = 'Creates dummy data for Stepper, TaskStep, Action, and Attachment models'

    def handle(self, *args, **kwargs):
        # First, clear the existing data
        self.stdout.write(self.style.WARNING('Deleting existing records...'))

        try:
            # Deleting related objects in reverse order due to foreign key constraints
            self.stdout.write(f"Attachments before delete: {Attachment.objects.count()}")
            Attachment.objects.all().delete()
            self.stdout.write(f"Attachments after delete: {Attachment.objects.count()}")

            self.stdout.write(f"Actions before delete: {Action.objects.count()}")
            Action.objects.all().delete()
            self.stdout.write(f"Actions after delete: {Action.objects.count()}")

            self.stdout.write(f"TaskSteps before delete: {TaskStep.objects.count()}")
            TaskStep.objects.all().delete()
            self.stdout.write(f"TaskSteps after delete: {TaskStep.objects.count()}")

            self.stdout.write(f"Steppers before delete: {Stepper.objects.count()}")
            Stepper.objects.all().delete()
            self.stdout.write(f"Steppers after delete: {Stepper.objects.count()}")

            self.stdout.write(self.style.SUCCESS('Successfully deleted all existing Stepper, TaskStep, Action, and Attachment records.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error occurred during deletion: {str(e)}"))
            return  # Exit early if deletion fails
        
        # Fetch the specified users (sanitized demo usernames)
        user_usernames = ['user01', 'user02', 'user03', 'user04', 'user05', 'user06', 'user07']
        users = list(User.objects.filter(username__in=user_usernames))

        # Fetch ObratiOddelki for obrat = 'Ljubljana'
        obrati_oddelki = list(ObratiOddelki.objects.filter(obrat='Ljubljana'))
        
        # Fetch all user groups
        user_groups = list(UserGroup.objects.all())

        # Path to the static image folder
        static_image_path = os.path.join(settings.BASE_DIR, 'static', 'img')

        if not obrati_oddelki:
            self.stdout.write(self.style.ERROR("No ObratiOddelki found for obrat='Ljubljana'."))
            return

        # Prepare lists to collect objects for bulk_create
        steppers_to_create = []
        stepper_groups = []  # To handle ManyToMany relationships after creation
        task_steps_to_create = []
        actions_to_create = []
        attachments_to_create = []

        # Get the path to the media/uploads/dummy folder
        dummy_files_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'dummy')

        # Use glob to find all .jpg, .png, and .pdf files
        image_files = glob.glob(os.path.join(dummy_files_path, '*.[jp][pn]g'))  # Matches .jpg, .png
        pdf_files = glob.glob(os.path.join(dummy_files_path, '*.pdf'))  # Matches .pdf

        # Get only the file names (without the full path)
        image_file_names = [os.path.basename(file) for file in image_files]
        pdf_file_names = [os.path.basename(file) for file in pdf_files]

        # Create Stepper instances where 'user01' is the assigner
        martinmi = next((user for user in users if user.username == 'user01'), None)

        for user in users:
            if user.username == 'user01':
                continue
            for _ in range(8):  # Create 8 steppers for each user
                obrat_oddelek = random.choice(obrati_oddelki)
                project = generate_random_project_name()
                stepper = Stepper(
                    project=project,
                    assigner=martinmi.username,
                    assignee=user.username,
                    assignee_username=user.username,
                    loggedusername=martinmi.username,
                    obrat_oddelek=obrat_oddelek
                )
                steppers_to_create.append(stepper)
                # Assign random groups to the Stepper (handled after saving)
                selected_groups = random.sample(user_groups, k=random.randint(0, len(user_groups)))
                stepper_groups.append((stepper, selected_groups))

        # Create Stepper instances where other users are the assigners
        for user in users:
            if user.username == 'user01':
                continue
            obrat_oddelek = random.choice(obrati_oddelki)
            project = generate_random_project_name()
            stepper = Stepper(
                project=project,
                assigner=user.username,
                assignee=martinmi.username,
                assignee_username=martinmi.username,
                loggedusername=user.username,
                obrat_oddelek=obrat_oddelek
            )
            steppers_to_create.append(stepper)
            selected_groups = random.sample(user_groups, k=random.randint(0, len(user_groups)))
            stepper_groups.append((stepper, selected_groups))

            for other_user in users:
                if other_user.username == user.username:
                    continue
                obrat_oddelek = random.choice(obrati_oddelki)
                project = generate_random_project_name()
                stepper = Stepper(
                    project=project,
                    assigner=user.username,
                    assignee=other_user.username,
                    assignee_username=other_user.username,
                    loggedusername=user.username,
                    obrat_oddelek=obrat_oddelek
                )
                steppers_to_create.append(stepper)
                selected_groups = random.sample(user_groups, k=random.randint(0, len(user_groups)))
                stepper_groups.append((stepper, selected_groups))

        # Bulk create steppers
        Stepper.objects.bulk_create(steppers_to_create)
        self.stdout.write(self.style.SUCCESS(f"Created {len(steppers_to_create)} steppers."))

        # Handle ManyToMany relationships for steppers
        for stepper, groups in stepper_groups:
            stepper.groups.set(groups)

        # Now, create TaskSteps, Actions, and Attachments for each stepper
        # Fetch the saved steppers from the database
        all_steppers = list(Stepper.objects.all())

        for stepper in all_steppers:
            num_steps = random.randint(3, 7)  # Create 3-7 steps for each stepper
            for i in range(1, num_steps + 1):
                # Randomize the status_modified_at over the past 7 months with evenly distributed dates
                today = timezone.now()

                # Ensure the timezone is set to GMT+1 (Ljubljana time)
                local_today = today.astimezone(timezone.get_current_timezone())

                # Offset randomly within the last 7 months
                random_month_offset = random.randint(0, 6)
                date_in_month = local_today - relativedelta(months=random_month_offset)

                # Get the year and month
                year = date_in_month.year
                month = date_in_month.month

                # Get the last valid day of the month
                last_day_of_month = calendar.monthrange(year, month)[1]

                # Choose a random day within the month
                random_day = random.randint(1, last_day_of_month)

                # Generate a random time and ensure it does not exceed the current local time
                random_time = date_in_month.replace(day=random_day, hour=random.randint(0, 23), minute=random.randint(0, 59))

                # Ensure the generated datetime is not in the future
                if random_time > local_today:
                    random_time = local_today

                created_at = date_in_month.replace(day=random_day, hour=random.randint(0, 23), minute=random.randint(0, 59))
                if created_at > local_today:
                    created_at = local_today  # Ensure the datetime is not in the future

                status_modified_at = random_time

                task_step = TaskStep(
                    stepper=stepper,
                    exp_time=timezone.now() + timezone.timedelta(days=random.randint(-10, 10)),
                    order=i,
                    status=random.choice(statuses),
                    machine=f"Machine {random.randint(100, 999)}",
                    product=f"Product {random.randint(1000, 9999)}",
                    description=random.choice(dummy_descriptions),
                    priority=random.choice(priority_choices),
                    status_modified_at=status_modified_at,
                    created_at=created_at,
                    status_modified_by=user.username,
                )
                task_steps_to_create.append(task_step)

        # Bulk create task steps
        TaskStep.objects.bulk_create(task_steps_to_create)
        self.stdout.write(self.style.SUCCESS(f"Created {len(task_steps_to_create)} task steps."))

        # Now create Actions and Attachments for each task step
        # Fetch the saved task steps from the database
        all_task_steps = list(TaskStep.objects.all())

        for task_step in all_task_steps:
            # Actions
            num_actions = random.randint(3, 9)  # Create 3-9 actions for each step
            for _ in range(num_actions):
                action = Action(
                    task_step=task_step,
                    action_name=random.choice(dummy_actions),
                    user=task_step.stepper.assignee_username
                )
                actions_to_create.append(action)

            # Attachments
            num_attachments = random.randint(1, 3)  # Create 1-3 attachments
            for _ in range(num_attachments):
                if random.choice([True, False]):  # Randomly choose between PDF and image
                    if pdf_file_names:
                        pdf_file = random.choice(pdf_file_names)
                        attachment = Attachment(
                            task_step=task_step,
                            file=os.path.join('uploads', 'dummy', pdf_file)  # Relative URL for PDF
                        )
                        attachments_to_create.append(attachment)
                else:
                    if image_file_names:
                        image_file = random.choice(image_file_names)
                        attachment = Attachment(
                            task_step=task_step,
                            file=os.path.join('uploads', 'dummy', image_file)  # Relative URL for image
                        )
                        attachments_to_create.append(attachment)

        # Bulk create actions and attachments
        Action.objects.bulk_create(actions_to_create)
        self.stdout.write(self.style.SUCCESS(f"Created {len(actions_to_create)} actions."))

        Attachment.objects.bulk_create(attachments_to_create)
        self.stdout.write(self.style.SUCCESS(f"Created {len(attachments_to_create)} attachments."))

        self.stdout.write(self.style.SUCCESS('Successfully created dummy data for steppers, steps, actions, and attachments'))
