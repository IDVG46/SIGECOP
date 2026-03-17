from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.procurement.services.consistency import validate_order_budget_consistency
from apps.procurement.utils.decimal_utils import to_decimal

_to_decimal = to_decimal


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


def validate_budget_against_order(order, budget):
    """Valida consistencia de contrato y objeto de gasto entre orden y presupuesto."""
    return validate_order_budget_consistency(order, budget)


def validate_payment_context(order, budget, already_paid, payment_amount):
    """Valida contrato/objeto de gasto y monto pendiente de orden para un pago."""
    validate_budget_against_order(order, budget)
    order_total = getattr(order, "total_amount", None)
    validate_payment_against_order(order_total=order_total, already_paid=already_paid, payment_amount=payment_amount)
    return True
