import csv
from datetime import datetime

def initialize_log_file(file_path):
    """
    Initialize or overwrite the log file with headers.
    """
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')  # Use ';' as delimiter
        # Write headers
        writer.writerow([
            "timestamp", "artikel", "stroj", "postaja", "del_id", "sarza", "event_type", "message"
        ])

def log_production_event(
    csv_writer,
    artikel,
    stroj,
    postaja,
    del_id,
    sarza,
    event_type,
    message
):
    """
    Write a row to the CSV log with details about the event.

    :param csv_writer: The csv.writer object already opened in append mode.
    :param artikel: The artikel or product ID
    :param stroj: The machine ID
    :param postaja: The postaja ID (station)
    :param del_id: The part ID
    :param sarza: The batch (sarza) if applicable
    :param event_type: A short tag like 'INFO', 'WARNING', 'ERROR', etc.
    :param message: More detailed explanation.
    """
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")  # Format as dd.mm.YYYY HH:MM
    csv_writer.writerow([
        timestamp,
        artikel or "",
        stroj or "",
        postaja or "",
        del_id or "",
        sarza or "",
        event_type,
        message
    ])

def append_to_log(file_path, rows):
    """
    Append rows to an existing CSV log file.
    """
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')  # Use ';' as delimiter
        for row in rows:
            log_production_event(writer, *row)
