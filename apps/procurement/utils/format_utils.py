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
