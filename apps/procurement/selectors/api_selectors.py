"""
API Selectors - Data aggregation for JSON API endpoints.

These selectors handle the complex logic of fetching and structuring
data for API responses (select dropdowns, data tables, etc.).
Each selector returns a dictionary/list ready to be JSON-serialized.
"""

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract
from apps.procurement.models import ContractLotBalance, ItemQuantityBalance
from apps.procurement.services.rules import should_enforce_quantity_limit_for_lot_and_quantity


def get_contract_line_options_data(contract):
	"""
	Fetch and structure contract line options (items and subitems) for form dropdowns.
	
	Returns:
		dict with keys: contract_id, contract, lots, items, subitems
	"""
	if not contract.award:
		return {
			"contract_id": contract.id,
			"contract": _format_contract_data(contract),
			"lots": [],
			"items": [],
			"subitems": [],
		}

	# Fetch award items and subitems with optimizations
	award_items = list(
		AwardItem.objects.filter(award=contract.award)
		.select_related("item", "item__lot")
		.order_by("item__lot_id", "item_id")
	)
	award_subitems = list(
		AwardSubItem.objects.filter(award=contract.award)
		.select_related("subitem", "subitem__item", "subitem__item__lot")
		.order_by("subitem__item__lot_id", "subitem_id")
	)

	# Fetch balance data in bulk
	lot_balances = {
		balance.lot_id: balance
		for balance in ContractLotBalance.objects.filter(contract=contract).select_related("lot")
	}
	qty_balances_by_item = {
		balance.award_item_id: balance
		for balance in ItemQuantityBalance.objects.filter(contract=contract, award_item__isnull=False)
	}
	qty_balances_by_subitem = {
		balance.award_subitem_id: balance
		for balance in ItemQuantityBalance.objects.filter(contract=contract, award_subitem__isnull=False)
	}

	# Build lots data
	lots_data = {}
	for award_item in award_items:
		lot = award_item.item.lot if award_item.item else None
		if not lot or lot.id in lots_data:
			continue
		lot_balance = lot_balances.get(lot.id)
		lots_data[lot.id] = _format_lot_data(lot, lot_balance)

	for award_subitem in award_subitems:
		lot = award_subitem.subitem.item.lot if award_subitem.subitem and award_subitem.subitem.item else None
		if not lot or lot.id in lots_data:
			continue
		lot_balance = lot_balances.get(lot.id)
		lots_data[lot.id] = _format_lot_data(lot, lot_balance)

	for lot_balance in lot_balances.values():
		if lot_balance.lot.id not in lots_data:
			lots_data[lot_balance.lot.id] = _format_lot_data(lot_balance.lot, lot_balance)

	# Build items data
	items_data = []
	for award_item in award_items:
		if not award_item.item or not award_item.item.lot:
			continue
		items_data.append(_format_award_item_data(award_item, qty_balances_by_item))

	# Build subitems data
	subitems_data = []
	for award_subitem in award_subitems:
		if not award_subitem.subitem or not award_subitem.subitem.item:
			continue
		subitems_data.append(_format_award_subitem_data(award_subitem, qty_balances_by_subitem))

	return {
		"contract_id": contract.id,
		"contract": _format_contract_data(contract),
		"lots": list(lots_data.values()),
		"items": items_data,
		"subitems": subitems_data,
	}


# Helper formatters
def _format_contract_data(contract):
	"""Format contract info for API response."""
	return {
		"id": contract.id,
		"status": contract.status_details or "-",
		"amount": str(contract.value_amount or 0),
		"currency": (contract.value_currency.symbol or contract.value_currency.code) if contract.value_currency else "",
		"tender": contract.award.tender.title if contract.award and contract.award.tender else "-",
		"tender_id": contract.award.tender.tenderID if contract.award and contract.award.tender else "-",
		"award_id": contract.award.id if contract.award else "-",
	}


def _format_lot_data(lot, lot_balance=None):
	"""Format lot info for API response."""
	if lot_balance:
		max_amount = str(lot_balance.max_amount)
		available_amount = str(lot_balance.available_amount)
	else:
		max_amount = str(lot.value_amount or 0)
		available_amount = str(lot.value_amount or 0)

	return {
		"id": lot.id,
		"text": lot.title,
		"max_amount": max_amount,
		"available_amount": available_amount,
	}


def _format_award_item_data(award_item, qty_balances_by_item):
	"""Format award item for API response."""
	lot = award_item.item.lot
	enforce_quantity_limit = should_enforce_quantity_limit_for_lot_and_quantity(lot, award_item.quantity)
	qty_balance = qty_balances_by_item.get(award_item.id)
	order_value = award_item.orden_licitado if award_item.orden_licitado is not None else "-"

	if enforce_quantity_limit:
		max_qty = qty_balance.max_quantity if qty_balance else award_item.quantity
		available_qty = qty_balance.available_quantity if qty_balance else award_item.quantity
	else:
		max_qty = None
		available_qty = None

	return {
		"id": award_item.id,
		"lot_id": award_item.item.lot_id,
		"item_definition_id": award_item.item.id,
		"text": f"{order_value} - {award_item.item.description}",
		"unit_price": str(award_item.unit_price_amount or 0),
		"enforce_quantity_limit": enforce_quantity_limit,
		"quantity_control_mode": "quantity" if enforce_quantity_limit else "amount",
		"max_quantity": str(max_qty) if max_qty is not None else None,
		"available_quantity": str(available_qty) if available_qty is not None else None,
	}


def _format_award_subitem_data(award_subitem, qty_balances_by_subitem):
	"""Format award subitem for API response."""
	lot = award_subitem.subitem.item.lot
	enforce_quantity_limit = should_enforce_quantity_limit_for_lot_and_quantity(lot, award_subitem.quantity)
	qty_balance = qty_balances_by_subitem.get(award_subitem.id)
	order_value = award_subitem.orden_licitado if award_subitem.orden_licitado is not None else "-"

	if enforce_quantity_limit:
		max_qty = qty_balance.max_quantity if qty_balance else award_subitem.quantity
		available_qty = qty_balance.available_quantity if qty_balance else award_subitem.quantity
	else:
		max_qty = None
		available_qty = None

	return {
		"id": award_subitem.id,
		"lot_id": award_subitem.subitem.item.lot_id,
		"item_definition_id": award_subitem.subitem.item_id,
		"text": f"{order_value} - {award_subitem.subitem.description}",
		"unit_price": str(award_subitem.unit_price_amount or 0),
		"enforce_quantity_limit": enforce_quantity_limit,
		"quantity_control_mode": "quantity" if enforce_quantity_limit else "amount",
		"max_quantity": str(max_qty) if max_qty is not None else None,
		"available_quantity": str(available_qty) if available_qty is not None else None,
	}
