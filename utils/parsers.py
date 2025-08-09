# utils/parsers.py
from datetime import datetime
from bs4 import BeautifulSoup
import pytz

class LogParser:
    def parse_html_logs(self, html_content, parse_first_get_and_put=False):
        soup = BeautifulSoup(html_content, "lxml")  # Use lxml parser for speed
        logs = []
        rows = soup.find_all("tr")

        found_get = False
        found_put = False

        local_tz = pytz.timezone('Europe/Ljubljana')

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                label = cells[0].text.strip()
                timestamp_str = cells[1].text.strip()
                message = cells[2].text.strip()

                try:
                    # Parse timestamp and localize
                    timestamp = datetime.strptime(timestamp_str, '%d.%m.%Y %H:%M:%S.%f')
                    timestamp = local_tz.localize(timestamp)
                except ValueError:
                    continue  # Skip invalid timestamps

                log_entry = {
                    "label": label,
                    "timestamp": timestamp,  # Already aware datetime
                    "message": message,
                }

                logs.append(log_entry)

                if parse_first_get_and_put:
                    if not found_get and "GET" in message:
                        found_get = True
                    if not found_put and "PUT" in message:
                        found_put = True

                    if found_get and found_put:
                        break  # Stop parsing further

        return logs
