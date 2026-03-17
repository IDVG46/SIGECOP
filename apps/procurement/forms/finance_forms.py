from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import inlineformset_factory
from django.forms import modelformset_factory

from apps.dncp_integration.models import Contract
from apps.procurement.forms.mixins import LocalizedDecimalMixin
from apps.procurement.models import (
    ContractAmendment,
    ContractBudget,
    FulfillmentMemo,
    FulfillmentMemoLine,
    FulfillmentMemoPartialLine,
    Payment,
    PaymentAllocation,
    PurchaseOrder,
    PurchaseOrderLine,
)


class ContractBudgetForm(LocalizedDecimalMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        contract_id = None
        if self.is_bound:
            contract_id = self.data.get("contract")
        if not contract_id and self.instance and self.instance.pk:
            contract_id = self.instance.contract_id

        current_value = self.initial.get("financial_code") or getattr(self.instance, "financial_code", "")
        choices = self._financial_code_choices(contract_id, current_value=current_value)
        self.fields["financial_code"].widget = forms.Select(attrs={"class": "form-control select2"}, choices=choices)

    @staticmethod
    def _financial_code_choices(contract_id, current_value=""):
        values = set()
        if contract_id:
            values.add(str(contract_id).strip())

            amendment_codes = (
                ContractAmendment.objects.filter(
                    contract_id=contract_id,
                    status__in=[
                        ContractAmendment.STATUS_DRAFT,
                        ContractAmendment.STATUS_APPROVED,
                        ContractAmendment.STATUS_ACTIVE,
                    ],
                )
                .exclude(financial_code="")
                .values_list("financial_code", flat=True)
            )
            values.update(str(code).strip() for code in amendment_codes if code)

            existing_budget_codes = (
                ContractBudget.objects.filter(contract_id=contract_id)
                .exclude(financial_code="")
                .values_list("financial_code", flat=True)
            )
            values.update(str(code).strip() for code in existing_budget_codes if code)

        if current_value:
            values.add(str(current_value).strip())

        ordered = sorted(code for code in values if code)
        return [("", "---------")] + [(code, code) for code in ordered]

    class Meta:
        model = ContractBudget
        fields = [
            "contract",
            "expense_object",
            "fiscal_year",
            "financial_code",
            "funding_source",
            "cdp_number",
            "assigned_amount",
            "committed_amount",
            "executed_amount",
            "status",
        ]
        widgets = {
            "contract": forms.Select(attrs={"class": "form-control select2"}),
            "expense_object": forms.Select(attrs={"class": "form-control select2"}),
            "fiscal_year": forms.NumberInput(attrs={"class": "form-control"}),
            "financial_code": forms.Select(attrs={"class": "form-control select2"}),
            "funding_source": forms.TextInput(attrs={"class": "form-control"}),
            "cdp_number": forms.TextInput(attrs={"class": "form-control"}),
            "assigned_amount": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "committed_amount": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "executed_amount": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "status": forms.Select(attrs={"class": "form-control select2"}),
        }

    def clean_assigned_amount(self):
        return self._clean_localized_decimal_field("assigned_amount")

    def clean_committed_amount(self):
        return self._clean_localized_decimal_field("committed_amount")

    def clean_executed_amount(self):
        return self._clean_localized_decimal_field("executed_amount")

class FulfillmentMemoForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].required = False
        self.fields["fulfillment_mode"].required = False
        self.fields["fulfillment_mode"].initial = FulfillmentMemo.MODE_PARTIAL
        self.fields["fulfillment_mode"].widget = forms.HiddenInput()

        contract_qs = Contract.objects.order_by("id")
        self.fields["contract"] = forms.ModelChoiceField(
            queryset=contract_qs,
            required=True,
            label="Contrato",
            widget=forms.Select(attrs={"class": "form-control select2"}),
        )

        if self.is_bound:
            contract_id = self.data.get(self.add_prefix("contract"))
            self.fields["contract"].initial = contract_id
        elif self.instance and self.instance.pk:
            self.fields["contract"].initial = self.instance.contract_id or getattr(self.instance.purchase_order, "contract_id", None)

    class Meta:
        model = FulfillmentMemo
        fields = [
            "contract",
            "purchase_order",
            "fulfillment_mode",
            "beneficiary_sector",
            "memo_number",
            "memo_date",
            "received_by",
            "sender_position",
            "notes",
        ]
        widgets = {
            "contract": forms.Select(attrs={"class": "form-control select2"}),
            "purchase_order": forms.Select(attrs={"class": "form-control select2"}),
            "fulfillment_mode": forms.Select(attrs={"class": "form-control select2"}),
            "beneficiary_sector": forms.TextInput(attrs={"class": "form-control"}),
            "memo_number": forms.TextInput(attrs={"class": "form-control"}),
            "memo_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "received_by": forms.TextInput(attrs={"class": "form-control"}),
            "sender_position": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class FulfillmentMemoLineForm(forms.ModelForm):
    line_mode = forms.ChoiceField(
        choices=FulfillmentMemoLine.MODE_CHOICES,
        required=True,
        initial=FulfillmentMemoLine.MODE_PARTIAL,
        label="Modo",
        widget=forms.Select(attrs={"class": "form-control select2 row-line-mode"}),
    )

    class Meta:
        model = FulfillmentMemoLine
        fields = ["purchase_order", "observations"]
        widgets = {
            "purchase_order": forms.Select(attrs={"class": "form-control select2 row-order-select"}),
            "observations": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].required = True
        if self.instance and self.instance.pk:
            self.fields["line_mode"].initial = self.instance.fulfillment_mode or FulfillmentMemoLine.MODE_PARTIAL

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("purchase_order")
        line_mode = cleaned.get("line_mode") or FulfillmentMemoLine.MODE_PARTIAL

        if order is None:
            raise ValidationError({"purchase_order": "Debe seleccionar una orden de compra."})

        if line_mode not in {FulfillmentMemoLine.MODE_PARTIAL, FulfillmentMemoLine.MODE_TOTAL}:
            raise ValidationError({"line_mode": "Modo de cumplimiento inválido."})

        return cleaned


class BaseFulfillmentMemoLineFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        contract = kwargs.pop("contract", None)
        super().__init__(*args, **kwargs)

        resolved_contract = contract
        if resolved_contract is None and self.instance and self.instance.pk:
            resolved_contract = self.instance.contract or getattr(self.instance.purchase_order, "contract", None)

        self.contract = resolved_contract

        if resolved_contract is not None:
            orders_qs = (
                PurchaseOrder.objects.filter(contract=resolved_contract)
                .exclude(status=PurchaseOrder.STATUS_CANCELLED)
                .order_by("-issue_date", "order_number")
            )
        else:
            orders_qs = PurchaseOrder.objects.none()

        for form in self.forms:
            form.fields["purchase_order"].queryset = orders_qs

    def clean(self):
        super().clean()
        if self.contract is None:
            return

        seen_total_order_ids = set()
        seen_partial_order_ids = set()
        seen_partial_order_ids = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            order = form.cleaned_data.get("purchase_order")
            line_mode = form.cleaned_data.get("line_mode") or FulfillmentMemoLine.MODE_PARTIAL
            if order is None:
                continue

            if order.contract_id != self.contract.id:
                raise ValidationError("La orden seleccionada no pertenece al contrato del memorandum.")

            if line_mode == FulfillmentMemoLine.MODE_TOTAL:
                if order.id in seen_partial_order_ids:
                    raise ValidationError(
                        f"La orden {order.order_number} no puede mezclarse en modo total y parcial."
                    )
                if order.id in seen_total_order_ids:
                    raise ValidationError(f"La orden {order.order_number} esta repetida en modo total.")
                seen_total_order_ids.add(order.id)
                continue

            if order.id in seen_total_order_ids:
                raise ValidationError(
                    f"La orden {order.order_number} no puede mezclarse en modo parcial y total."
                )
            seen_partial_order_ids.add(order.id)


FulfillmentMemoLineFormSet = inlineformset_factory(
    FulfillmentMemo,
    FulfillmentMemoLine,
    form=FulfillmentMemoLineForm,
    formset=BaseFulfillmentMemoLineFormSet,
    extra=1,
    can_delete=True,
)


class FulfillmentMemoPartialLineForm(LocalizedDecimalMixin, forms.ModelForm):
    class Meta:
        model = FulfillmentMemoPartialLine
        fields = ["purchase_order", "purchase_order_line", "fulfilled_quantity", "observations"]
        widgets = {
            "purchase_order": forms.Select(attrs={"class": "form-control select2 partial-order-select"}),
            "purchase_order_line": forms.Select(attrs={"class": "form-control select2 partial-order-line-select"}),
            "fulfilled_quantity": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "observations": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.contract = kwargs.pop("contract", None)
        super().__init__(*args, **kwargs)
        orders_qs = PurchaseOrder.objects.none()
        if self.contract is not None:
            orders_qs = (
                PurchaseOrder.objects.filter(contract=self.contract)
                .exclude(status=PurchaseOrder.STATUS_CANCELLED)
                .order_by("-issue_date", "order_number")
            )
        self.fields["purchase_order"].queryset = orders_qs

        current_order = None
        if self.is_bound:
            order_raw = self.data.get(self.add_prefix("purchase_order"))
            try:
                current_order = orders_qs.filter(pk=order_raw).first()
            except (TypeError, ValueError):
                current_order = None
        elif self.instance and self.instance.pk:
            current_order = self.instance.purchase_order

        if current_order is not None:
            self.fields["purchase_order_line"].queryset = PurchaseOrderLine.objects.filter(
                purchase_order=current_order
            ).order_by("id")
        else:
            self.fields["purchase_order_line"].queryset = PurchaseOrderLine.objects.none()

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("purchase_order")
        order_line = cleaned.get("purchase_order_line")
        qty = cleaned.get("fulfilled_quantity")

        if order is None:
            raise ValidationError({"purchase_order": "Debe seleccionar una orden de compra."})
        if order_line is None:
            raise ValidationError({"purchase_order_line": "Debe seleccionar una linea de orden."})
        if order_line.purchase_order_id != order.id:
            raise ValidationError({"purchase_order_line": "La linea seleccionada no pertenece a la orden."})
        if qty is None or qty <= 0:
            raise ValidationError({"fulfilled_quantity": "Debe ingresar una cantidad cumplida mayor a cero."})
        return cleaned

    def clean_fulfilled_quantity(self):
        value = self._clean_localized_decimal_field("fulfilled_quantity")
        if value is not None:
            if value != value.to_integral_value():
                raise ValidationError("La cantidad cumplida debe ser un numero entero.")
            return value
        return value


FulfillmentMemoPartialLineFormSet = modelformset_factory(
    FulfillmentMemoPartialLine,
    form=FulfillmentMemoPartialLineForm,
    extra=1,
    can_delete=True,
)


class PaymentForm(LocalizedDecimalMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer contract required (requerido en el form, no en la BD)
        self.fields["contract"].required = True
    
    class Meta:
        model = Payment
        fields = [
            "contract",
            "payment_number",
            "payment_date",
            "amount_total",
            "document_number",
        ]
        widgets = {
            "contract": forms.Select(attrs={"class": "form-control select2", "data-placeholder": "Seleccione contrato"}),
            "payment_number": forms.TextInput(attrs={"class": "form-control"}),
            "payment_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "amount_total": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "document_number": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_amount_total(self):
        return self._clean_localized_decimal_field("amount_total")


class PaymentAllocationForm(LocalizedDecimalMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract_budget"].required = True

    class Meta:
        model = PaymentAllocation
        fields = ["purchase_order", "contract_budget", "amount"]
        widgets = {
            "purchase_order": forms.Select(attrs={"class": "form-control select2"}),
            "contract_budget": forms.Select(attrs={"class": "form-control select2"}),
            "amount": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
        }

    def clean_amount(self):
        return self._clean_localized_decimal_field("amount")


class BasePaymentAllocationFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✓ ESTRATEGIA: Aceptar TODAS las órdenes, let clean() validate relationships
        # RAZÓN: Permite que el formset acepte órdenes sin conocer el contrato del pago aún
        # En CREATE: Payment.contract aún no existe
        # En UPDATE: Payment.contract existe but queryset filter needed for form rendering
        # Solución: Cargar TODAS las órdenes, JavaScript filtra el UI dinámicamente
        
        orders_qs = PurchaseOrder.objects.exclude(status=PurchaseOrder.STATUS_CANCELLED).select_related("contract", "supplier")
        budgets_qs = ContractBudget.objects.exclude(status=ContractBudget.STATUS_CANCELLED).select_related("contract", "expense_object")

        for form in self.forms:
            form.fields["purchase_order"].queryset = orders_qs
            form.fields["contract_budget"].queryset = budgets_qs

    def clean(self):
        super().clean()

        # Validar que si el Payment tiene contrato, todas las órdenes deben ser de ese contrato
        payment_contract = getattr(self.instance, "contract", None) if self.instance else None

        submitted_by_order = {}
        submitted_by_budget = {}
        has_allocations = False

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            purchase_order = form.cleaned_data.get("purchase_order")
            budget = form.cleaned_data.get("contract_budget")
            amount = form.cleaned_data.get("amount")
            if purchase_order is None or budget is None or amount in (None, ""):
                continue

            # Validar que la orden pertenece al contrato del pago (si está asignado)
            if payment_contract and purchase_order.contract_id != payment_contract.id:
                raise ValidationError(
                    f"La orden {purchase_order.order_number} pertenece al contrato {purchase_order.contract_id}, "
                    f"pero el pago está asignado al contrato {payment_contract.id}."
                )

            has_allocations = True
            submitted_by_order[purchase_order.id] = submitted_by_order.get(purchase_order.id, 0) + amount
            submitted_by_budget[budget.id] = submitted_by_budget.get(budget.id, 0) + amount

            if purchase_order.contract_id != budget.contract_id:
                raise ValidationError(
                    f"La orden {purchase_order.order_number} y el presupuesto {budget.id} no pertenecen al mismo contrato."
                )

            if purchase_order.expense_object_id != budget.expense_object_id:
                raise ValidationError(
                    f"La orden {purchase_order.order_number} y el presupuesto {budget.id} no coinciden en objeto de gasto."
                )

        if not has_allocations:
            raise ValidationError("Debe registrar al menos una asignacion de pago.")

        for order_id, submitted_amount in submitted_by_order.items():
            order = PurchaseOrder.objects.filter(pk=order_id).first()
            if order is None:
                raise ValidationError("Se selecciono una orden de compra inexistente.")

            already_paid = (
                order.payment_allocations.filter(payment__status=Payment.STATUS_POSTED)
                .exclude(payment_id=self.instance.pk)
                .aggregate(total=models.Sum("amount"))["total"]
                or 0
            )

            approved_lines = FulfillmentMemoLine.objects.filter(
                purchase_order=order,
                memo__status=FulfillmentMemo.STATUS_APPROVED,
            )
            approved_fulfilled_amount = Decimal("0.00")
            ordered_qty = order.lines.aggregate(total=models.Sum("quantity"))["total"] or Decimal("0.000")
            for ml in approved_lines:
                if ml.fulfillment_mode == FulfillmentMemoLine.MODE_TOTAL:
                    total_mode_qty = ml.fulfilled_quantity or Decimal("0.000")
                    if total_mode_qty <= Decimal("0.000"):
                        total_mode_qty = ordered_qty
                    if ordered_qty > Decimal("0.000"):
                        ratio = total_mode_qty / ordered_qty
                        approved_fulfilled_amount += (order.total_amount or Decimal("0.00")) * ratio
                else:
                    approved_qty = ml.fulfilled_quantity or Decimal("0.000")
                    if ordered_qty > Decimal("0.000"):
                        ratio = approved_qty / ordered_qty
                        approved_fulfilled_amount += (order.total_amount or Decimal("0.00")) * ratio

            pending_by_order = (order.total_amount or 0) - already_paid
            if submitted_amount > pending_by_order:
                raise ValidationError(
                    f"El monto para la orden {order.order_number} excede su saldo pendiente ({pending_by_order})."
                )

            if already_paid + submitted_amount > approved_fulfilled_amount:
                raise ValidationError(
                    f"El monto para la orden {order.order_number} excede el monto maximo de cumplimiento."
                )

        for budget_id, submitted_amount in submitted_by_budget.items():
            budget = ContractBudget.objects.filter(pk=budget_id).first()
            if budget is None:
                raise ValidationError("Se selecciono un presupuesto inexistente.")

            if submitted_amount > (budget.available_amount or 0):
                raise ValidationError(
                    f"El monto asignado al presupuesto {budget.id} excede su disponible ({budget.available_amount})."
                )


PaymentAllocationFormSet = inlineformset_factory(
    Payment,
    PaymentAllocation,
    form=PaymentAllocationForm,
    formset=BasePaymentAllocationFormSet,
    extra=1,
    can_delete=False,
)

PaymentAllocationUpdateFormSet = inlineformset_factory(
    Payment,
    PaymentAllocation,
    form=PaymentAllocationForm,
    formset=BasePaymentAllocationFormSet,
    extra=1,
    can_delete=True,
)
