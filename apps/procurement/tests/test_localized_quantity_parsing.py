from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.procurement.forms.finance_forms import ContractBudgetForm, FulfillmentMemoPartialLineForm, PaymentAllocationForm, PaymentForm
from apps.procurement.forms.order_forms import PurchaseOrderLineForm


class LocalizedQuantityParsingTests(SimpleTestCase):
    def test_order_line_quantity_accepts_thousands_dot(self):
        form = PurchaseOrderLineForm(data={"quantity": "1.292"})
        form.cleaned_data = {"quantity": None}

        value = form.clean_quantity()

        self.assertEqual(value, Decimal("1292"))

    def test_order_line_quantity_rejects_decimal_comma(self):
        form = PurchaseOrderLineForm(data={"quantity": "1,25"})
        form.cleaned_data = {"quantity": None}

        with self.assertRaises(ValidationError):
            form.clean_quantity()

    def test_fulfillment_quantity_accepts_thousands_dot(self):
        form = FulfillmentMemoPartialLineForm(data={"fulfilled_quantity": "2.500"})
        form.cleaned_data = {"fulfilled_quantity": None}

        value = form.clean_fulfilled_quantity()

        self.assertEqual(value, Decimal("2500"))

    def test_fulfillment_quantity_rejects_decimal_comma(self):
        form = FulfillmentMemoPartialLineForm(data={"fulfilled_quantity": "2,5"})
        form.cleaned_data = {"fulfilled_quantity": None}

        with self.assertRaises(ValidationError):
            form.clean_fulfilled_quantity()

    def test_order_line_unit_price_accepts_thousands_dot(self):
        form = PurchaseOrderLineForm(data={"unit_price": "2.584.000"})
        form.cleaned_data = {"unit_price": None}

        value = form.clean_unit_price()

        self.assertEqual(value, Decimal("2584000"))

    def test_budget_amount_accepts_thousands_dot(self):
        form = ContractBudgetForm(data={"assigned_amount": "1.250.000"})
        form.cleaned_data = {"assigned_amount": None}

        value = form.clean_assigned_amount()

        self.assertEqual(value, Decimal("1250000"))

    def test_payment_amount_accepts_thousands_dot(self):
        form = PaymentForm(data={"amount_total": "1.250.000"})
        form.cleaned_data = {"amount_total": None}

        value = form.clean_amount_total()

        self.assertEqual(value, Decimal("1250000"))

    def test_allocation_amount_accepts_decimal_comma(self):
        form = PaymentAllocationForm(data={"amount": "3,50"})
        form.cleaned_data = {"amount": None}

        value = form.clean_amount()

        self.assertEqual(value, Decimal("3.50"))
