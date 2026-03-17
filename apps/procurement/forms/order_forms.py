from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.dncp_integration.models import AwardItem, AwardSubItem, Lot, Party
from apps.procurement.forms.mixins import LocalizedDecimalMixin
from apps.procurement.models import ExpenseObject, PurchaseOrder, PurchaseOrderLine


class PurchaseOrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        contract = kwargs.pop("contract", None)
        super().__init__(*args, **kwargs)

        self.fields["supplier"].queryset = Party.objects.filter(role=Party.ROLE_SUPPLIER)
        self.fields["issue_date"].input_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        self.fields["expense_object"].queryset = ExpenseObject.objects.filter(is_active=True).order_by("code")

        if self.instance and self.instance.pk and self.instance.expense_object_id and not self.instance.expense_object.is_active:
            self.fields["expense_object"].queryset = ExpenseObject.objects.filter(pk=self.instance.expense_object_id)

        contract_obj = contract
        if contract_obj is None and self.instance and self.instance.pk:
            contract_obj = self.instance.contract

        if contract_obj is not None:
            self.fields["contract"].initial = contract_obj.pk
            self.fields["supplier"].queryset = contract_obj.award.suppliers.filter(role=Party.ROLE_SUPPLIER)

    class Meta:
        model = PurchaseOrder
        fields = [
            "order_number",
            "contract",
            "supplier",
            "issue_date",
            "expense_object",
            "delivery_term",
            "delivery_place",
            "status",
            "notes",
        ]
        widgets = {
            "issue_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "order_number": forms.TextInput(attrs={"class": "form-control"}),
            "contract": forms.Select(attrs={"class": "form-control select2"}),
            "supplier": forms.Select(attrs={"class": "form-control select2"}),
            "expense_object": forms.Select(attrs={"class": "form-control select2"}),
            "delivery_term": forms.TextInput(attrs={"class": "form-control"}),
            "delivery_place": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control select2"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class PurchaseOrderLineForm(LocalizedDecimalMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        contract = kwargs.pop("contract", None)
        super().__init__(*args, **kwargs)

        self.fields["lot"].queryset = Lot.objects.none()
        self.fields["award_item"].queryset = AwardItem.objects.none()
        self.fields["award_subitem"].queryset = AwardSubItem.objects.none()

        contract_obj = contract
        if contract_obj is None and self.instance and self.instance.pk:
            contract_obj = self.instance.purchase_order.contract

        if contract_obj is not None:
            self.fields["lot"].queryset = Lot.objects.filter(tender=contract_obj.award.tender).order_by("id")
            self.fields["award_item"].queryset = AwardItem.objects.filter(award=contract_obj.award).select_related("item")
            self.fields["award_subitem"].queryset = AwardSubItem.objects.filter(award=contract_obj.award).select_related("subitem")

    class Meta:
        model = PurchaseOrderLine
        fields = ["lot", "award_item", "award_subitem", "quantity", "unit_price"]
        widgets = {
            "lot": forms.Select(attrs={"class": "form-control select2"}),
            "award_item": forms.Select(attrs={"class": "form-control select2"}),
            "award_subitem": forms.Select(attrs={"class": "form-control select2"}),
            "quantity": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "decimal",
                    "autocomplete": "off",
                    "placeholder": "0",
                }
            ),
            "unit_price": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "decimal",
                    "autocomplete": "off",
                    "placeholder": "0",
                }
            ),
        }

    def clean_quantity(self):
        value = self._clean_localized_decimal_field("quantity")
        if value is None:
            return value
        if value != value.to_integral_value():
            raise ValidationError("La cantidad debe ser un numero entero.")
        return value

    def clean_unit_price(self):
        return self._clean_localized_decimal_field("unit_price")

PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=1,
    can_delete=True,
)
