from decimal import Decimal, ROUND_HALF_UP

from django import template

register = template.Library()


from apps.procurement.utils.decimal_utils import to_decimal as _to_decimal


def _group_integer_part(integer_text):
    sign = ""
    text = integer_text
    if text.startswith("-"):
        sign = "-"
        text = text[1:]
    grouped = f"{int(text):,}".replace(",", ".")
    return f"{sign}{grouped}"


@register.filter(name="format_amount")
def format_amount(value):
    amount = _to_decimal(value, "0")
    rounded = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return _group_integer_part(str(rounded))


@register.filter(name="format_quantity")
def format_quantity(value):
    quantity = _to_decimal(value, "0").quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    text = f"{quantity:.3f}"
    integer_part, decimal_part = text.split(".")
    grouped_integer = _group_integer_part(integer_part)
    decimal_part = decimal_part.rstrip("0")
    if not decimal_part:
        return grouped_integer
    return f"{grouped_integer},{decimal_part}"
