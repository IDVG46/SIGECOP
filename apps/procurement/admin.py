from django.contrib import admin

from apps.procurement.models import (
	BudgetLedgerEntry,
	ContractAmendment,
	ContractBudget,
	ContractLotBalance,
	ExpenseObject,
	FulfillmentMemo,
	FulfillmentMemoLine,
	ItemQuantityBalance,
	Payment,
	PaymentAllocation,
	PurchaseOrder,
	PurchaseOrderLine,
)


class PurchaseOrderLineInline(admin.TabularInline):
	model = PurchaseOrderLine
	extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
	list_display = ("order_number", "contract", "supplier", "expense_object", "issue_date", "status", "total_amount")
	list_filter = ("status", "issue_date", "expense_object")
	search_fields = ("order_number", "contract__id", "supplier__name", "expense_object__code", "expense_object__description")
	inlines = [PurchaseOrderLineInline]


@admin.register(ExpenseObject)
class ExpenseObjectAdmin(admin.ModelAdmin):
	list_display = ("code", "description", "is_active")
	list_filter = ("is_active",)
	search_fields = ("code", "description")


@admin.register(ContractLotBalance)
class ContractLotBalanceAdmin(admin.ModelAdmin):
	list_display = ("contract", "lot", "min_amount", "max_amount", "committed_amount", "executed_amount")
	search_fields = ("contract__id", "lot__id")


@admin.register(ItemQuantityBalance)
class ItemQuantityBalanceAdmin(admin.ModelAdmin):
	list_display = ("contract", "award_item", "award_subitem", "max_quantity", "committed_quantity", "executed_quantity")
	search_fields = ("contract__id",)


class FulfillmentMemoLineInline(admin.TabularInline):
	model = FulfillmentMemoLine
	extra = 0


@admin.register(ContractBudget)
class ContractBudgetAdmin(admin.ModelAdmin):
	list_display = (
		"contract",
		"expense_object",
		"fiscal_year",
		"financial_code",
		"funding_source",
		"assigned_amount",
		"committed_amount",
		"executed_amount",
		"status",
	)
	list_filter = ("status", "fiscal_year", "expense_object")
	search_fields = ("contract__id", "expense_object__code", "financial_code", "funding_source", "cdp_number")


@admin.register(ContractAmendment)
class ContractAmendmentAdmin(admin.ModelAdmin):
	list_display = (
		"contract",
		"amendment_number",
		"amendment_type",
		"financial_code",
		"amount_delta",
		"effective_date",
		"status",
	)
	list_filter = ("amendment_type", "status", "effective_date")
	search_fields = ("contract__id", "amendment_number", "financial_code")


@admin.register(FulfillmentMemo)
class FulfillmentMemoAdmin(admin.ModelAdmin):
	list_display = ("memo_number", "contract", "beneficiary_sector", "memo_date", "status")
	list_filter = ("status", "memo_date", "beneficiary_sector")
	search_fields = ("memo_number", "contract__id", "beneficiary_sector")
	inlines = [FulfillmentMemoLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ("payment_number", "payment_date", "amount_total", "status")
	list_filter = ("status", "payment_date")
	search_fields = ("payment_number", "document_number")


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
	list_display = ("payment", "purchase_order", "contract_budget", "amount")
	search_fields = ("payment__payment_number", "purchase_order__order_number", "contract_budget__contract__id")


@admin.register(BudgetLedgerEntry)
class BudgetLedgerEntryAdmin(admin.ModelAdmin):
	list_display = ("contract_budget", "entry_type", "amount", "source_type", "source_id", "created_at")
	list_filter = ("entry_type", "source_type", "created_at")
	search_fields = ("contract_budget__contract__id", "source_id")
