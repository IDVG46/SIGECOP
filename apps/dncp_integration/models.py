from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models



class ImportRun(models.Model):
	STATUS_PENDING = "pending"
	STATUS_RUNNING = "running"
	STATUS_SUCCESS = "success"
	STATUS_PARTIAL = "partial"
	STATUS_FAILED = "failed"

	STATUS_CHOICES = (
		(STATUS_PENDING, "Pendiente"),
		(STATUS_RUNNING, "En ejecución"),
		(STATUS_SUCCESS, "Exitoso"),
		(STATUS_PARTIAL, "Parcial"),
		(STATUS_FAILED, "Fallido"),
	)

	SOURCE_COMMAND = "management_command"
	SOURCE_HTTP = "http"

	SOURCE_CHOICES = (
		(SOURCE_COMMAND, "Linea de comandos"),
		(SOURCE_HTTP, "HTTP"),
	)

	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_COMMAND)
	started_at = models.DateTimeField(auto_now_add=True)
	finished_at = models.DateTimeField(null=True, blank=True)
	from_date = models.DateTimeField(null=True, blank=True)
	to_date = models.DateTimeField(null=True, blank=True)
	total_records = models.PositiveIntegerField(default=0)
	imported_records = models.PositiveIntegerField(default=0)
	skipped_records = models.PositiveIntegerField(default=0)
	failed_records = models.PositiveIntegerField(default=0)
	last_error = models.TextField(null=True, blank=True)

	class Meta:
		ordering = ["-started_at"]
		indexes = [
			models.Index(fields=["status"], name="importrun_status_idx"),
		]

	def __str__(self):
		return f"ImportRun #{self.pk} ({self.status})"


class RawRelease(models.Model):
	ocid = models.CharField(max_length=255, db_index=True)
	release_id = models.CharField(max_length=255)
	release_date = models.DateTimeField(db_index=True)
	payload = models.JSONField()
	payload_hash = models.CharField(max_length=64, db_index=True, unique=True)
	import_run = models.ForeignKey(ImportRun, on_delete=models.SET_NULL, null=True, blank=True)
	fetched_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["ocid", "release_id"], name="uq_rawrelease_ocid_id"),
		]
		indexes = [
			models.Index(fields=["ocid", "release_date"], name="rawrelease_ocid_date_idx"),
			models.Index(fields=["import_run"], name="rawrelease_import_run_idx"),
		]

	def __str__(self):
		return f"{self.ocid} ({self.release_id})"


class Currency(models.Model):
	code = models.CharField(max_length=10, primary_key=True)
	name = models.CharField(max_length=50)
	symbol = models.CharField(max_length=10, blank=True, null=True)

	def __str__(self):
		return self.name


class AuditedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	is_user_modified = models.BooleanField(default=False)
	modified_at = models.DateTimeField(null=True, blank=True)
	modified_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="dncp_modified_%(class)s",
	)

	class Meta:
		abstract = True


class CompiledRelease(models.Model):
	ocid = models.CharField(max_length=255, unique=True)
	release_id = models.CharField(max_length=255)
	date = models.DateTimeField()
	raw_release = models.ForeignKey(RawRelease, on_delete=models.SET_NULL, null=True, blank=True)
	last_synced_at = models.DateTimeField(null=True, blank=True)
	import_run = models.ForeignKey(ImportRun, on_delete=models.SET_NULL, null=True, blank=True)

	def __str__(self):
		return self.ocid


class Party(AuditedModel):
	ROLE_PROCURING_ENTITY = "procuring_entity"
	ROLE_SUPPLIER = "supplier"
	
	ROLE_CHOICES = (
		(ROLE_PROCURING_ENTITY, "Entidad Convocante"),
		(ROLE_SUPPLIER, "Proveedor"),
	)
	
	party_id = models.CharField(max_length=255, unique=True)
	name = models.CharField(max_length=255)
	role = models.CharField(max_length=20, choices=ROLE_CHOICES)
	identifier_scheme = models.CharField(max_length=50, null=True, blank=True)
	identifier_id = models.CharField(max_length=255, null=True, blank=True)
	legal_name = models.CharField(max_length=255, null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["party_id", "role"], name="uq_party_id_role"),
		]

	def __str__(self):
		return f"{self.party_id} - {self.name}"


class Tender(AuditedModel):
	id = models.CharField(max_length=255, primary_key=True)
	compiled_release = models.ForeignKey(CompiledRelease, on_delete=models.CASCADE, related_name="tenders")
	tenderID = models.PositiveIntegerField(
		unique=True,
		db_index=True,
		validators=[MinValueValidator(100000), MaxValueValidator(999999)],
	)
	title = models.CharField(max_length=255)
	award_criteria_details = models.CharField(max_length=50)
	status_details = models.CharField(max_length=50)
	main_procurement_category_details = models.CharField(max_length=255)
	value_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	value_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
	date_published = models.DateTimeField(null=True, blank=True)
	procurement_method_details = models.CharField(max_length=255)
	procuring_entity = models.ForeignKey(Party, on_delete=models.PROTECT, null=True, blank=True)

	def __str__(self):
		return self.title


class Lot(AuditedModel):
	id = models.CharField(max_length=255, primary_key=True)
	tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="lots")
	title = models.CharField(max_length=255)
	status_details = models.CharField(max_length=50, null=True, blank=True)
	open_contract_type = models.CharField(max_length=50, null=True, blank=True)
	value_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	value_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
	min_value_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	min_value_currency = models.ForeignKey(
		Currency, on_delete=models.PROTECT, null=True, blank=True, related_name="min_value_lots"
	)

	def __str__(self):
		return self.title


class Classification(AuditedModel):
	id = models.CharField(max_length=50, primary_key=True)
	description = models.CharField(max_length=255, null=True, blank=True)

	def __str__(self):
		return f"{self.id}"


class ItemDefinition(AuditedModel):
	id = models.CharField(max_length=255, primary_key=True)
	description = models.TextField()
	classification = models.ForeignKey(Classification, on_delete=models.PROTECT, null=True, blank=True)
	lot = models.ForeignKey(Lot, on_delete=models.PROTECT, null=True, blank=True, related_name="items")
	unit_name = models.CharField(max_length=50, null=True, blank=True)
	attributes = models.JSONField(null=True, blank=True)

	def __str__(self):
		return self.description


class SubItemDefinition(AuditedModel):
	id = models.CharField(max_length=255, primary_key=True)
	item = models.ForeignKey(ItemDefinition, on_delete=models.CASCADE, related_name="subitems")
	description = models.TextField()
	unit_name = models.CharField(max_length=50, null=True, blank=True)
	attributes = models.JSONField(null=True, blank=True)

	def __str__(self):
		return self.description


class TenderItem(AuditedModel):
	tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="tender_items")
	item = models.ForeignKey(ItemDefinition, on_delete=models.PROTECT, related_name="tender_items")
	quantity = models.IntegerField(null=True, blank=True)
	min_quantity = models.IntegerField(null=True, blank=True)
	unit_price_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	unit_price_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
	orden = models.IntegerField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["tender", "item"],
				name="uq_tender_item",
			),
		]
		indexes = [
			models.Index(fields=["tender"], name="tender_item_tender_idx"),
			models.Index(fields=["item"], name="tender_item_item_idx"),
		]

	def __str__(self):
		return f"{self.tender_id} - {self.item_id}"


class Award(AuditedModel):
	id = models.CharField(max_length=255, primary_key=True)
	tender = models.ForeignKey(Tender, related_name="awards", on_delete=models.CASCADE)
	status_details = models.CharField(max_length=50)
	date = models.DateTimeField()
	value_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	value_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
	suppliers = models.ManyToManyField(Party, related_name="awards")

	def __str__(self):
		return self.id


class AwardItem(AuditedModel):
	award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name="award_items")
	item = models.ForeignKey(ItemDefinition, on_delete=models.PROTECT, related_name="award_items")
	quantity = models.IntegerField(null=True, blank=True)
	unit_price_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	unit_price_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["award", "item"],
				name="uq_award_item",
			),
		]
		indexes = [
			models.Index(fields=["award"], name="award_item_award_idx"),
			models.Index(fields=["item"], name="award_item_item_idx"),
		]

	def __str__(self):
		return f"{self.award_id} - {self.item_id}"


class Contract(AuditedModel):
	id = models.CharField(max_length=255, primary_key=True)
	award = models.ForeignKey(Award, related_name="contracts", on_delete=models.CASCADE)
	status_details = models.CharField(max_length=50, null=True, blank=True)
	period_start_date = models.DateTimeField(null=True, blank=True)
	period_end_date = models.DateTimeField(null=True, blank=True)
	value_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	value_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)

	class Meta:
		ordering = ["-period_start_date"]
		indexes = [
			models.Index(fields=["-period_start_date"], name="contract_date_idx"),
		]

	def __str__(self):
		return self.id


class TenderSubItem(AuditedModel):
	tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="tender_subitems")
	subitem = models.ForeignKey(SubItemDefinition, on_delete=models.PROTECT, related_name="tender_subitems")
	quantity = models.IntegerField(null=True, blank=True)
	min_quantity = models.IntegerField(null=True, blank=True)
	unit_price_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	unit_price_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)
	orden = models.IntegerField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["tender", "subitem"],
				name="uq_tender_subitem",
			),
		]
		indexes = [
			models.Index(fields=["tender"], name="tender_subitem_tender_idx"),
			models.Index(fields=["subitem"], name="tender_subitem_subitem_idx"),
		]

	def __str__(self):
		return f"{self.tender_id} - {self.subitem_id}"


class AwardSubItem(AuditedModel):
	award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name="award_subitems")
	subitem = models.ForeignKey(SubItemDefinition, on_delete=models.PROTECT, related_name="award_subitems")
	quantity = models.IntegerField(null=True, blank=True)
	unit_price_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
	unit_price_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["award", "subitem"],
				name="uq_award_subitem",
			),
		]
		indexes = [
			models.Index(fields=["award"], name="award_subitem_award_idx"),
			models.Index(fields=["subitem"], name="award_subitem_subitem_idx"),
		]

	def __str__(self):
		return f"{self.award_id} - {self.subitem_id}"
