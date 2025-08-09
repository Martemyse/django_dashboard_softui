# home/management/commands/poll_terminals.py
import requests
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from home.models import Terminal, Signal
from utils.parsers import LogParser

class Command(BaseCommand):
    help = "Poll terminals for logs and process them."

    def handle(self, *args, **options):
        log_parser = LogParser()
        terminals = Terminal.objects.exclude(roboservice_url__isnull=True)

        parse_first_get_and_put = True  # Set this to toggle the parsing behavior

        for terminal in terminals:
            try:
                response = requests.get(terminal.roboservice_url, timeout=10)
                response.raise_for_status()
                data = response.text

                self.process_signal_data(terminal, data, log_parser, parse_first_get_and_put)
            except requests.RequestException as e:
                self.stderr.write(f"Error communicating with terminal {terminal}: {e}")
                # Handle terminal communication status if necessary

    def process_signal_data(self, terminal, raw_data, log_parser, parse_first_get_and_put):
        parsed_logs = log_parser.parse_html_logs(raw_data, parse_first_get_and_put=parse_first_get_and_put)

        new_signals = []
        for parsed_log in parsed_logs:
            new_signal = Signal(
                terminal=terminal,
                timestamp=parsed_log['timestamp'],  # Already an aware datetime
                level=parsed_log['label'],
                message=parsed_log['message'],
            )
            new_signals.append(new_signal)

        if new_signals:
            try:
                Signal.objects.bulk_create(new_signals, ignore_conflicts=True)
            except TypeError:
                # For Django versions < 2.2
                for signal in new_signals:
                    try:
                        signal.save()
                    except IntegrityError:
                        pass  # Signal already exists, skip
