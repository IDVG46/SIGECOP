from apps.procurement.models import FulfillmentMemo


def get_fulfillment_memos_queryset():
	"""
	Optimized queryset for listing fulfillment memos.
	Includes only valid header relations and prefetches line/partial rows,
	ordered by memo date.
	"""
	return FulfillmentMemo.objects.select_related(
		"contract",
		"created_by",
	).prefetch_related(
		"lines__purchase_order_line__purchase_order",
		"partial_lines__purchase_order_line__purchase_order",
	).order_by("-memo_date", "-id")
