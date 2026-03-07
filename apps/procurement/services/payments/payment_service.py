from decimal import Decimal

from django.core.exceptions import ValidationError


def _to_decimal(value, default="0.00"):
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def validate_payment_against_order(order_total, already_paid, payment_amount):
    """Valida que un pago no exceda el pendiente de la orden."""
    total = _to_decimal(order_total)
    paid = _to_decimal(already_paid)
    incoming = _to_decimal(payment_amount)

    if incoming <= Decimal("0"):
        raise ValidationError("El monto de pago debe ser mayor a cero.")

    pending = total - paid
    if pending < Decimal("0"):
        raise ValidationError("La orden ya presenta sobrepago y requiere correccion.")

    if incoming > pending:
        raise ValidationError(
            f"El pago excede el saldo pendiente de la orden. Pendiente actual: {pending}."
        )

    return True
