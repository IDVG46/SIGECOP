from django.urls import path

from apps.procurement.views import (
    contract_line_options,
	contract_suppliers,
	PurchaseOrderCancelView,
	PurchaseOrderCreateView,
	PurchaseOrderDeleteView,
	PurchaseOrderListView,
	PurchaseOrderUpdateView,
)

app_name = "procurement"

urlpatterns = [
	path("orders/", PurchaseOrderListView.as_view(), name="order_list"),
	path("orders/add/", PurchaseOrderCreateView.as_view(), name="order_create"),
	path("orders/<int:pk>/edit/", PurchaseOrderUpdateView.as_view(), name="order_update"),
	path("orders/<int:pk>/delete/", PurchaseOrderDeleteView.as_view(), name="order_delete"),
	path("orders/<int:pk>/cancel/", PurchaseOrderCancelView.as_view(), name="order_cancel"),
	path("api/contracts/<str:contract_id>/line-options/", contract_line_options, name="contract_line_options"),
	path("api/contracts/<str:contract_id>/suppliers/", contract_suppliers, name="contract_suppliers"),
]