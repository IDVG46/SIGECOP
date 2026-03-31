from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.procurement.models import (
    BudgetLedgerEntry,
    ContractAmendment,
    ContractBudget,
    FulfillmentMemo,
    FulfillmentMemoLine,
    FulfillmentMemoPartialLine,
    Payment,
    PurchaseOrder,
)
from apps.procurement.services.fulfillment_metrics import (
    approved_fulfilled_amount_for_order,
    approved_fulfilled_quantity_for_order,
    approved_fulfilled_quantity_for_order_line,
    ordered_quantity_for_order,
)
from apps.procurement.services.payments import validate_payment_context
from apps.procurement.utils.decimal_utils import to_decimal


_to_decimal = to_decimal


def _approved_fulfilled_amount(order):
    """Monto de cumplimiento aprobado para una orden."""
    return approved_fulfilled_amount_for_order(order)


def get_unapproved_memos_for_orders(orders_list):
    """Retorna {order_id: [memos no aprobados]} por orden."""
    order_ids = [order.id for order in orders_list]
    if not order_ids:
        return {}

    unapproved_lines = (
        FulfillmentMemoLine.objects.filter(
            purchase_order_id__in=order_ids,
            memo__status__in=[
                FulfillmentMemo.STATUS_DRAFT,
                FulfillmentMemo.STATUS_ISSUED,
                FulfillmentMemo.STATUS_REJECTED,
            ],
        )
        .select_related("memo")
        .order_by("purchase_order_id", "-memo__updated_at")
    )

    result = {}
    seen = set()
    for memo_line in unapproved_lines:
        order_id = memo_line.purchase_order_id
        memo = memo_line.memo
        key = (order_id, memo.id)
        if key in seen:
            continue
        seen.add(key)
        result.setdefault(order_id, []).append(memo)
    return result


def _posted_paid_amount(order):
    result = order.payment_allocations.filter(payment__status=Payment.STATUS_POSTED).aggregate(total=Sum("amount"))
    return _to_decimal(result["total"])


def _validate_budget_financial_code(budget, payment_date):
    financial_code = (budget.financial_code or "").strip()
    if not financial_code:
        return

    normalized_code = financial_code.upper()
    if normalized_code.startswith("CD-"):
        return

    # Si el código financiero ES el ID del propio contrato, es el presupuesto base — sin adenda requerida.
    if budget.contract_id and normalized_code == str(budget.contract_id).upper():
        return

    amendment = (
        ContractAmendment.objects.filter(
            contract=budget.contract,
            financial_code__iexact=financial_code,
            status=ContractAmendment.STATUS_ACTIVE,
        )
        .order_by("-effective_date", "-updated_at")
        .first()
    )
    if amendment is None:
        raise ValidationError(
            f"No existe una adenda activa para el codigo financiero {financial_code} en el contrato {budget.contract_id}."
        )

    if amendment.amendment_type == ContractAmendment.TYPE_PERIOD:
        raise ValidationError(
            f"La adenda {amendment.amendment_number} no habilita ampliacion de monto para pagos."
        )

    if payment_date and payment_date < amendment.effective_date:
        raise ValidationError(
            f"La fecha de pago es anterior a la vigencia de la adenda {amendment.amendment_number}."
        )


def _total_ordered_quantity(order):
    return ordered_quantity_for_order(order)


def _approved_fulfilled_quantity_for_order(order, *, exclude_memo=None):
    return approved_fulfilled_quantity_for_order(order, exclude_memo=exclude_memo)


def _pending_fulfilled_quantity_for_order(order, *, exclude_memo=None):
    ordered_qty = _total_ordered_quantity(order)
    approved_qty = _approved_fulfilled_quantity_for_order(order, exclude_memo=exclude_memo)
    pending = ordered_qty - approved_qty
    return pending if pending > Decimal("0.000") else Decimal("0.000")


def _pending_fulfilled_quantity_for_order_line(order_line, *, exclude_memo=None):
    approved_qty = approved_fulfilled_quantity_for_order_line(order_line, exclude_memo=exclude_memo)
    pending = _to_decimal(order_line.quantity, default="0.000") - approved_qty
    return pending if pending > Decimal("0.000") else Decimal("0.000")


def validate_payment_allocation_batch(allocations, payment_contract=None, excluded_payment_id=None):
    """
    Valida un conjunto de asignaciones de pago contra reglas de negocio centralizadas.
    
    Argumentos:
    - allocations: list de PaymentAllocation objects (o dicts con purchase_order, contract_budget, amount)
    - payment_contract: Contract opcional si el Payment está asignado a un contrato específico
    - excluded_payment_id: ID del pago a excluir del cálculo de 'ya pagado' (para ediciones)
    
    Retorna:
    - dict con {
        'submitted_by_order': {order_id: amount_sum},
        'submitted_by_budget': {budget_id: amount_sum},
        'orders': {order_id: order_obj},
        'budgets': {budget_id: budget_obj},
      }
    
    Lanza ValidationError si hay inconsistencias.
    """
    if not allocations:
        raise ValidationError("Debe registrar al menos una asignacion de pago.")
    
    submitted_by_order = {}
    submitted_by_budget = {}
    orders_dict = {}
    budgets_dict = {}
    
    # Paso 1: Recolectar y validar asignaciones básicas
    for alloc in allocations:
        # Soportar tanto objetos como dicts
        if isinstance(alloc, dict):
            purchase_order = alloc.get("purchase_order")
            budget = alloc.get("contract_budget")
            amount = alloc.get("amount")
        else:
            purchase_order = alloc.purchase_order
            budget = alloc.contract_budget
            amount = alloc.amount
        
        if purchase_order is None or budget is None or amount in (None, ""):
            continue
        
        # Validar que la orden pertenece al contrato del pago (si está asignado)
        if payment_contract and purchase_order.contract_id != payment_contract.id:
            raise ValidationError(
                f"La orden {purchase_order.order_number} pertenece al contrato {purchase_order.contract_id}, "
                f"pero el pago está asignado al contrato {payment_contract.id}."
            )
        
        # Validar coherencia orden-presupuesto
        if purchase_order.contract_id != budget.contract_id:
            raise ValidationError(
                f"La orden {purchase_order.order_number} y el presupuesto {budget.id} no pertenecen al mismo contrato."
            )
        
        if purchase_order.expense_object_id != budget.expense_object_id:
            raise ValidationError(
                f"La orden {purchase_order.order_number} y el presupuesto {budget.id} no coinciden en objeto de gasto."
            )
        
        # Acumular montos
        amount_decimal = _to_decimal(amount)
        submitted_by_order[purchase_order.id] = submitted_by_order.get(purchase_order.id, Decimal("0.00")) + amount_decimal
        submitted_by_budget[budget.id] = submitted_by_budget.get(budget.id, Decimal("0.00")) + amount_decimal
        
        # Cachear objetos para paso 2
        if purchase_order.id not in orders_dict:
            orders_dict[purchase_order.id] = purchase_order
        if budget.id not in budgets_dict:
            budgets_dict[budget.id] = budget
    
    if not submitted_by_order:
        raise ValidationError("Debe registrar al menos una asignacion de pago.")
    
    # Paso 2: Validar saldos per-orden
    for order_id, submitted_amount in submitted_by_order.items():
        order = orders_dict[order_id]
        
        # Calcular montos ya pagados (excluyendo el pago actual si se proporciona ID)
        filter_kwargs = {"payment__status": Payment.STATUS_POSTED}
        if excluded_payment_id:
            already_paid_qs = order.payment_allocations.filter(**filter_kwargs).exclude(payment_id=excluded_payment_id)
        else:
            already_paid_qs = order.payment_allocations.filter(**filter_kwargs)
        
        already_paid = _to_decimal(already_paid_qs.aggregate(total=Sum("amount"))["total"])
        
        # Calcular monto cumplido aprobado
        approved_fulfilled_amount = _approved_fulfilled_amount(order)
        
        # Validar saldo pendiente
        pending_by_order = (order.total_amount or Decimal("0.00")) - already_paid
        if submitted_amount > pending_by_order:
            raise ValidationError(
                f"El monto para la orden {order.order_number} excede su saldo pendiente ({pending_by_order})."
            )
        
        # Validar no exceder monto cumplido aprobado
        if already_paid + submitted_amount > approved_fulfilled_amount:
            raise ValidationError(
                f"El monto para la orden {order.order_number} excede el monto maximo de cumplimiento."
            )
    
    # Paso 3: Validar disponibilidad de presupuestos
    for budget_id, submitted_amount in submitted_by_budget.items():
        budget = budgets_dict[budget_id]
        if submitted_amount > (budget.available_amount or Decimal("0.00")):
            raise ValidationError(
                f"El monto asignado al presupuesto {budget.id} excede su disponible ({budget.available_amount})."
            )
    
    return {
        'submitted_by_order': submitted_by_order,
        'submitted_by_budget': submitted_by_budget,
        'orders': orders_dict,
        'budgets': budgets_dict,
    }


def _resolve_fulfillment_lines_data(
    contract,
    fulfillment_mode,
    lines_data=None,
    partial_lines_data=None,
    *,
    exclude_memo=None,
):
    if contract is None:
        raise ValidationError("Debe seleccionar un contrato para el memorandum.")

    resolved_lines = list(lines_data or [])
    if not resolved_lines:
        raise ValidationError("Debe agregar al menos una linea de cumplimiento.")

    normalized_lines = []
    normalized_partial_lines = []
    seen_total_order_ids = set()
    seen_partial_order_ids = set()
    seen_partial_order_line_ids = set()
    for line_data in resolved_lines:
        order_line = line_data.get("purchase_order_line")
        order = line_data.get("purchase_order")
        if order is None and order_line is not None:
            order = order_line.purchase_order
        line_mode = line_data.get("line_mode") or fulfillment_mode or FulfillmentMemoLine.MODE_PARTIAL

        if order is None:
            raise ValidationError("Cada linea de cumplimiento debe tener una orden de compra.")
        if order.contract_id != contract.id:
            raise ValidationError(f"La orden {order.order_number} no pertenece al contrato del memorandum.")
        if line_mode == FulfillmentMemoLine.MODE_TOTAL:
            if order.id in seen_partial_order_ids:
                raise ValidationError(
                    f"La orden {order.order_number} no puede mezclarse en modo total y parcial dentro del mismo memorandum."
                )
            if order.id in seen_total_order_ids:
                raise ValidationError(f"La orden {order.order_number} esta repetida en modo total.")
            seen_total_order_ids.add(order.id)

            pending_qty = _pending_fulfilled_quantity_for_order(order, exclude_memo=exclude_memo)
            if pending_qty <= Decimal("0.000"):
                raise ValidationError(
                    f"La orden {order.order_number} no tiene saldo pendiente para cumplimiento total."
                )
            fulfilled_quantity = pending_qty
            if order_line is not None and order_line.purchase_order_id != order.id:
                raise ValidationError(f"La linea seleccionada no pertenece a la orden {order.order_number}.")
        else:
            if order.id in seen_total_order_ids:
                raise ValidationError(
                    f"La orden {order.order_number} no puede mezclarse en modo parcial y total dentro del mismo memorandum."
                )
            seen_partial_order_ids.add(order.id)
            fulfilled_quantity = None

        normalized_lines.append(
            {
                "purchase_order": order,
                "purchase_order_line": order_line if line_mode == FulfillmentMemoLine.MODE_TOTAL else None,
                "fulfilled_quantity": fulfilled_quantity,
                "line_mode": line_mode,
                "observations": line_data.get("observations", ""),
            }
        )

    partial_rows = list(partial_lines_data or [])

    # Backward compatibility: if partial rows are still sent through lines_data, convert them.
    if not partial_rows:
        for line_data in resolved_lines:
            line_mode = line_data.get("line_mode") or fulfillment_mode or FulfillmentMemoLine.MODE_PARTIAL
            if line_mode != FulfillmentMemoLine.MODE_PARTIAL:
                continue
            order = line_data.get("purchase_order")
            order_line = line_data.get("purchase_order_line")
            if order is None and order_line is not None:
                order = order_line.purchase_order
            fulfilled_quantity = line_data.get("fulfilled_quantity")
            if order is None or order_line is None or fulfilled_quantity in (None, ""):
                continue
            partial_rows.append(
                {
                    "purchase_order": order,
                    "purchase_order_line": order_line,
                    "fulfilled_quantity": fulfilled_quantity,
                    "observations": line_data.get("observations", ""),
                }
            )

    partial_order_ids = {
        line["purchase_order"].id for line in normalized_lines if line["line_mode"] == FulfillmentMemoLine.MODE_PARTIAL
    }

    for row in partial_rows:
        order = row.get("purchase_order")
        order_line = row.get("purchase_order_line")
        if order is None and order_line is not None:
            order = order_line.purchase_order

        if order is None or order_line is None:
            raise ValidationError("Cada detalle parcial debe incluir orden y linea de orden.")

        if order.contract_id != contract.id:
            raise ValidationError(f"La orden {order.order_number} del detalle parcial no pertenece al contrato del memorandum.")

        if order.id not in partial_order_ids:
            raise ValidationError(
                f"La orden {order.order_number} tiene detalle parcial pero no esta marcada en modo parcial en lineas de cumplimiento."
            )

        if order_line.purchase_order_id != order.id:
            raise ValidationError(f"La linea {order_line.id} no pertenece a la orden {order.order_number}.")

        if order_line.id in seen_partial_order_line_ids:
            raise ValidationError(f"La linea {order_line.id} de la orden {order.order_number} esta repetida en detalle parcial.")
        seen_partial_order_line_ids.add(order_line.id)

        fulfilled_quantity = _to_decimal(row.get("fulfilled_quantity"), default="0.000")
        if fulfilled_quantity <= Decimal("0.000"):
            raise ValidationError(
                f"La cantidad cumplida para la linea {order_line.id} de la orden {order.order_number} debe ser mayor a cero."
            )

        pending_qty = _pending_fulfilled_quantity_for_order_line(order_line, exclude_memo=exclude_memo)
        if fulfilled_quantity > pending_qty:
            raise ValidationError(
                f"La cantidad cumplida para la linea {order_line.id} de la orden {order.order_number} excede el saldo pendiente ({pending_qty})."
            )

        normalized_partial_lines.append(
            {
                "purchase_order": order,
                "purchase_order_line": order_line,
                "fulfilled_quantity": fulfilled_quantity,
                "observations": row.get("observations", ""),
            }
        )

    for order_id in partial_order_ids:
        if not any(row["purchase_order"].id == order_id for row in normalized_partial_lines):
            order = PurchaseOrder.objects.filter(pk=order_id).first()
            order_number = order.order_number if order else order_id
            raise ValidationError(f"La orden {order_number} esta en modo parcial y requiere al menos un detalle parcial.")

    partial_sum_by_order = {}
    for row in normalized_partial_lines:
        oid = row["purchase_order"].id
        partial_sum_by_order[oid] = partial_sum_by_order.get(oid, Decimal("0.000")) + _to_decimal(
            row["fulfilled_quantity"],
            default="0.000",
        )

    for line in normalized_lines:
        if line["line_mode"] == FulfillmentMemoLine.MODE_PARTIAL:
            line["fulfilled_quantity"] = partial_sum_by_order.get(line["purchase_order"].id, Decimal("0.000"))

    return normalized_lines, normalized_partial_lines


@transaction.atomic
def create_budget(
    *,
    contract,
    expense_object,
    fiscal_year,
    funding_source,
    assigned_amount,
    cdp_number="",
    financial_code="",
    created_by=None,
):
    budget = ContractBudget(
        contract=contract,
        expense_object=expense_object,
        fiscal_year=fiscal_year,
        financial_code=financial_code or "",
        funding_source=funding_source,
        cdp_number=cdp_number or "",
        assigned_amount=_to_decimal(assigned_amount),
        status=ContractBudget.STATUS_DRAFT,
    )
    budget.full_clean()
    budget.save()
    return budget


@transaction.atomic
def approve_budget(budget):
    if budget.status not in {ContractBudget.STATUS_DRAFT, ContractBudget.STATUS_ACTIVE}:
        raise ValidationError("Solo se puede aprobar un presupuesto en borrador o activo.")

    budget.status = ContractBudget.STATUS_ACTIVE
    budget.full_clean()
    budget.save(update_fields=["status", "updated_at"])
    return budget


@transaction.atomic
def create_fulfillment_memo(
    *,
    contract=None,
    beneficiary_sector,
    memo_number,
    memo_date,
    received_by="",
    sender_position="",
    created_by=None,
    lines_data=None,
    partial_lines_data=None,
    notes="",
    fulfillment_mode=FulfillmentMemo.MODE_PARTIAL,
):
    lines_data, partial_lines_data = _resolve_fulfillment_lines_data(
        contract,
        fulfillment_mode,
        lines_data,
        partial_lines_data,
    )

    memo = FulfillmentMemo.objects.create(
        contract=contract,
        fulfillment_mode=fulfillment_mode,
        beneficiary_sector=beneficiary_sector,
        memo_number=memo_number,
        memo_date=memo_date,
        received_by=received_by or "",
        sender_position=sender_position or "",
        status=FulfillmentMemo.STATUS_DRAFT,
        created_by=created_by,
        notes=notes,
    )

    for line_data in lines_data:
        line = FulfillmentMemoLine(
            memo=memo,
            purchase_order=line_data["purchase_order"],
            purchase_order_line=line_data.get("purchase_order_line"),
            fulfillment_mode=line_data.get("line_mode", FulfillmentMemoLine.MODE_PARTIAL),
            fulfilled_quantity=line_data.get("fulfilled_quantity"),  # None for total mode
            observations=line_data.get("observations", ""),
        )
        line.full_clean()
        line.save()

    for partial_data in partial_lines_data:
        partial_line = FulfillmentMemoPartialLine(
            memo=memo,
            purchase_order=partial_data["purchase_order"],
            purchase_order_line=partial_data["purchase_order_line"],
            fulfilled_quantity=partial_data["fulfilled_quantity"],
            observations=partial_data.get("observations", ""),
        )
        partial_line.full_clean()
        partial_line.save()

    return memo


@transaction.atomic
def update_fulfillment_memo(
    memo,
    *,
    contract=None,
    beneficiary_sector,
    memo_number,
    memo_date,
    received_by="",
    sender_position="",
    notes="",
    fulfillment_mode=FulfillmentMemo.MODE_PARTIAL,
    lines_data=None,
    partial_lines_data=None,
):
    if memo.status in {FulfillmentMemo.STATUS_APPROVED, FulfillmentMemo.STATUS_CANCELLED, FulfillmentMemo.STATUS_REJECTED}:
        raise ValidationError("Solo se puede editar un memorandum pendiente de aprobacion.")

    resolved_lines, resolved_partial_lines = _resolve_fulfillment_lines_data(
        contract,
        fulfillment_mode,
        lines_data,
        partial_lines_data,
        exclude_memo=memo,
    )

    memo.contract = contract
    memo.fulfillment_mode = fulfillment_mode
    memo.beneficiary_sector = beneficiary_sector
    memo.memo_number = memo_number
    memo.memo_date = memo_date
    memo.received_by = received_by or ""
    memo.sender_position = sender_position or ""
    memo.notes = notes
    memo.status = FulfillmentMemo.STATUS_DRAFT
    memo.full_clean()
    memo.save()

    memo.lines.all().delete()
    memo.partial_lines.all().delete()
    for line_data in resolved_lines:
        line = FulfillmentMemoLine(
            memo=memo,
            purchase_order=line_data["purchase_order"],
            purchase_order_line=line_data.get("purchase_order_line"),
            fulfillment_mode=line_data.get("line_mode", FulfillmentMemoLine.MODE_PARTIAL),
            fulfilled_quantity=line_data.get("fulfilled_quantity"),  # None for total mode
            observations=line_data.get("observations", ""),
        )
        line.full_clean()
        line.save()

    for partial_data in resolved_partial_lines:
        partial_line = FulfillmentMemoPartialLine(
            memo=memo,
            purchase_order=partial_data["purchase_order"],
            purchase_order_line=partial_data["purchase_order_line"],
            fulfilled_quantity=partial_data["fulfilled_quantity"],
            observations=partial_data.get("observations", ""),
        )
        partial_line.full_clean()
        partial_line.save()

    return memo


@transaction.atomic
def approve_fulfillment_memo(memo):
    if memo.status in {FulfillmentMemo.STATUS_CANCELLED, FulfillmentMemo.STATUS_REJECTED}:
        raise ValidationError("No se puede aprobar un memorandum anulado o rechazado.")

    memo_lines = list(memo.lines.select_related("purchase_order"))
    if not memo_lines:
        raise ValidationError("No se puede aprobar un memorandum sin lineas de cumplimiento.")

    memo_partial_lines = list(memo.partial_lines.select_related("purchase_order", "purchase_order_line"))

    for memo_line in memo_lines:
        order = memo_line.purchase_order
        if memo_line.fulfillment_mode == FulfillmentMemoLine.MODE_TOTAL:
            pending_order_qty = _pending_fulfilled_quantity_for_order(order, exclude_memo=memo)
            total_qty = _to_decimal(memo_line.fulfilled_quantity, default="0.000")
            if total_qty <= Decimal("0.000"):
                total_qty = pending_order_qty
            if total_qty > pending_order_qty:
                raise ValidationError(
                    f"El cumplimiento total para la orden {order.order_number} excede el saldo pendiente ({pending_order_qty})."
                )
            continue

        if memo_line.purchase_order_line_id is None:
            pass

        partials_for_order = [p for p in memo_partial_lines if p.purchase_order_id == order.id]
        if not partials_for_order:
            raise ValidationError(f"La orden {order.order_number} en modo parcial requiere detalle de lineas parciales.")

        for partial in partials_for_order:
            pending_line_qty = _pending_fulfilled_quantity_for_order_line(partial.purchase_order_line, exclude_memo=memo)
            line_qty = _to_decimal(partial.fulfilled_quantity, default="0.000")
            if line_qty > pending_line_qty:
                raise ValidationError(
                    f"El cumplimiento aprobado excede la cantidad ordenada para la linea {partial.purchase_order_line_id} de la orden {order.order_number}."
                )

        order_partial_total = sum((_to_decimal(p.fulfilled_quantity, default="0.000") for p in partials_for_order), Decimal("0.000"))
        pending_order_qty = _pending_fulfilled_quantity_for_order(order, exclude_memo=memo)
        if order_partial_total > pending_order_qty:
            raise ValidationError(
                f"El cumplimiento parcial aprobado excede el saldo pendiente de la orden {order.order_number}."
            )

    memo.status = FulfillmentMemo.STATUS_APPROVED
    memo.save(update_fields=["status", "updated_at"])
    return memo


@transaction.atomic
def post_payment(payment):
    if payment.status != Payment.STATUS_DRAFT:
        raise ValidationError("Solo se puede imputar un pago en estado borrador.")

    allocations = list(payment.allocations.select_related("purchase_order", "contract_budget"))
    if not allocations:
        raise ValidationError("No se puede imputar un pago sin asignaciones a ordenes.")

    allocations_total = sum((_to_decimal(alloc.amount) for alloc in allocations), Decimal("0.00"))
    if allocations_total != _to_decimal(payment.amount_total):
        raise ValidationError("La suma de asignaciones debe ser igual al total del pago.")

    # Validación centralizada de asignaciones
    validation_result = validate_payment_allocation_batch(
        allocations, 
        payment_contract=getattr(payment, "contract", None),
        excluded_payment_id=payment.id
    )
    
    submitted_by_order = validation_result['submitted_by_order']
    submitted_by_budget = validation_result['submitted_by_budget']
    budgets_dict = validation_result['budgets']

    # Validar código financiero y contexto de pago para cada asignación
    for alloc in allocations:
        order = alloc.purchase_order
        budget = alloc.contract_budget
        _validate_budget_financial_code(budget, payment.payment_date)
        validate_payment_context(order, budget, already_paid=_posted_paid_amount(order), payment_amount=alloc.amount)

    # Lock y ejecutar presupuestos
    locked_budgets = {
        budget.id: budget
        for budget in ContractBudget.objects.select_for_update().filter(id__in=list(submitted_by_budget.keys()))
    }

    for budget_id, submitted in submitted_by_budget.items():
        budget = locked_budgets[budget_id]
        available = _to_decimal(getattr(budget, "available_amount", None))
        delta = _to_decimal(submitted)
        if delta > available:
            raise ValidationError(
                f"El monto del pago excede el saldo disponible del presupuesto {budget.id}."
            )
        budget.executed_amount = _to_decimal(budget.executed_amount) + delta
        budget.full_clean()
        budget.save(update_fields=["executed_amount", "updated_at"])

        BudgetLedgerEntry.objects.create(
            contract_budget=budget,
            entry_type=BudgetLedgerEntry.ENTRY_EXECUTE,
            amount=delta,
            source_type=BudgetLedgerEntry.SOURCE_PAYMENT,
            source_id=str(payment.id),
            created_by=payment.created_by,
            notes=f"Imputacion de pago {payment.payment_number}",
        )

    payment.status = Payment.STATUS_POSTED
    payment.save(update_fields=["status", "updated_at"])

    return payment


@transaction.atomic
def cancel_payment(payment):
    if payment.status != Payment.STATUS_POSTED:
        raise ValidationError("Solo se puede anular un pago imputado.")

    allocations = list(payment.allocations.select_related("contract_budget"))
    if not allocations:
        raise ValidationError("No se puede anular un pago sin asignaciones.")

    submitted_by_budget = {}
    for alloc in allocations:
        submitted_by_budget[alloc.contract_budget_id] = submitted_by_budget.get(alloc.contract_budget_id, Decimal("0.00")) + _to_decimal(alloc.amount)

    locked_budgets = {
        budget.id: budget
        for budget in ContractBudget.objects.select_for_update().filter(id__in=list(submitted_by_budget.keys()))
    }

    for budget_id, submitted in submitted_by_budget.items():
        budget = locked_budgets[budget_id]
        delta = _to_decimal(submitted)
        current_executed = _to_decimal(budget.executed_amount)
        if delta > current_executed:
            raise ValidationError(
                f"No se puede anular {delta} del presupuesto {budget.id} porque supera su ejecutado actual."
            )

        budget.executed_amount = current_executed - delta
        budget.full_clean()
        budget.save(update_fields=["executed_amount", "updated_at"])

        BudgetLedgerEntry.objects.create(
            contract_budget=budget,
            entry_type=BudgetLedgerEntry.ENTRY_REVERSE_EXECUTE,
            amount=delta,
            source_type=BudgetLedgerEntry.SOURCE_PAYMENT,
            source_id=str(payment.id),
            created_by=payment.created_by,
            notes=f"Anulacion de pago {payment.payment_number}",
        )

    payment.status = Payment.STATUS_CANCELLED
    payment.save(update_fields=["status", "updated_at"])

    return payment


def reconcile_order_payment(order):
    approved_fulfilled = _approved_fulfilled_amount(order)
    already_paid = _posted_paid_amount(order)
    total_amount = _to_decimal(order.total_amount)

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "order_total": total_amount,
        "approved_fulfilled_amount": approved_fulfilled,
        "paid_amount": already_paid,
        "pending_by_order": total_amount - already_paid,
        "payable_by_fulfillment": approved_fulfilled - already_paid,
    }
