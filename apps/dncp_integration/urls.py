from django.urls import path

from apps.dncp_integration.views import contract_views, tender_views, contract_edit_views

app_name = "dncp_integration"

urlpatterns = [
    path("tenders/", tender_views.tender_list, name="tender_list"),
    path("tenders/<str:ocid>/", tender_views.tender_detail, name="tender_detail"),
    path("contratos/", contract_views.contract_list, name="contract_list"),
    path("contratos/<str:contract_id>/", contract_views.contract_detail, name="contract_detail"),
    path("contratos/<str:contract_id>/edit/", contract_edit_views.contract_edit, name="contract_edit"),
    path("api/award-items/<int:award_item_id>/update/", contract_edit_views.update_award_item, name="update_award_item"),
    path("api/award-subitems/<int:award_subitem_id>/update/", contract_edit_views.update_award_subitem, name="update_award_subitem"),
]