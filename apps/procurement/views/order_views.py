from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.dncp_integration.models import Contract
from apps.dncp_integration.views.local_views import _format_amount
from apps.procurement.forms import PurchaseOrderForm, PurchaseOrderLineFormSet
from apps.procurement.models import PurchaseOrder
from apps.procurement.selectors import get_purchase_orders_queryset
from apps.procurement.services import recalculate_contract_balances, recalculate_order_totals_and_balances


class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "procurement.view_purchaseorder"
    template_name = "procurement/order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        queryset = get_purchase_orders_queryset().order_by("-issue_date")
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(order_number__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for order in context.get("orders", []):
            currency = getattr(order.contract, "value_currency", None)
            order.formatted_total_amount = _format_amount(order.total_amount, currency)
        return context


class PurchaseOrderBaseView(LoginRequiredMixin, PermissionRequiredMixin):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    success_url = reverse_lazy("procurement:order_list")
    template_name = "procurement/order_form.html"

    def _resolve_contract(self):
        contract_id = None

        if self.request.method == "POST":
            contract_id = self.request.POST.get("contract")
        elif getattr(self, "object", None):
            return self.object.contract
        else:
            contract_id = self.request.GET.get("contract")

        if not contract_id:
            return None

        try:
            return Contract.objects.select_related("award", "award__tender").get(pk=contract_id)
        except Contract.DoesNotExist:
            return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        contract = self._resolve_contract()
        if contract:
            kwargs["contract"] = contract
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self._resolve_contract()
        form_kwargs = {"contract": contract} if contract else {}
        parent_instance = getattr(self, "object", None)
        form_obj = kwargs.get("form")
        if form_obj is not None:
            parent_instance = form_obj.instance

        if self.request.method == "POST":
            context["line_formset"] = PurchaseOrderLineFormSet(
                self.request.POST,
                instance=parent_instance,
                form_kwargs=form_kwargs,
            )
        else:
            context["line_formset"] = PurchaseOrderLineFormSet(
                instance=parent_instance,
                form_kwargs=form_kwargs,
            )
        context["line_options_base_url"] = reverse_lazy("procurement:contract_line_options", kwargs={"contract_id": "__CONTRACT_ID__"})
        context["supplier_options_base_url"] = reverse_lazy("procurement:contract_suppliers", kwargs={"contract_id": "__CONTRACT_ID__"})
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        line_formset = context["line_formset"]
        line_formset.instance = form.instance

        if not line_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        with transaction.atomic():
            self.object = form.save()
            line_formset.instance = self.object
            line_formset.save()
            recalculate_order_totals_and_balances(self.object)

        messages.success(self.request, "Orden de compra guardada correctamente.")
        return redirect(self.success_url)


class PurchaseOrderCreateView(PurchaseOrderBaseView, CreateView):
    permission_required = "procurement.add_purchaseorder"


class PurchaseOrderUpdateView(PurchaseOrderBaseView, UpdateView):
    permission_required = "procurement.change_purchaseorder"


class PurchaseOrderDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "procurement.delete_purchaseorder"
    model = PurchaseOrder
    success_url = reverse_lazy("procurement:order_list")
    template_name = "procurement/order_confirm_delete.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        contract = self.object.contract

        with transaction.atomic():
            self.object.delete()
            recalculate_contract_balances(contract)

        messages.success(request, "Orden de compra eliminada correctamente.")
        return HttpResponseRedirect(self.success_url)


class PurchaseOrderCancelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "procurement.change_purchaseorder"

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk)

        if order.status == PurchaseOrder.STATUS_CANCELLED:
            messages.info(request, "La orden ya estaba anulada.")
            return redirect("procurement:order_list")

        with transaction.atomic():
            order.status = PurchaseOrder.STATUS_CANCELLED
            order.save(update_fields=["status", "updated_at"])
            recalculate_contract_balances(order.contract)

        messages.success(request, "Orden anulada correctamente y saldos recalculados.")
        return redirect("procurement:order_list")
