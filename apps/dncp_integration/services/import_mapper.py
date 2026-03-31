import json
import logging
from collections import defaultdict
from decimal import Decimal, InvalidOperation

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

_OPEN_CONTRACT_TYPES = {"monto", "por monto", "cantidad"}


class ImportMapper:
    def __init__(self):
        self._special_case_counts = defaultdict(int)
        self._special_case_examples = defaultdict(list)

    def _reset_special_cases(self):
        self._special_case_counts = defaultdict(int)
        self._special_case_examples = defaultdict(list)

    def _record_special_case(self, code, message, **context):
        self._special_case_counts[code] += 1
        # Guardar solo ejemplos por codigo para mantener el reporte breve.
        if len(self._special_case_examples[code]) < 3:
            self._special_case_examples[code].append(
                {
                    "message": message,
                    "context": context,
                }
            )

    def _flush_special_case_report(self, compiled_release_obj, tender_id):
        if not self._special_case_counts:
            return

        counts = dict(sorted(self._special_case_counts.items(), key=lambda kv: (-kv[1], kv[0])))
        compact_counts = ", ".join(f"{code}:{count}" for code, count in counts.items())

        logger.warning(
            "SPECIAL_CASE_SUMMARY ocid=%s tender_id=%s total=%s codes=%s",
            compiled_release_obj.ocid,
            tender_id,
            sum(counts.values()),
            compact_counts,
        )

        summary = {
            "ocid": compiled_release_obj.ocid,
            "tender_id": tender_id,
            "total_special_cases": sum(counts.values()),
            "special_case_counts": counts,
            "examples_by_code": self._special_case_examples,
        }
        logger.warning("SPECIAL_CASE_REPORT %s", json.dumps(summary, ensure_ascii=True))

    def _is_open_lot(self, lot_obj):
        open_type = (getattr(lot_obj, "open_contract_type", "") or "").strip().lower()
        return open_type in _OPEN_CONTRACT_TYPES

    def _sync_non_open_lot_amounts_from_award(self, award_obj, tender_id=None, contract_id=None):
        """Sincroniza Lot.value_amount con suma adjudicada de AwardItem para lotes no abiertos.

        Regla: solo aplica a lotes que NO son abiertos por monto/cantidad.
        """
        if not award_obj:
            return

        lot_totals = defaultdict(lambda: Decimal("0"))
        lot_currency = {}

        award_items = AwardItem.objects.select_related("item__lot", "unit_price_currency").filter(award=award_obj)

        for award_item in award_items:
            item_obj = getattr(award_item, "item", None)
            lot_obj = getattr(item_obj, "lot", None) if item_obj is not None else None
            if lot_obj is None:
                continue
            if self._is_open_lot(lot_obj):
                continue

            qty = award_item.quantity
            unit_price = award_item.unit_price_amount
            if qty is None or unit_price is None:
                continue

            lot_totals[lot_obj.id] += Decimal(str(qty)) * unit_price
            if lot_obj.id not in lot_currency and award_item.unit_price_currency_id:
                lot_currency[lot_obj.id] = award_item.unit_price_currency

        for lot_id, total in lot_totals.items():
            lot_obj = Lot.objects.filter(id=lot_id).first()
            if lot_obj is None:
                continue
            if getattr(lot_obj, "is_user_modified", False):
                self._record_special_case(
                    "lot_amount_sync_skipped_user_modified",
                    "lote marcado como modificado por usuario; no se sincroniza monto",
                    tender_id=tender_id,
                    contract_id=contract_id,
                    award_id=award_obj.id,
                    lot_id=lot_id,
                )
                continue

            update_fields = []
            if lot_obj.value_amount != total:
                lot_obj.value_amount = total
                update_fields.append("value_amount")

            if lot_obj.value_currency_id is None and lot_id in lot_currency:
                lot_obj.value_currency = lot_currency[lot_id]
                update_fields.append("value_currency")

            if update_fields:
                lot_obj.save(update_fields=update_fields)
                self._record_special_case(
                    "lot_amount_synced_from_award_items",
                    "monto de lote sincronizado desde items adjudicados para contrato no abierto",
                    tender_id=tender_id,
                    contract_id=contract_id,
                    award_id=award_obj.id,
                    lot_id=lot_id,
                    synced_amount=str(total),
                )

    def _resolve_item_amount_and_currency(self, *, item, tender_id, context, award_id=None):
        """Obtiene monto/currency de item, con fallback por suma de subitems.

        Retorna (amount, currency, is_fallback).
        is_fallback=True indica que el monto fue calculado desde subitems, no del
        campo unit.value.amount del propio item. El llamador puede usar este flag
        para evitar sobreescribir un monto directo ya persistido.
        """
        unit_value = (item or {}).get("unit", {}).get("value", {})
        item_amount = get_amount(unit_value)
        item_currency = unit_value.get("currency")

        if item_amount is not None:
            return item_amount, item_currency, False

        subitems = (item or {}).get("subItems", []) or []
        total = Decimal("0")
        has_amount = False
        currencies = set()

        for subitem in subitems:
            sub_value = (subitem or {}).get("unit", {}).get("value", {})
            sub_amount_raw = get_amount(sub_value)
            if sub_amount_raw is None:
                continue

            try:
                sub_amount = Decimal(str(sub_amount_raw))
            except (InvalidOperation, TypeError, ValueError):
                continue

            sub_qty_raw = subitem.get("quantity")
            try:
                sub_qty = Decimal(str(sub_qty_raw)) if sub_qty_raw is not None else Decimal("1")
            except (InvalidOperation, TypeError, ValueError):
                sub_qty = Decimal("1")

            total += sub_amount * sub_qty
            has_amount = True

            sub_currency = sub_value.get("currency")
            if sub_currency:
                currencies.add(sub_currency)

        if not has_amount:
            return None, item_currency, False

        if item_currency:
            resolved_currency = item_currency
        elif len(currencies) == 1:
            resolved_currency = next(iter(currencies))
        else:
            resolved_currency = None

        self._record_special_case(
            "item_amount_fallback_from_subitems",
            "monto de item calculado desde subitems por falta de unit.value.amount",
            tender_id=tender_id,
            context=context,
            award_id=award_id,
            item_id=item.get("id"),
            subitems_count=len(subitems),
            resolved_currency=resolved_currency,
        )

        return total, resolved_currency, True

    def _build_lot_resolution_strategy(self, tender_id, tender_items, lot_index, lot_order_index):
        """Define estrategia por licitación para resolver lotes de items.

        Regla general: usar relatedLot.
        Caso especial automático: si relatedLot viene masivamente inconsistente,
        habilitar fallback por Orden para los items con relatedLot inválido.
        """
        items = tender_items or []
        total_items = len(items)
        if total_items == 0:
            return {
                "allow_order_fallback_on_related_lot_mismatch": False,
                "reason": "no_items",
            }

        with_related_lot = 0
        related_lot_matches = 0
        invalid_related_with_order_match = 0

        for item in items:
            related_lot_id = item.get("relatedLot")
            item_order = parse_order_int(get_attribute_value(item.get("attributes"), "Orden"))
            if related_lot_id:
                with_related_lot += 1
                if related_lot_id in lot_index:
                    related_lot_matches += 1
                elif item_order is not None and item_order in lot_order_index:
                    invalid_related_with_order_match += 1

        mismatch_count = with_related_lot - related_lot_matches
        mismatch_ratio = (mismatch_count / with_related_lot) if with_related_lot else 0
        order_recoverable_ratio = (
            (invalid_related_with_order_match / mismatch_count) if mismatch_count else 0
        )

        # Caso especial: inconsistencia masiva de IDs en relatedLot,
        # pero mapeo por Orden mayoritariamente confiable.
        allow_order_fallback = (
            with_related_lot > 0
            and mismatch_ratio >= 0.60
            and order_recoverable_ratio >= 0.80
        )

        logger.info(
            "Tender %s: estrategia lotes/items | total_items=%s with_relatedLot=%s "
            "relatedLot_match=%s mismatch_ratio=%.2f order_recoverable_ratio=%.2f "
            "order_fallback_especial=%s",
            tender_id,
            total_items,
            with_related_lot,
            related_lot_matches,
            mismatch_ratio,
            order_recoverable_ratio,
            allow_order_fallback,
        )

        return {
            "allow_order_fallback_on_related_lot_mismatch": allow_order_fallback,
            "reason": "massive_relatedlot_inconsistency" if allow_order_fallback else "default",
        }

    def _resolve_item_lot(
        self,
        *,
        tender_id,
        item,
        lot_index,
        lot_order_index,
        single_lot_fallback,
        strategy,
    ):
        """Resuelve el lote de un item priorizando relatedLot.

        Reglas:
        1) Siempre priorizar relatedLot cuando exista y sea válido.
        2) Aplicar fallback solo en casos especiales explícitos.
        """
        related_lot_id = item.get("relatedLot")
        item_order = parse_order_int(get_attribute_value(item.get("attributes"), "Orden"))

        if related_lot_id:
            lot_obj = lot_index.get(related_lot_id)
            if lot_obj is not None:
                return lot_obj

            # Caso especial automático: relatedLot inválido con mapeo por Orden confiable.
            if strategy.get("allow_order_fallback_on_related_lot_mismatch") and item_order is not None:
                lot_by_order = lot_order_index.get(item_order)
                if lot_by_order is not None:
                    logger.warning(
                        "Tender %s: relatedLot='%s' inconsistente. "
                        "Caso especial masivo: se corrige por Orden=%s al lote '%s'.",
                        tender_id,
                        related_lot_id,
                        item_order,
                        lot_by_order.id,
                    )
                    self._record_special_case(
                        "relatedlot_mismatch_corrected_by_order",
                        "relatedLot inconsistente corregido por Orden",
                        tender_id=tender_id,
                        related_lot_id=related_lot_id,
                        orden=item_order,
                        lot_id=lot_by_order.id,
                    )
                    return lot_by_order

            if single_lot_fallback is not None:
                logger.warning(
                    "Tender %s: item con relatedLot='%s' inexistente. "
                    "Caso especial single-lot: se asigna lote '%s'.",
                    tender_id,
                    related_lot_id,
                    single_lot_fallback.id,
                )
                self._record_special_case(
                    "single_lot_fallback_relatedlot_invalid",
                    "relatedLot invalido en single-lot, se asigna unico lote",
                    tender_id=tender_id,
                    related_lot_id=related_lot_id,
                    lot_id=single_lot_fallback.id,
                )
                return single_lot_fallback

            logger.warning(
                "Tender %s: item con relatedLot='%s' no coincide con lots[].id "
                "(multi-lote). Item omitido para evitar asignación incorrecta.",
                tender_id,
                related_lot_id,
            )
            self._record_special_case(
                "relatedlot_mismatch_item_omitted",
                "relatedLot no coincide en multi-lote, item omitido",
                tender_id=tender_id,
                related_lot_id=related_lot_id,
            )
            return None

        # relatedLot ausente: solo usar fallback en casos especiales.
        if single_lot_fallback is not None:
            logger.warning(
                "Tender %s: item sin relatedLot. "
                "Caso especial single-lot: se asigna lote '%s'.",
                tender_id,
                single_lot_fallback.id,
            )
            self._record_special_case(
                "single_lot_fallback_missing_relatedlot",
                "item sin relatedLot en single-lot",
                tender_id=tender_id,
                lot_id=single_lot_fallback.id,
            )
            return single_lot_fallback

        if item_order is not None:
            lot_by_order = lot_order_index.get(item_order)
            if lot_by_order is not None:
                logger.warning(
                    "Tender %s: item sin relatedLot. "
                    "Caso especial por Orden=%s: se asigna lote '%s'.",
                    tender_id,
                    item_order,
                    lot_by_order.id,
                )
                self._record_special_case(
                    "order_fallback_missing_relatedlot",
                    "item sin relatedLot corregido por Orden",
                    tender_id=tender_id,
                    orden=item_order,
                    lot_id=lot_by_order.id,
                )
                return lot_by_order

        logger.warning(
            "Tender %s: item sin relatedLot y sin fallback confiable. Item omitido.",
            tender_id,
        )
        self._record_special_case(
            "missing_relatedlot_item_omitted",
            "item sin relatedLot ni fallback confiable",
            tender_id=tender_id,
        )
        return None

    def _has_required_tender_item_data(self, item, tender_id):
        item_id = item.get("id") or fallback_item_id(item, prefix=tender_id)
        if not item_id:
            return False, "id"
        if not item.get("description"):
            return False, "description"
        return True, item_id

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
        self._reset_special_cases()
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
            self._record_special_case(
                "missing_tender_id",
                "compiledRelease sin tender.id, no se persiste tender",
                ocid=compiled_release_obj.ocid,
            )
            self._flush_special_case_report(compiled_release_obj, tender_id=None)
            return

        lot_index = {}
        lot_order_index = {}
        for lot in tender_data.get("lots", []) or []:
            lot_id = lot.get("id")
            if not lot_id or not lot.get("title"):
                self._record_special_case(
                    "lot_incomplete_omitted",
                    "lote omitido por dato obligatorio faltante",
                    tender_id=tender_id,
                    lot_id=lot_id,
                    has_title=bool(lot.get("title")),
                )
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
            lot_order = parse_order_int(get_attribute_value(lot.get("attributes"), "Orden"))
            if lot_order is not None and lot_order not in lot_order_index:
                lot_order_index[lot_order] = lot_obj

        # Precomputar fallback para inconsistencias en el API: cuando hay exactamente
        # un lote pero los items apuntan a un relatedLot con ID diferente al almacenado.
        _single_lot_fallback = next(iter(lot_index.values())) if len(lot_index) == 1 else None

        item_index = {}
        lot_resolution_strategy = self._build_lot_resolution_strategy(
            tender_id,
            tender_data.get("items", []) or [],
            lot_index,
            lot_order_index,
        )
        for item in tender_data.get("items", []) or []:
            is_complete, item_id_or_missing = self._has_required_tender_item_data(item, tender_id)
            if not is_complete:
                logger.warning(
                    "Tender %s: item omitido por dato obligatorio faltante (%s).",
                    tender_id,
                    item_id_or_missing,
                )
                self._record_special_case(
                    "tender_item_incomplete_omitted",
                    "item de licitacion omitido por dato faltante",
                    tender_id=tender_id,
                    missing_field=item_id_or_missing,
                )
                continue

            item_id = item_id_or_missing
            classification_obj = self._upsert_classification(item.get("classification", {}))
            lot_obj = self._resolve_item_lot(
                tender_id=tender_id,
                item=item,
                lot_index=lot_index,
                lot_order_index=lot_order_index,
                single_lot_fallback=_single_lot_fallback,
                strategy=lot_resolution_strategy,
            )

            # Si el tender define lotes, el item debe quedar ligado a uno.
            if lot_index and lot_obj is None:
                logger.warning(
                    "Tender %s: item '%s' omitido por no poder resolver lote de forma confiable.",
                    tender_id,
                    item_id,
                )
                self._record_special_case(
                    "tender_item_unresolved_lot_omitted",
                    "item omitido por lote no resoluble",
                    tender_id=tender_id,
                    item_id=item_id,
                )
                continue

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

            item_amount, item_currency, _fallback = self._resolve_item_amount_and_currency(
                item=item,
                tender_id=tender_id,
                context="tender_item",
            )

            self._upsert(
                TenderItem,
                lookup={"tender": tender_obj, "item": item_obj},
                defaults={
                    "quantity": item.get("quantity") or 1,
                    "min_quantity": item.get("minQuantity"),
                    "unit_price_amount": item_amount,
                    "unit_price_currency": self._get_currency(item_currency),
                    "orden": parse_order_int(get_attribute_value(item.get("attributes"), "Orden")),
                },
            )

            for subitem in item.get("subItems", []) or []:
                subitem_id = subitem.get("id") or fallback_subitem_id(item_id, subitem)
                if not subitem_id or not subitem.get("description"):
                    self._record_special_case(
                        "tender_subitem_incomplete_omitted",
                        "subitem de licitacion omitido por dato faltante",
                        tender_id=tender_id,
                        item_id=item_id,
                        subitem_id=subitem_id,
                        has_description=bool(subitem.get("description")),
                    )
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
                        "quantity": subitem.get("quantity") or 1,
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
                self._record_special_case(
                    "award_missing_id_omitted",
                    "award omitido por id faltante",
                    tender_id=tender_id,
                )
                continue
            
            # Skip incomplete awards (awards used only to add item attributes)
            award_date = parse_dt(award.get("date"))
            if not award_date:
                self._record_special_case(
                    "award_incomplete_omitted",
                    "award omitido por fecha faltante/invalida",
                    tender_id=tender_id,
                    award_id=award_id,
                )
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
                    self._record_special_case(
                        "award_item_missing_id_omitted",
                        "item adjudicado omitido por id y fallback vacios",
                        tender_id=tender_id,
                        award_id=award_id,
                    )
                    continue
                
                # Buscar el item en el índice del tender
                item_obj = item_index.get(item_id)
                
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
                            self._record_special_case(
                                "award_item_ghost_mapped",
                                "item adjudicado fantasma mapeado a item original",
                                tender_id=tender_id,
                                award_id=award_id,
                                award_item_id=item_id,
                                mapped_item_id=original_item_id,
                            )
                        else:
                            logger.warning(
                                f"Item original '{original_item_id}' no encontrado en item_index"
                            )
                            self._record_special_case(
                                "award_item_ghost_mapping_failed",
                                "item adjudicado fantasma no encontro item original en index",
                                tender_id=tender_id,
                                award_id=award_id,
                                award_item_id=item_id,
                                original_item_id=original_item_id,
                            )
                    
                    # Si aún no tenemos item_obj Y el item tiene descripción, crearlo como fallback
                    if not item_obj and item.get("description"):
                        logger.warning(
                            f"Creando ItemDefinition para award item '{item_id}' "
                            f"(no se pudo mapear a tender item)"
                        )
                        self._record_special_case(
                            "award_item_fallback_created",
                            "creado ItemDefinition fallback para award item",
                            tender_id=tender_id,
                            award_id=award_id,
                            award_item_id=item_id,
                        )
                        
                        classification_obj = self._upsert_classification(item.get("classification", {}))
                        item_obj, _ = self._upsert(
                            ItemDefinition,
                            lookup={"id": item_id},
                            defaults={
                                "description": item.get("description"),
                                "classification": classification_obj,
                                "unit_name": item.get("unit", {}).get("name"),
                            },
                        )

                # Procesar solo si tenemos un item_obj válido
                if not item_obj:
                    logger.warning(f"No se pudo obtener item_obj para award item '{item_id}', omitiendo")
                    self._record_special_case(
                        "award_item_unresolved_omitted",
                        "item adjudicado omitido por no resolver item_obj",
                        tender_id=tender_id,
                        award_id=award_id,
                        award_item_id=item_id,
                    )
                    continue

                item_amount, item_currency, is_fallback_amount = self._resolve_item_amount_and_currency(
                    item=item,
                    tender_id=tender_id,
                    context="award_item",
                    award_id=award_id,
                )

                award_item_defaults = {
                    "orden_licitado": parse_order_int(
                        get_attribute_value(item.get("attributes"), "Orden")
                    ),
                    "quantity": item.get("quantity") or 1,
                    "unit_price_amount": item_amount,
                    "unit_price_currency": self._get_currency(item_currency),
                }
                # Si el monto viene de un fallback (suma de subitems), no sobreescribir
                # un monto directo ya persistido (ej: ghost item mapea al mismo item_obj
                # que ya fue guardado con unit.value.amount propio).
                self._upsert(
                    AwardItem,
                    lookup={"award": award_obj, "item": item_obj},
                    defaults=award_item_defaults,
                    preserve_non_null_fields={"unit_price_amount", "unit_price_currency"} if is_fallback_amount else None,
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
                        self._record_special_case(
                            "award_subitem_incomplete_omitted",
                            "subitem adjudicado omitido por dato faltante",
                            tender_id=tender_id,
                            award_id=award_id,
                            award_item_id=item_id,
                            subitem_id=subitem_id,
                            has_description=bool(subitem.get("description")),
                        )
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
                                "quantity": subitem.get("quantity") or 1,
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
                missing_reasons = []
                if not contract_id:
                    missing_reasons.append("missing_contract_id")
                if not award_id:
                    missing_reasons.append("missing_award_id")
                elif award_obj is None:
                    missing_reasons.append("award_not_found")

                self._record_special_case(
                    "contract_incomplete_omitted",
                    "contrato omitido por id faltante o award inexistente",
                    tender_id=tender_id,
                    contract_id=contract_id,
                    award_id=award_id,
                    reasons=missing_reasons,
                )
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

            # Regla de negocio: para contratos no abiertos, el monto del lote
            # debe reflejar lo adjudicado en items del award.
            self._sync_non_open_lot_amounts_from_award(
                award_obj=award_obj,
                tender_id=tender_id,
                contract_id=contract_id,
            )

        self._flush_special_case_report(compiled_release_obj, tender_id)

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

    def _upsert(self, model_cls, lookup, defaults, preserve_non_null_fields=None):
        """Crea o actualiza un objeto.

        preserve_non_null_fields: conjunto de nombres de campo que NO deben
        sobreescribirse si ya tienen un valor no-nulo en el registro existente.
        Útil para evitar que un fallback calculado pise un valor directo ya guardado.
        """
        obj, created = model_cls.objects.get_or_create(**lookup, defaults=defaults)
        if created:
            return obj, created
        if getattr(obj, "is_user_modified", False):
            return obj, created
        preserve_nn = set(preserve_non_null_fields or [])
        update_fields = []
        for key, value in defaults.items():
            if key in preserve_nn and getattr(obj, key, None) is not None:
                continue  # no sobreescribir valor directo existente con fallback
            setattr(obj, key, value)
            update_fields.append(key)
        if update_fields:
            obj.save(update_fields=update_fields)
        return obj, created
