from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.dncp_integration.forms.entity_forms import DNCPOrganizationForm, DNCPOrganizationSelectForm
from apps.dncp_integration.models import DNCPOrganization, UserDNCPOrganizationSelection


@login_required
@require_http_methods(["GET", "POST"])
def organization_list(request):
    organizations = DNCPOrganization.objects.all().order_by("name")

    if request.method == "POST" and request.POST.get("action") == "create":
        form = DNCPOrganizationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Entidad DNCP creada correctamente.")
            return redirect("dncp_integration:organization_list")
    else:
        form = DNCPOrganizationForm()

    current_selection = UserDNCPOrganizationSelection.objects.filter(user=request.user).select_related("organization").first()
    selected_org = current_selection.organization if current_selection else None

    select_form = DNCPOrganizationSelectForm(
        initial={"organization": selected_org.id if selected_org else None}
    )

    context = {
        "organizations": organizations,
        "form": form,
        "select_form": select_form,
        "selected_org": selected_org,
    }
    return render(request, "dncp_integration/organization_list.html", context)


@login_required
@require_http_methods(["POST"])
def organization_update(request, org_id):
    organization = get_object_or_404(DNCPOrganization, pk=org_id)
    form = DNCPOrganizationForm(request.POST, instance=organization)

    if form.is_valid():
        form.save()
        messages.success(request, "Entidad DNCP actualizada correctamente.")
    else:
        messages.warning(request, "No se pudo actualizar la entidad. Verifica los datos.")

    return redirect("dncp_integration:organization_list")


@login_required
@require_http_methods(["POST"])
def organization_select(request):
    form = DNCPOrganizationSelectForm(request.POST)
    if not form.is_valid():
        messages.warning(request, "Seleccion de entidad invalida.")
        return redirect("dncp_integration:organization_list")

    organization = form.cleaned_data["organization"]

    UserDNCPOrganizationSelection.objects.update_or_create(
        user=request.user,
        defaults={"organization": organization},
    )

    request.session["selected_dncp_organization_id"] = organization.id
    messages.success(request, f"Entidad activa establecida: {organization.name}.")
    return redirect("dncp_api:dncp_list")
