from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.dncp_integration.views.local_views import _format_amount
from apps.procurement.forms import ContractBudgetForm
from apps.procurement.models import ContractBudget
from apps.procurement.services import approve_budget


class ContractBudgetListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "procurement.view_contractbudget"
    model = ContractBudget
    template_name = "procurement/budget_list.html"
    context_object_name = "budgets"

    def get_queryset(self):
        queryset = ContractBudget.objects.select_related("contract", "expense_object").order_by("-fiscal_year", "contract_id")
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(contract_id__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for budget in context.get("budgets", []):
            currency = getattr(budget.contract, "value_currency", None)
            budget.formatted_assigned_amount = _format_amount(budget.assigned_amount, currency)
            budget.formatted_committed_amount = _format_amount(budget.committed_amount, currency)
            budget.formatted_executed_amount = _format_amount(budget.executed_amount, currency)
        return context


class ContractBudgetCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "procurement.add_contractbudget"
    model = ContractBudget
    form_class = ContractBudgetForm
    template_name = "procurement/budget_form.html"
    success_url = reverse_lazy("procurement:budget_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["financial_codes_base_url"] = str(
            reverse_lazy(
                "procurement:contract_financial_codes",
                kwargs={"contract_id": "__CONTRACT_ID__"},
            )
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            budget = form.save(commit=False)
            budget.full_clean()
            budget.save()
        messages.success(self.request, "Presupuesto creado correctamente.")
        return redirect(self.success_url)


class ContractBudgetUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "procurement.change_contractbudget"
    model = ContractBudget
    form_class = ContractBudgetForm
    template_name = "procurement/budget_form.html"
    success_url = reverse_lazy("procurement:budget_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["financial_codes_base_url"] = str(
            reverse_lazy(
                "procurement:contract_financial_codes",
                kwargs={"contract_id": "__CONTRACT_ID__"},
            )
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            budget = form.save(commit=False)
            budget.full_clean()
            budget.save()
        messages.success(self.request, "Presupuesto actualizado correctamente.")
        return redirect(self.success_url)


class ContractBudgetApproveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "procurement.change_contractbudget"

    def post(self, request, pk):
        budget = get_object_or_404(ContractBudget, pk=pk)
        approve_budget(budget)
        messages.success(request, "Presupuesto aprobado correctamente.")
        return redirect("procurement:budget_list")
