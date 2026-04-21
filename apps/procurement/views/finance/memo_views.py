from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.dncp_integration.models import Contract
from apps.procurement.forms import (
    FulfillmentMemoForm,
    FulfillmentMemoLineEditFormSet,
    FulfillmentMemoLineFormSet,
)
from apps.procurement.models import FulfillmentMemo, FulfillmentMemoLine
from apps.procurement.selectors import get_fulfillment_memos_queryset
from apps.procurement.services import (
    approve_fulfillment_memo,
    create_fulfillment_memo,
    update_fulfillment_memo,
)
from apps.procurement.views.mixins import HtmxTemplateMixin


class FulfillmentMemoListView(HtmxTemplateMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "procurement.view_fulfillmentmemo"
    model = FulfillmentMemo
    template_name = "procurement/finance/memos/list.html"
    partial_template_name = "procurement/finance/memos/_table.html"
    context_object_name = "memos"

    def get_queryset(self):
        return get_fulfillment_memos_queryset()


def _extract_memo_lines_data(formset, form):
    """Extrae las líneas válidas del formset y devuelve una lista de dicts.

    Retorna ``None`` y agrega error al formulario si no hay líneas válidas.
    """
    lines_data = []
    for line_form in formset.forms:
        if not line_form.cleaned_data:
            continue
        if line_form.cleaned_data.get("DELETE"):
            continue
        purchase_order = line_form.cleaned_data.get("purchase_order")
        if purchase_order is None:
            continue
        lines_data.append(
            {
                "purchase_order": purchase_order,
                "purchase_order_line": line_form.cleaned_data.get("purchase_order_line"),
                "fulfilled_quantity": line_form.cleaned_data.get("fulfilled_quantity"),
                "application_scope": line_form.cleaned_data.get("application_scope"),
                "application_detail": line_form.cleaned_data.get("application_detail", ""),
                "observations": line_form.cleaned_data.get("observations", ""),
            }
        )
    if not lines_data:
        form.add_error(None, "Debe agregar al menos una linea de cumplimiento.")
        return None
    return lines_data


class FulfillmentMemoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "procurement.add_fulfillmentmemo"
    model = FulfillmentMemo
    form_class = FulfillmentMemoForm
    template_name = "procurement/finance/memos/form.html"
    success_url = reverse_lazy("procurement:memo_list")

    def _resolve_contract(self):
        contract_id = self.request.POST.get("contract") if self.request.method == "POST" else self.request.GET.get("contract")
        if not contract_id:
            return None
        return Contract.objects.filter(pk=contract_id).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self._resolve_contract()

        if self.request.method == "POST":
            context["line_formset"] = FulfillmentMemoLineFormSet(
                self.request.POST,
                instance=self.object,
                contract=contract,
            )
        else:
            context["line_formset"] = FulfillmentMemoLineFormSet(
                instance=self.object,
                contract=contract,
            )
        context["contract_orders_base_url"] = str(
            reverse_lazy(
                "procurement:contract_orders_options",
                kwargs={"contract_id": "__CONTRACT_ID__"},
            )
        )
        context["order_lines_base_url"] = str(
            reverse_lazy(
                "procurement:order_lines_options",
                kwargs={"order_id": 0},
            )
        ).replace("/0/", "/__ORDER_ID__/")
        context["application_scope_create_url"] = reverse_lazy("procurement:application_scope_create")
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        line_formset = context["line_formset"]

        if not line_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        lines_data = _extract_memo_lines_data(line_formset, form)
        if lines_data is None:
            return self.render_to_response(self.get_context_data(form=form))

        with transaction.atomic():
            create_fulfillment_memo(
                contract=form.cleaned_data["contract"],
                application_scope=form.cleaned_data.get("application_scope"),
                application_detail=form.cleaned_data.get("application_detail", ""),
                memo_number=form.cleaned_data["memo_number"],
                memo_date=form.cleaned_data["memo_date"],
                received_by=form.cleaned_data.get("received_by", ""),
                sender_position=form.cleaned_data.get("sender_position", ""),
                created_by=self.request.user,
                notes=form.cleaned_data.get("notes", ""),
                lines_data=lines_data,
            )

        messages.success(self.request, "Memorandum de cumplimiento guardado en borrador.")
        return redirect(self.success_url)


class FulfillmentMemoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "procurement.change_fulfillmentmemo"
    model = FulfillmentMemo
    form_class = FulfillmentMemoForm
    template_name = "procurement/finance/memos/form.html"
    success_url = reverse_lazy("procurement:memo_list")

    def dispatch(self, request, *args, **kwargs):
        memo = self.get_object()
        if memo.status in {FulfillmentMemo.STATUS_APPROVED, FulfillmentMemo.STATUS_CANCELLED, FulfillmentMemo.STATUS_REJECTED}:
            messages.error(request, "Solo se puede editar un memorandum pendiente de aprobacion.")
            return redirect("procurement:memo_list")
        return super().dispatch(request, *args, **kwargs)

    def _resolve_contract(self):
        contract_id = self.request.POST.get("contract") if self.request.method == "POST" else None
        if contract_id:
            return Contract.objects.filter(pk=contract_id).first()
        return self.object.contract

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self._resolve_contract()

        if self.request.method == "POST":
            context["line_formset"] = FulfillmentMemoLineEditFormSet(
                self.request.POST,
                instance=self.object,
                contract=contract,
            )
        else:
            context["line_formset"] = FulfillmentMemoLineEditFormSet(
                instance=self.object,
                contract=contract,
            )
        context["contract_orders_base_url"] = str(
            reverse_lazy(
                "procurement:contract_orders_options",
                kwargs={"contract_id": "__CONTRACT_ID__"},
            )
        )
        context["order_lines_base_url"] = str(
            reverse_lazy(
                "procurement:order_lines_options",
                kwargs={"order_id": 0},
            )
        ).replace("/0/", "/__ORDER_ID__/")
        context["application_scope_create_url"] = reverse_lazy("procurement:application_scope_create")
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        line_formset = context["line_formset"]

        if not line_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        lines_data = _extract_memo_lines_data(line_formset, form)
        if lines_data is None:
            return self.render_to_response(self.get_context_data(form=form))

        with transaction.atomic():
            update_fulfillment_memo(
                self.object,
                contract=form.cleaned_data["contract"],
                application_scope=form.cleaned_data.get("application_scope"),
                application_detail=form.cleaned_data.get("application_detail", ""),
                memo_number=form.cleaned_data["memo_number"],
                memo_date=form.cleaned_data["memo_date"],
                received_by=form.cleaned_data.get("received_by", ""),
                sender_position=form.cleaned_data.get("sender_position", ""),
                notes=form.cleaned_data.get("notes", ""),
                lines_data=lines_data,
            )

        messages.success(self.request, "Memorandum de cumplimiento actualizado correctamente.")
        return redirect(self.success_url)


class FulfillmentMemoApproveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "procurement.change_fulfillmentmemo"

    def post(self, request, pk):
        memo = get_object_or_404(FulfillmentMemo, pk=pk)
        approve_fulfillment_memo(memo)
        messages.success(request, "Memorandum aprobado correctamente.")
        return redirect("procurement:memo_list")
