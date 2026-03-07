from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract
from apps.procurement.models import ContractLotBalance, ItemQuantityBalance
from apps.procurement.services.rules import should_enforce_quantity_limit_for_lot_and_quantity


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