# populate_signals.py
from django.core.management.base import BaseCommand
from utils.parsers import LogParser  # Correct import
from home.models import Signal, Terminal
from datetime import datetime

class Command(BaseCommand):
    help = "Populate Signal table with realistic log data using full raw data"

    def handle(self, *args, **kwargs):
        terminals = Terminal.objects.all()

        if not terminals.exists():
            self.stdout.write(self.style.ERROR("No terminals found in the database."))
            return

        # Example raw data logs
        raw_data_logs = [
            "INFO\t25.09.2024 09:44:37.866\tTX (183 ms): PUT|20|40|520022331003006847+00130070F03Z2004EW|DMC;@Kvaliteta;@Temperatura;25.00@Tesnost zrak;1.620@Tesnost helij;0.00077@Prebitost;1.00 => ACK",
            "INFO\t25.09.2024 09:44:37.690\tRX: PUT|20|40|520022331003006847+00130070F03Z2004EW|DMC;@Kvaliteta;@Temperatura;25.00@Tesnost zrak;1.620@Tesnost helij;0.00077@Prebitost;1.00",
            "INFO\t25.09.2024 09:43:17.337\tTX (199 ms): GET|20|520022331003006569+00130070F03Z2004EW => 20|40| 0|OK| | 90|1| 40| TMB22| 20| 0| 025463301| | ( )|",
            "INFO\t25.09.2024 09:43:17.145\tRX: GET|20|520022331003006569+00130070F03Z2004EW",
            "INFO\t25.09.2024 09:38:32.339\tTX (539 ms): GET|20|520022331003006841+00130070F03Z2004EW => 20|40| 0|OK| | 90|1| 40| TMB22| 20| 0| 025463301| | ( )|",
            "INFO\t25.09.2024 09:38:31.809\tRX: GET|20|520022331003006841+00130070F03Z2004EW",
            "INFO\t25.09.2024 09:32:35.676\tTX (184 ms): GET|20|520022331003006571+00130070F03Z2004EW => 20|40| 0|OK| | 90|1| 40| TMB22| 20| 0| 025463301| | ( )|",
            "INFO\t25.09.2024 09:32:35.495\tRX: GET|20|520022331003006571+00130070F03Z2004EW",
            "INFO\t25.09.2024 09:31:56.569\tTX (229 ms): GET|20|520022331003006847+00130070F03Z2004EW => 20|40| 0|OK| | 90|1| 40| TMB22| 20| 0| 025463301| | ( )|",
            "INFO\t25.09.2024 09:31:56.346\tRX: GET|20|520022331003006847+00130070F03Z2004EW",
        ]

        signals = []
        log_parser = LogParser()

        for terminal in terminals:
            for raw_log in raw_data_logs:
                try:
                    parsed_log = log_parser.parse_log(raw_log)
                    signals.append(Signal(
                        terminal=terminal,
                        timestamp=parsed_log['timestamp'],
                        level=parsed_log['level'],
                        message=parsed_log['message'],
                        raw_data=parsed_log['raw_data']
                    ))
                except ValueError as e:
                    self.stdout.write(self.style.ERROR(f"Error parsing log: {raw_log}. Error: {e}"))

        Signal.objects.bulk_create(signals)
        self.stdout.write(self.style.SUCCESS(f"Populated {len(signals)} signals for terminals."))
