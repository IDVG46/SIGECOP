from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.procurement.models import ContractLotBalance, ItemQuantityBalance, PurchaseOrder
from apps.procurement.services.rules import should_enforce_quantity_limit_for_lot_and_quantity


def _line_total(line):
    return (line.quantity or Decimal("0")) * (line.unit_price or Decimal("0"))


def _line_max_quantity(line):
    if getattr(line, "award_subitem_id", None):
        return (line.award_subitem.quantity if line.award_subitem else None)
    if getattr(line, "award_item_id", None):
        return (line.award_item.quantity if line.award_item else None)
    return None


def _should_enforce_quantity_limit(line):
    max_qty = _line_max_quantity(line)
    lot = getattr(line, "lot", None)
    return should_enforce_quantity_limit_for_lot_and_quantity(lot, max_qty)


def _validate_contract_amount_limit(order):
    active_total = (
        PurchaseOrder.objects.filter(contract=order.contract)
        .exclude(status=PurchaseOrder.STATUS_CANCELLED)
        .aggregate(total=Sum("total_amount"))["total"]
        or Decimal("0.00")
    )
    contract_max = order.contract.value_amount or Decimal("0.00")
    if active_total > contract_max:
        raise ValidationError(
            f"El total comprometido del contrato excede el máximo permitido. Disponible: {contract_max - active_total}."
        )


def _update_line_totals(order):
    lines = list(order.lines.all())
    total = Decimal("0.00")
    for line in lines:
        current_total = _line_total(line)
        total += current_total
        if line.line_total != current_total:
            line.line_total = current_total
            line.save(update_fields=["line_total"])

    order.total_amount = total
    order.save(update_fields=["total_amount", "updated_at"])


def _collect_contract_aggregates(contract):
    lot_amounts = {}
    item_quantities = {}
    lines_by_lot = {}
    lines_by_item = {}

    active_orders = (
        contract.purchase_orders.exclude(status=PurchaseOrder.STATUS_CANCELLED)
        .prefetch_related("lines__lot", "lines__award_item", "lines__award_subitem")
    )

    for order in active_orders:
        for line in order.lines.all():
            current_total = _line_total(line)
            lot_amounts[line.lot_id] = lot_amounts.get(line.lot_id, Decimal("0.00")) + current_total
            lines_by_lot.setdefault(line.lot_id, line)

            if _should_enforce_quantity_limit(line):
                balance_key = (line.award_item_id, line.award_subitem_id)
                item_quantities[balance_key] = item_quantities.get(balance_key, Decimal("0.000")) + (line.quantity or Decimal("0.000"))
                lines_by_item.setdefault(balance_key, line)

    return lot_amounts, item_quantities, lines_by_lot, lines_by_item


def _validate_and_apply_contract_balances(contract):
    lot_amounts, item_quantities, lines_by_lot, lines_by_item = _collect_contract_aggregates(contract)

    existing_lot_balances = {
        balance.lot_id: balance
        for balance in ContractLotBalance.objects.select_for_update().filter(contract=contract)
    }

    for lot_id in set(existing_lot_balances.keys()) | set(lot_amounts.keys()):
        amount = lot_amounts.get(lot_id, Decimal("0.00"))
        lot_balance = existing_lot_balances.get(lot_id)

        if lot_balance is None:
            line_ref = lines_by_lot.get(lot_id)
            lot_default_max = (line_ref.lot.value_amount if line_ref and line_ref.lot else Decimal("0.00")) or Decimal("0.00")
            lot_balance = ContractLotBalance.objects.create(
                contract=contract,
                lot_id=lot_id,
                min_amount=Decimal("0.00"),
                max_amount=lot_default_max,
                committed_amount=Decimal("0.00"),
            )

        if amount > lot_balance.max_amount:
            raise ValidationError(
                f"El monto en lote {lot_balance.lot_id} excede el máximo permitido ({lot_balance.max_amount})."
            )

        if amount > 0 and amount < lot_balance.min_amount:
            raise ValidationError(
                f"El monto en lote {lot_balance.lot_id} está por debajo del mínimo requerido ({lot_balance.min_amount})."
            )

        if lot_balance.committed_amount != amount:
            lot_balance.committed_amount = amount
            lot_balance.save(update_fields=["committed_amount"])

    existing_qty_balances = {
        (balance.award_item_id, balance.award_subitem_id): balance
        for balance in ItemQuantityBalance.objects.select_for_update().filter(contract=contract)
    }

    for balance_key in set(existing_qty_balances.keys()) | set(item_quantities.keys()):
        qty = item_quantities.get(balance_key, Decimal("0.000"))
        qty_balance = existing_qty_balances.get(balance_key)
        award_item_id, award_subitem_id = balance_key

        if qty_balance is None:
            line_obj = lines_by_item.get(balance_key)
            max_qty_default = Decimal("0.000")
            if line_obj and line_obj.award_item_id:
                max_qty_default = line_obj.award_item.quantity or Decimal("0.000")
            if line_obj and line_obj.award_subitem_id:
                max_qty_default = line_obj.award_subitem.quantity or Decimal("0.000")

            qty_balance = ItemQuantityBalance.objects.create(
                contract=contract,
                award_item_id=award_item_id,
                award_subitem_id=award_subitem_id,
                max_quantity=max_qty_default,
                committed_quantity=Decimal("0.000"),
            )

        if qty > qty_balance.max_quantity:
            raise ValidationError(
                f"La cantidad comprometida excede el máximo para el item/subitem ({qty_balance.max_quantity})."
            )
        if qty_balance.committed_quantity != qty:
            qty_balance.committed_quantity = qty
            qty_balance.save(update_fields=["committed_quantity"])


@transaction.atomic
def recalculate_contract_balances(contract):
    _validate_and_apply_contract_balances(contract)


@transaction.atomic
def recalculate_order_totals_and_balances(order):
    _update_line_totals(order)
    _validate_contract_amount_limit(order)
    recalculate_contract_balances(order.contract)
