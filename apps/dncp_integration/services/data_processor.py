from datetime import datetime


class DNCPDataProcessor:
    """Procesa y transforma datos crudos de la API DNCP."""

    @staticmethod
    def format_date(date_str):
        """Convierte ISO date a formato legible (dd/mm/yyyy HH:MM)."""
        if not date_str:
            return None
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            return None

    @staticmethod
    def format_currency(amount, currency="Gs."):
        """Formatea monto como moneda (ej: Gs. 1.000.000)."""
        if amount is None:
            return None
        return f"{currency} {amount:,.0f}".replace(",", ".")

    @staticmethod
    def extract_ocid_number(ocid):
        """Extrae número del OCID (ej: 'ocid-xxx-1234' -> '1234')."""
        if not ocid:
            return None
        parts = ocid.split("-")
        return parts[2] if len(parts) > 2 else None

    @classmethod
    def process_process_list(cls, records):
        """Procesa lista de procesos de licitación de la API."""
        licitaciones = []
        ocid_list = []

        for record in records:
            compiled_release = record.get("compiledRelease", {})
            tender = compiled_release.get("tender", {})
            ocid = record.get("ocid", "")

            ocid_list.append({"ocid": ocid, "start_date": tender.get("tenderPeriod", {}).get("startDate")})

            licitaciones.append({
                "ocid": ocid,
                "id": cls.extract_ocid_number(ocid),
                "title": tender.get("title"),
                "procuringEntity": tender.get("procuringEntity", {}).get("name"),
                "status": tender.get("statusDetails"),
                "category": tender.get("mainProcurementCategoryDetails"),
                "method": tender.get("procurementMethodDetails"),
                "start_date": cls.format_date(tender.get("tenderPeriod", {}).get("startDate")),
                "end_date": cls.format_date(tender.get("tenderPeriod", {}).get("endDate")),
            })

        return licitaciones, ocid_list
    
    @classmethod
    def process_record_detail(cls, record):
        """Procesa detalles de un proceso individual."""
        compiled_release = record.get("compiledRelease", {})
        tender = compiled_release.get("tender", {})
        awards = compiled_release.get("awards", [])
        ocid = record.get("ocid", "")

        tender_data = {
            "ocid": ocid,
            "id": cls.extract_ocid_number(ocid),
            "title": tender.get("title"),
            "procuringEntity": tender.get("procuringEntity", {}).get("name"),
            "category": tender.get("mainProcurementCategoryDetails"),
            "method": tender.get("procurementMethodDetails"),
            "status": tender.get("statusDetails"),
            "awardCriteriaDetails": tender.get("awardCriteriaDetails"),
            "value": cls.format_currency(tender.get("value", {}).get("amount")),
            "currency": tender.get("value", {}).get("currency"),
            "start_date": cls.format_date(tender.get("tenderPeriod", {}).get("startDate")),
            "end_date": cls.format_date(tender.get("tenderPeriod", {}).get("endDate")),
        }

        awards_list = []
        for award in awards:
            award_items = award.get("items", [])
            awards_list.append({
                "title": award.get("title"),
                "status": award.get("status"),
                "date": cls.format_date(award.get("date")),
                "value": cls.format_currency(award.get("value", {}).get("amount")),
                "supplier": award.get("suppliers", [{}])[0].get("name"),
                "items": [
                    {
                        "description": item.get("description"),
                        "quantity": item.get("quantity"),
                        "unit": item.get("unit", {}).get("name"),
                        "value": cls.format_currency(item.get("value", {}).get("amount")),
                    }
                    for item in award_items
                ],
            })

        return tender_data, awards_list