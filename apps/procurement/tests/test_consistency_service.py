from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.procurement.services.consistency import validate_order_budget_consistency


class ConsistencyServiceTest(SimpleTestCase):
    def test_order_and_budget_consistency_success(self):
        order = SimpleNamespace(contract_id="contract-1", expense_object_id=10)
        budget = SimpleNamespace(contract_id="contract-1", expense_object_id=10)

        self.assertTrue(validate_order_budget_consistency(order, budget))

    def test_order_and_budget_consistency_invalid_contract(self):
        order = SimpleNamespace(contract_id="contract-1", expense_object_id=10)
        budget = SimpleNamespace(contract_id="contract-2", expense_object_id=10)

        with self.assertRaises(ValidationError):
            validate_order_budget_consistency(order, budget)

    def test_order_and_budget_consistency_invalid_expense_object(self):
        order = SimpleNamespace(contract_id="contract-1", expense_object_id=10)
        budget = SimpleNamespace(contract_id="contract-1", expense_object_id=99)

        with self.assertRaises(ValidationError):
            validate_order_budget_consistency(order, budget)
