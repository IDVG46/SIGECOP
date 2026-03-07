from decimal import Decimal

from django.core.exceptions import ValidationError


# Nota: este servicio esta preparado para enchufarse al futuro modelo ContractBudget.
# Se apoya en atributos convencionales: assigned_amount, committed_amount, executed_amount.
def _to_decimal(value, default="0.00"):
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _assert_amount(value, label):
    if value <= Decimal("0"):
        raise ValidationError(f"{label} debe ser mayor a cero.")


def apply_budget_commitment(budget, amount):
    delta = _to_decimal(amount)
    _assert_amount(delta, "El monto a comprometer")

    assigned = _to_decimal(getattr(budget, "assigned_amount", None))
    committed = _to_decimal(getattr(budget, "committed_amount", None))
    executed = _to_decimal(getattr(budget, "executed_amount", None))

    if committed + executed + delta > assigned:
        raise ValidationError("El compromiso excede el presupuesto disponible.")

    budget.committed_amount = committed + delta
    return budget


def release_budget_commitment(budget, amount):
    delta = _to_decimal(amount)
    _assert_amount(delta, "El monto a liberar")

    committed = _to_decimal(getattr(budget, "committed_amount", None))
    new_committed = committed - delta
    if new_committed < Decimal("0"):
        raise ValidationError("El comprometido no puede quedar en negativo.")

    budget.committed_amount = new_committed
    return budget


def apply_budget_execution(budget, amount):
    delta = _to_decimal(amount)
    _assert_amount(delta, "El monto a ejecutar")

    committed = _to_decimal(getattr(budget, "committed_amount", None))
    executed = _to_decimal(getattr(budget, "executed_amount", None))

    if delta > committed:
        raise ValidationError("No se puede ejecutar mas que el comprometido.")

    budget.committed_amount = committed - delta
    budget.executed_amount = executed + delta
    return budget


def reverse_budget_execution(budget, amount):
    delta = _to_decimal(amount)
    _assert_amount(delta, "El monto a revertir")

    executed = _to_decimal(getattr(budget, "executed_amount", None))
    if delta > executed:
        raise ValidationError("No se puede revertir mas que el ejecutado.")

    budget.executed_amount = executed - delta
    budget.committed_amount = _to_decimal(getattr(budget, "committed_amount", None)) + delta
    return budget
