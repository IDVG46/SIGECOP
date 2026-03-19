from apps.procurement.models import FulfillmentMemo


def get_fulfillment_memos_queryset():
	"""
	Optimized queryset for listing fulfillment memos.
	Includes contract and purchase_order relations, ordered by memo date.
	"""
	return FulfillmentMemo.objects.select_related(
		"contract",
		"purchase_order",
		"purchase_order__contract",
	).prefetch_related(
		"lines__purchase_order_line__purchase_order",
		"partial_lines__purchase_order_line__purchase_order",
	).order_by("-memo_date", "-id")
