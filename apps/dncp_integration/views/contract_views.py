from collections import defaultdict

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract
from apps.dncp_integration.views.local_views import (
    _format_amount,
    _format_date,
    _format_open_contract_type,
    _format_quantity,
    _format_total_display,
)


@require_http_methods(["GET"])
def contract_list(request):
    contracts = (
        Contract.objects.select_related(
            "award",
            "award__tender",
            "award__tender__procuring_entity",
            "value_currency",
        )
        .prefetch_related("award__suppliers")
        .order_by("-period_start_date")
    )

    entries = []
    for contract in contracts:
        award = contract.award
        tender = award.tender if award else None
        suppliers = ", ".join([s.name for s in award.suppliers.all()]) if award else "-"
        period_start = _format_date(contract.period_start_date)
        period_end = _format_date(contract.period_end_date)
        period_display = f"{period_start} -> {period_end}" if period_start != "-" or period_end != "-" else "-"

        entries.append({
            "id": contract.id,
            "tender_id": tender.tenderID if tender else "-",
            "title": tender.title if tender else "-",
            "status": contract.status_details or "-",
            "period": period_display,
            "value": _format_amount(contract.value_amount, contract.value_currency),
            "suppliers": suppliers or "-",
        })

    context = {
        "contracts": entries,
        "total": len(entries),
    }

    return render(request, "dncp_integration/contract_list.html", context)


@require_http_methods(["GET"])
def contract_detail(request, contract_id):
    contract = (
        Contract.objects.select_related(
            "award",
            "award__tender",
            "award__tender__procuring_entity",
            "value_currency",
        )
        .prefetch_related("award__suppliers")
        .filter(id=contract_id)
        .first()
    )

    if not contract:
        messages.error(request, "No se encontro el contrato solicitado")
        return redirect("dncp_integration:contract_list")

    award = contract.award
    tender = award.tender if award else None

    award_items = (
        AwardItem.objects.filter(award=award)
        .select_related("item", "unit_price_currency", "item__lot")
        .all()
    )
    award_subitems = (
        AwardSubItem.objects.filter(award=award)
        .select_related("subitem", "subitem__item", "unit_price_currency")
        .all()
    )

    subitems_by_item = defaultdict(list)
    for award_subitem in award_subitems:
        subitem = award_subitem.subitem
        item_id = subitem.item_id if subitem else None
        subitems_by_item[item_id].append(award_subitem)
    criteria = (tender.award_criteria_details or "").lower().strip() if tender else ""
    is_item_criteria = "item" in criteria or "ítem" in criteria
    is_total_criteria = "total" in criteria
    is_lot_criteria = "lote" in criteria
    show_lot_groups = is_lot_criteria or is_total_criteria

    item_entries = []
    lot_entries = []
    lot_entries_index = {}

    for award_item in award_items:
        item = award_item.item
        if not item:
            continue

        item_data = {
            "id": item.id,
            "description": item.description,
            "quantity": _format_quantity(award_item.quantity),
            "unit": item.unit_name or "-",
            "unit_price": _format_amount(award_item.unit_price_amount, award_item.unit_price_currency),
            "total": _format_total_display(
                award_item.unit_price_amount,
                award_item.quantity,
                award_item.unit_price_currency,
            ),
            "subitems": [],
        }

        for award_subitem in subitems_by_item.get(item.id, []):
            subitem = award_subitem.subitem
            item_data["subitems"].append({
                "description": subitem.description if subitem else "",
                "quantity": _format_quantity(award_subitem.quantity),
                "unit": subitem.unit_name if subitem else "-",
                "unit_price": _format_amount(award_subitem.unit_price_amount, award_subitem.unit_price_currency),
                "total": _format_total_display(
                    award_subitem.unit_price_amount,
                    award_subitem.quantity,
                    award_subitem.unit_price_currency,
                ),
            })

        if show_lot_groups and item.lot:
            lot_id = item.lot.id
            entry = lot_entries_index.get(lot_id)
            if not entry:
                entry = {
                    "id": lot_id,
                    "title": item.lot.title or "Lote",
                    "open_contract_type_display": _format_open_contract_type(item.lot.open_contract_type),
                    "value": _format_amount(item.lot.value_amount, item.lot.value_currency),
                    "min_value": _format_amount(item.lot.min_value_amount, item.lot.min_value_currency),
                    "items": [],
                }
                lot_entries_index[lot_id] = entry
                lot_entries.append(entry)
            entry["items"].append(item_data)
        elif show_lot_groups:
            entry = lot_entries_index.get(None)
            if not entry:
                entry = {
                    "id": None,
                    "title": "Sin lote",
                    "open_contract_type_display": "",
                    "value": "-",
                    "min_value": "-",
                    "items": [],
                }
                lot_entries_index[None] = entry
                lot_entries.append(entry)
            entry["items"].append(item_data)
        else:
            item_entries.append(item_data)

    suppliers = ", ".join([s.name for s in award.suppliers.all()]) if award else "-"

    context = {
        "contract": contract,
        "award": award,
        "tender": tender,
        "items": item_entries,
        "lots": lot_entries,
        "show_lot_groups": show_lot_groups,
        "formatted": {
            "value": _format_amount(contract.value_amount, contract.value_currency),
            "period_start": _format_date(contract.period_start_date),
            "period_end": _format_date(contract.period_end_date),
            "suppliers": suppliers or "-",
        },
    }

    return render(request, "dncp_integration/contract_detail.html", context)
