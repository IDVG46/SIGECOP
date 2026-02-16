from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from apps.dncp_integration.models import (
    Award,
    CompiledRelease,
    Tender,
    TenderItem,
    TenderSubItem,
)


def _format_amount(amount, currency=None):
    if amount is None:
        return "-"
    formatted = f"{amount:,.0f}".replace(",", ".")
    if currency and hasattr(currency, 'symbol'):
        return f"{currency.symbol} {formatted}"
    return formatted


def _format_date(value):
    if not value:
        return "-"
    dt = value
    if timezone.is_naive(dt):
        local_dt = dt
    else:
        local_dt = timezone.localtime(dt)
    return local_dt.strftime("%d/%m/%Y %H:%M")


def _compute_total(unit_price, quantity):
    if unit_price is None or quantity is None:
        return "-"
    try:
        total = Decimal(unit_price) * Decimal(quantity)
    except Exception:
        return "-"
    return total


def _format_quantity(quantity):
    if quantity is None:
        return "Definido por monto"
    return quantity


def _format_total_display(unit_price, quantity, currency):
    if quantity is None:
        return "Definido por monto"
    total_value = _compute_total(unit_price, quantity)
    return _format_amount(total_value, currency) if total_value != "-" else "-"


def _format_open_contract_type(value):
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in ("no", "n/a", "none"):
        return "No"
    if lowered.startswith("por "):
        return f"Por {text[4:].strip()}"
    if lowered in ("monto", "cantidad", "total"):
        return f"Por {lowered}"
    return f"Por {text}"


def _format_award_criteria(value):
    if not value:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    lowered = text.lower()
    if "item" in lowered or "ítem" in lowered:
        return "Por item"
    if "lote" in lowered:
        return "Por lote"
    if "total" in lowered:
        return "Por total"
    return text


@require_http_methods(["GET"])
def tender_list(request):
    tenders = (
        Tender.objects.select_related("compiled_release", "procuring_entity")
        .order_by("-tenderID")
    )

    tender_entries = []
    for tender in tenders:
        compiled_release = tender.compiled_release
        published = tender.date_published or (compiled_release.date if compiled_release else None)
        tender_entries.append({
            "ocid": compiled_release.ocid if compiled_release else "-",
            "tender_id": tender.tenderID,
            "title": tender.title,
            "procuring_entity": tender.procuring_entity.name if tender.procuring_entity else "-",
            "status": tender.status_details or "-",
            "date": _format_date(published),
        })

    context = {
        "tenders": tender_entries,
        "total": len(tender_entries),
    }

    return render(request, "dncp_integration/tender_list.html", context)


@require_http_methods(["GET"])
def tender_detail(request, ocid):
    compiled_release = CompiledRelease.objects.filter(ocid=ocid).first()
    if not compiled_release:
        messages.error(request, "No se encontro un proceso local para el OCID indicado")
        return redirect("dncp_integration:tender_list")

    tender = Tender.objects.filter(compiled_release=compiled_release).select_related(
        "value_currency",
        "procuring_entity",
    ).first()
    if not tender:
        messages.error(request, "No se encontro el tender local asociado al OCID")
        return redirect("dncp_integration:tender_list")

    ordering_qs = Tender.objects.select_related("compiled_release").order_by("-tenderID", "-id")
    current_key = tender.tenderID or 0

    previous_tender = ordering_qs.filter(
        Q(tenderID__gt=current_key)
        | Q(tenderID=current_key, id__gt=tender.id)
    ).order_by("tenderID", "id").first()

    next_tender = ordering_qs.filter(
        Q(tenderID__lt=current_key)
        | Q(tenderID=current_key, id__lt=tender.id)
    ).order_by("-tenderID", "-id").first()

    first_tender = ordering_qs.first()
    last_tender = ordering_qs.last()

    lots = list(
        tender.lots.select_related("value_currency", "min_value_currency").all()
    )

    tender_items = list(
        TenderItem.objects.filter(tender=tender)
        .select_related("item", "item__lot", "unit_price_currency")
        .all()
    )

    tender_subitems = list(
        TenderSubItem.objects.filter(tender=tender)
        .select_related("subitem", "subitem__item", "unit_price_currency")
        .all()
    )

    items_by_lot = defaultdict(list)
    items_by_id = {}
    for tender_item in tender_items:
        item = tender_item.item
        lot_id = item.lot_id if item else None
        items_by_lot[lot_id].append(tender_item)
        if item:
            items_by_id[item.id] = item

    subitems_by_item = defaultdict(list)
    for tender_subitem in tender_subitems:
        subitem = tender_subitem.subitem
        item_id = subitem.item_id if subitem else None
        subitems_by_item[item_id].append(tender_subitem)

    lot_entries = []
    
    # Detectar criterio de adjudicación
    criteria = (tender.award_criteria_details or "").lower().strip()
    is_item_criteria = "item" in criteria or "ítem" in criteria
    is_total_criteria = "total" in criteria
    is_lot_criteria = "lote" in criteria
    is_contract_by_item = False  # Inicializar antes del condicional

    # Determinar si agrupar items
    # Por Lote o Por Total => mostrar lotes separados
    # Por Ítem => agrupar todos los items
    if is_lot_criteria or is_total_criteria:
        show_individual_lots = True
        is_grouped_items = False
    elif is_item_criteria:
        show_individual_lots = False
        is_grouped_items = True
    else:
        # Fallback: detectar si es por ítem según estructura
        total_items = sum(len(items_list) for items_list in items_by_lot.values() if items_list)
        is_contract_by_item = (
            len(lots) > 1
            and len(lots) == total_items
            and all(
                lot.open_contract_type and lot.open_contract_type.lower() not in ("no", "n/a", "none", "")
                for lot in lots
            )
        ) if lots else False
        show_individual_lots = not is_contract_by_item
        is_grouped_items = is_contract_by_item
    
    if is_grouped_items and lots:
        # Agrupar todos los items bajo un solo lote representativo
        representative_lot = lots[0]
        group_title = representative_lot.title if is_total_criteria and representative_lot.title else "Ítems del Solicitados"
        group_open_contract_type = next(
            (lot.open_contract_type for lot in lots if lot.open_contract_type), ""
        )

        value_total = Decimal("0")
        min_total = Decimal("0")
        value_currency = None
        min_currency = None
        value_valid = True
        min_valid = True
        value_seen = False
        min_seen = False

        for lot in lots:
            if lot.value_amount is not None:
                value_seen = True
                if value_currency is None:
                    value_currency = lot.value_currency
                elif lot.value_currency != value_currency:
                    value_valid = False
                value_total += lot.value_amount
            if lot.min_value_amount is not None:
                min_seen = True
                if min_currency is None:
                    min_currency = lot.min_value_currency
                elif lot.min_value_currency != min_currency:
                    min_valid = False
                min_total += lot.min_value_amount

        group_value_amount = value_total if value_seen and value_valid else None
        group_value_currency = value_currency if value_seen and value_valid else None
        group_min_amount = min_total if min_seen and min_valid else None
        group_min_currency = min_currency if min_seen and min_valid else None

        lot_entries.append({
            "id": "grouped",
            "title": group_title,
            "status_details": representative_lot.status_details,
            "open_contract_type_display": _format_open_contract_type(group_open_contract_type),
            "value": _format_amount(group_value_amount, group_value_currency),
            "min_value": _format_amount(group_min_amount, group_min_currency),
            "items": [],
        })
    elif show_individual_lots:
        # Mostrar cada lote por separado (Por Lote, Por Total)
        for lot in lots:
            lot_entries.append({
                "id": lot.id,
                "title": lot.title,
                "status_details": lot.status_details,
                "open_contract_type_display": _format_open_contract_type(lot.open_contract_type),
                "value": _format_amount(lot.value_amount, lot.value_currency),
                "min_value": _format_amount(lot.min_value_amount, lot.min_value_currency),
                "items": [],
            })
    else:
        # Fallback: un lote por cada Lot
        for lot in lots:
            lot_entries.append({
                "id": lot.id,
                "title": lot.title,
                "status_details": lot.status_details,
                "open_contract_type_display": _format_open_contract_type(lot.open_contract_type),
                "value": _format_amount(lot.value_amount, lot.value_currency),
                "min_value": _format_amount(lot.min_value_amount, lot.min_value_currency),
                "items": [],
            })

    if None in items_by_lot:
        lot_entries.append({
            "id": None,
            "title": "Sin lote",
            "status_details": "",
            "open_contract_type_display": "",
            "value": "-",
            "min_value": "-",
            "items": [],
        })

    lot_entries_index = {entry["id"]: entry for entry in lot_entries}

    for lot_id, lot_items in items_by_lot.items():
        # Decidir a qué entrada agregar los items
        if is_grouped_items:
            # Agrupar todos los items en una sola entrada (Por Ítem)
            entry = lot_entries_index.get("grouped")
        else:
            # Cada item va a su lote correspondiente (Por Lote, Por Total)
            entry = lot_entries_index.get(lot_id)
        
        if not entry:
            continue
        for tender_item in sorted(lot_items, key=lambda x: x.orden or 0):
            item = tender_item.item
            item_id = item.id if item else None
            total_value = _compute_total(tender_item.unit_price_amount, tender_item.quantity)
            entry["items"].append({
                "id": item_id,
                "description": item.description if item else "",
                "quantity": _format_quantity(tender_item.quantity),
                "unit": item.unit_name if item else "",
                "unit_price": _format_amount(tender_item.unit_price_amount, tender_item.unit_price_currency),
                "total": _format_total_display(
                    tender_item.unit_price_amount,
                    tender_item.quantity,
                    tender_item.unit_price_currency,
                ),
                "orden": tender_item.orden,
                "subitems": [],
            })

            for tender_subitem in subitems_by_item.get(item_id, []):
                subitem = tender_subitem.subitem
                sub_total = _compute_total(
                    tender_subitem.unit_price_amount,
                    tender_subitem.quantity,
                )
                
                entry["items"][-1]["subitems"].append({
                    "id": subitem.id if subitem else None,
                    "description": subitem.description if subitem else "",
                    "orden": tender_subitem.orden,
                    "quantity": _format_quantity(tender_subitem.quantity),
                    "unit": subitem.unit_name if subitem else "",
                    "unit_price": _format_amount(
                        tender_subitem.unit_price_amount,
                        tender_subitem.unit_price_currency,
                    ),
                    "total": _format_total_display(
                        tender_subitem.unit_price_amount,
                        tender_subitem.quantity,
                        tender_subitem.unit_price_currency,
                    ),
                })

    awards = list(
        Award.objects.filter(tender=tender)
        .prefetch_related("suppliers")
        .select_related("value_currency")
        .all()
    )
    award_entries = []
    for award in awards:
        suppliers = ", ".join([supplier.name for supplier in award.suppliers.all()])
        award_entries.append({
            "id": award.id,
            "status_details": award.status_details,
            "date": _format_date(award.date),
            "value": _format_amount(award.value_amount, award.value_currency),
            "suppliers": suppliers or "-",
        })

    context = {
        "ocid": ocid,
        "tender": tender,
        "compiled_release": compiled_release,
        "lots": lot_entries,
        "is_contract_by_item": is_contract_by_item,
        "is_total_criteria": is_total_criteria,
        "awards": award_entries,
        "nav_tenders": {
            "first": first_tender,
            "previous": previous_tender,
            "next": next_tender,
            "last": last_tender,
        },
        "formatted": {
            "tender_value": _format_amount(tender.value_amount, tender.value_currency),
            "date_published": _format_date(tender.date_published),
            "release_date": _format_date(compiled_release.date),
            "award_criteria": _format_award_criteria(tender.award_criteria_details),
        },
    }

    return render(request, "dncp_integration/tender_detail.html", context)
