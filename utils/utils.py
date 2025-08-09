# utils/utils.py
import pika
from django.conf import settings
import json
import uuid
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail

# Mappings for obrat and oddelek
OBRAT_MAPPING = {
    'Ljubljana': 'LJ',
    'Škofja Loka': 'SL',
    'Trata': 'TR',
    'Benkovac': 'BE',
    'Čakovec': 'CK',
    'Ohrid': 'OH',
    'LTH': 'LTH',
}

# Inverse mapping for convenience
OBRAT_INVERSE_MAPPING = {v: k for k, v in OBRAT_MAPPING.items()}

def get_short_obrat(long_name):
    """Convert long name to short name."""
    return OBRAT_MAPPING.get(long_name, '')

def get_long_obrat(short_name):
    """Convert short name to long name."""
    return OBRAT_INVERSE_MAPPING.get(short_name, '')

# Mappings for URL conversion
URL_TO_RAW_MAPPING = {
    'tehno_obd': 'Tehnologija obdelave',
    'obd': 'Obdelava',
    'var': 'Varnost',
    'liv': 'Livarna',
    'vzd': 'Vzdrževanje',
    'razvoj': 'Razvoj',
    'ekologija': 'Ekologija',
    'tc': 'Tehnična čistost',
    'sredstva': 'Sredstva & Energenti',
    'lth': 'LTH',
    'aktivnosti': 'LTH Pregled aktivnosti',
    'urna_produkcija': 'Urna Produkcija',
    'urnik': 'Urnik',
    'kakovost':'Kakovost',
    'reklamacija':'Reklamacije',
    'svd':'Varnostni Pregledi SVD',
    'signali_strojev':'Signali strojev',
    'vgradni_deli':'Vgradni deli',

}

URL_TO_RAW_MAPPING_APP = {
    'sredstva': 'Sredstva & Energenti',
    'lth': 'LTH',
    'aktivnosti': 'LTH Pregled aktivnosti',
    'urna_produkcija': 'Urna Produkcija',
    'urnik': 'Urnik',
    'reklamacija':'Reklamacije',
    'svd':'Varnostni Pregledi SVD',
    'signali_strojev':'Signali strojev',
    'vgradni_deli':'Vgradni deli',
}

# Create the inverse mapping for app
RAW_TO_URL_MAPPING_APP = {v: k for k, v in URL_TO_RAW_MAPPING_APP.items()}

# Create the inverse mapping for all mappings
RAW_TO_URL_MAPPING = {v: k for k, v in URL_TO_RAW_MAPPING.items()}

# URL-safe mapping for obrat
SAFE_URL_OBRAT_MAPPING = {
    'Ljubljana': 'lj',
    'Škofja Loka': 'sl',
    'Trata': 'tr',
    'Benkovac': 'be',
    'Čakovec': 'ck',
    'Ohrid': 'oh',
    'LTH': 'lth'
}

OBRAT_MAPPING = {
    'Ljubljana': 'LJ',
    'Škofja Loka': 'SL',
    'Trata': 'TR',
    'Benkovac': 'BE',
    'Čakovec': 'CK',
    'Ohrid': 'OH',
    'LTH': 'LTH',
}

OBRAT_INVERSE_MAPPING = {v: k for k, v in OBRAT_MAPPING.items()}

def get_short_obrat(long_name):
    return OBRAT_MAPPING.get(long_name, '')

def get_long_obrat(short_name):
    return OBRAT_INVERSE_MAPPING.get(short_name, '')

def send_notification_via_rabbitmq(notification):
    credentials = pika.PlainCredentials(settings.RABBITMQ_USERNAME, settings.RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    exchange_name = 'notifications'
    channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)

    if notification.receiver_token:
        routing_key = str(notification.receiver_token.token)
        print(f"Sending notification with routing key: {routing_key}")
    else:
        print("No receiver token found, notification cannot be sent.")
        connection.close()
        return

    message = {
        'notification_id': notification.id,
        'key': notification.key,
        'sender_user': notification.sender_user.username,
        'notification_content': notification.notification_content,
    }

    channel.basic_publish(
        exchange=exchange_name,
        routing_key=routing_key,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,
        )
    )
    connection.close()


def get_client_ip(request):
    # print(f"Request META: {request.META}")
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    print(f"Detected client IP: {ip}")
    return ip

def register_token_in_rabbitmq(token):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(settings.RABBITMQ_USERNAME, settings.RABBITMQ_PASSWORD)
        )
    )
    channel = connection.channel()
    
    # Declare an exchange for notifications
    channel.exchange_declare(exchange='notifications', exchange_type='direct', durable=True)
    
    # Bind the token to a queue using the token as the routing key
    queue_name = f'queue_{token}'
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(exchange='notifications', queue=queue_name, routing_key=token)
    
    connection.close()

def generate_and_register_token(user, terminal=None, ip_address=None):
    # Generate a unique token
    token = str(uuid.uuid4())
    
    # Create ClientToken entry
    client_token = ClientToken.objects.create(
        token=token,
        user=user,
        terminal=terminal,
        ip_address=ip_address,
        expires_at=timezone.now() + timezone.timedelta(hours=9)  # Token valid for 1 hour
    )
    
    # Register token with RabbitMQ
    register_token_in_rabbitmq(token)
    
    # return client_token.token

def send_notification_email(recipient, subject, message_content):
    """
    Send an email notification to a specified user.

    Parameters:
    recipient (User): The user to whom the email will be sent. It must have a valid email attribute.
    subject (str): Subject of the email.
    message_content (str): Main content of the notification email.
    """
    if not recipient.email:
        raise ValueError("Recipient must have a valid email address")

    # Render the HTML and plain text content
    html_content = render_to_string("notifications/email_template.html", {
        'username': recipient.username,
        'message_content': message_content,
    })
    text_content = strip_tags(html_content)

    send_mail(
        subject=subject,
        message=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient.email],
        html_message=html_content
    )

def send_response_email(notification):
    subject = f"Response to Your Notification: {notification.key}"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_email = notification.sender_user.email

    # Render email content
    email_content = render_to_string('email_templates/response_notification_email.html', {
        'sender': notification.receiver_user,
        'notification_content': notification.notification_content,
        'reply_content': notification.reply_content,
        'timestamp': notification.time_replied,
        'terminal_info': notification.receiver_terminal,
        'obrat_oddelek': notification.receiver_user.obrat_oddelek,
    })

    # Send email
    send_mail(subject, email_content, from_email, [recipient_email], fail_silently=False)

# from ipware import get_client_ip

# def get_client_ip_ipware(request):
#     ip, is_routable = get_client_ip(request)
#     if ip:
#         print(f"Client IP: {ip}")
#     else:
#         print("Unable to get the client's IP address")
#     return ip