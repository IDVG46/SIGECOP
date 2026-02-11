import hashlib

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def extract_tender_number(ocid):
    if not ocid:
        return None
    parts = ocid.split("-")
    if len(parts) < 3:
        return None
    number = parts[2]
    return int(number) if number.isdigit() else None


def get_amount(value):
    if not isinstance(value, dict):
        return None
    return value.get("amount")


def parse_dt(value):
    if not value:
        return None
    dt = parse_datetime(value)
    if not dt:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def fallback_item_id(item, prefix):
    description = item.get("description") or ""
    if not description:
        return None
    digest = hashlib.sha1(description.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def get_attribute_value(attributes, name):
    for attr in attributes or []:
        if attr.get("name") == name:
            return attr.get("value")
    return None


def fallback_subitem_id(item_id, subitem):
    description = subitem.get("description") or ""
    if not description:
        return None
    digest = hashlib.sha1(description.encode("utf-8")).hexdigest()[:12]
    return f"{item_id}-{digest}"
