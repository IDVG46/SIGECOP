from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.procurement.services.payments import (
    validate_budget_against_order,
    validate_payment_against_order,
    validate_payment_context,
)


class PaymentServiceTest(SimpleTestCase):
    def test_payment_within_pending_is_valid(self):
        self.assertTrue(validate_payment_against_order(order_total=1000, already_paid=300, payment_amount=200))

    def test_payment_cannot_exceed_pending(self):
        with self.assertRaises(ValidationError):
            validate_payment_against_order(order_total=1000, already_paid=800, payment_amount=250)

    def test_payment_must_be_positive(self):
        with self.assertRaises(ValidationError):
            validate_payment_against_order(order_total=1000, already_paid=100, payment_amount=0)

    def test_budget_must_match_order_contract(self):
        order = SimpleNamespace(contract_id="contract-1", expense_object_id=10, total_amount=1000)
        budget = SimpleNamespace(contract_id="contract-2", expense_object_id=10)

        with self.assertRaises(ValidationError):
            validate_budget_against_order(order, budget)

    def test_budget_must_match_order_expense_object(self):
        order = SimpleNamespace(contract_id="contract-1", expense_object_id=10, total_amount=1000)
        budget = SimpleNamespace(contract_id="contract-1", expense_object_id=20)

        with self.assertRaises(ValidationError):
            validate_budget_against_order(order, budget)

    def test_validate_payment_context_success(self):
        order = SimpleNamespace(contract_id="contract-1", expense_object_id=10, total_amount=1000)
        budget = SimpleNamespace(contract_id="contract-1", expense_object_id=10)

        self.assertTrue(validate_payment_context(order, budget, already_paid=200, payment_amount=300))
