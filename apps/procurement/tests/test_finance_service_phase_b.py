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
from apps.procurement.models import (
    BudgetLedgerEntry,
    ContractAmendment,
    ContractBudget,
    ExpenseObject,
    FulfillmentMemo,
    Payment,
    PaymentAllocation,
    PurchaseOrder,
    PurchaseOrderLine,
)
from apps.procurement.services.finance_service import (
    approve_fulfillment_memo,
    cancel_payment,
    create_fulfillment_memo,
    post_payment,
    reconcile_order_payment,
    update_fulfillment_memo,
)
from apps.procurement.services.payments import build_payment_lot_report_sections


class FinanceServicePhaseBTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="phaseb", password="phaseb123")
        self.currency = Currency.objects.create(code="PYG", name="Guarani", symbol="Gs")
        self.compiled = CompiledRelease.objects.create(
            ocid="ocid-phaseb-001",
            release_id="release-phaseb-1",
            date=timezone.now(),
        )
        self.buyer = Party.objects.create(
            party_id="entidad-phaseb-1",
            name="Entidad",
            role=Party.ROLE_PROCURING_ENTITY,
        )
        self.supplier = Party.objects.create(
            party_id="proveedor-phaseb-1",
            name="Proveedor Uno",
            role=Party.ROLE_SUPPLIER,
        )
        self.tender = Tender.objects.create(
            id="tender-phaseb-1",
            compiled_release=self.compiled,
            tenderID=223355,
            title="Licitacion fase B",
            award_criteria_details="total",
            status_details="active",
            main_procurement_category_details="goods",
            procurement_method_details="open",
            value_amount=Decimal("8000.00"),
            value_currency=self.currency,
            procuring_entity=self.buyer,
        )
        self.lot = Lot.objects.create(
            id="lot-phaseb-1",
            tender=self.tender,
            title="Lote 1",
            open_contract_type="Por cantidad",
            value_amount=Decimal("8000.00"),
            value_currency=self.currency,
            min_value_amount=Decimal("0.00"),
            min_value_currency=self.currency,
        )
        self.item = ItemDefinition.objects.create(
            id="item-phaseb-1",
            description="Item 1",
            lot=self.lot,
            unit_name="unidad",
        )
        self.award = Award.objects.create(
            id="award-phaseb-1",
            tender=self.tender,
            status_details="active",
            date=timezone.now(),
            value_amount=Decimal("8000.00"),
            value_currency=self.currency,
        )
        self.award.suppliers.add(self.supplier)
        self.award_item = AwardItem.objects.create(
            award=self.award,
            item=self.item,
            quantity=20,
            unit_price_amount=Decimal("100.00"),
            unit_price_currency=self.currency,
        )
        self.contract = Contract.objects.create(
            id="contract-phaseb-1",
            award=self.award,
            status_details="active",
            period_start_date=timezone.now(),
            value_amount=Decimal("8000.00"),
            value_currency=self.currency,
        )
        self.expense_object = ExpenseObject.objects.create(code="290", description="Bienes y servicios")

        self.order = PurchaseOrder.objects.create(
            order_number="OC-PHASEB-001",
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
            cdp_number="CDP-B-001",
            assigned_amount=Decimal("5000.00"),
            committed_amount=Decimal("1500.00"),
            executed_amount=Decimal("0.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )

    def test_approve_fulfillment_memo_blocks_overfulfillment(self):
        memo_1 = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-001",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("7.000")}],
        )
        approve_fulfillment_memo(memo_1)

        with self.assertRaises(ValidationError):
            create_fulfillment_memo(
                contract=self.contract,
                beneficiary_sector="Mantenimiento",
                memo_number="MEMO-B-002",
                memo_date=timezone.now().date(),
                created_by=self.user,
                lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("4.000")}],
            )

    def test_post_payment_success_updates_budget_and_ledger(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-003",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("8.000")}],
        )
        approve_fulfillment_memo(memo)

        payment = Payment.objects.create(
            payment_number="PAGO-B-001",
            payment_date=timezone.now().date(),
            amount_total=Decimal("600.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("600.00"),
        )

        post_payment(payment)

        self.budget.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_POSTED)
        self.assertEqual(self.budget.committed_amount, Decimal("1500.00"))
        self.assertEqual(self.budget.executed_amount, Decimal("600.00"))
        self.assertTrue(
            BudgetLedgerEntry.objects.filter(
                contract_budget=self.budget,
                entry_type=BudgetLedgerEntry.ENTRY_EXECUTE,
                source_type=BudgetLedgerEntry.SOURCE_PAYMENT,
                source_id=str(payment.id),
            ).exists()
        )

    def test_post_payment_fails_if_exceeds_approved_fulfillment(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-004",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("2.000")}],
        )
        approve_fulfillment_memo(memo)

        payment = Payment.objects.create(
            payment_number="PAGO-B-002",
            payment_date=timezone.now().date(),
            amount_total=Decimal("300.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("300.00"),
        )

        with self.assertRaises(ValidationError):
            post_payment(payment)

    def test_cancel_payment_reverses_execution(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-005",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("9.000")}],
        )
        approve_fulfillment_memo(memo)

        payment = Payment.objects.create(
            payment_number="PAGO-B-003",
            payment_date=timezone.now().date(),
            amount_total=Decimal("500.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("500.00"),
        )
        post_payment(payment)

        cancel_payment(payment)

        self.budget.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_CANCELLED)
        self.assertEqual(self.budget.committed_amount, Decimal("1500.00"))
        self.assertEqual(self.budget.executed_amount, Decimal("0.00"))
        self.assertTrue(
            BudgetLedgerEntry.objects.filter(
                contract_budget=self.budget,
                entry_type=BudgetLedgerEntry.ENTRY_REVERSE_EXECUTE,
                source_type=BudgetLedgerEntry.SOURCE_PAYMENT,
                source_id=str(payment.id),
            ).exists()
        )

    def test_reconcile_order_payment_returns_expected_snapshot(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-006",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("5.000")}],
        )
        approve_fulfillment_memo(memo)

        payment = Payment.objects.create(
            payment_number="PAGO-B-004",
            payment_date=timezone.now().date(),
            amount_total=Decimal("300.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("300.00"),
        )
        post_payment(payment)

        snapshot = reconcile_order_payment(self.order)

        self.assertEqual(snapshot["order_number"], self.order.order_number)
        self.assertEqual(snapshot["approved_fulfilled_amount"], Decimal("500.00"))
        self.assertEqual(snapshot["paid_amount"], Decimal("300.00"))

    def test_create_total_memo_auto_generates_pending_lines(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            fulfillment_mode=FulfillmentMemo.MODE_TOTAL,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-007",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order": self.order, "purchase_order_line": self.order_line}],
        )

        line = memo.lines.get(purchase_order=self.order)
        self.assertEqual(line.fulfilled_quantity, Decimal("10.000"))

    def test_create_fulfillment_memo_starts_as_draft(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-011",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("2.000")}],
        )

        self.assertEqual(memo.status, FulfillmentMemo.STATUS_DRAFT)

    def test_update_fulfillment_memo_replaces_lines_before_approval(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-012",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("2.000")}],
        )

        update_fulfillment_memo(
            memo,
            contract=self.contract,
            beneficiary_sector="Laboratorio",
            memo_number="MEMO-B-012-EDIT",
            memo_date=timezone.now().date(),
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("4.000"), "observations": "Ajustado"}],
            fulfillment_mode=FulfillmentMemo.MODE_PARTIAL,
        )

        memo.refresh_from_db()
        self.assertEqual(memo.status, FulfillmentMemo.STATUS_DRAFT)
        self.assertEqual(memo.memo_number, "MEMO-B-012-EDIT")
        self.assertEqual(memo.beneficiary_sector, "Laboratorio")
        self.assertEqual(memo.lines.count(), 1)
        self.assertEqual(memo.lines.first().fulfilled_quantity, Decimal("4.000"))

    def test_create_total_memo_uses_remaining_pending_quantity(self):
        partial = create_fulfillment_memo(
            contract=self.contract,
            fulfillment_mode=FulfillmentMemo.MODE_PARTIAL,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-008",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("3.000")}],
        )
        approve_fulfillment_memo(partial)

        total = create_fulfillment_memo(
            contract=self.contract,
            fulfillment_mode=FulfillmentMemo.MODE_TOTAL,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-009",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order": self.order, "purchase_order_line": self.order_line}],
        )

        line = total.lines.get(purchase_order_line=self.order_line)
        self.assertEqual(line.fulfilled_quantity, Decimal("7.000"))

    def test_create_partial_memo_requires_lines(self):
        with self.assertRaises(ValidationError):
            create_fulfillment_memo(
                contract=self.contract,
                fulfillment_mode=FulfillmentMemo.MODE_PARTIAL,
                beneficiary_sector="Mantenimiento",
                memo_number="MEMO-B-010",
                memo_date=timezone.now().date(),
                created_by=self.user,
                lines_data=[],
            )

    def test_post_payment_ac_budget_requires_active_amendment(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-011",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("6.000")}],
        )
        approve_fulfillment_memo(memo)

        ac_budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            financial_code="AC-28001-24-47969",
            funding_source="10",
            cdp_number="CDP-B-AC-001",
            assigned_amount=Decimal("1200.00"),
            committed_amount=Decimal("600.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )
        payment = Payment.objects.create(
            payment_number="PAGO-B-005",
            payment_date=timezone.now().date(),
            amount_total=Decimal("400.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order,
            contract_budget=ac_budget,
            amount=Decimal("400.00"),
        )

        with self.assertRaises(ValidationError):
            post_payment(payment)

    def test_post_payment_ac_budget_with_active_amendment_succeeds(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-012",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("6.000")}],
        )
        approve_fulfillment_memo(memo)

        ContractAmendment.objects.create(
            contract=self.contract,
            amendment_number="ADD-001",
            amendment_type=ContractAmendment.TYPE_AMOUNT,
            financial_code="AC-28001-24-47969",
            amount_delta=Decimal("1200.00"),
            effective_date=timezone.now().date(),
            status=ContractAmendment.STATUS_ACTIVE,
        )

        ac_budget = ContractBudget.objects.create(
            contract=self.contract,
            expense_object=self.expense_object,
            fiscal_year=2026,
            financial_code="AC-28001-24-47969",
            funding_source="10",
            cdp_number="CDP-B-AC-002",
            assigned_amount=Decimal("1200.00"),
            committed_amount=Decimal("600.00"),
            status=ContractBudget.STATUS_ACTIVE,
        )
        payment = Payment.objects.create(
            payment_number="PAGO-B-006",
            payment_date=timezone.now().date(),
            amount_total=Decimal("400.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
        )
        PaymentAllocation.objects.create(
            payment=payment,
            purchase_order=self.order,
            contract_budget=ac_budget,
            amount=Decimal("400.00"),
        )

        post_payment(payment)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_POSTED)

    def test_build_payment_lot_report_sections_uses_previous_posted_payments_as_snapshot(self):
        memo = create_fulfillment_memo(
            contract=self.contract,
            beneficiary_sector="Mantenimiento",
            memo_number="MEMO-B-013",
            memo_date=timezone.now().date(),
            created_by=self.user,
            lines_data=[{"purchase_order_line": self.order_line, "fulfilled_quantity": Decimal("10.000")}],
        )
        approve_fulfillment_memo(memo)

        first_payment = Payment.objects.create(
            payment_number="PAGO-B-007",
            payment_date=timezone.now().date(),
            amount_total=Decimal("300.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
            contract=self.contract,
        )
        PaymentAllocation.objects.create(
            payment=first_payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("300.00"),
        )
        post_payment(first_payment)

        second_payment = Payment.objects.create(
            payment_number="PAGO-B-008",
            payment_date=timezone.now().date() + timezone.timedelta(days=1),
            amount_total=Decimal("200.00"),
            status=Payment.STATUS_DRAFT,
            created_by=self.user,
            contract=self.contract,
        )
        second_allocation = PaymentAllocation.objects.create(
            payment=second_payment,
            purchase_order=self.order,
            contract_budget=self.budget,
            amount=Decimal("200.00"),
        )

        lot_sections, lot_sections_total = build_payment_lot_report_sections(
            payment=second_payment,
            allocations=[second_allocation],
            contract=self.contract,
        )

        self.assertEqual(len(lot_sections), 1)
        self.assertEqual(lot_sections[0]["max_amount"], Decimal("8000.00"))
        self.assertEqual(lot_sections[0]["prev_paid"], Decimal("300.00"))
        self.assertEqual(lot_sections[0]["saldo_anterior"], Decimal("7700.00"))
        self.assertEqual(lot_sections_total, Decimal("1000.00"))
