from django import template
import os

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}

@register.filter
def in_group(user, group_names):
    return user.user_role in group_names.split(',')

@register.filter
def in_list(value, the_list):
    """Check if a value is in a given list."""
    return value in the_list

@register.filter
def extract_days(time_str):
    """Extracts days from a timesince output string."""
    parts = time_str.split(',')
    if len(parts) > 0 and 'day' in parts[0]:
        return parts[0].strip()
    return "0 dni"

@register.filter
def extract_hours(time_str):
    """Extracts hours from a timesince output string."""
    parts = time_str.split(',')
    for part in parts:
        if 'hour' in part or 'ure' in part:
            return part.strip()
    return "0 ur"

@register.filter
def file_extension(value):
    """Extracts the file extension from a filename."""
    return os.path.splitext(value)[1][1:].lower()

@register.filter
def basename(value):
    """Extracts the base name of a file."""
    return os.path.basename(value)

@register.filter
def get_receiver_username(notification):
    return notification.receiver_user.username if notification.receiver_user else "N/A"

@register.filter
def is_within_threshold(value, threshold):
    """Checks if a value is within a threshold."""
    try:
        return float(value) <= float(threshold)
    except (ValueError, TypeError):
        return False