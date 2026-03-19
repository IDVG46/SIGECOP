from django.db.models import Count

from apps.procurement.models import Payment


def get_payments_queryset():
	"""
	Optimized queryset for listing payments with allocation metrics.
	Includes contract and allocation relations, with counts for allocations and budgets.
	"""
	return Payment.objects.select_related("contract").prefetch_related(
		"allocations__contract_budget__contract",
		"allocations__contract_budget__expense_object",
	).annotate(
		allocation_count=Count("allocations", distinct=True),
		budget_count=Count("allocations__contract_budget", distinct=True),
	).order_by("-payment_date", "-created_at")
