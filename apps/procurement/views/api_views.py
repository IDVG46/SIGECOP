from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract
from apps.procurement.models import ContractLotBalance, ItemQuantityBalance
from apps.procurement.models import (
    ContractAmendment,
    ContractBudget,
    FulfillmentMemo,
    FulfillmentMemoLine,
    Payment,
    PurchaseOrder,
    PurchaseOrderLine,
)
from apps.procurement.services.fulfillment_metrics import (
    approved_fulfilled_amount_for_order,
    approved_fulfilled_quantity_for_order,
    approved_fulfilled_quantity_for_order_line,
)
from apps.procurement.services.rules import should_enforce_quantity_limit_for_lot_and_quantity
from apps.procurement.utils.decimal_utils import to_decimal
from apps.procurement.utils.format_utils import format_gs_amount


@login_required
@require_GET
def contract_line_options(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related(
            "award",
            "award__tender",
            "value_currency",
        ),
        id=contract_id,
    )

    award_items = (
        AwardItem.objects.filter(award=contract.award)
        .select_related("item", "item__lot")
        .order_by("item__lot_id", "item_id")
    )
    award_subitems = (
        AwardSubItem.objects.filter(award=contract.award)
        .select_related("subitem", "subitem__item", "subitem__item__lot")
        .order_by("subitem__item__lot_id", "subitem_id")
    )

    lot_balances = {
        balance.lot_id: balance
        for balance in ContractLotBalance.objects.filter(contract=contract).select_related("lot")
    }
    qty_balances_by_item = {
        balance.award_item_id: balance
        for balance in ItemQuantityBalance.objects.filter(contract=contract, award_item__isnull=False)
    }
    qty_balances_by_subitem = {
        balance.award_subitem_id: balance
        for balance in ItemQuantityBalance.objects.filter(contract=contract, award_subitem__isnull=False)
    }

    lots_data = {}
    for award_item in award_items:
        lot = award_item.item.lot if award_item.item else None
        if not lot:
            continue
        if lot.id in lots_data:
            continue
        lot_balance = lot_balances.get(lot.id)
        lots_data[lot.id] = {
            "id": lot.id,
            "text": f"{lot.title}",
            "max_amount": str(lot_balance.max_amount) if lot_balance else str(lot.value_amount or 0),
            "available_amount": str(lot_balance.available_amount) if lot_balance else str(lot.value_amount or 0),
        }

    for award_subitem in award_subitems:
        lot = award_subitem.subitem.item.lot if award_subitem.subitem and award_subitem.subitem.item else None
        if not lot or lot.id in lots_data:
            continue
        lot_balance = lot_balances.get(lot.id)
        lots_data[lot.id] = {
            "id": lot.id,
            "text": f"{lot.title}",
            "max_amount": str(lot_balance.max_amount) if lot_balance else str(lot.value_amount or 0),
            "available_amount": str(lot_balance.available_amount) if lot_balance else str(lot.value_amount or 0),
        }

    for lot_balance in lot_balances.values():
        lot = lot_balance.lot
        if lot.id in lots_data:
            continue
        lots_data[lot.id] = {
            "id": lot.id,
            "text": f"{lot.title}",
            "max_amount": str(lot_balance.max_amount),
            "available_amount": str(lot_balance.available_amount),
        }

    items_data = []
    for award_item in award_items:
        if not award_item.item or not award_item.item.lot:
            continue

        lot = award_item.item.lot
        enforce_quantity_limit = should_enforce_quantity_limit_for_lot_and_quantity(lot, award_item.quantity)
        qty_balance = qty_balances_by_item.get(award_item.id)
        order_value = award_item.orden_licitado if award_item.orden_licitado is not None else "-"

        if enforce_quantity_limit:
            max_qty = qty_balance.max_quantity if qty_balance else award_item.quantity
            available_qty = qty_balance.available_quantity if qty_balance else award_item.quantity
        else:
            max_qty = None
            available_qty = None

        items_data.append(
            {
                "id": award_item.id,
                "lot_id": award_item.item.lot_id,
                "item_definition_id": award_item.item.id,
                "text": f"Orden {order_value}: {award_item.item.description}",
                "unit_price": str(award_item.unit_price_amount or 0),
                "enforce_quantity_limit": enforce_quantity_limit,
                "quantity_control_mode": "quantity" if enforce_quantity_limit else "amount",
                "max_quantity": str(max_qty) if max_qty is not None else None,
                "available_quantity": str(available_qty) if available_qty is not None else None,
            }
        )

    subitems_data = []
    for award_subitem in award_subitems:
        if not award_subitem.subitem or not award_subitem.subitem.item:
            continue
        lot_id = award_subitem.subitem.item.lot_id
        lot = award_subitem.subitem.item.lot
        enforce_quantity_limit = should_enforce_quantity_limit_for_lot_and_quantity(lot, award_subitem.quantity)
        qty_balance = qty_balances_by_subitem.get(award_subitem.id)
        order_value = award_subitem.orden_licitado if award_subitem.orden_licitado is not None else "-"

        if enforce_quantity_limit:
            max_qty = qty_balance.max_quantity if qty_balance else award_subitem.quantity
            available_qty = qty_balance.available_quantity if qty_balance else award_subitem.quantity
        else:
            max_qty = None
            available_qty = None

        subitems_data.append(
            {
                "id": award_subitem.id,
                "lot_id": lot_id,
                "item_definition_id": award_subitem.subitem.item_id,
                "text": f"Orden {order_value}: {award_subitem.subitem.description}",
                "unit_price": str(award_subitem.unit_price_amount or 0),
                "enforce_quantity_limit": enforce_quantity_limit,
                "quantity_control_mode": "quantity" if enforce_quantity_limit else "amount",
                "max_quantity": str(max_qty) if max_qty is not None else None,
                "available_quantity": str(available_qty) if available_qty is not None else None,
            }
        )

    return JsonResponse(
        {
            "contract_id": contract.id,
            "contract": {
                "id": contract.id,
                "status": contract.status_details or "-",
                "amount": str(contract.value_amount or 0),
                "currency": (contract.value_currency.symbol or contract.value_currency.code) if contract.value_currency else "",
                "tender": contract.award.tender.title if contract.award and contract.award.tender else "-",
                "award_id": contract.award.id if contract.award else "-",
            },
            "lots": list(lots_data.values()),
            "items": items_data,
            "subitems": subitems_data,
        }
    )


@login_required
@require_GET
def contract_suppliers(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related(
            "award",
            "award__tender",
            "value_currency",
        ),
        id=contract_id,
    )
    suppliers = contract.award.suppliers.filter(role="supplier").order_by("name")

    supplier_payload = [
        {
            "id": supplier.id,
            "text": supplier.name,
        }
        for supplier in suppliers
    ]

    contract_data = {
        "id": contract.id,
        "status": contract.status_details or "-",
        "amount": str(contract.value_amount or 0),
        "currency": (contract.value_currency.symbol or contract.value_currency.code) if contract.value_currency else "",
        "tender": contract.award.tender.title if contract.award and contract.award.tender else "-",
        "award_id": contract.award.id if contract.award else "-",
    }

    return JsonResponse(
        {
            "contract_id": contract.id,
            "contract": contract_data,
            "suppliers": supplier_payload,
            "preferred_supplier_id": supplier_payload[0]["id"] if len(supplier_payload) == 1 else None,
        }
    )


@login_required
@require_GET
def contract_financial_codes(request, contract_id):
    contract = get_object_or_404(Contract, id=contract_id)

    codes = {str(contract.id).strip()}

    amendment_codes = (
        ContractAmendment.objects.filter(
            contract=contract,
            status__in=[
                ContractAmendment.STATUS_DRAFT,
                ContractAmendment.STATUS_APPROVED,
                ContractAmendment.STATUS_ACTIVE,
            ],
        )
        .exclude(financial_code="")
        .values_list("financial_code", flat=True)
    )
    for code in amendment_codes:
        if code:
            codes.add(str(code).strip())

    budget_codes = (
        ContractBudget.objects.filter(contract=contract)
        .exclude(financial_code="")
        .values_list("financial_code", flat=True)
    )
    for code in budget_codes:
        if code:
            codes.add(str(code).strip())

    ordered_codes = sorted(code for code in codes if code)
    payload = [{"value": code, "label": code} for code in ordered_codes]

    return JsonResponse(
        {
            "contract_id": contract.id,
            "financial_codes": payload,
        }
    )


@login_required
@require_GET
def order_lines_options(request, order_id):
    memo_id = request.GET.get("memo_id")
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("contract", "expense_object", "supplier"),
        pk=order_id,
    )

    lines = (
        PurchaseOrderLine.objects.filter(purchase_order=order)
        .select_related("lot", "award_item__item", "award_subitem__subitem")
        .order_by("id")
    )

    payload = []
    for line in lines:
        approved_line_qty = approved_fulfilled_quantity_for_order_line(line, exclude_memo_id=memo_id)
        pending_quantity = (line.quantity or Decimal("0.000")) - approved_line_qty
        if pending_quantity < Decimal("0.000"):
            pending_quantity = Decimal("0.000")

        item_description = ""
        if line.award_item and line.award_item.item:
            item_description = line.award_item.item.description
        elif line.award_subitem and line.award_subitem.subitem:
            item_description = line.award_subitem.subitem.description

        payload.append(
            {
                "id": line.id,
                "text": f"Linea {line.id} - Lote {line.lot_id} - {item_description} - Pendiente: {pending_quantity}",
                "ordered_quantity": str(line.quantity),
                "pending_quantity": str(pending_quantity),
                "unit_price": str(line.unit_price),
            }
        )

    return JsonResponse(
        {
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "contract_id": order.contract_id,
                "expense_object_id": order.expense_object_id,
                "supplier": order.supplier.name,
            },
            "lines": payload,
        }
    )


@login_required
@require_GET
def contract_lines_options(request, contract_id):
    memo_id = request.GET.get("memo_id")
    contract = get_object_or_404(Contract, pk=contract_id)

    lines = (
        PurchaseOrderLine.objects.filter(purchase_order__contract=contract)
        .exclude(purchase_order__status=PurchaseOrder.STATUS_CANCELLED)
        .select_related(
            "purchase_order",
            "lot",
            "award_item__item",
            "award_subitem__subitem",
        )
        .order_by("purchase_order__order_number", "id")
    )

    payload = []
    line_approved_cache = {}
    for line in lines:
        if line.id not in line_approved_cache:
            line_approved_cache[line.id] = approved_fulfilled_quantity_for_order_line(line, exclude_memo_id=memo_id)

        pending_quantity = (line.quantity or Decimal("0.000")) - line_approved_cache[line.id]
        if pending_quantity < Decimal("0.000"):
            pending_quantity = Decimal("0.000")

        item_description = ""
        if line.award_item and line.award_item.item:
            item_description = line.award_item.item.description
        elif line.award_subitem and line.award_subitem.subitem:
            item_description = line.award_subitem.subitem.description

        payload.append(
            {
                "id": line.id,
                "text": (
                    f"OC {line.purchase_order.order_number} - "
                    f"Linea {line.id} - Lote {line.lot_id} - {item_description} - "
                    f"Pendiente: {pending_quantity}"
                ),
                "order_id": line.purchase_order_id,
                "order_number": line.purchase_order.order_number,
                "ordered_quantity": str(line.quantity),
                "pending_quantity": str(pending_quantity),
                "unit_price": str(line.unit_price),
            }
        )

    return JsonResponse(
        {
            "contract": {
                "id": contract.id,
            },
            "lines": payload,
        }
    )


@login_required
@require_GET
def order_budgets_options(request, order_id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("contract", "expense_object"),
        pk=order_id,
    )

    budgets = (
        ContractBudget.objects.filter(
            contract=order.contract,
            expense_object=order.expense_object,
        )
        .exclude(status=ContractBudget.STATUS_CANCELLED)
        .order_by("-fiscal_year", "id")
    )

    payload = []
    for budget in budgets:
        payload.append(
            {
                "id": budget.id,
                "text": (
                    f"Presupuesto {budget.id} - "
                    f"Disponible: {format_gs_amount(budget.available_amount)} - "
                    f"Fuente: {budget.funding_source}"
                ),
                "available_amount": str(budget.available_amount),
            }
        )

    return JsonResponse(
        {
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "contract_id": order.contract_id,
                "expense_object_id": order.expense_object_id,
            },
            "budgets": payload,
        }
    )


@login_required
@require_GET
def budget_orders_options(request, budget_id):
    budget = get_object_or_404(
        ContractBudget.objects.select_related("contract", "expense_object"),
        pk=budget_id,
    )

    base_orders = PurchaseOrder.objects.filter(contract=budget.contract).exclude(status=PurchaseOrder.STATUS_CANCELLED)
    orders = (
        PurchaseOrder.objects.filter(
            contract=budget.contract,
            expense_object=budget.expense_object,
        )
        .exclude(status=PurchaseOrder.STATUS_CANCELLED)
        .order_by("-issue_date", "order_number")
    )

    payload = []
    for order in orders:
        already_paid = (
            order.payment_allocations.filter(payment__status=Payment.STATUS_POSTED).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )
        approved_fulfilled_amount = approved_fulfilled_amount_for_order(order)
        order_total = order.total_amount or 0
        pending_by_order = order_total - already_paid
        payable_by_fulfillment = approved_fulfilled_amount - already_paid

        payload.append(
            {
                "id": order.id,
                "text": (
                    f"{order.order_number} - "
                    f"Pendiente orden: {format_gs_amount(pending_by_order)} - "
                    f"Aprobado por cumplimiento: {format_gs_amount(payable_by_fulfillment)}"
                ),
                "order_total": str(order_total),
                "already_paid": str(already_paid),
                "approved_fulfilled_amount": str(approved_fulfilled_amount),
                "pending_by_order": str(pending_by_order),
                "payable_by_fulfillment": str(payable_by_fulfillment),
            }
        )

    return JsonResponse(
        {
            "budget": {
                "id": budget.id,
                "contract_id": budget.contract_id,
                "expense_object_id": budget.expense_object_id,
                "available_amount": str(budget.available_amount),
            },
            "diagnostics": {
                "orders_in_contract": base_orders.count(),
                "orders_compatible": len(payload),
            },
            "orders": payload,
        }
    )


@login_required
@require_GET
def contract_orders_options(request, contract_id):
    """
    Devuelve órdenes de compra filtradas por contrato, excluyendo las canceladas.
    Optimiza la carga de órdenes en el formulario de pago evitando cargar todas a la vez.
    """
    from django.shortcuts import get_object_or_404
    contract = get_object_or_404(Contract, id=contract_id)

    orders = (
        PurchaseOrder.objects.filter(contract=contract)
        .exclude(status=PurchaseOrder.STATUS_CANCELLED)
        .select_related("supplier", "expense_object")
        .order_by("-issue_date", "order_number")
    )

    payload = []
    for order in orders:
        already_paid = (
            order.payment_allocations.filter(payment__status=Payment.STATUS_POSTED).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )
        order_total = order.total_amount or 0
        pending_by_order = order_total - already_paid

        ordered_qty = (
            order.lines.aggregate(total=models.Sum("quantity"))["total"]
            or Decimal("0.000")
        )
        approved_qty = approved_fulfilled_quantity_for_order(order)
        pending_quantity = ordered_qty - approved_qty
        if pending_quantity < Decimal("0.000"):
            pending_quantity = Decimal("0.000")

        payload.append(
            {
                "id": order.id,
                "text": f"{order.order_number} - Proveedor: {order.supplier.name} - Pendiente: {format_gs_amount(pending_by_order)}",
                "order_number": order.order_number,
                "supplier": order.supplier.name,
                "expense_object_id": order.expense_object_id,
                "order_total": str(order_total),
                "already_paid": str(already_paid),
                "pending_by_order": str(pending_by_order),
                    "pending_quantity": str(pending_quantity),
                "status": order.status,
            }
        )

    return JsonResponse(
        {
            "contract_id": contract_id,
            "orders_count": len(payload),
            "orders": payload,
        }
    )