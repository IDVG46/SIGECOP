import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Sum

from apps.dncp_integration.models import AwardItem as DncpAwardItem
from apps.procurement.models import (
    ContractLotBalance,
    FulfillmentMemo,
    FulfillmentMemoLine,
    Payment,
    PaymentAllocation,
    PurchaseOrderLine,
)
from apps.procurement.utils.decimal_utils import to_decimal as _as_dec


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
            "purchase_order__application_scope",
            "award_item__item",
            "award_subitem__subitem__item",
        )
    )

    current_paid_by_order = defaultdict(lambda: Decimal("0.00"))
    for alloc in allocations:
        current_paid_by_order[alloc.purchase_order_id] += _as_dec(alloc.amount)

    order_total_map = defaultdict(lambda: Decimal("0.00"))
    for purchase_order_line in item_lines:
        order_total_map[purchase_order_line.purchase_order_id] += _as_dec(purchase_order_line.line_total)

    memo_lines_by_pol = defaultdict(lambda: defaultdict(lambda: Decimal("0.000")))
    if item_lines:
        pol_ids = [line.id for line in item_lines]
        memo_lines = (
            FulfillmentMemoLine.objects.filter(
                purchase_order_line_id__in=pol_ids,
                memo__status__in=[FulfillmentMemo.STATUS_ISSUED, FulfillmentMemo.STATUS_APPROVED],
            )
            .select_related("application_scope", "memo__application_scope")
            .order_by("id")
        )
        for memo_line in memo_lines:
            detail = (memo_line.application_detail or "").strip()
            scope_name = ""
            if memo_line.application_scope_id and memo_line.application_scope:
                scope_name = (memo_line.application_scope.name or "").strip()
            elif memo_line.memo and memo_line.memo.application_scope_id and memo_line.memo.application_scope:
                scope_name = (memo_line.memo.application_scope.name or "").strip()
            memo_header_detail = (memo_line.memo.application_detail or "").strip() if memo_line.memo else ""

            application_label = detail or memo_header_detail or scope_name or "Sin ámbito"
            memo_lines_by_pol[memo_line.purchase_order_line_id][application_label] += _as_dec(
                memo_line.fulfilled_quantity,
                "0.000",
            )

    fulfilled_total_by_order = defaultdict(lambda: Decimal("0.00"))
    for purchase_order_line in item_lines:
        breakdown = memo_lines_by_pol.get(purchase_order_line.id)
        if not breakdown:
            continue
        fulfilled_qty = sum(breakdown.values(), Decimal("0.000"))
        if fulfilled_qty <= Decimal("0.000"):
            continue
        fulfilled_total_by_order[purchase_order_line.purchase_order_id] += (
            fulfilled_qty * purchase_order_line.unit_price
        )

    order_ratio_map = {}
    for order_id, paid_amount in current_paid_by_order.items():
        basis_total = fulfilled_total_by_order.get(order_id, Decimal("0.00"))
        if basis_total <= Decimal("0.00"):
            basis_total = order_total_map.get(order_id, Decimal("0.00"))
        if basis_total <= Decimal("0.00"):
            order_ratio_map[order_id] = Decimal("0.00")
            continue
        ratio = paid_amount / basis_total
        if ratio < Decimal("0.00"):
            ratio = Decimal("0.00")
        if ratio > Decimal("1.00"):
            ratio = Decimal("1.00")
        order_ratio_map[order_id] = ratio

    # --- Numeración jerárquica de subitems: "padre.X" --------------------------
    # Para cada AwardSubItem, determinar el orden_licitado del AwardItem padre y
    # asignarle un índice secuencial dentro del grupo (mismo padre) → "1.1", "1.2"
    award_item_ord_map = {}   # {(award_id, item_id): orden_licitado}
    subitem_pols_by_parent = defaultdict(list)  # {(award_id, item_id): [pol, ...]}
    for pol in item_lines:
        if pol.award_subitem_id and pol.award_subitem:
            parent_item_id = pol.award_subitem.subitem.item_id
            award_id = pol.award_subitem.award_id
            subitem_pols_by_parent[(award_id, parent_item_id)].append(pol)

    if subitem_pols_by_parent:
        all_award_ids = {k[0] for k in subitem_pols_by_parent}
        for ai in DncpAwardItem.objects.filter(award_id__in=all_award_ids).values("award_id", "item_id", "orden_licitado"):
            award_item_ord_map[(ai["award_id"], ai["item_id"])] = ai["orden_licitado"]

    subitem_label_map = {}  # {pol_id: "parent_num.subitem_orden"}
    for (award_id, parent_item_id), pols in subitem_pols_by_parent.items():
        parent_num = award_item_ord_map.get((award_id, parent_item_id))
        for pol in pols:
            sub_ord = pol.award_subitem.orden_licitado
            label = f"{parent_num}.{sub_ord}" if parent_num is not None else f"?.{sub_ord}"
            subitem_label_map[pol.id] = label
    # ---------------------------------------------------------------------------

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
        if purchase_order_line.award_subitem_id is not None:
            parent_item_id = purchase_order_line.award_subitem.subitem.item_id
            award_id = purchase_order_line.award_subitem.award_id
            parent_ord = award_item_ord_map.get((award_id, parent_item_id), 9999) or 9999
            sub_ord = purchase_order_line.award_subitem.orden_licitado or 9999
            return (order_number, parent_ord, sub_ord, entry[0])
        if purchase_order_line.award_item_id is not None:
            parent_ord = purchase_order_line.award_item.orden_licitado or 9999
            return (order_number, parent_ord, 0, entry[0])
        return (order_number, 9999, 0, entry[0])

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
            order_ratio = order_ratio_map.get(purchase_order_line.purchase_order_id, Decimal("0.00"))
            if order_ratio <= Decimal("0.00"):
                continue

            _parent_key = None
            _parent_num = None
            _parent_description = None
            if purchase_order_line.award_subitem_id is not None:
                _si = purchase_order_line.award_subitem
                _parent_item_id = _si.subitem.item_id
                _parent_award_id = _si.award_id
                _parent_num = award_item_ord_map.get((_parent_award_id, _parent_item_id))
                _parent_key = (_parent_award_id, _parent_item_id, purchase_order_line.purchase_order_id)
                _parent_description = _si.subitem.item.description if _si.subitem.item_id else ""
                item_number = subitem_label_map.get(purchase_order_line.id, _si.orden_licitado)
                description = re.sub(r"^\d+\.\d+\s+", "", _si.subitem.description or "").strip()
            elif purchase_order_line.award_item_id is not None:
                item_number = purchase_order_line.award_item.orden_licitado
                description = purchase_order_line.award_item.item.description
            else:
                item_number = None
                description = "-"

            breakdown = memo_lines_by_pol.get(purchase_order_line.id)
            if breakdown:
                for application_label, scope_qty in breakdown.items():
                    if scope_qty <= Decimal("0.000"):
                        continue
                    scaled_qty_raw = (scope_qty * order_ratio).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                    if scaled_qty_raw <= Decimal("0.000"):
                        continue
                    scope_total = (scaled_qty_raw * purchase_order_line.unit_price).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP,
                    )
                    scaled_qty_display = scaled_qty_raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    current_amount += scope_total
                    items.append(
                        {
                            "item_number": item_number,
                            "description": description,
                            "order_number": purchase_order_line.purchase_order.order_number,
                            "unit_price": purchase_order_line.unit_price,
                            "invoiced_qty": scaled_qty_display,
                            "line_total": scope_total,
                            "application_label": application_label,
                            "is_subitem": _parent_key is not None,
                            "_parent_key": _parent_key,
                            "_parent_num": _parent_num,
                            "_parent_description": _parent_description,
                        }
                    )
            else:
                # Si no hay cumplimiento aprobado para la línea, no se incluye en el reporte de facturación actual.
                continue

        # Inyectar filas de cabecera por item padre antes del primer subitem del grupo
        seen_parent_headers = set()
        items_with_headers = []
        for _it in items:
            _pk = _it.get("_parent_key")
            if _pk is not None and _pk not in seen_parent_headers:
                seen_parent_headers.add(_pk)
                items_with_headers.append({
                    "item_number": _it["_parent_num"],
                    "description": _it["_parent_description"] or "",
                    "order_number": _it["order_number"],
                    "unit_price": None,
                    "invoiced_qty": None,
                    "line_total": Decimal("0.00"),
                    "application_label": _it["application_label"],
                    "is_subitem_header": True,
                })
            items_with_headers.append({k: v for k, v in _it.items() if not k.startswith("_")})
        items = items_with_headers

        # Filas de datos por orden
        order_rowspans = defaultdict(int)
        for item in items:
            order_rowspans[item["order_number"]] += 1

        # Separadores de ámbito que caen DENTRO del rowspan de cada orden:
        # cada cambio de application_label entre ítems consecutivos de la misma orden
        # genera una fila <tr class="detail-application-row"> que el browser cuenta dentro del span.
        order_items_labels = defaultdict(list)
        for item in items:
            order_items_labels[item["order_number"]].append(item["application_label"])
        order_inter_separators = {
            order: sum(
                1 for i in range(1, len(labels)) if labels[i] != labels[i - 1]
            )
            for order, labels in order_items_labels.items()
        }

        seen_orders = set()
        for item in items:
            order_number = item["order_number"]
            if order_number in seen_orders:
                item["show_order"] = False
                item["order_rowspan"] = 0
            else:
                item["show_order"] = True
                item["order_rowspan"] = (
                    order_rowspans[order_number]
                    + order_inter_separators.get(order_number, 0)
                )
                seen_orders.add(order_number)

        # Agrupar filas por orden para poder renderizar cada bloque en un <tbody>
        # y reducir cortes de pagina en impresion.
        order_groups = []
        current_group = None
        for item in items:
            if item["show_order"] or current_group is None:
                current_group = {
                    "order_number": item["order_number"],
                    "order_rowspan": item["order_rowspan"],
                    "items": [],
                }
                order_groups.append(current_group)
            current_group["items"].append(item)

        lot_sections.append(
            {
                "lot": lot,
                "max_amount": max_amount,
                "saldo_anterior": saldo_anterior,
                "current_amount": current_amount,
                "saldo_actual": saldo_anterior - current_amount,
                "prev_paid": prev_paid,
                "items": items,
                "order_groups": order_groups,
            }
        )
        lot_sections_total += current_amount

    return lot_sections, lot_sections_total
