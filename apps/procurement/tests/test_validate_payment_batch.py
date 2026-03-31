from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.dncp_integration.models import (
    Award,
    AwardItem,
    CompiledRelease,
    Contract,
    Currency,
    ItemDefinition,
    Lot,
    Party,
    Tender,
)
from apps.procurement.models import ContractBudget, ExpenseObject, Payment, PaymentAllocation, PurchaseOrder, PurchaseOrderLine
from apps.procurement.services.finance_service import (
    approve_fulfillment_memo,
    create_fulfillment_memo,
    validate_payment_allocation_batch,
)


class ValidatePaymentAllocationBatchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="batch-user", password="batch-pass")
        self.currency = Currency.objects.create(code="PYG", name="Guarani", symbol="Gs")
        self.compiled = CompiledRelease.objects.create(
            ocid="ocid-batch-001",
            release_id="release-batch-1",
            date=timezone.now(),
        )
        self.buyer = Party.objects.create(
            party_id="entidad-batch-1",
            name="Entidad Batch",
            role=Party.ROLE_PROCURING_ENTITY,
        )
        self.supplier = Party.objects.create(
            party_id="proveedor-batch-1",
            name="Proveedor Batch",
            role=Party.ROLE_SUPPLIER,
        )
        self.tender = Tender.objects.create(
            id="tender-batch-1",
            compiled_release=self.compiled,
            tenderID=999001,
            title="Licitacion Batch",
            award_criteria_details="total",
            status_details="active",
            main_procurement_category_details="goods",
            procurement_method_details="open",
            value_amount=Decimal("15000.00"),
            value_currency=self.currency,
            procuring_entity=self.buyer,
        )
        self.lot = Lot.objects.create(
            id="lot-batch-1",
            tender=self.tender,
            title="Lote Batch",
            open_contract_type="Por cantidad",
            value_amount=Decimal("15000.00"),
            value_currency=self.currency,
            min_value_amount=Decimal("0.00"),
            min_value_currency=self.currency,
        )
        self.item = ItemDefinition.objects.create(
            id="item-batch-1",
            description="Item Batch",
            lot=self.lot,
            unit_name="unidad",
        )
        self.award = Award.objects.create(
            id="award-batch-1",
            tender=self.tender,
            status_details="active",
            date=timezone.now(),
            value_amount=Decimal("15000.00"),
            value_currency=self.currency,
        )
        self.award.suppliers.add(self.supplier)
        self.award_item = AwardItem.objects.create(
            award=self.award,
            item=self.item,
            quantity=20,
            unit_price_amount=Decimal("500.00"),
            unit_price_currency=self.currency,
        )
        self.contract = Contract.objects.create(
            id="contract-batch-1",
            award=self.award,
            status_details="active",
            period_start_date=timezone.now(),
            value_amount=Decimal("15000.00"),
            value_currency=self.currency,
        )
        self.expense_object = ExpenseObject.objects.create(code="290", description="Servicios")
        self.other_expense_object = ExpenseObject.objects.create(code="300", description="Bienes")

        self.order = PurchaseOrder.objects.create(
            order_number="OC-BATCH-001",
            contract=self.contract,
            supplier=self.supplier,
            expense_object=self.expense_object,
            issue_date=timezone.now().date(),
            total_amount=Decimal("1000.00"),
            status=PurchaseOrder.STATUS_APPROVED,
        )
        self.order_line = PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            lot=self.lot,
            award_item=self.award_item,
            quantity=Decimal("10.000"),
            unit_price=Decimal("100.00"),
            line_total=Decimal("1000.00"),
        )

        self.budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            financial_code="CD-BASE-2026",
            funding_source="10",
            cdp_number="CDP-BATCH-001",
            assigned_amount=Decimal("5000.00"),
            committed_amount=Decimal("0.00"),
            executed_amount=Decimal("0.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )

        self.memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-BATCH-001",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("10.000")}],
        )
        approve_fulfillment_memo(self.memo)

    def test_validate_batch_success(self):
        result = validate_payment_allocation_batch(
            [{"purchase_order": self.order, "contract_budget": self.budget, "amount": Decimal("300.00")}]
        )
        self.assertEqual(result["submitted_by_order"][self.order.id], Decimal("300.00"))
        self.assertEqual(result["submitted_by_budget"][self.budget.id], Decimal("300.00"))

    def test_validate_batch_empty_allocations(self):
        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch([])

    def test_validate_batch_contract_mismatch(self):
        other_contract = Contract.objects.create(
            id="contract-batch-2",
            award=self.award,
            status_details="active",
            period_start_date=timezone.now(),
            value_amount=Decimal("2000.00"),
            value_currency=self.currency,
        )
        other_budget = ContractBudget.objects.create(
            contract=other_contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            financial_code="CD-BASE-2026-2",
            funding_source="10",
            cdp_number="CDP-BATCH-002",
            assigned_amount=Decimal("1000.00"),
            committed_amount=Decimal("0.00"),
            executed_amount=Decimal("0.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )
        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch(
                [{"purchase_order": self.order, "contract_budget": other_budget, "amount": Decimal("100.00")}]
            )

    def test_validate_batch_expense_object_mismatch(self):
        other_budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.other_expense_object,
            fiscal_year=2026,
            financial_code="CD-BASE-2026-3",
            funding_source="10",
            cdp_number="CDP-BATCH-003",
            assigned_amount=Decimal("1000.00"),
            committed_amount=Decimal("0.00"),
            executed_amount=Decimal("0.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )
        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch(
                [{"purchase_order": self.order, "contract_budget": other_budget, "amount": Decimal("100.00")}]
            )

    def test_validate_batch_exceeds_pending_by_order(self):
        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch(
                [{"purchase_order": self.order, "contract_budget": self.budget, "amount": Decimal("1200.00")}]
            )

    def test_validate_batch_exceeds_fulfillment_amount(self):
        self.memo.status = "cancelled"
        self.memo.save(update_fields=["status", "updated_at"])

        limited_memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-BATCH-002",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("2.000")}],
        )
        approve_fulfillment_memo(limited_memo)

        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch(
                [{"purchase_order": self.order, "contract_budget": self.budget, "amount": Decimal("300.00")}]
            )

    def test_validate_batch_exceeds_budget_available(self):
        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch(
                [{"purchase_order": self.order, "contract_budget": self.budget, "amount": Decimal("6000.00")}]
            )

    def test_validate_batch_excluded_payment_id(self):
        posted_payment = Payment.objects.create(
            payment_number="PAGO-BATCH-001",
            payment_date=timezone.now().date(),
            amount_total=Decimal("500.00"),
            status=Payment.STATUS_POSTED,
            contract=self.contract,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=posted_payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("500.00"),
        )

        with self.assertRaises(ValidationError):
            validate_payment_allocation_batch(
                [{"purchase_order": self.order, "contract_budget": self.budget, "amount": Decimal("600.00")}]
            )

        result = validate_payment_allocation_batch(
            [{"purchase_order": self.order, "contract_budget": self.budget, "amount": Decimal("600.00")}],
            excluded_payment_id=posted_payment.id,
        )
        self.assertEqual(result["submitted_by_order"][self.order.id], Decimal("600.00"))
