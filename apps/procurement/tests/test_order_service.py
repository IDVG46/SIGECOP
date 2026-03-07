from decimal import Decimal

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
from apps.procurement.models import ContractLotBalance, ItemQuantityBalance, PurchaseOrder, PurchaseOrderLine
from apps.procurement.services import recalculate_contract_balances, recalculate_order_totals_and_balances


class ProcurementOrderServiceTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="PYG", name="Guaraní", symbol="Gs")
        self.compiled = CompiledRelease.objects.create(
            ocid="ocid-test-001",
            release_id="release-1",
            date=timezone.now(),
        )
        self.buyer = Party.objects.create(
            party_id="entidad-1",
            name="Entidad",
            role=Party.ROLE_PROCURING_ENTITY,
        )
        self.supplier = Party.objects.create(
            party_id="proveedor-1",
            name="Proveedor Uno",
            role=Party.ROLE_SUPPLIER,
        )
        self.tender = Tender.objects.create(
            id="tender-1",
            compiled_release=self.compiled,
            tenderID=123456,
            title="Licitación prueba",
            award_criteria_details="total",
            status_details="active",
            main_procurement_category_details="goods",
            procurement_method_details="open",
            value_amount=Decimal("1000.00"),
            value_currency=self.currency,
            procuring_entity=self.buyer,
        )
        self.lot = Lot.objects.create(
            id="lot-1",
            tender=self.tender,
            title="Lote 1",
            open_contract_type="Por cantidad",
            value_amount=Decimal("1000.00"),
            value_currency=self.currency,
            min_value_amount=Decimal("0.00"),
            min_value_currency=self.currency,
        )
        self.item = ItemDefinition.objects.create(
            id="item-1",
            description="Item 1",
            lot=self.lot,
            unit_name="unidad",
        )
        self.award = Award.objects.create(
            id="award-1",
            tender=self.tender,
            status_details="active",
            date=timezone.now(),
            value_amount=Decimal("1000.00"),
            value_currency=self.currency,
        )
        self.award.suppliers.add(self.supplier)
        self.award_item = AwardItem.objects.create(
            award=self.award,
            item=self.item,
            quantity=10,
            unit_price_amount=Decimal("100.00"),
            unit_price_currency=self.currency,
        )
        self.contract = Contract.objects.create(
            id="contract-1",
            award=self.award,
            status_details="active",
            period_start_date=timezone.now(),
            value_amount=Decimal("1000.00"),
            value_currency=self.currency,
        )

    def _create_order_with_line(self, number, qty, unit_price, status=PurchaseOrder.STATUS_DRAFT):
        order = PurchaseOrder.objects.create(
            order_number=number,
            contract=self.contract,
            supplier=self.supplier,
            issue_date=timezone.now().date(),
            status=status,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            lot=self.lot,
            award_item=self.award_item,
            quantity=Decimal(str(qty)),
            unit_price=Decimal(str(unit_price)),
        )
        return order

    def test_recalculate_balances_aggregate_active_orders(self):
        order_1 = self._create_order_with_line("OC-001", "2", "100.00")
        order_2 = self._create_order_with_line("OC-002", "3", "100.00")

        recalculate_order_totals_and_balances(order_1)
        recalculate_order_totals_and_balances(order_2)

        lot_balance = ContractLotBalance.objects.get(contract=self.contract, lot=self.lot)
        qty_balance = ItemQuantityBalance.objects.get(contract=self.contract, award_item=self.award_item)

        self.assertEqual(order_1.total_amount, Decimal("200.00"))
        self.assertEqual(order_2.total_amount, Decimal("300.00"))
        self.assertEqual(lot_balance.committed_amount, Decimal("500.00"))
        self.assertEqual(qty_balance.committed_quantity, Decimal("5.000"))

    def test_recalculate_balances_after_cancel(self):
        order_1 = self._create_order_with_line("OC-003", "2", "100.00")
        order_2 = self._create_order_with_line("OC-004", "3", "100.00")

        recalculate_order_totals_and_balances(order_1)
        recalculate_order_totals_and_balances(order_2)

        order_1.status = PurchaseOrder.STATUS_CANCELLED
        order_1.save(update_fields=["status"])
        recalculate_contract_balances(self.contract)

        lot_balance = ContractLotBalance.objects.get(contract=self.contract, lot=self.lot)
        qty_balance = ItemQuantityBalance.objects.get(contract=self.contract, award_item=self.award_item)

        self.assertEqual(lot_balance.committed_amount, Decimal("300.00"))
        self.assertEqual(qty_balance.committed_quantity, Decimal("3.000"))

    def test_contract_amount_limit_validation(self):
        order_1 = self._create_order_with_line("OC-005", "8", "100.00")
        recalculate_order_totals_and_balances(order_1)

        order_2 = self._create_order_with_line("OC-006", "3", "100.00")
        with self.assertRaises(ValidationError):
            recalculate_order_totals_and_balances(order_2)

    def test_quantity_limit_not_enforced_when_no_max_quantity_defined(self):
        self.award_item.quantity = None
        self.award_item.save(update_fields=["quantity"])

        order = self._create_order_with_line("OC-007", "7", "100.00")

        # Debe controlar por monto (700 <= 1000), sin bloquear por cantidad.
        recalculate_order_totals_and_balances(order)

        self.assertEqual(order.total_amount, Decimal("700.00"))
        self.assertFalse(
            ItemQuantityBalance.objects.filter(contract=self.contract, award_item=self.award_item).exists()
        )

    def test_quantity_limit_not_enforced_for_non_quantity_based_lot(self):
        lot_amount = Lot.objects.create(
            id="lot-2",
            tender=self.tender,
            title="Lote por monto",
            open_contract_type="Por monto",
            value_amount=Decimal("1000.00"),
            value_currency=self.currency,
            min_value_amount=Decimal("0.00"),
            min_value_currency=self.currency,
        )
        item_amount = ItemDefinition.objects.create(
            id="item-2",
            description="Item por monto",
            lot=lot_amount,
            unit_name="unidad",
        )
        award_item_amount = AwardItem.objects.create(
            award=self.award,
            item=item_amount,
            quantity=1,
            unit_price_amount=Decimal("100.00"),
            unit_price_currency=self.currency,
        )

        order = PurchaseOrder.objects.create(
            order_number="OC-008",
            contract=self.contract,
            supplier=self.supplier,
            issue_date=timezone.now().date(),
            status=PurchaseOrder.STATUS_DRAFT,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            lot=lot_amount,
            award_item=award_item_amount,
            quantity=Decimal("4"),
            unit_price=Decimal("100.00"),
        )

        # No debe restringir por cantidad (aunque quantity adjudicada sea 1), solo por monto.
        recalculate_order_totals_and_balances(order)

        self.assertEqual(order.total_amount, Decimal("400.00"))
        self.assertFalse(
            ItemQuantityBalance.objects.filter(contract=self.contract, award_item=award_item_amount).exists()
        )

    def test_quantity_limit_enforced_for_non_quantity_based_lot_when_max_gt_one(self):
        lot_amount = Lot.objects.create(
            id="lot-3",
            tender=self.tender,
            title="Lote por monto con cantidad",
            open_contract_type="Por monto",
            value_amount=Decimal("1000.00"),
            value_currency=self.currency,
            min_value_amount=Decimal("0.00"),
            min_value_currency=self.currency,
        )
        item_amount = ItemDefinition.objects.create(
            id="item-3",
            description="Item con cantidad definida",
            lot=lot_amount,
            unit_name="unidad",
        )
        award_item_amount = AwardItem.objects.create(
            award=self.award,
            item=item_amount,
            quantity=2,
            unit_price_amount=Decimal("100.00"),
            unit_price_currency=self.currency,
        )

        order = PurchaseOrder.objects.create(
            order_number="OC-009",
            contract=self.contract,
            supplier=self.supplier,
            issue_date=timezone.now().date(),
            status=PurchaseOrder.STATUS_DRAFT,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            lot=lot_amount,
            award_item=award_item_amount,
            quantity=Decimal("3"),
            unit_price=Decimal("100.00"),
        )

        with self.assertRaises(ValidationError):
            recalculate_order_totals_and_balances(order)
