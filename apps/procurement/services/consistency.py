from django.core.exceptions import ValidationError


def _resolve_id(entity, attr_name):
    if entity is None:
        return None

    direct_value = getattr(entity, attr_name, None)
    if direct_value is not None:
        return direct_value

    related_attr = attr_name[:-3] if attr_name.endswith("_id") else None
    if related_attr:
        related_obj = getattr(entity, related_attr, None)
        return getattr(related_obj, "id", None)

    return None


def validate_order_budget_consistency(order, budget):
    """Validate contract and expense object consistency between order and budget."""
    order_contract_id = _resolve_id(order, "contract_id")
    budget_contract_id = _resolve_id(budget, "contract_id")
    if order_contract_id is None or budget_contract_id is None:
        raise ValidationError("No se pudo determinar el contrato para validar la consistencia.")

    if order_contract_id != budget_contract_id:
        raise ValidationError("La orden de compra debe pertenecer al mismo contrato que el presupuesto.")

    order_expense_object_id = _resolve_id(order, "expense_object_id")
    budget_expense_object_id = _resolve_id(budget, "expense_object_id")
    if order_expense_object_id is None or budget_expense_object_id is None:
        raise ValidationError("Orden y presupuesto deben tener objeto de gasto para validar la consistencia.")

    if order_expense_object_id != budget_expense_object_id:
        raise ValidationError("La orden de compra debe tener el mismo objeto de gasto que el presupuesto.")

    return True
