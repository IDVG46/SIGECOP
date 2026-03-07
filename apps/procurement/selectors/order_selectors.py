from apps.procurement.models import PurchaseOrder


def get_purchase_orders_queryset():
    return PurchaseOrder.objects.select_related(
        "contract",
        "supplier",
        "contract__award",
        "contract__award__tender",
    ).prefetch_related("lines")