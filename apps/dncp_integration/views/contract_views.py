from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.db.models import DateTimeField, DecimalField, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract, TenderItem, TenderSubItem
from apps.dncp_integration.views.local_views import (
    _format_amount,
    _format_date,
    _format_open_contract_type,
    _format_quantity,
    _format_total_display,
)


def _build_lot_structure_from_db(award_items_qs, award_subitems_qs, tender):
    """
    Reconstruye la estructura de lotes/items/subitems desde queries de la BD.
    
    Args:
        award_items_qs: QuerySet de AwardItem
        award_subitems_qs: QuerySet de AwardSubItem  
        tender: Objeto Tender
        
    Returns:
        Diccionario con estructura organizada por lotes
    """
    # Agrupar subitems por item
    subitems_by_item = defaultdict(list)
    for award_subitem in award_subitems_qs:
        subitem = award_subitem.subitem
        item_id = subitem.item_id if subitem else None
        subitems_by_item[item_id].append(award_subitem)
    
    # Organizar items por lote
    items_by_lot = defaultdict(list)
    for award_item in award_items_qs:
        item = award_item.item
        if not item:
            continue
        lot_id = item.lot_id if item.lot else None
        items_by_lot[lot_id].append({
            'award_item': award_item,
            'item': item,
            'subitems': subitems_by_item.get(item.id, [])
        })
    
    # Construir estructura de lotes
    lot_structure = {}
    
    if tender:
        criteria = (tender.award_criteria_details or "").lower().strip()
        is_lot_criteria = "lote" in criteria
        is_total_criteria = "total" in criteria
        show_lot_groups = is_lot_criteria or is_total_criteria
        
        if show_lot_groups and tender.lots.exists():
            # Hay lotes definidos - estructurar por lotes
            for lot in tender.lots.all():
                lot_structure[lot.id] = {
                    'lot': lot,
                    'items': items_by_lot.get(lot.id, [])
                }
            
            # Items sin lote asignado
            if None in items_by_lot:
                lot_structure[None] = {
                    'lot': None,
                    'items': items_by_lot[None]
                }
        else:
            # No hay criterio de lotes - agrupar todo
            all_items = []
            for items_list in items_by_lot.values():
                all_items.extend(items_list)
            lot_structure['all'] = {
                'lot': None,
                'items': all_items
            }
    else:
        # Sin tender, agrupar todo
        all_items = []
        for items_list in items_by_lot.values():
            all_items.extend(items_list)
        lot_structure['all'] = {
            'lot': None,
            'items': all_items
        }
    
    return lot_structure


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

        period_start_sort = contract.period_start_date.isoformat() if contract.period_start_date else ""

        entries.append({
            "id": contract.id,
            "tender_id": tender.tenderID if tender else "-",
            "title": tender.title if tender else "-",
            "status": contract.status_details or "-",
            "period": period_display,
            "period_start_sort": period_start_sort,
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

    ordering_qs = Contract.objects.annotate(
        sort_date=Coalesce(
            "period_start_date",
            Value(datetime.min),
            output_field=DateTimeField(),
        ),
    ).order_by("-sort_date", "-id")
    current_sort = contract.period_start_date or datetime.min

    previous_contract = ordering_qs.filter(
        Q(sort_date__gt=current_sort)
        | Q(sort_date=current_sort, id__gt=contract.id)
    ).order_by("sort_date", "id").first()

    next_contract = ordering_qs.filter(
        Q(sort_date__lt=current_sort)
        | Q(sort_date=current_sort, id__lt=contract.id)
    ).order_by("-sort_date", "-id").first()

    first_contract = ordering_qs.first()
    last_contract = ordering_qs.last()

    award_items = AwardItem.objects.filter(award=award).select_related(
        "item",
        "unit_price_currency",
        "item__lot",
    )

    award_subitems = AwardSubItem.objects.filter(award=award).select_related(
        "subitem",
        "subitem__item",
        "unit_price_currency",
    )

    if tender:
        tender_item_order = TenderItem.objects.filter(
            tender=tender,
            item=OuterRef("item_id"),
        ).values("orden")[:1]

        award_items = award_items.annotate(
            sort_order=Coalesce(
                "orden_licitado",
                Subquery(tender_item_order),
                Value(999999),
                output_field=IntegerField(),
            ),
        ).order_by("sort_order", "item_id")

        tender_subitem_order = TenderSubItem.objects.filter(
            tender=tender,
            subitem=OuterRef("subitem_id"),
        ).values("orden")[:1]

        award_subitems = award_subitems.annotate(
            sort_order=Coalesce(
                "orden_licitado",
                Subquery(tender_subitem_order),
                Value(999999),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
        ).order_by("subitem__item_id", "sort_order", "subitem_id")
    else:
        award_items = award_items.order_by("item_id")
        award_subitems = award_subitems.order_by("subitem__item_id", "subitem_id")

    # Agrupar subitems por item_id
    # Esto es crucial porque en la BD, items y subitems están en tablas separadas
    # pero en la visualización deben mostrarse jerárquicamente
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

        sort_order = getattr(award_item, "sort_order", None)
        item_order = award_item.orden_licitado
        if item_order in (None, ""):
            item_order = None if sort_order in (None, "") else sort_order

        item_data = {
            "id": item.id,
            "description": item.description,
            "order": item_order,
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

        # Agregar subitems a este item
        # Los subitems ya están ordenados por sort_order en el querysetanterior
        for award_subitem in subitems_by_item.get(item.id, []):
            subitem = award_subitem.subitem
            if not subitem:
                continue  # Skip si el subitem no existe
            
            subitem_order = award_subitem.orden_licitado
            
            item_data["subitems"].append({
                "description": subitem.description if subitem else "",
                "order": subitem_order,
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
        "nav_contracts": {
            "first": first_contract,
            "previous": previous_contract,
            "next": next_contract,
            "last": last_contract,
        },
        "formatted": {
            "value": _format_amount(contract.value_amount, contract.value_currency),
            "period_start": _format_date(contract.period_start_date),
            "period_end": _format_date(contract.period_end_date),
            "suppliers": suppliers or "-",
        },
    }

    return render(request, "dncp_integration/contract_detail.html", context)
