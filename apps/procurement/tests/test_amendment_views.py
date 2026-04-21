from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dncp_integration.models import Award, CompiledRelease, Contract, Currency, Party, Tender
from apps.procurement.forms import ContractAmendmentForm
from apps.procurement.models import ContractAmendment


class ContractAmendmentViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="amend-user", password="amend-123")
        permissions = Permission.objects.filter(
            codename__in=[
                "view_contractamendment",
                "add_contractamendment",
                "change_contractamendment",
            ]
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)

        self.currency = Currency.objects.create(code="PYG", name="Guarani", symbol="Gs")
        self.compiled = CompiledRelease.objects.create(
            ocid="ocid-amend-001",
            release_id="release-amend-1",
            date=timezone.now(),
        )
        self.buyer = Party.objects.create(
            party_id="entidad-amend-1",
            name="Entidad Auditada",
            role=Party.ROLE_PROCURING_ENTITY,
        )
        self.supplier = Party.objects.create(
            party_id="proveedor-amend-1",
            name="Proveedor Adenda",
            role=Party.ROLE_SUPPLIER,
        )
        self.tender = Tender.objects.create(
            id="tender-amend-1",
            compiled_release=self.compiled,
            tenderID=998877,
            title="Contrato con adendas",
            award_criteria_details="total",
            status_details="active",
            main_procurement_category_details="goods",
            procurement_method_details="open",
            value_amount=Decimal("120000.00"),
            value_currency=self.currency,
            procuring_entity=self.buyer,
        )
        self.award = Award.objects.create(
            id="award-amend-1",
            tender=self.tender,
            status_details="active",
            date=timezone.now(),
            value_amount=Decimal("120000.00"),
            value_currency=self.currency,
        )
        self.award.suppliers.add(self.supplier)
        self.contract = Contract.objects.create(
            id="contract-amend-1",
            award=self.award,
            status_details="active",
            period_start_date=timezone.now(),
            value_amount=Decimal("120000.00"),
            value_currency=self.currency,
        )

    def test_period_amendment_requires_period_data(self):
        form = ContractAmendmentForm(
            data={
                "contract": self.contract.pk,
                "amendment_number": "ADD-001",
                "amendment_type": ContractAmendment.TYPE_PERIOD,
                "financial_code": "FIN-2026-00",
                "amount_delta": "",
                "period_extension_days": "",
                "new_end_date": "",
                "effective_date": "2026-01-15",
                "status": ContractAmendment.STATUS_DRAFT,
                "notes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("period_extension_days", form.errors)

    def test_financial_code_is_required_for_any_amendment(self):
        form = ContractAmendmentForm(
            data={
                "contract": self.contract.pk,
                "amendment_number": "ADD-001B",
                "amendment_type": ContractAmendment.TYPE_PERIOD,
                "financial_code": "",
                "amount_delta": "",
                "period_extension_days": "10",
                "new_end_date": "",
                "effective_date": "2026-01-15",
                "status": ContractAmendment.STATUS_DRAFT,
                "notes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("financial_code", form.errors)

    def test_create_view_persists_amendment(self):
        response = self.client.post(
            reverse("procurement:amendment_create"),
            data={
                "contract": self.contract.pk,
                "amendment_number": "ADD-002",
                "amendment_type": ContractAmendment.TYPE_AMOUNT,
                "financial_code": "FIN-2026-01",
                "amount_delta": "15000",
                "period_extension_days": "",
                "new_end_date": "",
                "effective_date": "2026-02-01",
                "status": ContractAmendment.STATUS_APPROVED,
                "notes": "Ampliación financiera inicial.",
            },
        )

        amendment = ContractAmendment.objects.get(amendment_number="ADD-002")
        self.assertRedirects(response, reverse("procurement:amendment_detail", args=[amendment.pk]))
        self.assertEqual(amendment.amount_delta, Decimal("15000"))

    def test_list_view_displays_registered_amendment(self):
        ContractAmendment.objects.create(
            contract=self.contract,
            amendment_number="ADD-003",
            amendment_type=ContractAmendment.TYPE_MIXED,
            financial_code="FIN-2026-02",
            amount_delta=Decimal("5000.00"),
            period_extension_days=20,
            effective_date=timezone.now().date(),
            status=ContractAmendment.STATUS_ACTIVE,
            notes="Prórroga y monto adicional.",
        )

        response = self.client.get(reverse("procurement:amendment_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ADD-003")
        self.assertContains(response, "Adendas")