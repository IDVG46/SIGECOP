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
    def process_tender_lots_and_items(cls, tender):
        """Procesa lotes e items del tender con su estructura completa."""
        tender_items = tender.get("items", [])
        tender_lotes = tender.get("lots", [])
        award_criteria = tender.get("awardCriteriaDetails")
        
        if award_criteria in ["Por Lote", "Por Total"]:
            # Agrupar por lotes
            lotes = []
            for lote in tender_lotes:
                lote_data = {
                    "description": lote.get("title"),
                    "id": lote.get("id"),
                    "description1": lote.get("title", "").split("-")[-1].strip(),
                    "value": cls.format_currency(lote.get("value", {}).get("amount")),
                    "min_value": cls.format_currency(lote.get("minValue", {}).get("amount")),
                    "openContractType": lote.get("openContractType") if lote.get("openContractType") is not None else "No",
                    "orden": next((attr.get("id") for attr in lote.get("attributes", []) if attr.get("name") == "Orden"), None),
                    "items": []
                }
                
                # Items del lote
                for item in tender_items:
                    if item.get("relatedLot") == lote.get("id"):
                        item_data = {
                            "description": item.get("description"),
                            "relatedLot": item.get("relatedLot"),
                            "idcatalogo": item.get("classification", {}).get("id"),
                            "quantity": item.get("quantity") if item.get("quantity") is not None else lote.get("openContractType"),
                            "unit": item.get("unit", {}).get("name"),
                            "value": f"{item.get('unit', {}).get('value', {}).get('amount', 0):,.0f}".replace(",", "."),
                            "total_value": f"{item.get('unit', {}).get('value', {}).get('amount', 0) * (item.get('quantity') or 1):,.0f}".replace(",", "."),
                            "orden": next((attr.get("value") for attr in item.get("attributes", []) if attr.get("name") == "Orden"), None),
                        }
                        lote_data["items"].append(item_data)
                
                # Ordenar items por orden
                lote_data["items"] = sorted(
                    lote_data["items"],
                    key=lambda x: float(x["orden"]) if x["orden"] and str(x["orden"]).replace('.', '', 1).isdigit() else float('inf')
                )
                lotes.append(lote_data)
            
            # Ordenar lotes por orden
            lotes = sorted(
                lotes,
                key=lambda x: float(x["orden"]) if x["orden"] and str(x["orden"]).isdigit() else float('inf')
            )
        else:
            # Lote único con todos los items
            lotes = [{
                "description": "",
                "id": "unique",
                "description1": "Todos los items",
                "value": cls.format_currency(tender.get("value", {}).get("amount")),
                "min_value": None,
                "openContractType": "No",
                "orden": "1",
                "items": [
                    {
                        "description": item.get("description"),
                        "relatedLot": item.get("relatedLot"),
                        "idcatalogo": item.get("classification", {}).get("id"),
                        "quantity": item.get("quantity"),
                        "unit": item.get("unit", {}).get("name"),
                        "value": f"{item.get('unit', {}).get('value', {}).get('amount', 0):,.0f}".replace(",", "."),
                        "total_value": f"{item.get('unit', {}).get('value', {}).get('amount', 0) * item.get('quantity', 0):,.0f}".replace(",", "."),
                        "orden": next((attr.get("value") for attr in item.get("attributes", []) if attr.get("name") == "Orden"), None),
                    }
                    for item in tender_items
                ]
            }]
        
        return lotes    
    
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