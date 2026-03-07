from django import forms

from apps.dncp_integration.models import DNCPOrganization


class DNCPOrganizationForm(forms.ModelForm):
    class Meta:
        model = DNCPOrganization
        fields = ["code", "name", "procuring_entity_name", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: 1369"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre corto"}),
            "procuring_entity_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre exacto usado en API DNCP",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "ace"}),
        }


class DNCPOrganizationSelectForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=DNCPOrganization.objects.none(),
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Entidad activa",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = DNCPOrganization.objects.filter(is_active=True).order_by("name")
