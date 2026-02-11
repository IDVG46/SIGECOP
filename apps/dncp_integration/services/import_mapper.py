from apps.dncp_integration.models import (
    Award,
    AwardItem,
    AwardSubItem,
    Classification,
    Contract,
    Currency,
    ItemDefinition,
    Lot,
    Party,
    SubItemDefinition,
    Tender,
    TenderItem,
    TenderSubItem,
)
from apps.dncp_integration.services.import_helpers import (
    extract_tender_number,
    fallback_item_id,
    fallback_subitem_id,
    get_amount,
    get_attribute_value,
    parse_dt,
)


class ImportMapper:
    def persist(self, compiled_release_obj, compiled_release):
        tender_data = compiled_release.get("tender", {})
        awards_data = compiled_release.get("awards", [])
        contracts_data = compiled_release.get("contracts", [])
        parties_data = compiled_release.get("parties", [])

        party_index = {party.get("id"): party for party in parties_data if party.get("id")}

        procuring_entity = tender_data.get("procuringEntity", {})
        procuring_entity_id = procuring_entity.get("id")
        procuring_entity_obj = None
        if procuring_entity_id:
            procuring_entity_obj = self._upsert_party(
                party_index.get(procuring_entity_id, {}),
                party_id=procuring_entity_id,
                role=Party.ROLE_PROCURING_ENTITY,
                fallback_name=procuring_entity.get("name"),
            )

        tender_id = tender_data.get("id")
        if tender_id:
            tender_obj, _ = self._upsert(
                Tender,
                lookup={"id": tender_id},
                defaults={
                    "compiled_release": compiled_release_obj,
                    "tenderID": extract_tender_number(compiled_release_obj.ocid),
                    "title": tender_data.get("title") or "",
                    "award_criteria_details": tender_data.get("awardCriteriaDetails") or "",
                    "status_details": tender_data.get("statusDetails") or "",
                    "main_procurement_category_details": tender_data.get("mainProcurementCategoryDetails") or "",
                    "value_amount": get_amount(tender_data.get("value")),
                    "value_currency": self._get_currency(tender_data.get("value", {}).get("currency")),
                    "date_published": parse_dt(tender_data.get("datePublished")),
                    "procurement_method_details": tender_data.get("procurementMethodDetails") or "",
                    "procuring_entity": procuring_entity_obj,
                },
            )
        else:
            return

        lot_index = {}
        for lot in tender_data.get("lots", []) or []:
            lot_id = lot.get("id")
            if not lot_id:
                continue
            lot_obj, _ = self._upsert(
                Lot,
                lookup={"id": lot_id},
                defaults={
                    "tender": tender_obj,
                    "title": lot.get("title") or "",
                    "status_details": lot.get("statusDetails") or "",
                    "open_contract_type": lot.get("openContractType") or "",
                    "value_amount": get_amount(lot.get("value")),
                    "value_currency": self._get_currency(lot.get("value", {}).get("currency")),
                    "min_value_amount": get_amount(lot.get("minValue")),
                    "min_value_currency": self._get_currency(lot.get("minValue", {}).get("currency")),
                },
            )
            lot_index[lot_id] = lot_obj

        item_index = {}
        for item in tender_data.get("items", []) or []:
            item_id = item.get("id") or fallback_item_id(item, prefix=tender_id)
            if not item_id:
                continue
            classification_obj = self._upsert_classification(item.get("classification", {}))
            related_lot_id = item.get("relatedLot")
            lot_obj = lot_index.get(related_lot_id)
            item_obj, _ = self._upsert(
                ItemDefinition,
                lookup={"id": item_id},
                defaults={
                    "description": item.get("description") or "",
                    "classification": classification_obj,
                    "lot": lot_obj,
                    "unit_name": item.get("unit", {}).get("name"),
                    "attributes": item.get("attributes") or None,
                },
            )
            item_index[item_id] = item_obj

            self._upsert(
                TenderItem,
                lookup={"tender": tender_obj, "item": item_obj},
                defaults={
                    "quantity": item.get("quantity"),
                    "min_quantity": item.get("minQuantity"),
                    "unit_price_amount": get_amount(item.get("unit", {}).get("value")),
                    "unit_price_currency": self._get_currency(item.get("unit", {}).get("value", {}).get("currency")),
                    "orden": get_attribute_value(item.get("attributes"), "Orden"),
                },
            )

            for subitem in item.get("subItems", []) or []:
                subitem_id = subitem.get("id") or fallback_subitem_id(item_id, subitem)
                if not subitem_id:
                    continue
                subitem_obj, _ = self._upsert(
                    SubItemDefinition,
                    lookup={"id": subitem_id},
                    defaults={
                        "item": item_obj,
                        "description": subitem.get("description") or "",
                        "unit_name": subitem.get("unit", {}).get("name"),
                        "attributes": subitem.get("attributes") or None,
                    },
                )

                self._upsert(
                    TenderSubItem,
                    lookup={"tender": tender_obj, "subitem": subitem_obj},
                    defaults={
                        "quantity": subitem.get("quantity"),
                        "min_quantity": subitem.get("minQuantity"),
                        "unit_price_amount": get_amount(subitem.get("unit", {}).get("value")),
                        "unit_price_currency": self._get_currency(
                            subitem.get("unit", {}).get("value", {}).get("currency")
                        ),
                        "orden": subitem.get("group"),
                    },
                )

        for award in awards_data:
            award_id = award.get("id")
            if not award_id:
                continue
            award_obj, _ = self._upsert(
                Award,
                lookup={"id": award_id},
                defaults={
                    "tender": tender_obj,
                    "status_details": award.get("statusDetails") or "",
                    "date": parse_dt(award.get("date")),
                    "value_amount": get_amount(award.get("value")),
                    "value_currency": self._get_currency(award.get("value", {}).get("currency")),
                },
            )

            supplier_objs = []
            for supplier in award.get("suppliers", []) or []:
                supplier_id = supplier.get("id")
                if not supplier_id:
                    continue
                supplier_obj = self._upsert_party(
                    party_index.get(supplier_id, {}),
                    party_id=supplier_id,
                    role=Party.ROLE_SUPPLIER,
                    fallback_name=supplier.get("name"),
                )
                if supplier_obj:
                    supplier_objs.append(supplier_obj)
            if supplier_objs and not award_obj.is_user_modified:
                award_obj.suppliers.set(supplier_objs)

            for item in award.get("items", []) or []:
                item_id = item.get("id") or fallback_item_id(item, prefix=award_id)
                if not item_id:
                    continue
                item_obj = item_index.get(item_id)
                if not item_obj:
                    classification_obj = self._upsert_classification(item.get("classification", {}))
                    item_obj, _ = self._upsert(
                        ItemDefinition,
                        lookup={"id": item_id},
                        defaults={
                            "description": item.get("description") or "",
                            "classification": classification_obj,
                            "unit_name": item.get("unit", {}).get("name"),
                        },
                    )

                self._upsert(
                    AwardItem,
                    lookup={"award": award_obj, "item": item_obj},
                    defaults={
                        "quantity": item.get("quantity"),
                        "unit_price_amount": get_amount(item.get("unit", {}).get("value")),
                        "unit_price_currency": self._get_currency(item.get("unit", {}).get("value", {}).get("currency")),
                    },
                )

                for subitem in item.get("subItems", []) or []:
                    subitem_id = subitem.get("id") or fallback_subitem_id(item_id, subitem)
                    if not subitem_id:
                        continue
                    subitem_obj, _ = self._upsert(
                        SubItemDefinition,
                        lookup={"id": subitem_id},
                        defaults={
                            "item": item_obj,
                            "description": subitem.get("description") or "",
                            "unit_name": subitem.get("unit", {}).get("name"),
                            "attributes": subitem.get("attributes") or None,
                        },
                    )

                    self._upsert(
                        AwardSubItem,
                        lookup={"award": award_obj, "subitem": subitem_obj},
                        defaults={
                            "quantity": subitem.get("quantity"),
                            "unit_price_amount": get_amount(subitem.get("unit", {}).get("value")),
                            "unit_price_currency": self._get_currency(
                                subitem.get("unit", {}).get("value", {}).get("currency")
                            ),
                        },
                    )

        for contract in contracts_data:
            contract_id = contract.get("id")
            award_id = contract.get("awardID")
            award_obj = Award.objects.filter(id=award_id).first()
            if not contract_id or not award_obj:
                continue
            self._upsert(
                Contract,
                lookup={"id": contract_id},
                defaults={
                    "award": award_obj,
                    "status_details": contract.get("statusDetails") or "",
                    "period_start_date": parse_dt(contract.get("period", {}).get("startDate")),
                    "period_end_date": parse_dt(contract.get("period", {}).get("endDate")),
                    "value_amount": get_amount(contract.get("value")),
                    "value_currency": self._get_currency(contract.get("value", {}).get("currency")),
                },
            )

    def _get_currency(self, code):
        if not code:
            return None
        currency, _ = Currency.objects.get_or_create(
            code=code,
            defaults={"name": code, "symbol": None},
        )
        return currency

    def _upsert_classification(self, classification):
        if not isinstance(classification, dict):
            return None
        class_id = classification.get("id")
        if not class_id:
            return None
        return self._upsert(
            Classification,
            lookup={"id": class_id},
            defaults={
                "description": classification.get("description") or "",
            },
        )[0]

    def _upsert_party(self, party, party_id, role, fallback_name=None):
        if not party_id:
            return None
        name = party.get("name") or fallback_name or ""
        identifier = party.get("identifier", {}) if isinstance(party, dict) else {}
        party_obj, created = Party.objects.get_or_create(
            party_id=party_id,
            defaults={
                "name": name,
                "role": role,
                "identifier_scheme": identifier.get("scheme"),
                "identifier_id": identifier.get("id"),
                "legal_name": identifier.get("legalName"),
            },
        )
        if not created and not party_obj.is_user_modified:
            if party_obj.role == role:
                party_obj.name = name or party_obj.name
                party_obj.identifier_scheme = identifier.get("scheme") or party_obj.identifier_scheme
                party_obj.identifier_id = identifier.get("id") or party_obj.identifier_id
                party_obj.legal_name = identifier.get("legalName") or party_obj.legal_name
                party_obj.save(update_fields=[
                    "name",
                    "identifier_scheme",
                    "identifier_id",
                    "legal_name",
                ])
        return party_obj

    def _upsert(self, model_cls, lookup, defaults):
        obj, created = model_cls.objects.get_or_create(**lookup, defaults=defaults)
        if created:
            return obj, created
        if getattr(obj, "is_user_modified", False):
            return obj, created
        for key, value in defaults.items():
            setattr(obj, key, value)
        obj.save(update_fields=list(defaults.keys()))
        return obj, created
