from apps.procurement.models import ContractBudget


def get_contract_budgets_queryset():
	"""
	Optimized queryset for listing contract budgets.
	Includes contract and expense_object relations, ordered by fiscal year and contract.
	"""
	return ContractBudget.objects.select_related(
		"contract",
		"expense_object",
		"contract__value_currency",
	).order_by("-fiscal_year", "contract_id")
