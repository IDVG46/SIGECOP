from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.dncp_integration.forms.contract_edit_forms import ContractManualCreateForm
from apps.dncp_integration.models import Contract, ContractExtra


@login_required
@require_http_methods(["GET", "POST"])
def contract_create(request):
    form = ContractManualCreateForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            contract_id = form.cleaned_data.get("contract_id")
            if not contract_id:
                contract_id = f"manual-{uuid4().hex[:12]}"

            contract = Contract.objects.create(
                id=contract_id,
                award=form.cleaned_data["award"],
                status_details=form.cleaned_data.get("status_details") or None,
                period_start_date=form.cleaned_data.get("period_start_date"),
                period_end_date=form.cleaned_data.get("period_end_date"),
                value_amount=form.cleaned_data.get("value_amount"),
                value_currency=form.cleaned_data.get("value_currency"),
                is_user_modified=True,
                modified_by=request.user,
                modified_at=timezone.now(),
            )

            ContractExtra.objects.create(
                contract=contract,
                contract_number=form.cleaned_data.get("contract_number") or "",
                resolution_number=form.cleaned_data.get("resolution_number") or "",
                resolution_sender=form.cleaned_data.get("resolution_sender") or "",
                resolution_article=form.cleaned_data.get("resolution_article") or "",
                contract_administrator=form.cleaned_data.get("contract_administrator") or "",
                is_user_modified=True,
                modified_by=request.user,
                modified_at=timezone.now(),
            )

        messages.success(request, f"Contrato {contract.id} creado correctamente.")
        return redirect("dncp_integration:contract_detail", contract_id=contract.id)

    context = {"form": form}
    return render(request, "dncp_integration/contract_create.html", context)
