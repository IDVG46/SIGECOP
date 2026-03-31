from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
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
from apps.procurement.models import (
    BudgetLedgerEntry,
    ContractBudget,
    ExpenseObject,
    FulfillmentMemo,
    FulfillmentMemoLine,
    Payment,
    PaymentAllocation,
    PurchaseOrder,
    PurchaseOrderLine,
)


class FinanceModelsPhaseATests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="phasea", password="phasea123")
        self.currency = Currency.objects.create(code="PYG", name="Guarani", symbol="Gs")
        self.compiled = CompiledRelease.objects.create(
            ocid="ocid-phasea-001",
            release_id="release-phasea-1",
            date=timezone.now(),
        )
        self.buyer = Party.objects.create(
            party_id="entidad-phasea-1",
            name="Entidad",
            role=Party.ROLE_PROCURING_ENTITY,
        )
        self.supplier = Party.objects.create(
            party_id="proveedor-phasea-1",
            name="Proveedor Uno",
            role=Party.ROLE_SUPPLIER,
        )
        self.tender = Tender.objects.create(
            id="tender-phasea-1",
            compiled_release=self.compiled,
            tenderID=223344,
            title="Licitacion fase A",
            award_criteria_details="total",
            status_details="active",
            main_procurement_category_details="goods",
            procurement_method_details="open",
            value_amount=Decimal("5000.00"),
            value_currency=self.currency,
            procuring_entity=self.buyer,
        )
        self.lot = Lot.objects.create(
            id="lot-phasea-1",
            tender=self.tender,
            title="Lote 1",
            open_contract_type="Por cantidad",
            value_amount=Decimal("5000.00"),
            value_currency=self.currency,
            min_value_amount=Decimal("0.00"),
            min_value_currency=self.currency,
        )
        self.item_1 = ItemDefinition.objects.create(
            id="item-phasea-1",
            description="Item 1",
            lot=self.lot,
            unit_name="unidad",
        )
        self.item_2 = ItemDefinition.objects.create(
            id="item-phasea-2",
            description="Item 2",
            lot=self.lot,
            unit_name="unidad",
        )
        self.award = Award.objects.create(
            id="award-phasea-1",
            tender=self.tender,
            status_details="active",
            date=timezone.now(),
            value_amount=Decimal("5000.00"),
            value_currency=self.currency,
        )
        self.award.suppliers.add(self.supplier)
        self.award_item_1 = AwardItem.objects.create(
            award=self.award,
            item=self.item_1,
            quantity=10,
            unit_price_amount=Decimal("100.00"),
            unit_price_currency=self.currency,
        )
        self.award_item_2 = AwardItem.objects.create(
            award=self.award,
            item=self.item_2,
            quantity=10,
            unit_price_amount=Decimal("120.00"),
            unit_price_currency=self.currency,
        )
        self.contract = Contract.objects.create(
            id="contract-phasea-1",
            award=self.award,
            status_details="active",
            period_start_date=timezone.now(),
            value_amount=Decimal("5000.00"),
            value_currency=self.currency,
        )
        self.expense_object = ExpenseObject.objects.create(code="260", description="Servicios tecnicos")

        self.order_1 = PurchaseOrder.objects.create(
            order_number="OC-PHASEA-001",
            contract=self.contract,
            supplier=self.supplier,
            expense_object=self.expense_object,
            issue_date=timezone.now().date(),
            total_amount=Decimal("1000.00"),
        )
        self.order_2 = PurchaseOrder.objects.create(
            order_number="OC-PHASEA-002",
            contract=self.contract,
            supplier=self.supplier,
            expense_object=self.expense_object,
            issue_date=timezone.now().date(),
            total_amount=Decimal("800.00"),
        )
        self.order_line_1 = PurchaseOrderLine.objects.create(
            purchase_order=self.order_1,
            lot=self.lot,
            award_item=self.award_item_1,
            quantity=Decimal("5"),
            unit_price=Decimal("100.00"),
            line_total=Decimal("500.00"),
        )
        self.order_line_2 = PurchaseOrderLine.objects.create(
            purchase_order=self.order_2,
            lot=self.lot,
            award_item=self.award_item_2,
            quantity=Decimal("4"),
            unit_price=Decimal("120.00"),
            line_total=Decimal("480.00"),
        )

    def test_contract_budget_available_amount(self):
        budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            funding_source="10",
            cdp_number="CDP-001",
            assigned_amount=Decimal("1000.00"),
            committed_amount=Decimal("250.00"),
            executed_amount=Decimal("300.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )

        self.assertEqual(budget.available_amount, Decimal("450.00"))

    def test_fulfillment_memo_line_must_belong_to_same_order(self):
        memo = FulfillmentMemo.objects.create(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-001",
            memo_date=timezone.now().date(),
            status=FulfillmentMemo.STATUS_ISSUED,
            created_by=self.user,
        )

        line = FulfillmentMemoLine(
            memo=memo,
            purchase_order=self.order_1,
            purchase_order_line=self.order_line_2,
            fulfilled_quantity=Decimal("1.000"),
        )

        with self.assertRaises(ValidationError):
            line.full_clean()

    def test_payment_allocation_unique_per_order_and_payment(self):
        budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            funding_source="10",
            cdp_number="CDP-002",
            assigned_amount=Decimal("2000.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )
        payment = Payment.objects.create(
            payment_number="PAGO-001",
            payment_date=timezone.now().date(),
            amount_total=Decimal("500.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )

        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order_1,
            contract_budget=budget,
            amount=Decimal("300.00"),
        )

        second_budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            funding_source="11",
            cdp_number="CDP-002B",
            assigned_amount=Decimal("2000.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )

        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order_1,
            contract_budget=second_budget,
            amount=Decimal("50.00"),
        )

        with self.assertRaises(IntegrityError):
            PaymentAllocation.objects.create(
                payment=payment,
                purchase_order=self.order_1,
                contract_budget=budget,
                amount=Decimal("100.00"),
            )

    def test_budget_ledger_entry_amount_must_be_positive(self):
        budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            funding_source="20",
            cdp_number="CDP-003",
            assigned_amount=Decimal("500.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )
        entry = BudgetLedgerEntry(
            contract_budget=budget,
            entry_type=BudgetLedgerEntry.ENTRY_COMMIT,
            amount=Decimal("0.00"),
            source_type=BudgetLedgerEntry.SOURCE_MANUAL_ADJUSTMENT,
            source_id="adjust-1",
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            entry.full_clean()
