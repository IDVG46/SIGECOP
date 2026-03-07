from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.procurement.services.payments import validate_payment_against_order


class PaymentServiceTest(SimpleTestCase):
    def test_payment_within_pending_is_valid(self):
        self.assertTrue(validate_payment_against_order(order_total=1000, already_paid=300, payment_amount=200))

    def test_payment_cannot_exceed_pending(self):
        with self.assertRaises(ValidationError):
            validate_payment_against_order(order_total=1000, already_paid=800, payment_amount=250)

    def test_payment_must_be_positive(self):
        with self.assertRaises(ValidationError):
            validate_payment_against_order(order_total=1000, already_paid=100, payment_amount=0)
