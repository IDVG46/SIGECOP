from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract, Lot, Party


class PurchaseOrder(models.Model):
	STATUS_DRAFT = "draft"
	STATUS_APPROVED = "approved"
	STATUS_PARTIAL = "partial"
	STATUS_CLOSED = "closed"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = (
		(STATUS_DRAFT, "Borrador"),
		(STATUS_APPROVED, "Aprobada"),
		(STATUS_PARTIAL, "Parcial"),
		(STATUS_CLOSED, "Cerrada"),
		(STATUS_CANCELLED, "Anulada"),
	)

	order_number = models.CharField(max_length=100, unique=True, verbose_name="N° de orden")
	contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="purchase_orders")
	supplier = models.ForeignKey(
		Party,
		on_delete=models.PROTECT,
		related_name="purchase_orders",
		limit_choices_to={"role": Party.ROLE_SUPPLIER},
	)
	issue_date = models.DateField(db_index=True, verbose_name="Fecha de emisión")
	delivery_term = models.CharField(max_length=255, blank=True, default="", verbose_name="Plazo de entrega")
	delivery_place = models.CharField(max_length=255, blank=True, default="", verbose_name="Lugar de entrega")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
	total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
	notes = models.TextField(blank=True, default="")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-issue_date", "-created_at"]
		indexes = [
			models.Index(fields=["contract", "status"], name="po_contract_status_idx"),
			models.Index(fields=["supplier", "issue_date"], name="po_supplier_date_idx"),
		]

	def __str__(self):
		return self.order_number

	def clean(self):
		if self.contract_id and self.supplier_id:
			award = self.contract.award
			if award and not award.suppliers.filter(id=self.supplier_id).exists():
				raise ValidationError({"supplier": "El proveedor no pertenece a la adjudicación del contrato."})


class PurchaseOrderLine(models.Model):
	purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
	lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="purchase_order_lines")
	award_item = models.ForeignKey(
		AwardItem,
		on_delete=models.PROTECT,
		related_name="purchase_order_lines",
		null=True,
		blank=True,
	)
	award_subitem = models.ForeignKey(
		AwardSubItem,
		on_delete=models.PROTECT,
		related_name="purchase_order_lines",
		null=True,
		blank=True,
	)
	quantity = models.DecimalField(
		max_digits=18,
		decimal_places=3,
		validators=[MinValueValidator(Decimal("0.001"))],
	)
	unit_price = models.DecimalField(
		max_digits=18,
		decimal_places=2,
		validators=[MinValueValidator(Decimal("0.01"))],
	)
	line_total = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

	class Meta:
		constraints = [
			models.CheckConstraint(
				condition=(Q(award_item__isnull=False, award_subitem__isnull=True) | Q(award_item__isnull=True, award_subitem__isnull=False)),
				name="po_line_item_xor_subitem_ck",
			),
		]
		indexes = [
			models.Index(fields=["purchase_order", "lot"], name="po_line_order_lot_idx"),
		]

	def __str__(self):
		return f"{self.purchase_order.order_number} - línea {self.pk}"

	def clean(self):
		if bool(self.award_item_id) == bool(self.award_subitem_id):
			raise ValidationError("Debe seleccionar item o subitem, no ambos.")

		contract_award_id = None
		if self.purchase_order_id:
			contract_award_id = self.purchase_order.contract.award_id
		else:
			# Durante CreateView el formset puede validar con una orden aun no persistida.
			purchase_order = getattr(self, "purchase_order", None)
			contract_obj = getattr(purchase_order, "contract", None) if purchase_order is not None else None
			contract_award_id = getattr(contract_obj, "award_id", None)

		if self.award_item_id and contract_award_id and self.award_item.award_id != contract_award_id:
			raise ValidationError({"award_item": "El item no pertenece a la adjudicación del contrato."})

		if self.award_subitem_id and contract_award_id and self.award_subitem.award_id != contract_award_id:
			raise ValidationError({"award_subitem": "El subitem no pertenece a la adjudicación del contrato."})

		if self.award_item_id and self.award_item.item and self.award_item.item.lot_id != self.lot_id:
			raise ValidationError({"lot": "El lote no coincide con el item seleccionado."})

		if self.award_subitem_id and self.award_subitem.subitem and self.award_subitem.subitem.item:
			item_lot_id = self.award_subitem.subitem.item.lot_id
			if item_lot_id != self.lot_id:
				raise ValidationError({"lot": "El lote no coincide con el subitem seleccionado."})


class ContractLotBalance(models.Model):
	contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="lot_balances")
	lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="contract_balances")
	min_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
	max_amount = models.DecimalField(max_digits=18, decimal_places=2)
	committed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
	executed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["contract", "lot"], name="uq_contract_lot_balance"),
			models.CheckConstraint(condition=Q(max_amount__gte=0), name="lot_balance_max_non_negative_ck"),
			models.CheckConstraint(condition=Q(min_amount__gte=0), name="lot_balance_min_non_negative_ck"),
		]

	@property
	def available_amount(self):
		return self.max_amount - self.committed_amount - self.executed_amount


class ItemQuantityBalance(models.Model):
	contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="item_balances")
	award_item = models.ForeignKey(
		AwardItem,
		on_delete=models.CASCADE,
		related_name="quantity_balances",
		null=True,
		blank=True,
	)
	award_subitem = models.ForeignKey(
		AwardSubItem,
		on_delete=models.CASCADE,
		related_name="quantity_balances",
		null=True,
		blank=True,
	)
	max_quantity = models.DecimalField(max_digits=18, decimal_places=3)
	committed_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
	executed_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))

	class Meta:
		constraints = [
			models.CheckConstraint(
				condition=(Q(award_item__isnull=False, award_subitem__isnull=True) | Q(award_item__isnull=True, award_subitem__isnull=False)),
				name="item_balance_item_xor_subitem_ck",
			),
			models.CheckConstraint(condition=Q(max_quantity__gt=0), name="item_balance_max_qty_positive_ck"),
		]

	@property
	def available_quantity(self):
		return self.max_quantity - self.committed_quantity - self.executed_quantity
