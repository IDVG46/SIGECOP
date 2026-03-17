"""
Utilidades decimales centralizadas para el módulo procurement.

Antes de esta centralización la función _to_decimal y los helpers de
validación de rango estaban duplicados en al menos 5 archivos:
  - services/balance/balance_service.py
  - services/budget/budget_service.py
  - services/payments/payment_service.py
  - services/finance_service.py
  - templatetags/procurement_format.py
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


def to_decimal(value, default: str = "0.00") -> Decimal:
    """Convierte cualquier valor a Decimal de forma segura.

    Args:
        value: int, float, str, Decimal o None.
        default: cadena decimal usada cuando value es None o no convertible.
    """
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def assert_positive(value: Decimal, label: str) -> None:
    """Lanza ValidationError si value <= 0."""
    if value <= Decimal("0"):
        raise ValidationError(f"{label} debe ser mayor a cero.")


def assert_non_negative(value: Decimal, label: str) -> None:
    """Lanza ValidationError si value < 0."""
    if value < Decimal("0"):
        raise ValidationError(f"{label} no puede quedar en negativo.")
