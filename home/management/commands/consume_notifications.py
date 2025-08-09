import json
import logging
import pika
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from home.models import Notification, NotificationStatus
from utils.utils import send_response_email

class Command(BaseCommand):
    help = 'Consume notification responses from RabbitMQ'

    def handle(self, *args, **options):
        consumer = NotificationConsumer()
        try:
            consumer.run()
        except KeyboardInterrupt:
            consumer.stop()
        except Exception as e:
            logging.exception("An unexpected error occurred.")

class NotificationConsumer:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._url = self._get_connection_parameters()
        self._exchange = 'notifications_responses'
        self._exchange_type = 'direct'
        self._queue = None
        self._routing_key = 'django_server'
        self._reconnect_delay = 5  # Initial delay for reconnection attempts

    def _get_connection_parameters(self):
        credentials = pika.PlainCredentials(settings.RABBITMQ_USERNAME, settings.RABBITMQ_PASSWORD)
        return pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=600,  # Adjust heartbeat if necessary
            blocked_connection_timeout=300  # Adjust timeout if necessary
        )

    def run(self):
        """Run the consumer by connecting to RabbitMQ and starting the IOLoop."""
        self._connection = self._connect()
        self._connection.ioloop.start()

    def _connect(self):
        """Connect to RabbitMQ using the asynchronous adapter."""
        logging.info('Connecting to RabbitMQ')
        return pika.SelectConnection(
            parameters=self._url,
            on_open_callback=self._on_connection_open,
            on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_closed
        )

    def _on_connection_open(self, connection):
        """Callback when the connection to RabbitMQ is open."""
        logging.info('Connection opened')
        self._reconnect_delay = 5  # Reset the delay after a successful connection
        self._open_channel()

    def _on_connection_open_error(self, connection, exception):
        """Callback when the connection to RabbitMQ fails to open."""
        logging.error('Connection open failed: %s', exception)
        self._schedule_reconnect()

    def _on_connection_closed(self, connection, reason):
        """Callback when the connection to RabbitMQ is closed."""
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            logging.warning('Connection closed, reason: %s', reason)
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt after a delay."""
        if self._closing:
            return
        logging.info('Reconnecting in %d seconds...', self._reconnect_delay)
        self._connection.ioloop.call_later(self._reconnect_delay, self._reconnect)
        # Exponential backoff with a maximum delay
        self._reconnect_delay = min(self._reconnect_delay * 2, 300)

    def _reconnect(self):
        """Attempt to reconnect to RabbitMQ."""
        if self._closing:
            return
        logging.info('Attempting to reconnect to RabbitMQ')
        self._connection = self._connect()

    def _open_channel(self):
        """Open a new channel with RabbitMQ."""
        logging.info('Creating a new channel')
        self._connection.channel(on_open_callback=self._on_channel_open)

    def _on_channel_open(self, channel):
        """Callback when the channel is open."""
        logging.info('Channel opened')
        self._channel = channel
        self._setup_exchange(self._exchange)

    def _setup_exchange(self, exchange_name):
        """Declare the exchange to use."""
        logging.info('Declaring exchange %s', exchange_name)
        self._channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=self._exchange_type,
            durable=True,
            callback=self._on_exchange_declareok
        )

    def _on_exchange_declareok(self, unused_frame):
        """Callback when the exchange is declared."""
        logging.info('Exchange declared')
        self._setup_queue()

    def _setup_queue(self):
        """Declare the queue to consume from."""
        logging.info('Declaring queue')
        self._channel.queue_declare(
            queue='',  # Let RabbitMQ generate a unique queue name
            exclusive=True,
            callback=self._on_queue_declareok
        )

    def _on_queue_declareok(self, method_frame):
        """Callback when the queue is declared."""
        self._queue = method_frame.method.queue
        logging.info('Binding %s to %s with %s', self._exchange, self._queue, self._routing_key)
        self._channel.queue_bind(
            queue=self._queue,
            exchange=self._exchange,
            routing_key=self._routing_key,
            callback=self._on_bindok
        )

    def _on_bindok(self, unused_frame):
        """Callback when the queue is bound to the exchange."""
        logging.info('Queue bound')
        self._start_consuming()

    def _start_consuming(self):
        """Start consuming messages from the queue."""
        logging.info('Starting to consume')
        self._add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(
            queue=self._queue,
            on_message_callback=self._on_message
        )

    def _add_on_cancel_callback(self):
        """Add a callback for when the consumer is cancelled."""
        logging.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self._on_consumer_cancelled)

    def _on_consumer_cancelled(self, method_frame):
        """Callback when the consumer is cancelled."""
        logging.info('Consumer was cancelled remotely, shutting down: %r', method_frame)
        if self._channel:
            self._channel.close()

    def _on_message(self, ch, method, properties, body):
        """Callback when a message is received."""
        logging.info('Received message # %s: %s', method.delivery_tag, body)
        try:
            message = json.loads(body)
            notification_id = message.get('notification_id')
            user_response = message.get('user_response', None)
            status = message.get('status')

            self.update_notification_status(notification_id, status, user_response)
        except Exception as e:
            logging.error(f"Error processing message: {e}")
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def update_notification_status(self, notification_id, status, user_response=None):
        """Update the notification status in the database."""
        try:
            notification = Notification.objects.get(id=notification_id)
            notification_status, created = NotificationStatus.objects.get_or_create(notification=notification)
            notification_status.status = status
            notification_status.save()

            if status == 'replied' and user_response is not None:
                notification.reply_content = user_response
                notification.time_replied = timezone.now()
                notification.receiver_notified = True
                notification.save()

                # Handle sending response email if needed
                if notification.notify_response_email:
                    try:
                        send_response_email(notification)
                        logging.info(f"Response email sent for notification {notification_id}.")
                    except Exception as e:
                        logging.error(f"Failed to send response email for notification {notification_id}: {e}")
            elif status == 'read':
                notification.receiver_notified = True
                notification.save()
            elif status == 'delivered':
                # Update any additional fields if necessary
                pass

            logging.info(f"Notification {notification_id} status updated to '{status}'.")

        except Notification.DoesNotExist:
            logging.error(f"Notification {notification_id} does not exist.")
        except Exception as e:
            logging.error(f"Error updating notification status: {e}")

    def stop(self):
        """Stop the consumer gracefully."""
        logging.info('Stopping')
        self._closing = True
        if self._channel:
            self._channel.basic_cancel(self._consumer_tag, callback=self._on_cancelok)
        else:
            self._connection.ioloop.stop()

    def _on_cancelok(self, unused_frame):
        """Callback when the consumer cancellation is acknowledged."""
        logging.info('Consumer cancelled successfully')
        self._close_channel()

    def _close_channel(self):
        """Close the channel."""
        logging.info('Closing the channel')
        if self._channel:
            self._channel.close()

    def _close_connection(self):
        """Close the connection."""
        logging.info('Closing connection')
        if self._connection:
            self._connection.close()
