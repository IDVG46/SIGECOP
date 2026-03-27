from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Sum
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.dncp_integration.models import Contract, ContractExtra
from apps.dncp_integration.views.local_views import _format_amount
from apps.procurement.forms import (
    PaymentAllocationFormSet,
    PaymentAllocationUpdateFormSet,
    PaymentForm,
)
from apps.procurement.models import (
    FulfillmentMemo,
    Payment,
    PurchaseOrder,
)
from apps.procurement.selectors import get_payments_queryset
from apps.procurement.services import cancel_payment, post_payment
from apps.procurement.services.finance_service import get_unapproved_memos_for_orders
from apps.procurement.services.payments import build_payment_lot_report_sections


class PaymentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "procurement.view_payment"
    model = Payment
    template_name = "procurement/finance/payments/list.html"
    partial_template_name = "procurement/finance/payments/_table.html"
    context_object_name = "payments"

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return [self.partial_template_name]
        return [self.template_name]

    def get_queryset(self):
        return get_payments_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for payment in context.get("payments", []):
            contract = payment.contract
            if contract is None:
                first_alloc = next(iter(payment.allocations.all()), None)
                if first_alloc and first_alloc.contract_budget_id:
                    contract = first_alloc.contract_budget.contract
            currency = getattr(contract, "value_currency", None) if contract else None
            payment.formatted_amount_total = _format_amount(payment.amount_total, currency)

        return context


class PaymentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "procurement.add_payment"
    model = Payment
    form_class = PaymentForm
    template_name = "procurement/finance/payments/form.html"
    success_url = reverse_lazy("procurement:payment_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            context["allocation_formset"] = PaymentAllocationFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            context["allocation_formset"] = PaymentAllocationFormSet(
                instance=self.object,
            )
        context["order_budgets_base_url"] = str(
            reverse_lazy(
                "procurement:order_budgets_options",
                kwargs={"order_id": 0},
            )
        ).replace("/0/", "/__ORDER_ID__/")
        context["contract_orders_base_url"] = str(
            reverse_lazy(
                "procurement:contract_orders_options",
                kwargs={"contract_id": 0},
            )
        ).replace("/0/", "/__CONTRACT_ID__/")
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        allocation_formset = context.get("allocation_formset")

        if not allocation_formset:
            if self.request.method == "POST":
                allocation_formset = PaymentAllocationFormSet(self.request.POST, instance=self.object)
            else:
                allocation_formset = PaymentAllocationFormSet(instance=self.object)
        if not allocation_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        orders_to_pay = []
        for alloc_form in allocation_formset.forms:
            if not alloc_form.cleaned_data:
                continue
            if alloc_form.cleaned_data.get("DELETE"):
                continue
            purchase_order = alloc_form.cleaned_data.get("purchase_order")
            if purchase_order and purchase_order not in orders_to_pay:
                orders_to_pay.append(purchase_order)

        if not orders_to_pay:
            messages.error(
                self.request,
                mark_safe(
                    "<strong>Error: Sin Asignaciones</strong><br><br>"
                    "Debe asignar al menos una orden de compra antes de guardar el pago.<br><br>"
                    "<strong>Accion:</strong> Haz clic en <strong>Agregar asignacion</strong> e ingresa una orden."
                )
            )
            return redirect("procurement:payment_list")

        unapproved_by_order = get_unapproved_memos_for_orders(orders_to_pay)
        if unapproved_by_order:
            error_lines = [
                "<strong>Cumplimientos Pendientes de Aprobacion</strong><br><br>",
                "Las siguientes ordenes tienen cumplimientos sin aprobar:<br><br>",
            ]
            for order_id, memos in sorted(unapproved_by_order.items()):
                order = next((order for order in orders_to_pay if order.id == order_id), None)
                if order:
                    error_lines.append(f"<strong>Orden {order.order_number}:</strong><br>")
                    for memo in memos[:3]:
                        status_label = dict(FulfillmentMemo.STATUS_CHOICES).get(memo.status, memo.status)
                        error_lines.append(f"- Memo {memo.memo_number} ({status_label})<br>")
                    if len(memos) > 3:
                        error_lines.append(f"- ... y {len(memos) - 3} mas<br><br>")

            error_lines.append("<strong>Accion:</strong> Ve a <strong>Cumplimientos</strong> y aprueba todos los memos antes de crear este pago.")
            messages.warning(
                self.request,
                mark_safe("".join(error_lines))
            )
            return redirect("procurement:payment_list")

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.status = Payment.STATUS_DRAFT
            self.object.created_by = self.request.user
            self.object.full_clean()
            self.object.save()

            for alloc_form in allocation_formset.forms:
                if not alloc_form.cleaned_data:
                    continue
                if alloc_form.cleaned_data.get("DELETE"):
                    continue
                purchase_order = alloc_form.cleaned_data.get("purchase_order")
                amount = alloc_form.cleaned_data.get("amount")
                if purchase_order is None or amount in (None, ""):
                    continue

                self.object.allocations.create(
                    purchase_order=purchase_order,
                    contract_budget=alloc_form.cleaned_data.get("contract_budget"),
                    amount=amount,
                )

        messages.success(self.request, "Pago en borrador creado correctamente.")
        return redirect(self.success_url)


class PaymentPostView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "procurement.change_payment"

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        try:
            post_payment(payment)
        except ValidationError as exc:
            error_messages = exc.messages if getattr(exc, "messages", None) else [str(exc)]
            error_html = "<strong>Error al Imputar el Pago</strong><br><br>"
            for idx, msg in enumerate(error_messages, 1):
                error_html += f"<strong>{idx}.</strong> {msg}<br>"

            error_html += (
                "<br><strong>Sugerencias:</strong><br>"
                "- Verifica que todos los cumplimientos esten aprobados<br>"
                "- Asegurate de que hay presupuesto disponible<br>"
                "- Revisa que las asignaciones de ordenes sean correctas"
            )

            messages.error(request, mark_safe(error_html))
            return redirect("procurement:payment_list")

        messages.success(request, "Pago imputado correctamente.")
        return redirect("procurement:payment_list")


class PaymentCancelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "procurement.change_payment"

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        try:
            cancel_payment(payment)
        except ValidationError as exc:
            message = "; ".join(exc.messages) if getattr(exc, "messages", None) else str(exc)
            messages.error(request, message)
            return redirect("procurement:payment_list")

        messages.success(request, "Pago anulado correctamente.")
        return redirect("procurement:payment_list")


class PaymentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "procurement.change_payment"
    model = Payment
    form_class = PaymentForm
    template_name = "procurement/finance/payments/form.html"
    success_url = reverse_lazy("procurement:payment_list")

    def dispatch(self, request, *args, **kwargs):
        payment = self.get_object()
        if payment.status != Payment.STATUS_DRAFT:
            messages.error(request, "Solo se puede editar un pago en estado borrador.")
            return redirect("procurement:payment_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            context["allocation_formset"] = PaymentAllocationUpdateFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            context["allocation_formset"] = PaymentAllocationUpdateFormSet(
                instance=self.object,
            )
        context["order_budgets_base_url"] = str(
            reverse_lazy(
                "procurement:order_budgets_options",
                kwargs={"order_id": 0},
            )
        ).replace("/0/", "/__ORDER_ID__/")
        context["contract_orders_base_url"] = str(
            reverse_lazy(
                "procurement:contract_orders_options",
                kwargs={"contract_id": 0},
            )
        ).replace("/0/", "/__CONTRACT_ID__/")
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        allocation_formset = context["allocation_formset"]

        if not allocation_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        with transaction.atomic():
            self.object = form.save()
            allocation_formset.instance = self.object
            allocation_formset.save()

        messages.success(self.request, "Pago actualizado correctamente.")
        return redirect(self.success_url)


class PaymentReportView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "procurement.view_payment"
    model = Payment
    template_name = "procurement/finance/payments/report.html"
    context_object_name = "payment"

    def get_queryset(self):
        return Payment.objects.select_related("contract").prefetch_related(
            "allocations__purchase_order__supplier",
            "allocations__contract_budget__expense_object",
            "allocations__contract_budget__contract",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object
        allocations = list(
            payment.allocations.select_related(
                "purchase_order__supplier",
                "contract_budget__expense_object",
                "contract_budget__contract",
            ).order_by(
                "contract_budget__financial_code",
                "contract_budget__expense_object__code",
                "purchase_order__order_number",
            )
        )

        contract = payment.contract
        if contract is None and allocations:
            contract = allocations[0].contract_budget.contract

        current_by_budget = {}
        for alloc in allocations:
            budget_id = alloc.contract_budget_id
            current_by_budget[budget_id] = current_by_budget.get(budget_id, Decimal("0.00")) + alloc.amount

        previous_by_budget = {}
        if contract is not None:
            previous_allocations = (
                payment.allocations.model.objects.filter(
                    contract_budget__contract=contract,
                    payment__status=Payment.STATUS_POSTED,
                )
                .exclude(payment=payment)
                .filter(
                    Q(payment__payment_date__lt=payment.payment_date)
                    | Q(payment__payment_date=payment.payment_date, payment__id__lt=payment.id)
                )
                .values("contract_budget_id")
                .annotate(total=Sum("amount"))
            )
            previous_by_budget = {row["contract_budget_id"]: row["total"] for row in previous_allocations}

        sections_map = {}
        budget_rows_by_id = {}
        for alloc in allocations:
            budget = alloc.contract_budget
            budget_id = budget.id

            if budget_id not in budget_rows_by_id:
                previous_paid_amount = previous_by_budget.get(budget_id, Decimal("0.00"))
                previous_amount = budget.assigned_amount - previous_paid_amount
                current_amount = current_by_budget.get(budget_id, Decimal("0.00"))
                remaining_amount = previous_amount - current_amount

                budget_rows_by_id[budget_id] = {
                    "budget": budget,
                    "assigned_amount": budget.assigned_amount,
                    "previous_amount": previous_amount,
                    "current_amount": current_amount,
                    "remaining_amount": remaining_amount,
                }

            section_key = budget.funding_source or "SIN-FUENTE"
            section = sections_map.setdefault(
                section_key,
                {
                    "funding_source": section_key,
                    "rows": [],
                    "totals": {
                        "assigned": 0,
                        "previous": 0,
                        "current": 0,
                        "remaining": 0,
                    },
                },
            )

            row_ref = budget_rows_by_id[budget_id]
            if row_ref not in section["rows"]:
                section["rows"].append(row_ref)

        sections = []
        overall = {"assigned": 0, "previous": 0, "current": 0, "remaining": 0}
        for key in sorted(sections_map.keys()):
            section = sections_map[key]
            for row in section["rows"]:
                section["totals"]["assigned"] += row["assigned_amount"]
                section["totals"]["previous"] += row["previous_amount"]
                section["totals"]["current"] += row["current_amount"]
                section["totals"]["remaining"] += row["remaining_amount"]

            overall["assigned"] += section["totals"]["assigned"]
            overall["previous"] += section["totals"]["previous"]
            overall["current"] += section["totals"]["current"]
            overall["remaining"] += section["totals"]["remaining"]
            sections.append(section)

        funding_summary = []
        funding_summary_totals = {"previous": Decimal("0.00"), "current": Decimal("0.00")}
        for section in sections:
            details = []
            for row in sorted(
                section["rows"],
                key=lambda r: (
                    (r["budget"].financial_code or ""),
                    (r["budget"].cdp_number or ""),
                    r["budget"].id,
                ),
            ):
                details.append(
                    {
                        "financial_code": row["budget"].financial_code or "SIN-CODIGO",
                        "cdp_number": row["budget"].cdp_number or "-",
                        "previous": row["previous_amount"],
                        "current": row["current_amount"],
                    }
                )

            previous_value = section["totals"]["previous"]
            current_value = section["totals"]["current"]
            funding_summary.append(
                {
                    "funding_source": section["funding_source"],
                    "details": details,
                    "totals": {
                        "previous": previous_value,
                        "current": current_value,
                    },
                }
            )
            funding_summary_totals["previous"] += previous_value
            funding_summary_totals["current"] += current_value

        supplier = allocations[0].purchase_order.supplier if allocations else None

        order_ids = list({alloc.purchase_order_id for alloc in allocations})
        memos = list(
            FulfillmentMemo.objects.filter(
                lines__purchase_order_id__in=order_ids,
                status__in=[FulfillmentMemo.STATUS_ISSUED, FulfillmentMemo.STATUS_APPROVED],
            )
            .distinct()
            .order_by("memo_date", "memo_number")
        )

        memos_grouped_dict = {}
        for memo in memos:
            key = (memo.beneficiary_sector, memo.received_by, memo.sender_position)
            if key not in memos_grouped_dict:
                memos_grouped_dict[key] = []
            memos_grouped_dict[key].append(memo.memo_number)

        memos_grouped = [
            {
                "sector": key[0],
                "received_by": key[1],
                "sender_position": key[2],
                "memo_numbers": memo_nums,
            }
            for key, memo_nums in memos_grouped_dict.items()
        ]

        contract_extra = None
        if contract is not None:
            contract_extra = ContractExtra.objects.filter(contract=contract).first()

        validity_range = "-"
        if contract is not None:
            start = contract.period_start_date
            end = contract.period_end_date
            if start and end:
                validity_range = f"{start:%d/%m/%Y} al {end:%d/%m/%Y}"
            elif start:
                validity_range = f"Desde {start:%d/%m/%Y}"
            elif end:
                validity_range = f"Hasta {end:%d/%m/%Y}"

        context["contract"] = contract
        context["contract_extra"] = contract_extra
        context["contract_number"] = (contract_extra.contract_number if contract_extra and contract_extra.contract_number else getattr(contract, "id", "-"))
        context["contract_resolution"] = contract_extra.resolution_number if contract_extra and contract_extra.resolution_number else "-"
        context["contract_resolution_sender"] = contract_extra.resolution_sender if contract_extra and contract_extra.resolution_sender else ""
        context["contract_resolution_article"] = contract_extra.resolution_article if contract_extra and contract_extra.resolution_article else "2"
        context["contract_validity"] = validity_range
        context["allocations"] = allocations
        context["sections"] = sections
        context["overall"] = overall
        context["funding_summary"] = funding_summary
        context["funding_summary_totals"] = funding_summary_totals
        context["supplier"] = supplier
        context["memos"] = memos
        context["memos_grouped"] = memos_grouped
        context["formatted_payment_total"] = _format_amount(payment.amount_total, getattr(contract, "value_currency", None) if contract else None)

        lot_sections, lot_sections_total = build_payment_lot_report_sections(
            payment=payment,
            allocations=allocations,
            contract=contract,
        )

        context["lot_sections"] = lot_sections
        context["lot_sections_total"] = lot_sections_total
        return context
