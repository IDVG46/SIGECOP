from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.dncp_integration.views.local_views import _format_amount
from apps.procurement.forms import ContractAmendmentForm
from apps.procurement.models import ContractAmendment
from apps.procurement.views.mixins import HtmxTemplateMixin


class ContractAmendmentListView(HtmxTemplateMixin, LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "procurement.view_contractamendment"
    model = ContractAmendment
    template_name = "procurement/finance/amendments/list.html"
    partial_template_name = "procurement/finance/amendments/_table.html"
    context_object_name = "amendments"

    def get_queryset(self):
        return ContractAmendment.objects.select_related("contract").order_by("-effective_date", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for amendment in context.get("amendments", []):
            currency = getattr(amendment.contract, "value_currency", None)
            amendment.formatted_amount_delta = _format_amount(amendment.amount_delta, currency)
        return context


class ContractAmendmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "procurement.add_contractamendment"
    model = ContractAmendment
    form_class = ContractAmendmentForm
    template_name = "procurement/finance/amendments/form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Adenda registrada correctamente.")
        return response

    def get_success_url(self):
        return reverse_lazy("procurement:amendment_detail", kwargs={"pk": self.object.pk})


class ContractAmendmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "procurement.change_contractamendment"
    model = ContractAmendment
    form_class = ContractAmendmentForm
    template_name = "procurement/finance/amendments/form.html"

    def get_queryset(self):
        return ContractAmendment.objects.select_related("contract")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Adenda actualizada correctamente.")
        return response

    def get_success_url(self):
        return reverse_lazy("procurement:amendment_detail", kwargs={"pk": self.object.pk})


class ContractAmendmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "procurement.view_contractamendment"
    model = ContractAmendment
    template_name = "procurement/finance/amendments/detail.html"
    context_object_name = "amendment"

    def get_queryset(self):
        return ContractAmendment.objects.select_related("contract")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        amendment = self.object
        currency = getattr(amendment.contract, "value_currency", None)
        context["formatted_amount_delta"] = _format_amount(amendment.amount_delta, currency)
        context["related_amendments"] = (
            ContractAmendment.objects.filter(contract=amendment.contract)
            .exclude(pk=amendment.pk)
            .order_by("-effective_date", "-id")[:5]
        )
        return context