from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.dncp_integration.models import Contract
from apps.dncp_integration.views.local_views import _format_amount
from apps.procurement.forms.finance_forms import ContractBudgetBatchFormSet
from apps.procurement.models import ContractBudget, PaymentAllocation, PurchaseOrder
from apps.procurement.selectors import get_contract_budgets_queryset
from apps.procurement.services import approve_budget
from apps.procurement.views.mixins import HtmxTemplateMixin


class ContractBudgetListView(HtmxTemplateMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "procurement.view_contractbudget"
    model = ContractBudget
    template_name = "procurement/finance/budgets/list.html"
    partial_template_name = "procurement/finance/budgets/_table.html"
    context_object_name = "budgets"

    def get_queryset(self):
        return get_contract_budgets_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for budget in context.get("budgets", []):
            currency = getattr(budget.contract, "value_currency", None)
            budget.formatted_assigned_amount = _format_amount(budget.assigned_amount, currency)
            budget.formatted_committed_amount = _format_amount(budget.committed_amount, currency)
            budget.formatted_executed_amount = _format_amount(budget.executed_amount, currency)
        return context


class ContractBudgetApproveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "procurement.change_contractbudget"

    def post(self, request, pk):
        budget = get_object_or_404(ContractBudget, pk=pk)
        approve_budget(budget)
        messages.success(request, "Presupuesto aprobado correctamente.")
        return redirect("procurement:budget_list")


class ContractBudgetBatchView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Editor inline de N presupuestos por contrato.
    • Sin contract_id (GET /budgets/batch/): muestra el selector de contrato y tabla vacía.
    • Con contract_id (GET /budgets/batch/<id>/): carga las filas existentes del contrato.
    • POST /budgets/batch/<id>/: guarda el formset.
    """

    permission_required = "procurement.change_contractbudget"
    template_name = "procurement/finance/budgets/batch_form.html"

    _BATCH_QS_ORDER = ("fiscal_year", "expense_object__code")
    _EMPTY_QS = ContractBudget.objects.none()

    def _contracts_qs(self):
        return Contract.objects.order_by("id")

    def _budget_qs(self, contract_id):
        return ContractBudget.objects.filter(contract_id=contract_id).order_by(*self._BATCH_QS_ORDER)

    def _batch_url_template(self, request):
        """URL con placeholder __CONTRACT_ID__ para la redirección de JS."""
        return request.build_absolute_uri(
            reverse("procurement:budget_batch", kwargs={"contract_id": "__CONTRACT_ID__"})
        )

    def _contract_summary(self, contract):
        """Saldo del contrato disponible para presupuestar.

        Muestra: valor total del contrato, total ya presupuestado
        (sum assigned_amount excl. cancelados) y lo disponible a presupuestar
        (contract.value_amount - total_assigned).
        """
        agg = ContractBudget.objects.filter(contract=contract).exclude(
            status=ContractBudget.STATUS_CANCELLED
        ).aggregate(
            total_assigned=Sum("assigned_amount", default=Decimal("0.00")),
        )
        currency = getattr(contract, "value_currency", None)
        value_amount = contract.value_amount
        total_assigned = agg["total_assigned"]
        if value_amount is not None:
            disponible = value_amount - total_assigned
        else:
            disponible = None
        return {
            "contract_value": _format_amount(value_amount, currency),
            "total_assigned": _format_amount(total_assigned, currency),
            "disponible_presupuestar": _format_amount(disponible, currency),
            "has_value": value_amount is not None,
            "disponible_negative": disponible is not None and disponible < Decimal("0.00"),
        }

    def get(self, request, contract_id=None):
        contract = get_object_or_404(Contract, pk=contract_id) if contract_id else None
        qs = self._budget_qs(contract_id) if contract else self._EMPTY_QS
        formset = ContractBudgetBatchFormSet(
            queryset=qs,
            form_kwargs={"contract": contract},
        )
        return render(request, self.template_name, {
            "contract": contract,
            "contracts": self._contracts_qs(),
            "formset": formset,
            "batch_url_template": self._batch_url_template(request),
            "contract_summary": self._contract_summary(contract) if contract else None,
        })

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        formset = ContractBudgetBatchFormSet(
            request.POST,
            queryset=self._budget_qs(contract_id),
            form_kwargs={"contract": contract},
        )
        if formset.is_valid():
            try:
                with transaction.atomic():
                    instances = formset.save(commit=False)
                    for instance in instances:
                        instance.contract = contract
                        instance.full_clean()
                        instance.save()
                    for obj in formset.deleted_objects:
                        obj.delete()
                messages.success(request, "Presupuestos guardados correctamente.")
                return redirect(reverse("procurement:budget_list"))
            except ValidationError as exc:
                messages.error(request, f"Error de validación: {'; '.join(exc.messages)}")
            except IntegrityError:
                messages.error(request, "Error: duplicado — ya existe un presupuesto con esa combinación.")
        return render(request, self.template_name, {
            "contract": contract,
            "contracts": self._contracts_qs(),
            "formset": formset,
            "batch_url_template": self._batch_url_template(request),
            "contract_summary": self._contract_summary(contract),
        })


class ContractBudgetDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Vista de detalle de un presupuesto: montos, órdenes relacionadas y pagos imputados."""

    permission_required = "procurement.view_contractbudget"
    model = ContractBudget
    template_name = "procurement/finance/budgets/detail.html"
    context_object_name = "budget"

    def get_queryset(self):
        return ContractBudget.objects.select_related(
            "contract", "expense_object", "contract__value_currency"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        budget = self.object
        currency = getattr(budget.contract, "value_currency", None)

        # Órdenes de compra que usan el mismo contrato + objeto de gasto
        context["orders"] = (
            PurchaseOrder.objects.filter(
                contract=budget.contract,
                expense_object=budget.expense_object,
            )
            .exclude(status=PurchaseOrder.STATUS_CANCELLED)
            .select_related("supplier", "expense_object")
            .order_by("-issue_date")
        )

        # Pagos imputados directamente a este presupuesto (con monto formateado)
        allocations = list(
            PaymentAllocation.objects.filter(contract_budget=budget)
            .select_related("payment", "purchase_order", "purchase_order__supplier")
            .order_by("-payment__payment_date")
        )
        for alloc in allocations:
            alloc.fmt_amount = _format_amount(alloc.amount, currency)
        context["allocations"] = allocations

        # Montos formateados
        context["fmt_assigned"] = _format_amount(budget.assigned_amount, currency)
        context["fmt_committed"] = _format_amount(budget.committed_amount, currency)
        context["fmt_executed"] = _format_amount(budget.executed_amount, currency)
        context["fmt_available"] = _format_amount(budget.available_amount, currency)

        # Porcentajes para la barra visual (safe: si assigned==0 evitar división)
        assigned = budget.assigned_amount or 1
        context["pct_committed"] = min(
            float(budget.committed_amount / assigned * 100), 100
        )
        context["pct_executed"] = min(
            float(budget.executed_amount / assigned * 100), 100
        )
        return context
