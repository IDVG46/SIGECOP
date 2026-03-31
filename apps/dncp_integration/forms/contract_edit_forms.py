from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import modelformset_factory
from django.utils import timezone
from apps.dncp_integration.models import (
    Contract,
    ContractExtra,
    Award,
    AwardItem,
    AwardSubItem,
    Currency,
    Party,
)


class ContractEditForm(forms.ModelForm):
    """Formulario para editar datos basicos del contrato"""

    contract_number = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Numero interno/legible del contrato",
            }
        ),
    )
    resolution_number = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Numero de resolucion",
            }
        ),
    )
    resolution_sender = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Ej.: la Rectoría, el Consejo Directivo",
            }
        ),
    )
    resolution_article = forms.CharField(
        required=False,
        max_length=50,
        label="N° Artículo (designa al Administrador/a)",
        help_text="Artículo de la resolución que designa al administrador/a del contrato. Ej.: 2",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Ej.: 2",
            }
        ),
    )
    contract_administrator = forms.CharField(
        required=False,
        max_length=255,
        label="Administrador/a del Contrato",
        help_text="Nombre del/la responsable de la administración del contrato (Jefa/e División de Control de Contratos)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Ej.: Ing. María García",
            }
        ),
    )

    period_start_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control form-control-sm",
                "type": "datetime-local",
            },
        ),
    )
    period_end_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control form-control-sm",
                "type": "datetime-local",
            },
        ),
    )
    value_amount = forms.DecimalField(
        required=False,
        max_digits=18,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm money-input",
                "inputmode": "decimal",
                "placeholder": "Monto",
            }
        ),
    )

    class Meta:
        model = Contract
        fields = ['status_details', 'period_start_date', 'period_end_date', 'value_amount']
        widgets = {
            'status_details': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Estado del contrato'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.extra_instance = kwargs.pop("extra_instance", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.period_start_date:
            start_date = self.instance.period_start_date
            if timezone.is_aware(start_date):
                start_date = timezone.localtime(start_date)
            self.initial["period_start_date"] = start_date.strftime("%Y-%m-%dT%H:%M")
        if self.instance and self.instance.period_end_date:
            end_date = self.instance.period_end_date
            if timezone.is_aware(end_date):
                end_date = timezone.localtime(end_date)
            self.initial["period_end_date"] = end_date.strftime("%Y-%m-%dT%H:%M")

        if self.extra_instance:
            self.initial["contract_number"] = self.extra_instance.contract_number
            self.initial["resolution_number"] = self.extra_instance.resolution_number
            self.initial["resolution_sender"] = self.extra_instance.resolution_sender
            self.initial["resolution_article"] = self.extra_instance.resolution_article
            self.initial["contract_administrator"] = self.extra_instance.contract_administrator

    def clean_value_amount(self):
        raw_value = self.cleaned_data.get("value_amount")
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, Decimal):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.replace(".", "").replace(",", ".").strip()
            try:
                return Decimal(normalized)
            except InvalidOperation:
                raise forms.ValidationError("Monto invalido.")
        return raw_value

    def save_extra(self, user=None):
        if self.instance is None or self.instance.pk is None:
            return None

        extra = self.extra_instance
        if extra is None:
            extra, _ = ContractExtra.objects.get_or_create(contract=self.instance)

        extra.contract_number = self.cleaned_data.get("contract_number", "") or ""
        extra.resolution_number = self.cleaned_data.get("resolution_number", "") or ""
        extra.resolution_sender = self.cleaned_data.get("resolution_sender", "") or ""
        extra.resolution_article = self.cleaned_data.get("resolution_article", "") or ""
        extra.contract_administrator = self.cleaned_data.get("contract_administrator", "") or ""
        if user is not None:
            extra.is_user_modified = True
            extra.modified_by = user
        extra.save()
        self.extra_instance = extra
        return extra


class AwardEditForm(forms.ModelForm):
    """Formulario para editar datos basicos de la adjudicacion"""

    date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control form-control-sm",
                "type": "datetime-local",
            },
        ),
    )
    value_amount = forms.DecimalField(
        required=False,
        max_digits=18,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm money-input",
                "inputmode": "decimal",
                "placeholder": "Monto",
            }
        ),
    )

    suppliers = forms.ModelMultipleChoiceField(
        queryset=Party.objects.filter(role=Party.ROLE_SUPPLIER),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Proveedores"
    )
    
    class Meta:
        model = Award
        fields = ['status_details', 'date', 'value_amount']
        widgets = {
            'status_details': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Estado de adjudicación'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.date:
            award_date = self.instance.date
            if timezone.is_aware(award_date):
                award_date = timezone.localtime(award_date)
            self.initial["date"] = award_date.strftime("%Y-%m-%dT%H:%M")

    def clean_value_amount(self):
        raw_value = self.cleaned_data.get("value_amount")
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, Decimal):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.replace(".", "").replace(",", ".").strip()
            try:
                return Decimal(normalized)
            except InvalidOperation:
                raise forms.ValidationError("Monto invalido.")
        return raw_value


class AwardItemEditForm(forms.ModelForm):
    """Formulario para editar items de adjudicación"""
    
    class Meta:
        model = AwardItem
        fields = ['quantity', 'unit_price_amount']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '1',
                'min': '0',
                'data-field': 'quantity',
                'placeholder': 'Cantidad'
            }),
            'unit_price_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '0.01',
                'min': '0',
                'data-field': 'unit_price_amount',
                'placeholder': 'Precio unitario'
            }),
        }


class AwardSubItemEditForm(forms.ModelForm):
    """Formulario para editar subitems de adjudicación"""
    
    class Meta:
        model = AwardSubItem
        fields = ['quantity', 'unit_price_amount']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '1',
                'min': '0',
                'data-field': 'quantity',
                'placeholder': 'Cantidad'
            }),
            'unit_price_amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm inline-edit',
                'step': '0.01',
                'min': '0',
                'data-field': 'unit_price_amount',
                'placeholder': 'Precio unitario'
            }),
        }


# FormSets para edición bulk de items y subitems
AwardItemFormSet = modelformset_factory(
    AwardItem,
    form=AwardItemEditForm,
    extra=0,
    can_delete=False,
    fields=['quantity', 'unit_price_amount']
)

AwardSubItemFormSet = modelformset_factory(
    AwardSubItem,
    form=AwardSubItemEditForm,
    extra=0,
    can_delete=False,
    fields=['quantity', 'unit_price_amount']
)


class AwardChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        tender_id = getattr(obj.tender, "tenderID", "-") if obj.tender else "-"
        return f"{obj.id} | Licitacion {tender_id}"


class ContractManualCreateForm(forms.Form):
    award = AwardChoiceField(
        queryset=Award.objects.select_related("tender").order_by("-date"),
        label="Adjudicacion asociada",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    contract_id = forms.CharField(
        required=False,
        max_length=255,
        label="ID de contrato",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Si se deja vacio, se genera automaticamente",
            }
        ),
    )
    status_details = forms.CharField(
        required=False,
        max_length=50,
        label="Estado",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    period_start_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"class": "form-control", "type": "datetime-local"},
        ),
    )
    period_end_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"class": "form-control", "type": "datetime-local"},
        ),
    )
    value_amount = forms.DecimalField(
        required=False,
        max_digits=18,
        decimal_places=2,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Monto"}),
    )
    value_currency = forms.ModelChoiceField(
        queryset=Currency.objects.all().order_by("code"),
        required=False,
        empty_label="Seleccionar moneda",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    contract_number = forms.CharField(
        required=False,
        max_length=100,
        label="Numero de contrato",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    resolution_number = forms.CharField(
        required=False,
        max_length=100,
        label="Numero de resolucion",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    resolution_sender = forms.CharField(
        required=False,
        max_length=255,
        label="Remitente de la resolucion",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    resolution_article = forms.CharField(
        required=False,
        max_length=50,
        label="Articulo de designacion",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contract_administrator = forms.CharField(
        required=False,
        max_length=255,
        label="Administrador/a del contrato",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def clean_contract_id(self):
        contract_id = (self.cleaned_data.get("contract_id") or "").strip()
        if not contract_id:
            return ""
        if Contract.objects.filter(id=contract_id).exists():
            raise forms.ValidationError("Ya existe un contrato con ese ID.")
        return contract_id

    def clean_value_amount(self):
        raw_value = self.cleaned_data.get("value_amount")
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, Decimal):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.replace(".", "").replace(",", ".").strip()
            try:
                return Decimal(normalized)
            except InvalidOperation:
                raise forms.ValidationError("Monto invalido.")
        return raw_value
