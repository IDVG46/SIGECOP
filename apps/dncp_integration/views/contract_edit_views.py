import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DateTimeField, DecimalField, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from collections import defaultdict
from datetime import datetime

from apps.dncp_integration.models import (
    Contract,
    Award,
    AwardItem,
    AwardSubItem,
    TenderItem,
    TenderSubItem,
)
from apps.dncp_integration.forms.contract_edit_forms import (
    ContractEditForm,
    AwardEditForm,
    AwardItemFormSet,
    AwardSubItemFormSet,
)
from apps.dncp_integration.views.local_views import (
    _format_amount,
    _format_date,
    _format_open_contract_type,
    _format_quantity,
    _format_total_display,
)


@login_required
@require_http_methods(["GET", "POST"])
def contract_edit(request, contract_id):
    """
    Vista para editar un contrato con formularios inline.
    Muestra todos los datos en una sola página.
    """
    contract = get_object_or_404(
        Contract.objects.select_related(
            "award",
            "award__tender",
            "award__tender__procuring_entity",
            "value_currency",
        ).prefetch_related("award__suppliers"),
        id=contract_id
    )
    
    award = contract.award
    tender = award.tender if award else None
    
    if request.method == "POST":
        contract_form = ContractEditForm(request.POST, instance=contract)
        award_form = AwardEditForm(request.POST, instance=award) if award else None
        
        if contract_form.is_valid():
            contract = contract_form.save(commit=False)
            contract.is_user_modified = True
            contract.modified_by = request.user
            from django.utils import timezone
            contract.modified_at = timezone.now()
            contract.save()
            
            if award_form and award_form.is_valid():
                award = award_form.save(commit=False)
                award.is_user_modified = True
                award.modified_by = request.user
                award.modified_at = timezone.now()
                award.save()
                if 'suppliers' in award_form.cleaned_data:
                    award.suppliers.set(award_form.cleaned_data['suppliers'])
            
            messages.success(request, "Contrato actualizado correctamente")
            return redirect('dncp_integration:contract_detail', contract_id=contract.id)
    else:
        contract_form = ContractEditForm(instance=contract)
        award_form = AwardEditForm(instance=award) if award else None
    
    # Obtener items y subitems
    award_items = AwardItem.objects.filter(award=award).select_related(
        "item",
        "unit_price_currency",
        "item__lot",
    ) if award else []
    
    award_subitems = AwardSubItem.objects.filter(award=award).select_related(
        "subitem",
        "subitem__item",
        "unit_price_currency",
    ) if award else []
    
    # Ordenar items
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
    
    # Agrupar subitems por item
    subitems_by_item = defaultdict(list)
    for award_subitem in award_subitems:
        subitem = award_subitem.subitem
        item_id = subitem.item_id if subitem else None
        subitems_by_item[item_id].append(award_subitem)
    
    # Construir estructura de items
    criteria = (tender.award_criteria_details or "").lower().strip() if tender else ""
    is_lot_criteria = "lote" in criteria
    is_total_criteria = "total" in criteria
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
            "award_item_id": award_item.id,
            "description": item.description,
            "order": item_order,
            "quantity": award_item.quantity,
            "quantity_display": _format_quantity(award_item.quantity),
            "unit": item.unit_name or "-",
            "unit_price": award_item.unit_price_amount,
            "unit_price_display": _format_amount(award_item.unit_price_amount, award_item.unit_price_currency),
            "total": _format_total_display(
                award_item.unit_price_amount,
                award_item.quantity,
                award_item.unit_price_currency,
            ),
            "subitems": [],
            "currency_id": award_item.unit_price_currency_id,
        }
        
        # Agregar subitems
        for award_subitem in subitems_by_item.get(item.id, []):
            subitem = award_subitem.subitem
            if not subitem:
                continue
            
            subitem_data = {
                "id": subitem.id,
                "award_subitem_id": award_subitem.id,
                "description": subitem.description,
                "order": award_subitem.orden_licitado,
                "quantity": award_subitem.quantity,
                "quantity_display": _format_quantity(award_subitem.quantity),
                "unit": subitem.unit_name or "-",
                "unit_price": award_subitem.unit_price_amount,
                "unit_price_display": _format_amount(award_subitem.unit_price_amount, award_subitem.unit_price_currency),
                "total": _format_total_display(
                    award_subitem.unit_price_amount,
                    award_subitem.quantity,
                    award_subitem.unit_price_currency,
                ),
                "currency_id": award_subitem.unit_price_currency_id,
            }
            item_data["subitems"].append(subitem_data)
        
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
    
    suppliers = [{'id': s.id, 'name': s.name} for s in award.suppliers.all()] if award else []
    
    context = {
        'contract': contract,
        'contract_form': contract_form,
        'award': award,
        'award_form': award_form,
        'tender': tender,
        'items': item_entries,
        'lots': lot_entries,
        'show_lot_groups': show_lot_groups,
        'suppliers': suppliers,
        'formatted': {
            'value': _format_amount(contract.value_amount, contract.value_currency),
            'period_start': _format_date(contract.period_start_date),
            'period_end': _format_date(contract.period_end_date),
            'suppliers': ", ".join([s['name'] for s in suppliers]) or "-",
        },
    }
    
    return render(request, 'dncp_integration/contract_edit.html', context)


@login_required
@require_http_methods(["POST"])
def update_award_item(request, award_item_id):
    """
    API endpoint para actualizar un item de adjudicación via AJAX.
    Acepta JSON con quantity, unit_price_amount.
    """
    award_item = get_object_or_404(AwardItem, id=award_item_id)
    
    try:
        data = json.loads(request.body)
        quantity = data.get('quantity')
        unit_price_amount = data.get('unit_price_amount')
        
        if quantity is not None:
            award_item.quantity = quantity
        if unit_price_amount is not None:
            award_item.unit_price_amount = unit_price_amount
        
        award_item.is_user_modified = True
        award_item.modified_by = request.user
        from django.utils import timezone
        award_item.modified_at = timezone.now()
        award_item.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Item actualizado correctamente',
            'total': float(award_item.quantity * award_item.unit_price_amount) if award_item.quantity and award_item.unit_price_amount else 0,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def update_award_subitem(request, award_subitem_id):
    """
    API endpoint para actualizar un subitem de adjudicación via AJAX.
    Acepta JSON con quantity, unit_price_amount.
    """
    award_subitem = get_object_or_404(AwardSubItem, id=award_subitem_id)
    
    try:
        data = json.loads(request.body)
        quantity = data.get('quantity')
        unit_price_amount = data.get('unit_price_amount')
        
        if quantity is not None:
            award_subitem.quantity = quantity
        if unit_price_amount is not None:
            award_subitem.unit_price_amount = unit_price_amount
        
        award_subitem.is_user_modified = True
        award_subitem.modified_by = request.user
        from django.utils import timezone
        award_subitem.modified_at = timezone.now()
        award_subitem.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Subitem actualizado correctamente',
            'total': float(award_subitem.quantity * award_subitem.unit_price_amount) if award_subitem.quantity and award_subitem.unit_price_amount else 0,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
