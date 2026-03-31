from django.urls import path

from apps.dncp_integration.views import (
    contract_views,
    tender_views,
    contract_edit_views,
    contract_create_views,
    entity_views,
)

app_name = "dncp_integration"

urlpatterns = [
    path("entidades/", entity_views.organization_list, name="organization_list"),
    path("entidades/select/", entity_views.organization_select, name="organization_select"),
    path("entidades/<int:org_id>/edit/", entity_views.organization_update, name="organization_update"),
    path("tenders/", tender_views.tender_list, name="tender_list"),
    path("tenders/<str:ocid>/", tender_views.tender_detail, name="tender_detail"),
    path("contratos/", contract_views.contract_list, name="contract_list"),
    path("contratos/crear/", contract_create_views.contract_create, name="contract_create"),
    path("contratos/<str:contract_id>/", contract_views.contract_detail, name="contract_detail"),
    path("contratos/<str:contract_id>/edit/", contract_edit_views.contract_edit, name="contract_edit"),
    path("api/award-items/<int:award_item_id>/update/", contract_edit_views.update_award_item, name="update_award_item"),
    path("api/award-subitems/<int:award_subitem_id>/update/", contract_edit_views.update_award_subitem, name="update_award_subitem"),
]