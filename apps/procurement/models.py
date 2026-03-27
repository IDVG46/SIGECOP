from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.dncp_integration.models import AwardItem, AwardSubItem, Contract, Lot, Party


class ExpenseObject(models.Model):
	code = models.CharField(max_length=50, unique=True, verbose_name="Objeto de gasto")  # unique ya crea índice
	description = models.CharField(max_length=255, verbose_name="Descripcion")
	is_active = models.BooleanField(default=True, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["code"]

	def __str__(self):
		return f"{self.code} - {self.description}"


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
	expense_object = models.ForeignKey(
		ExpenseObject,
		on_delete=models.PROTECT,
		related_name="purchase_orders",
		null=True,
		blank=True,
		verbose_name="Objeto de gasto",
	)
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
			models.Index(fields=["contract", "expense_object"], name="po_contract_expobj_idx"),
		]

	def __str__(self):
		return self.order_number

	def clean(self):
		if not self.expense_object_id:
			raise ValidationError({"expense_object": "Debe seleccionar un objeto de gasto."})

		if self.contract_id and self.supplier_id:
			award = self.contract.award
			if award and not award.suppliers.filter(id=self.supplier_id).exists():
				raise ValidationError({"supplier": "El proveedor no pertenece a la adjudicación del contrato."})

		if self.expense_object_id and not self.expense_object.is_active:
			raise ValidationError({"expense_object": "El objeto de gasto seleccionado esta inactivo."})


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
		constraints = []
		indexes = [
			models.Index(fields=["purchase_order", "lot"], name="po_line_order_lot_idx"),
		]

	def __str__(self):
		return f"{self.purchase_order.order_number} - línea {self.pk}"

	def clean(self):
		if not self.award_item_id and not self.award_subitem_id:
			raise ValidationError("Debe seleccionar un item.")

		if self.award_subitem_id and not self.award_item_id:
			raise ValidationError({"award_item": "Debe seleccionar un item para el subitem elegido."})

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

		if self.award_item_id and self.award_subitem_id and self.award_subitem.subitem and self.award_subitem.subitem.item:
			if self.award_subitem.subitem.item_id != self.award_item.item_id:
				raise ValidationError({"award_subitem": "El subitem no corresponde al item seleccionado."})

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
			models.CheckConstraint(condition=Q(committed_amount__gte=0), name="lot_balance_commit_non_neg_ck"),
			models.CheckConstraint(condition=Q(executed_amount__gte=0), name="lot_balance_exec_non_neg_ck"),
			models.CheckConstraint(
				condition=Q(committed_amount__lte=models.F("max_amount") - models.F("executed_amount")),
				name="lot_balance_commit_le_avail_ck",
			),
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
			models.CheckConstraint(condition=Q(committed_quantity__gte=0), name="item_bal_commit_non_neg_ck"),
			models.CheckConstraint(condition=Q(executed_quantity__gte=0), name="item_bal_exec_non_neg_ck"),
			models.CheckConstraint(
				condition=Q(committed_quantity__lte=models.F("max_quantity") - models.F("executed_quantity")),
				name="item_bal_commit_le_avail_ck",
			),
		]

	@property
	def available_quantity(self):
		return self.max_quantity - self.committed_quantity - self.executed_quantity


class ContractBudget(models.Model):
	STATUS_DRAFT = "draft"
	STATUS_ACTIVE = "active"
	STATUS_CLOSED = "closed"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = (
		(STATUS_DRAFT, "Borrador"),
		(STATUS_ACTIVE, "Activo"),
		(STATUS_CLOSED, "Cerrado"),
		(STATUS_CANCELLED, "Anulado"),
	)

	contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="budgets")
	expense_object = models.ForeignKey(ExpenseObject, on_delete=models.PROTECT, related_name="budgets")
	fiscal_year = models.PositiveSmallIntegerField(db_index=True)
	financial_code = models.CharField(max_length=80, blank=True, default="", db_index=True)
	funding_source = models.CharField(max_length=80)
	cdp_number = models.CharField(max_length=80, blank=True, default="")
	assigned_amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
	committed_amount = models.DecimalField(
		max_digits=18,
		decimal_places=2,
		default=Decimal("0.00"),
		validators=[MinValueValidator(Decimal("0.00"))],
	)
	executed_amount = models.DecimalField(
		max_digits=18,
		decimal_places=2,
		default=Decimal("0.00"),
		validators=[MinValueValidator(Decimal("0.00"))],
	)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=["contract", "expense_object"], name="budget_contract_exp_idx"),
			models.Index(fields=["contract", "financial_code"], name="budget_contract_fin_code_idx"),
			models.Index(fields=["fiscal_year", "status"], name="budget_year_status_idx"),
			# Consultas por contrato+ejercicio (muy frecuentes en presupuesto)
			models.Index(fields=["contract", "fiscal_year"], name="budget_ct_fy_idx"),
		]
		constraints = [
			models.UniqueConstraint(
				fields=["contract", "expense_object", "fiscal_year", "funding_source", "cdp_number", "financial_code"],
				name="uq_bud_ct_exp_fy_src_cdp_fc",
			),
			models.CheckConstraint(condition=Q(assigned_amount__gte=0), name="budget_assigned_non_negative_ck"),
			models.CheckConstraint(condition=Q(committed_amount__gte=0), name="budget_committed_non_negative_ck"),
			models.CheckConstraint(condition=Q(executed_amount__gte=0), name="budget_executed_non_negative_ck"),
			models.CheckConstraint(
				condition=Q(committed_amount__lte=models.F("assigned_amount") - models.F("executed_amount")),
				name="budget_commit_plus_exec_le_assigned_ck",
			),
		]

	def __str__(self):
		return f"{self.contract_id} - {self.expense_object.code} ({self.fiscal_year})"

	@property
	def available_amount(self):
		return self.assigned_amount - self.committed_amount - self.executed_amount


class ContractAmendment(models.Model):
	TYPE_AMOUNT = "amount"
	TYPE_PERIOD = "period"
	TYPE_MIXED = "mixed"

	TYPE_CHOICES = (
		(TYPE_AMOUNT, "Ampliacion de monto"),
		(TYPE_PERIOD, "Ampliacion de plazo"),
		(TYPE_MIXED, "Monto y plazo"),
	)

	STATUS_DRAFT = "draft"
	STATUS_APPROVED = "approved"
	STATUS_ACTIVE = "active"
	STATUS_CLOSED = "closed"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = (
		(STATUS_DRAFT, "Borrador"),
		(STATUS_APPROVED, "Aprobado"),
		(STATUS_ACTIVE, "Activo"),
		(STATUS_CLOSED, "Cerrado"),
		(STATUS_CANCELLED, "Anulado"),
	)

	contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="amendments")
	amendment_number = models.CharField(max_length=120, db_index=True)
	amendment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
	financial_code = models.CharField(max_length=80, blank=True, default="", db_index=True)
	amount_delta = models.DecimalField(
		max_digits=18,
		decimal_places=2,
		null=True,
		blank=True,
		validators=[MinValueValidator(Decimal("0.00"))],
	)
	period_extension_days = models.PositiveIntegerField(null=True, blank=True)
	new_end_date = models.DateField(null=True, blank=True)
	effective_date = models.DateField(db_index=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
	notes = models.TextField(blank=True, default="")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=["contract", "status"], name="amendment_contract_status_idx"),
			models.Index(fields=["contract", "financial_code"], name="amend_ct_fin_code_idx"),
		]
		constraints = [
			models.UniqueConstraint(fields=["contract", "amendment_number"], name="uq_amendment_contract_number"),
		]

	def __str__(self):
		return f"{self.contract_id} - {self.amendment_number}"

	def clean(self):
		super().clean()
		has_amount = self.amount_delta is not None and self.amount_delta > Decimal("0.00")
		has_period = bool(self.period_extension_days) or bool(self.new_end_date)

		if self.amendment_type == self.TYPE_AMOUNT and not has_amount:
			raise ValidationError({"amount_delta": "Una ampliacion de monto requiere un monto mayor a cero."})

		if self.amendment_type == self.TYPE_PERIOD and not has_period:
			raise ValidationError(
				{"period_extension_days": "Una ampliacion de plazo requiere dias o nueva fecha fin."}
			)

		if self.amendment_type == self.TYPE_MIXED:
			if not has_amount:
				raise ValidationError({"amount_delta": "Una adenda mixta requiere monto mayor a cero."})
			if not has_period:
				raise ValidationError(
					{"period_extension_days": "Una adenda mixta requiere dias o nueva fecha fin."}
				)

		if self.amendment_type in {self.TYPE_AMOUNT, self.TYPE_MIXED} and not self.financial_code:
			raise ValidationError({"financial_code": "La adenda con impacto financiero requiere codigo financiero."})


class FulfillmentMemo(models.Model):
	MODE_PARTIAL = "partial"
	MODE_TOTAL = "total"

	MODE_CHOICES = (
		(MODE_PARTIAL, "Parcial detallado"),
		(MODE_TOTAL, "Total"),
	)

	STATUS_DRAFT = "draft"
	STATUS_ISSUED = "issued"
	STATUS_APPROVED = "approved"
	STATUS_REJECTED = "rejected"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = (
		(STATUS_DRAFT, "Borrador"),
		(STATUS_ISSUED, "Emitido"),
		(STATUS_APPROVED, "Aprobado"),
		(STATUS_REJECTED, "Rechazado"),
		(STATUS_CANCELLED, "Anulado"),
	)

	contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="fulfillment_memos", null=True, blank=True)
	purchase_order = models.ForeignKey(
		PurchaseOrder,
		on_delete=models.PROTECT,
		related_name="fulfillment_memos",
		null=True,
		blank=True,
	)
	fulfillment_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_PARTIAL, db_index=True)
	beneficiary_sector = models.CharField(max_length=255)
	memo_number = models.CharField(max_length=100, db_index=True)
	memo_date = models.DateField(db_index=True)
	received_by = models.CharField(max_length=255, blank=True, default="")
	sender_position = models.CharField(max_length=255, blank=True, default="")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
	notes = models.TextField(blank=True, default="")
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="created_fulfillment_memos",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=["purchase_order", "status"], name="memo_order_status_idx"),
			models.Index(fields=["beneficiary_sector", "memo_date"], name="memo_sector_date_idx"),
			models.Index(fields=["contract", "status"], name="memo_ct_status_idx"),
		]
		constraints = [
			models.UniqueConstraint(fields=["beneficiary_sector", "memo_number"], name="uq_memo_sector_number"),
		]

	def __str__(self):
		if self.purchase_order_id:
			return f"Memo {self.memo_number} - {self.purchase_order.order_number}"
		if self.contract_id:
			return f"Memo {self.memo_number} - Contrato {self.contract_id}"
		return f"Memo {self.memo_number}"

	def clean(self):
		super().clean()
		if not self.contract_id and not self.purchase_order_id:
			raise ValidationError("El memorandum debe estar asociado a un contrato o a una orden de compra.")


class FulfillmentMemoLine(models.Model):
	MODE_PARTIAL = "partial"
	MODE_TOTAL = "total"

	MODE_CHOICES = (
		(MODE_PARTIAL, "Parcial"),
		(MODE_TOTAL, "Total"),
	)

	memo = models.ForeignKey(FulfillmentMemo, on_delete=models.CASCADE, related_name="lines")
	purchase_order = models.ForeignKey(
		PurchaseOrder,
		on_delete=models.PROTECT,
		related_name="fulfillment_lines",
		verbose_name="Orden de compra",
	)
	purchase_order_line = models.ForeignKey(
		"PurchaseOrderLine",
		on_delete=models.PROTECT,
		related_name="fulfillment_lines",
		null=True,
		blank=True,
		verbose_name="Linea de orden de compra",
	)
	fulfillment_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_PARTIAL, db_index=True)
	fulfilled_quantity = models.DecimalField(
		max_digits=18,
		decimal_places=3,
		null=True,
		blank=True,
	)
	observations = models.TextField(blank=True, default="")

	class Meta:
		indexes = [
			models.Index(fields=["memo", "purchase_order"], name="memo_line_memo_order_idx"),
			models.Index(fields=["memo", "purchase_order_line"], name="memo_line_memo_oline_idx"),
		]
		constraints = [
			models.UniqueConstraint(
				fields=["memo", "purchase_order"],
				condition=Q(purchase_order_line__isnull=True),
				name="uq_memo_purchase_order_total",
			),
			models.UniqueConstraint(
				fields=["memo", "purchase_order", "purchase_order_line"],
				condition=Q(purchase_order_line__isnull=False),
				name="uq_memo_purchase_order_line",
			),
		]

	def clean(self):
		super().clean()
		if self.memo_id and self.purchase_order_id:
			memo_contract_id = self.memo.contract_id
			if memo_contract_id is None and self.memo.purchase_order_id:
				memo_contract_id = self.memo.purchase_order.contract_id
			order_contract_id = self.purchase_order.contract_id
			if memo_contract_id and memo_contract_id != order_contract_id:
				raise ValidationError({"purchase_order": "La orden debe pertenecer al mismo contrato del memorandum."})

		if self.fulfillment_mode == self.MODE_TOTAL:
			if self.fulfilled_quantity is not None and self.fulfilled_quantity <= Decimal("0.000"):
				raise ValidationError({"fulfilled_quantity": "La cantidad en modo total debe ser mayor a cero."})

		if self.purchase_order_line_id and self.purchase_order_line.purchase_order_id != self.purchase_order_id:
			raise ValidationError({"purchase_order_line": "La linea seleccionada no pertenece a la orden de compra."})

	def __str__(self):
		return f"{self.memo.memo_number} - orden {self.purchase_order_id}"


class FulfillmentMemoPartialLine(models.Model):
	memo = models.ForeignKey(FulfillmentMemo, on_delete=models.CASCADE, related_name="partial_lines")
	purchase_order = models.ForeignKey(
		PurchaseOrder,
		on_delete=models.PROTECT,
		related_name="fulfillment_partial_lines",
		verbose_name="Orden de compra",
	)
	purchase_order_line = models.ForeignKey(
		"PurchaseOrderLine",
		on_delete=models.PROTECT,
		related_name="fulfillment_partial_lines",
		verbose_name="Linea de orden de compra",
	)
	fulfilled_quantity = models.DecimalField(max_digits=18, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
	observations = models.TextField(blank=True, default="")

	class Meta:
		indexes = [
			models.Index(fields=["memo", "purchase_order"], name="memo_partial_memo_ord_idx"),
			models.Index(fields=["memo", "purchase_order_line"], name="memo_partial_memo_oline_idx"),
		]
		constraints = [
			models.UniqueConstraint(fields=["memo", "purchase_order_line"], name="uq_memo_partial_oline"),
		]

	def clean(self):
		super().clean()
		if self.purchase_order_line_id and self.purchase_order_id:
			if self.purchase_order_line.purchase_order_id != self.purchase_order_id:
				raise ValidationError({"purchase_order_line": "La linea seleccionada no pertenece a la orden de compra."})

		if self.memo_id and self.purchase_order_id:
			memo_contract_id = self.memo.contract_id
			if memo_contract_id and memo_contract_id != self.purchase_order.contract_id:
				raise ValidationError({"purchase_order": "La orden debe pertenecer al mismo contrato del memorandum."})


class Payment(models.Model):
	STATUS_DRAFT = "draft"
	STATUS_POSTED = "posted"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = (
		(STATUS_DRAFT, "Borrador"),
		(STATUS_POSTED, "Imputado"),
		(STATUS_CANCELLED, "Anulado"),
	)

	payment_number = models.CharField(max_length=100, unique=True)  # unique ya crea índice
	payment_date = models.DateField(db_index=True)
	contract = models.ForeignKey(
		Contract,
		on_delete=models.PROTECT,
		related_name="payments",
		null=True,
		blank=True,
		verbose_name="Contrato",
		help_text="Contrato asociado a este pago. Todas las órdenes deben pertenecer a este contrato.",
	)
	amount_total = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
	document_number = models.CharField(max_length=255, blank=True, default="")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="created_procurement_payments",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=["payment_date", "status"], name="payment_date_status_idx"),
			models.Index(fields=["contract", "status"], name="payment_ct_status_idx"),
		]

	def __str__(self):
		return self.payment_number


class PaymentAllocation(models.Model):
	payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
	purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="payment_allocations")
	contract_budget = models.ForeignKey(
		ContractBudget,
		on_delete=models.PROTECT,
		related_name="payment_allocations",
	)
	amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])

	class Meta:
		indexes = [
			models.Index(fields=["payment", "purchase_order"], name="pay_alloc_pay_ord_idx"),
			models.Index(fields=["contract_budget", "payment"], name="pay_alloc_budget_pay_idx"),
		]
		constraints = [
			models.UniqueConstraint(
				fields=["payment", "purchase_order", "contract_budget"],
				name="uq_payment_alloc_order_budget",
			),
		]

	def __str__(self):
		return f"{self.payment.payment_number} -> {self.purchase_order.order_number} / Presupuesto {self.contract_budget_id}"

	def clean(self):
		super().clean()
		if self.purchase_order_id and self.contract_budget_id:
			if self.purchase_order.contract_id != self.contract_budget.contract_id:
				raise ValidationError(
					"La orden de compra y el presupuesto deben pertenecer al mismo contrato."
				)


class BudgetLedgerEntry(models.Model):
	ENTRY_COMMIT = "commit"
	ENTRY_RELEASE_COMMIT = "release_commit"
	ENTRY_EXECUTE = "execute"
	ENTRY_REVERSE_EXECUTE = "reverse_execute"

	ENTRY_TYPE_CHOICES = (
		(ENTRY_COMMIT, "Compromiso"),
		(ENTRY_RELEASE_COMMIT, "Liberacion de compromiso"),
		(ENTRY_EXECUTE, "Ejecucion"),
		(ENTRY_REVERSE_EXECUTE, "Reversion de ejecucion"),
	)

	SOURCE_PURCHASE_ORDER = "purchase_order"
	SOURCE_PAYMENT = "payment"
	SOURCE_MANUAL_ADJUSTMENT = "manual_adjustment"

	SOURCE_TYPE_CHOICES = (
		(SOURCE_PURCHASE_ORDER, "Orden de compra"),
		(SOURCE_PAYMENT, "Pago"),
		(SOURCE_MANUAL_ADJUSTMENT, "Ajuste manual"),
	)

	contract_budget = models.ForeignKey(ContractBudget, on_delete=models.PROTECT, related_name="ledger_entries")
	entry_type = models.CharField(max_length=30, choices=ENTRY_TYPE_CHOICES)
	amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
	source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES)
	source_id = models.CharField(max_length=100)
	notes = models.TextField(blank=True, default="")
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="created_budget_ledger_entries",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		indexes = [
			models.Index(fields=["contract_budget", "created_at"], name="ledger_budget_created_idx"),
			models.Index(fields=["source_type", "source_id"], name="ledger_source_idx"),
		]

	def __str__(self):
		return f"{self.contract_budget_id} - {self.entry_type} - {self.amount}"
