from decimal import Decimal

from django.db.models import Sum

from apps.procurement.models import FulfillmentMemo, FulfillmentMemoLine
from apps.procurement.utils.decimal_utils import to_decimal


def ordered_quantity_for_order(order):
    total = order.lines.aggregate(total=Sum("quantity"))["total"]
    return to_decimal(total, default="0.000")


def approved_fulfilled_quantity_for_order(order, *, exclude_memo_id=None, exclude_memo=None):
    qs = FulfillmentMemoLine.objects.filter(
        purchase_order=order,
        memo__status=FulfillmentMemo.STATUS_APPROVED,
    )
    if exclude_memo_id is not None:
        qs = qs.exclude(memo_id=exclude_memo_id)
    if exclude_memo is not None:
        qs = qs.exclude(memo=exclude_memo)

    return to_decimal(qs.aggregate(total=Sum("fulfilled_quantity"))["total"], default="0.000")


def approved_fulfilled_quantity_for_order_line(order_line, *, exclude_memo_id=None, exclude_memo=None):
    qs = FulfillmentMemoLine.objects.filter(
        purchase_order_line=order_line,
        memo__status=FulfillmentMemo.STATUS_APPROVED,
    )

    if exclude_memo_id is not None:
        qs = qs.exclude(memo_id=exclude_memo_id)
    if exclude_memo is not None:
        qs = qs.exclude(memo=exclude_memo)

    return to_decimal(qs.aggregate(total=Sum("fulfilled_quantity"))["total"], default="0.000")


def approved_fulfilled_amount_for_order(order, *, exclude_memo_id=None, exclude_memo=None):
    approved_qty = approved_fulfilled_quantity_for_order(
        order,
        exclude_memo_id=exclude_memo_id,
        exclude_memo=exclude_memo,
    )
    ordered_qty = ordered_quantity_for_order(order)
    order_total = to_decimal(getattr(order, "total_amount", None), default="0.00")

    if ordered_qty <= Decimal("0.000"):
        return Decimal("0.00")
    return order_total * (approved_qty / ordered_qty)
