from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.procurement.services.budget import (
    apply_budget_commitment,
    apply_budget_execution,
    release_budget_commitment,
    reverse_budget_execution,
)


class BudgetServiceTest(SimpleTestCase):
    def test_commitment_flow(self):
        budget = SimpleNamespace(assigned_amount=1000, committed_amount=0, executed_amount=0)

        apply_budget_commitment(budget, 300)
        self.assertEqual(budget.committed_amount, 300)

        apply_budget_execution(budget, 100)
        self.assertEqual(budget.committed_amount, 200)
        self.assertEqual(budget.executed_amount, 100)

        reverse_budget_execution(budget, 50)
        self.assertEqual(budget.committed_amount, 250)
        self.assertEqual(budget.executed_amount, 50)

        release_budget_commitment(budget, 50)
        self.assertEqual(budget.committed_amount, 200)

    def test_commitment_cannot_exceed_assigned(self):
        budget = SimpleNamespace(assigned_amount=500, committed_amount=400, executed_amount=50)
        with self.assertRaises(ValidationError):
            apply_budget_commitment(budget, 100)
