from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Sum

from apps.procurement.models import ContractLotBalance, Payment, PaymentAllocation, PurchaseOrderLine


def _as_dec(value, default="0.00"):
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def build_payment_lot_report_sections(payment, allocations, contract=None):
    lot_sections = []
    lot_sections_total = Decimal("0.00")

    current_order_ids = list({alloc.purchase_order_id for alloc in allocations})
    if not current_order_ids:
        return lot_sections, lot_sections_total

    item_lines = list(
        PurchaseOrderLine.objects.filter(purchase_order_id__in=current_order_ids).select_related(
            "lot",
            "purchase_order",
            "award_item__item",
            "award_subitem__subitem",
        )
    )

    lot_pol_totals = defaultdict(lambda: {"qty": Decimal("0.000"), "pol": None})
    lot_obj_map = {}
    for purchase_order_line in item_lines:
        lot_obj_map[purchase_order_line.lot_id] = purchase_order_line.lot
        key = (purchase_order_line.lot_id, purchase_order_line.id)
        lot_pol_totals[key]["qty"] += _as_dec(purchase_order_line.quantity, "0.000")
        lot_pol_totals[key]["pol"] = purchase_order_line

    prev_lot_paid = {}
    lot_balance_map = {}
    if contract is not None and lot_obj_map:
        for balance in ContractLotBalance.objects.filter(contract=contract, lot_id__in=list(lot_obj_map.keys())):
            lot_balance_map[balance.lot_id] = balance

        lot_ids_list = list(lot_obj_map.keys())
        lot_pol_rows = list(
            PurchaseOrderLine.objects.filter(lot_id__in=lot_ids_list).values(
                "lot_id", "purchase_order_id", "quantity", "unit_price"
            )
        )
        lot_order_line_totals = defaultdict(lambda: Decimal("0.00"))
        all_order_ids_for_lots = set()
        for row in lot_pol_rows:
            lot_total = _as_dec(row["quantity"], "0.000") * _as_dec(row["unit_price"])
            lot_order_line_totals[(row["lot_id"], row["purchase_order_id"])] += lot_total
            all_order_ids_for_lots.add(row["purchase_order_id"])

        all_order_ids_for_lots = list(all_order_ids_for_lots)
        order_grand_total_qs = (
            PurchaseOrderLine.objects.filter(purchase_order_id__in=all_order_ids_for_lots)
            .values("purchase_order_id")
            .annotate(grand_total=Sum("line_total"))
        )
        order_grand_totals_map = {
            row["purchase_order_id"]: _as_dec(row["grand_total"])
            for row in order_grand_total_qs
        }

        previous_allocations = (
            PaymentAllocation.objects.filter(
                purchase_order_id__in=all_order_ids_for_lots,
                payment__status=Payment.STATUS_POSTED,
            )
            .filter(
                Q(payment__payment_date__lt=payment.payment_date)
                | Q(payment__payment_date=payment.payment_date, payment__id__lt=payment.id)
            )
            .values("purchase_order_id", "amount")
        )
        order_prev_paid_map = defaultdict(lambda: Decimal("0.00"))
        for row in previous_allocations:
            order_prev_paid_map[row["purchase_order_id"]] += _as_dec(row["amount"])

        for (lot_id, order_id), lot_total in lot_order_line_totals.items():
            order_total = order_grand_totals_map.get(order_id, Decimal("0.00"))
            prev_paid = order_prev_paid_map.get(order_id, Decimal("0.00"))
            if prev_paid > 0 and order_total > 0:
                proportion = lot_total / order_total
                prev_lot_paid[lot_id] = prev_lot_paid.get(lot_id, Decimal("0.00")) + (prev_paid * proportion)

    lot_pols = defaultdict(list)
    for (lot_id, pol_id), data in lot_pol_totals.items():
        lot_pols[lot_id].append((pol_id, data))

    def _pol_sort_key(entry):
        purchase_order_line = entry[1]["pol"]
        order_number = purchase_order_line.purchase_order.order_number or ""
        if purchase_order_line.award_item_id is not None:
            return (order_number, purchase_order_line.award_item.orden_licitado or 9999, entry[0])
        if purchase_order_line.award_subitem_id is not None:
            return (order_number, purchase_order_line.award_subitem.orden_licitado or 9999, entry[0])
        return (order_number, 9999, entry[0])

    for lot_id in sorted(lot_pols.keys(), key=lambda current_lot_id: lot_obj_map[current_lot_id].title):
        lot = lot_obj_map[lot_id]
        lot_balance = lot_balance_map.get(lot_id)
        max_amount = _as_dec(lot_balance.max_amount) if lot_balance else (_as_dec(lot.value_amount) if lot.value_amount else Decimal("0.00"))
        prev_paid = prev_lot_paid.get(lot_id, Decimal("0.00"))
        saldo_anterior = max_amount - prev_paid

        items = []
        current_amount = Decimal("0.00")
        for _, data in sorted(lot_pols[lot_id], key=_pol_sort_key):
            purchase_order_line = data["pol"]
            qty = data["qty"]
            line_total = qty * purchase_order_line.unit_price
            current_amount += line_total

            if purchase_order_line.award_item_id is not None:
                item_number = purchase_order_line.award_item.orden_licitado
                description = purchase_order_line.award_item.item.description
            elif purchase_order_line.award_subitem_id is not None:
                item_number = purchase_order_line.award_subitem.orden_licitado
                description = purchase_order_line.award_subitem.subitem.description
            else:
                item_number = None
                description = "-"

            items.append(
                {
                    "item_number": item_number,
                    "description": description,
                    "order_number": purchase_order_line.purchase_order.order_number,
                    "unit_price": purchase_order_line.unit_price,
                    "invoiced_qty": qty,
                    "line_total": line_total,
                }
            )

        order_rowspans = defaultdict(int)
        for item in items:
            order_rowspans[item["order_number"]] += 1

        seen_orders = set()
        for item in items:
            order_number = item["order_number"]
            if order_number in seen_orders:
                item["show_order"] = False
                item["order_rowspan"] = 0
            else:
                item["show_order"] = True
                item["order_rowspan"] = order_rowspans[order_number]
                seen_orders.add(order_number)

        lot_sections.append(
            {
                "lot": lot,
                "max_amount": max_amount,
                "saldo_anterior": saldo_anterior,
                "current_amount": current_amount,
                "saldo_actual": saldo_anterior - current_amount,
                "prev_paid": prev_paid,
                "items": items,
            }
        )
        lot_sections_total += current_amount

    return lot_sections, lot_sections_total
