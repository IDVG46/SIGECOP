from django.core.exceptions import ValidationError
from django.db import transaction

from apps.procurement.models import ContractLotBalance, ItemQuantityBalance
from apps.procurement.utils.decimal_utils import assert_non_negative, assert_positive, to_decimal

# Alias para compatibilidad con el cuerpo del módulo
_to_decimal = to_decimal
_validate_non_negative = assert_non_negative
_validate_positive_delta = assert_positive


@transaction.atomic
def commit_lot_amount(lot_balance: ContractLotBalance, amount):
    delta = _to_decimal(amount)
    _validate_positive_delta(delta, "El monto a comprometer")

    max_amount = _to_decimal(lot_balance.max_amount)
    committed = _to_decimal(lot_balance.committed_amount)
    executed = _to_decimal(lot_balance.executed_amount)

    if committed + executed + delta > max_amount:
        raise ValidationError("El compromiso excede el maximo permitido del lote.")

    lot_balance.committed_amount = committed + delta
    lot_balance.save(update_fields=["committed_amount"])
    return lot_balance


@transaction.atomic
def release_lot_amount(lot_balance: ContractLotBalance, amount):
    delta = _to_decimal(amount)
    _validate_positive_delta(delta, "El monto a liberar")

    committed = _to_decimal(lot_balance.committed_amount)
    new_value = committed - delta
    _validate_non_negative(new_value, "El comprometido de lote")

    lot_balance.committed_amount = new_value
    lot_balance.save(update_fields=["committed_amount"])
    return lot_balance


@transaction.atomic
def execute_lot_amount(lot_balance: ContractLotBalance, amount):
    delta = _to_decimal(amount)
    _validate_positive_delta(delta, "El monto a ejecutar")

    committed = _to_decimal(lot_balance.committed_amount)
    executed = _to_decimal(lot_balance.executed_amount)

    if delta > committed:
        raise ValidationError("No se puede ejecutar mas monto del que esta comprometido en el lote.")

    lot_balance.committed_amount = committed - delta
    lot_balance.executed_amount = executed + delta
    lot_balance.save(update_fields=["committed_amount", "executed_amount"])
    return lot_balance


@transaction.atomic
def reverse_lot_execution(lot_balance: ContractLotBalance, amount):
    delta = _to_decimal(amount)
    _validate_positive_delta(delta, "El monto a revertir")

    executed = _to_decimal(lot_balance.executed_amount)
    new_executed = executed - delta
    _validate_non_negative(new_executed, "El ejecutado de lote")

    lot_balance.executed_amount = new_executed
    lot_balance.committed_amount = _to_decimal(lot_balance.committed_amount) + delta
    lot_balance.save(update_fields=["committed_amount", "executed_amount"])
    return lot_balance


@transaction.atomic
def commit_item_quantity(item_balance: ItemQuantityBalance, quantity):
    delta = _to_decimal(quantity, default="0.000")
    _validate_positive_delta(delta, "La cantidad a comprometer")

    max_qty = _to_decimal(item_balance.max_quantity, default="0.000")
    committed = _to_decimal(item_balance.committed_quantity, default="0.000")
    executed = _to_decimal(item_balance.executed_quantity, default="0.000")

    if committed + executed + delta > max_qty:
        raise ValidationError("El compromiso excede la cantidad maxima permitida para item/subitem.")

    item_balance.committed_quantity = committed + delta
    item_balance.save(update_fields=["committed_quantity"])
    return item_balance


@transaction.atomic
def release_item_quantity(item_balance: ItemQuantityBalance, quantity):
    delta = _to_decimal(quantity, default="0.000")
    _validate_positive_delta(delta, "La cantidad a liberar")

    committed = _to_decimal(item_balance.committed_quantity, default="0.000")
    new_value = committed - delta
    _validate_non_negative(new_value, "El comprometido de item/subitem")

    item_balance.committed_quantity = new_value
    item_balance.save(update_fields=["committed_quantity"])
    return item_balance


@transaction.atomic
def execute_item_quantity(item_balance: ItemQuantityBalance, quantity):
    delta = _to_decimal(quantity, default="0.000")
    _validate_positive_delta(delta, "La cantidad a ejecutar")

    committed = _to_decimal(item_balance.committed_quantity, default="0.000")
    executed = _to_decimal(item_balance.executed_quantity, default="0.000")

    if delta > committed:
        raise ValidationError("No se puede ejecutar mas cantidad de la comprometida en item/subitem.")

    item_balance.committed_quantity = committed - delta
    item_balance.executed_quantity = executed + delta
    item_balance.save(update_fields=["committed_quantity", "executed_quantity"])
    return item_balance


@transaction.atomic
def reverse_item_execution(item_balance: ItemQuantityBalance, quantity):
    delta = _to_decimal(quantity, default="0.000")
    _validate_positive_delta(delta, "La cantidad a revertir")

    executed = _to_decimal(item_balance.executed_quantity, default="0.000")
    new_executed = executed - delta
    _validate_non_negative(new_executed, "El ejecutado de item/subitem")

    item_balance.executed_quantity = new_executed
    item_balance.committed_quantity = _to_decimal(item_balance.committed_quantity, default="0.000") + delta
    item_balance.save(update_fields=["committed_quantity", "executed_quantity"])
    return item_balance
