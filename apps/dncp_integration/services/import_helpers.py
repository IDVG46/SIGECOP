import hashlib
import re
from decimal import Decimal

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
    if timezone.is_aware(dt):
        return timezone.make_naive(dt)
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


def parse_order_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return None


def parse_order_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        matches = re.findall(r"\d+(?:\.\d+)?", value)
        if not matches:
            return None
        first = matches[0]
        if "." in first:
            return Decimal(first)
        if len(matches) >= 2:
            return Decimal(f"{matches[0]}.{matches[1]}")
        return Decimal(first)
    return None


def parse_order_subitem_number(value):
    """
    Extrae solo el número de subitem de valores como:
    - '2.1-Cambio discos duros' -> 1
    - '2.10-Algo' -> 10
    - '2.150-Descripcion' -> 150
    """
    if value is None:
        return None
    
    # Convertir directamente a string
    str_value = str(value)
    
    # Buscar el punto decimal y extraer los dígitos después
    if '.' in str_value:
        parts = str_value.split('.')
        if len(parts) >= 2:
            # Tomar la parte después del primer punto
            after_dot = parts[1]
            
            # Extraer solo los dígitos iniciales (antes de cualquier carácter no numérico)
            subitem_digits = ''
            for char in after_dot:
                if char.isdigit():
                    subitem_digits += char
                else:
                    break  # Detener en el primer carácter no numérico
            
            if subitem_digits:
                return int(subitem_digits)
    
    return None


def fallback_subitem_id(item_id, subitem):
    description = subitem.get("description") or ""
    if not description:
        return None
    digest = hashlib.sha1(description.encode("utf-8")).hexdigest()[:12]
    return f"{item_id}-{digest}"
