from decimal import Decimal, ROUND_HALF_UP

from apps.procurement.utils.decimal_utils import to_decimal


def format_gs_amount(value):
    """Devuelve un monto en formato de guaranies: Gs. 1.234.567"""
    amount = to_decimal(value, default="0")
    rounded = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    integer_value = abs(int(rounded))
    grouped = f"{integer_value:,}".replace(",", ".")
    return f"Gs. {sign}{grouped}"


def format_quantity(value):
    """Formatea cantidades con separador local y sin ceros decimales innecesarios."""
    quantity = to_decimal(value, default="0").quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    text = f"{quantity:.3f}"
    integer_part, decimal_part = text.split(".")
    sign = ""
    if integer_part.startswith("-"):
        sign = "-"
        integer_part = integer_part[1:]
    grouped_integer = f"{int(integer_part):,}".replace(",", ".")
    decimal_part = decimal_part.rstrip("0")
    if not decimal_part:
        return f"{sign}{grouped_integer}"
    return f"{sign}{grouped_integer},{decimal_part}"
