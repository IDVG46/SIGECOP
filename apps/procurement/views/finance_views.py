"""Compatibility facade for finance views.

Deprecated import path kept to avoid breaking existing imports:
    apps.procurement.views.finance_views
Use the modular package instead:
    apps.procurement.views.finance
"""

from .finance import (
    ContractBudgetApproveView,
    ContractBudgetCreateView,
    ContractBudgetListView,
    ContractBudgetUpdateView,
    FulfillmentMemoApproveView,
    FulfillmentMemoCreateView,
    FulfillmentMemoListView,
    FulfillmentMemoUpdateView,
    PaymentCancelView,
    PaymentCreateView,
    PaymentListView,
    PaymentPostView,
    PaymentReportView,
    PaymentUpdateView,
)

__all__ = [
    "ContractBudgetListView",
    "ContractBudgetCreateView",
    "ContractBudgetUpdateView",
    "ContractBudgetApproveView",
    "FulfillmentMemoListView",
    "FulfillmentMemoCreateView",
    "FulfillmentMemoUpdateView",
    "FulfillmentMemoApproveView",
    "PaymentListView",
    "PaymentReportView",
    "PaymentCreateView",
    "PaymentPostView",
    "PaymentCancelView",
    "PaymentUpdateView",
]
