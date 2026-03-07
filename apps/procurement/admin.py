from django.contrib import admin

from apps.procurement.models import (
	ContractLotBalance,
	ItemQuantityBalance,
	PurchaseOrder,
	PurchaseOrderLine,
)


class PurchaseOrderLineInline(admin.TabularInline):
	model = PurchaseOrderLine
	extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
	list_display = ("order_number", "contract", "supplier", "issue_date", "status", "total_amount")
	list_filter = ("status", "issue_date")
	search_fields = ("order_number", "contract__id", "supplier__name")
	inlines = [PurchaseOrderLineInline]


@admin.register(ContractLotBalance)
class ContractLotBalanceAdmin(admin.ModelAdmin):
	list_display = ("contract", "lot", "min_amount", "max_amount", "committed_amount", "executed_amount")
	search_fields = ("contract__id", "lot__id")


@admin.register(ItemQuantityBalance)
class ItemQuantityBalanceAdmin(admin.ModelAdmin):
	list_display = ("contract", "award_item", "award_subitem", "max_quantity", "committed_quantity", "executed_quantity")
	search_fields = ("contract__id",)
