import logging

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
    parse_order_decimal,
    parse_order_int,
    parse_order_subitem_number,
    parse_dt,
)

logger = logging.getLogger(__name__)


class ImportMapper:
    def _deduplicate_subitems(self, subitems):
        """
        Elimina subitems duplicados basándose en el campo 'group'.
        Si hay duplicados, mantiene el primero encontrado.
        """
        if not subitems:
            return []
        
        seen_groups = {}
        unique_subitems = []
        duplicates_found = []
        
        for subitem in subitems:
            group = subitem.get("group")
            subitem_id = subitem.get("id")
            
            if not group:
                # Sin grupo, mantener (puede ser subitem sin group)
                unique_subitems.append(subitem)
                continue
            
            if group in seen_groups:
                # Duplicado detectado
                duplicates_found.append({
                    "group": group,
                    "id": subitem_id,
                    "kept_id": seen_groups[group]
                })
                logger.warning(
                    f"Subitem duplicado detectado: group='{group}', "
                    f"id='{subitem_id}' (descartado), "
                    f"kept_id='{seen_groups[group]}'"
                )
            else:
                # Primera vez que vemos este group
                seen_groups[group] = subitem_id
                unique_subitems.append(subitem)
        
        if duplicates_found:
            logger.info(f"Se eliminaron {len(duplicates_found)} subitems duplicados")
        
        return unique_subitems
    
    def _find_original_tender_item(self, award_item, tender_items):
        """
        Encuentra el item original del tender que corresponde a un award item "fantasma".
        
        Estrategia:
        1. Comparar por número de subitems
        2. Comparar descripciones de subitems (por campo 'group')
        3. Verificar orden de subitems
        
        Args:
            award_item: Dict con datos del award item
            tender_items: Lista de dicts con datos de tender items
        
        Returns:
            Dict del tender item original, o None si no se encuentra
        """
        award_subitems = award_item.get("subItems", [])
        
        if not award_subitems:
            return None
        
        # Deduplicar subitems del award antes de comparar
        award_subitems_unique = self._deduplicate_subitems(award_subitems)
        award_subitem_count = len(award_subitems_unique)
        
        # Extraer grupos de subitems del award para comparación
        award_groups = [sub.get("group") for sub in award_subitems_unique if sub.get("group")]
        award_groups_set = set(award_groups)
        
        if len(award_groups) == 0:
            return None
        
        best_match = None
        best_match_score = 0
        candidates_checked = 0
        
        for tender_item in tender_items:
            tender_subitems = tender_item.get("subItems", [])
            
            if not tender_subitems:
                continue
            
            candidates_checked += 1
            tender_subitem_count = len(tender_subitems)
            
            # Criterio 1: Número de subitems similar (±1 por posibles duplicados)
            if abs(tender_subitem_count - award_subitem_count) > 1:
                continue
            
            # Extraer grupos de tender subitems
            tender_groups = [sub.get("group") for sub in tender_subitems if sub.get("group")]
            tender_groups_set = set(tender_groups)
            
            # Criterio 2: Intersección de grupos
            matching_groups = award_groups_set & tender_groups_set
            match_ratio = len(matching_groups) / max(len(award_groups_set), 1)
            
            # Criterio 3: Orden de los grupos (primeros 3)
            order_match = 0
            for i in range(min(3, len(award_groups), len(tender_groups))):
                if award_groups[i] == tender_groups[i]:
                    order_match += 1
            
            # Puntaje total: 60% match ratio + 40% order match
            score = (match_ratio * 0.6) + ((order_match / max(3, 1)) * 0.4)
            
            if score > best_match_score and score >= 0.5:  # Umbral del 50% (prioriza coincidencia de grupos)
                best_match_score = score
                best_match = tender_item
        
        if best_match:
            logger.info(
                f"Mapeado: award item fantasma {award_item.get('id')[:20]}... → "
                f"tender item {best_match.get('id')[:20]}... (score: {best_match_score:.2f})"
            )
        else:
            logger.warning(
                f"No se pudo mapear award item fantasma {award_item.get('id')[:20]}... a tender item"
            )
        
        return best_match
    
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
            if not lot_id or not lot.get("title"):
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
            if not item_id or not item.get("description"):
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
                    "orden": parse_order_int(get_attribute_value(item.get("attributes"), "Orden")),
                },
            )

            for subitem in item.get("subItems", []) or []:
                subitem_id = subitem.get("id") or fallback_subitem_id(item_id, subitem)
                if not subitem_id or not subitem.get("description"):
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
                        "orden": parse_order_subitem_number(subitem.get("group")),
                    },
                )

        for award in awards_data:
            award_id = award.get("id")
            if not award_id:
                continue
            
            # Skip incomplete awards (awards used only to add item attributes)
            award_date = parse_dt(award.get("date"))
            if not award_date:
                continue
            
            award_obj, _ = self._upsert(
                Award,
                lookup={"id": award_id},
                defaults={
                    "tender": tender_obj,
                    "status_details": award.get("statusDetails") or "",
                    "date": award_date,
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
                
                # Buscar el item en el índice del tender
                item_obj = item_index.get(item_id)
                create_award_item = True  # Por defecto, crear AwardItem
                
                # Si el item NO existe en el índice, es un "item fantasma"
                if not item_obj:
                    # Intentar encontrar el item original del tender
                    original_tender_item = self._find_original_tender_item(
                        item, 
                        tender_data.get("items", [])
                    )
                    
                    if original_tender_item:
                        # Usar el item original del tender
                        original_item_id = original_tender_item.get("id")
                        item_obj = item_index.get(original_item_id)
                        
                        if item_obj:
                            logger.info(
                                f"Mapeando award item fantasma '{item_id}' → "
                                f"tender item original '{original_item_id}'"
                            )
                            # NO crear AwardItem para items fantasma, solo procesar subitems
                            create_award_item = False
                        else:
                            logger.warning(
                                f"Item original '{original_item_id}' no encontrado en item_index"
                            )
                    
                    # Si aún no tenemos item_obj Y el item tiene descripción, crearlo como fallback
                    if not item_obj and item.get("description"):
                        logger.warning(
                            f"Creando ItemDefinition para award item '{item_id}' "
                            f"(no se pudo mapear a tender item)"
                        )
                        
                        classification_obj = self._upsert_classification(item.get("classification", {}))
                        item_obj, _ = self._upsert(
                            ItemDefinition,
                            lookup={"id": item_id},
                            defaults={
                                "description": item.get("description") or f"Item adjudicado {item_id}",
                                "classification": classification_obj,
                                "unit_name": item.get("unit", {}).get("name"),
                            },
                        )

                # Procesar solo si tenemos un item_obj válido
                if not item_obj:
                    logger.warning(f"No se pudo obtener item_obj para award item '{item_id}', omitiendo")
                    continue

                # Crear AwardItem solo si es necesario (items normales, no fantasma)
                if create_award_item:
                    self._upsert(
                        AwardItem,
                        lookup={"award": award_obj, "item": item_obj},
                        defaults={
                            "orden_licitado": parse_order_int(
                                get_attribute_value(item.get("attributes"), "Orden")
                            ),
                            "quantity": item.get("quantity"),
                            "unit_price_amount": get_amount(item.get("unit", {}).get("value")),
                            "unit_price_currency": self._get_currency(item.get("unit", {}).get("value", {}).get("currency")),
                        },
                    )

                # Procesar subitems (tanto para items normales como fantasma)
                subitems = item.get("subItems", []) or []
                unique_subitems = self._deduplicate_subitems(subitems)
                
                if len(unique_subitems) < len(subitems):
                    logger.info(
                        f"Item '{item_obj.id}': {len(subitems)} subitems originales → "
                        f"{len(unique_subitems)} únicos (eliminados {len(subitems) - len(unique_subitems)} duplicados)"
                    )
                
                for subitem in unique_subitems:
                    subitem_id = subitem.get("id") or fallback_subitem_id(item_obj.id, subitem)
                    if not subitem_id or not subitem.get("description"):
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

                    if subitem_obj:
                        self._upsert(
                            AwardSubItem,
                            lookup={"award": award_obj, "subitem": subitem_obj},
                            defaults={
                                "orden_licitado": parse_order_subitem_number(
                                    subitem.get("group")
                                    or get_attribute_value(subitem.get("attributes"), "Orden")
                                ),
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
        """Crea o actualiza un Party buscando por (party_id, role).
        Un mismo party_id puede existir con distintos roles (OCDS multi-rol).
        """
        if not party_id:
            return None
        name = party.get("name") or fallback_name or ""
        identifier = party.get("identifier", {}) if isinstance(party, dict) else {}
        party_obj, created = Party.objects.get_or_create(
            party_id=party_id,
            role=role,
            defaults={
                "name": name,
                "identifier_scheme": identifier.get("scheme"),
                "identifier_id": identifier.get("id"),
                "legal_name": identifier.get("legalName"),
            },
        )
        if not created and not party_obj.is_user_modified:
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
