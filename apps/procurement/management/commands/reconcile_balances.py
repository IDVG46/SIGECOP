"""
Management command: reconcile_balances
=======================================
Detecta (y opcionalmente corrige) divergencias entre los montos almacenados
en los modelos denormalizados y la fuente de verdad para cada campo:

  ContractBudget.executed_amount
      Fuente de verdad: BudgetLedgerEntry (ENTRY_EXECUTE - ENTRY_REVERSE_EXECUTE)

  PurchaseOrder.total_amount
      Fuente de verdad: suma de PurchaseOrderLine.line_total

Uso:
    py manage.py reconcile_balances            # solo detecta
    py manage.py reconcile_balances --fix      # detecta y corrige
    py manage.py reconcile_balances --contract <id>   # limitar a un contrato
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum

from apps.procurement.models import (
    BudgetLedgerEntry,
    ContractBudget,
    PurchaseOrder,
)


class Command(BaseCommand):
    help = "Detecta drift entre montos almacenados y el ledger/líneas de OC."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Corregir automáticamente los valores divergentes.",
        )
        parser.add_argument(
            "--contract",
            metavar="CONTRACT_ID",
            help="Limitar la revisión a un contrato específico.",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        contract_id = options.get("contract")

        drift_count = 0

        # ── 1. ContractBudget.executed_amount vs ledger ────────────────────
        self.stdout.write("Verificando ContractBudget.executed_amount ...")
        budget_qs = ContractBudget.objects.all()
        if contract_id:
            budget_qs = budget_qs.filter(contract_id=contract_id)

        for budget in budget_qs.iterator():
            agg = budget.ledger_entries.aggregate(
                total_execute=Sum(
                    "amount",
                    filter=Q(entry_type=BudgetLedgerEntry.ENTRY_EXECUTE),
                    default=Decimal("0.00"),
                ),
                total_reverse=Sum(
                    "amount",
                    filter=Q(entry_type=BudgetLedgerEntry.ENTRY_REVERSE_EXECUTE),
                    default=Decimal("0.00"),
                ),
            )
            expected = agg["total_execute"] - agg["total_reverse"]

            if budget.executed_amount != expected:
                drift_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRIFT] ContractBudget {budget.id} ({budget.cdp_number}): "
                        f"executed_amount={budget.executed_amount} ≠ ledger={expected}"
                    )
                )
                if fix:
                    ContractBudget.objects.filter(pk=budget.pk).update(
                        executed_amount=expected
                    )
                    self.stdout.write(self.style.SUCCESS("    → corregido."))

        # ── 2. PurchaseOrder.total_amount vs sum(PurchaseOrderLine.line_total) ─
        self.stdout.write("Verificando PurchaseOrder.total_amount ...")
        order_qs = PurchaseOrder.objects.all()
        if contract_id:
            order_qs = order_qs.filter(contract_id=contract_id)

        for order in order_qs.iterator():
            expected = order.lines.aggregate(
                total=Sum("line_total", default=Decimal("0.00"))
            )["total"]

            if order.total_amount != expected:
                drift_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRIFT] PurchaseOrder {order.order_number}: "
                        f"total_amount={order.total_amount} ≠ sum(lines)={expected}"
                    )
                )
                if fix:
                    PurchaseOrder.objects.filter(pk=order.pk).update(
                        total_amount=expected
                    )
                    self.stdout.write(self.style.SUCCESS("    → corregido."))

        # ── Resumen ────────────────────────────────────────────────────────
        if drift_count == 0:
            self.stdout.write(self.style.SUCCESS("Sin divergencias detectadas."))
        else:
            msg = f"{drift_count} divergencia(s) {'corregida(s)' if fix else 'encontrada(s)'}."
            self.stdout.write(
                self.style.SUCCESS(msg) if fix else self.style.WARNING(msg)
            )
