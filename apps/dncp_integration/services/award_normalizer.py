"""
Servicio para normalizar la estructura de awards del DNCP.

**IMPORTANTE: Este módulo es SOLO para procesamiento de datos locales (BD).**
NO usar para visualización directa de API (esos datos vienen correctos).

Problema:
- En tender.items del DNCP, los subitems están correctamente anidados dentro de items
- En awards[].items del DNCP, los subitems también están anidados, pero la estructura
  puede variar y necesita normalización al guardar/consultar de BD local
- Cuando se importan datos a la BD, necesitamos asegurar la jerarquía correcta

Contexto del problema del usuario:
- Licitación por "Por Total" con 3 lotes/grupos
- Cada lote tiene items, algunos con subitems
- Al consultar de BD local, necesitamos reconstruir la  estructura de lotes
- Los items con subitems deben mostrarse correctamente agrupados por lote

Uso:
```python
# En import/visualización de datos locales
from apps.dncp_integration.services.award_normalizer import AwardItemNormalizer

# Normalizar items de un award
normalized_items = AwardItemNormalizer.normalize_award_items(award_items)

# Construir estructura completa de lotes
lot_structures = AwardItemNormalizer.build_lot_structure(award, tender_lots)

# Para visualización local (contract_views.py):
# Use la función _build_lot_structure_from_db() que consulta directamente la BD
```

NO usar en:
- api_views.py (visualización directa de API DNCP)
- data_processor.py para proceso_record_detail (solo reforma para vistas API)
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


class AwardItemNormalizer:
    """
    Normaliza la estructura de items en awards del DNCP.
    
    Maneja el caso donde los subitems aparecen como items independientes
    en el mismo nivel que items normales.
    """
    
    @classmethod
    def normalize_award_items(cls, award_items: List[Dict], tender_items: List[Dict] = None) -> List[Dict]:
        """
        Normaliza items de un award, identificando y reagrupando subitems.
        
        Args:
            award_items: Lista de items del award (puede contener items con subItems)
            tender_items: Lista de items del tender (opcional, para validación)
            
        Returns:
            Lista de items normalizados con estructura jerárquica correcta
        """
        if not award_items:
            return []
        
        # Separar items que son "grupos" (tienen subItems) de items normales
        group_items = []  # Items que contienen subItems
        regular_items = []  # Items normales sin subItems
        
        for item in award_items:
            subitems = item.get("subItems", [])
            if subitems and len(subitems) > 0:
                # Este es un item "grupo" que contiene subitems
                group_items.append(item)
            else:
                # Item normal
                regular_items.append(item)
        
        # Si no hay items grupo, retornar items regulares tal cual
        if not group_items:
            return regular_items
        
        # Reconstruir la estructura jerárquica
        normalized_items = []
        
        # Procesar items regulares (sin subitems)
        for item in regular_items:
            normalized_items.append({
                **item,
                "subItems": []  # Asegurar que tengan el campo
            })
        
        # Procesar items grupo (con subitems)
        for group_item in group_items:
            # El item "grupo" en sí puede no tener datos propios, 
            # solo sirve como contenedor de subitems
            normalized_item = {
                "id": group_item.get("id"),
                "description": group_item.get("description", ""),
                "relatedLot": group_item.get("relatedLot"),
                "attributes": group_item.get("attributes", []),
                "classification": group_item.get("classification"),
                "additionalClassifications": group_item.get("additionalClassifications"),
                "unit": group_item.get("unit", {}),
                "quantity": group_item.get("quantity"),
                "subItems": []
            }
            
            # Agregar los subitems
            for subitem in group_item.get("subItems", []):
                normalized_item["subItems"].append(subitem)
            
            normalized_items.append(normalized_item)
        
        return normalized_items
    
    @classmethod
    def group_items_by_lot(cls, normalized_items: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Agrupa items normalizados por lote.
        
        Args:
            normalized_items: Lista de items normalizados
            
        Returns:
            Diccionario con lote_id como clave y lista de items como valor
        """
        items_by_lot = defaultdict(list)
        
        for item in normalized_items:
            lot_id = item.get("relatedLot")
            items_by_lot[lot_id].append(item)
        
        return dict(items_by_lot)
    
    @classmethod
    def extract_orden(cls, item: Dict) -> Optional[str]:
        """
        Extrae el orden de un item desde sus atributos.
        
        Args:
            item: Diccionario del item
            
        Returns:
            Valor del orden o None
        """
        attributes = item.get("attributes", [])
        for attr in attributes:
            if attr.get("name") in ["Orden", "orden"]:
                return attr.get("value")
        return None
    
    @classmethod
    def sort_items_by_orden(cls, items: List[Dict]) -> List[Dict]:
        """
        Ordena items por su atributo de orden.
        
        Args:
            items: Lista de items
            
        Returns:
            Lista de items ordenados
        """
        def orden_key(item):
            orden = cls.extract_orden(item)
            if not orden:
                return float('inf')
            try:
                # Intentar convertir a número
                return float(str(orden).replace(',', '.'))
            except (ValueError, AttributeError):
                return float('inf')
        
        return sorted(items, key=orden_key)
    
    @classmethod
    def build_lot_structure(cls, award: Dict, tender_lots: List[Dict] = None) -> List[Dict]:
        """
        Construye la estructura completa de lotes con items y subitems para un award.
        
        Args:
            award: Diccionario del award
            tender_lots: Lista de lotes del tender (opcional)
            
        Returns:
            Lista de lotes con su estructura completa
        """
        award_items = award.get("items", [])
        normalized_items = cls.normalize_award_items(award_items)
        items_by_lot = cls.group_items_by_lot(normalized_items)
        
        # Crear estructura de lotes
        lot_structures = []
        
        # Si hay tender_lots, usar esa información
        if tender_lots:
            for tender_lot in tender_lots:
                lot_id = tender_lot.get("id")
                lot_items = items_by_lot.get(lot_id, [])
                
                lot_structure = {
                    "id": lot_id,
                    "title": tender_lot.get("title", ""),
                    "description": tender_lot.get("title", "").split("-")[-1].strip() if tender_lot.get("title") else "",
                    "value": tender_lot.get("value", {}).get("amount"),
                    "min_value": tender_lot.get("minValue", {}).get("amount"),
                    "orden": cls._extract_lot_orden(tender_lot),
                    "items": cls.sort_items_by_orden(lot_items)
                }
                lot_structures.append(lot_structure)
        else:
            # Si no hay tender_lots, crear lotes basados en los items
            for lot_id, lot_items in items_by_lot.items():
                if lot_id is None:
                    title = "Sin lote asignado"
                else:
                    # Intentar obtener título del primer item
                    title = f"Lote {lot_id}"
                
                lot_structure = {
                    "id": lot_id,
                    "title": title,
                    "description": title,
                    "value": None,
                    "min_value": None,
                    "orden": lot_id,
                    "items": cls.sort_items_by_orden(lot_items)
                }
                lot_structures.append(lot_structure)
        
        # Ordenar lotes por orden
        return cls._sort_lots(lot_structures)
    
    @classmethod
    def _extract_lot_orden(cls, lot: Dict) -> Optional[str]:
        """Extrae el orden de un lote."""
        attributes = lot.get("attributes", [])
        for attr in attributes:
            if attr.get("name") in ["Orden", "orden"]:
                return attr.get("value")
        return None
    
    @classmethod
    def _sort_lots(cls, lots: List[Dict]) -> List[Dict]:
        """Ordena lotes por su orden."""
        def lot_orden_key(lot):
            orden = lot.get("orden")
            if not orden:
                return float('inf')
            try:
                return float(str(orden).replace(',', '.'))
            except (ValueError, AttributeError):
                return float('inf')
        
        return sorted(lots, key=lot_orden_key)
    
    @classmethod
    def count_items_and_subitems(cls, normalized_items: List[Dict]) -> Tuple[int, int]:
        """
        Cuenta el número total de items y subitems.
        
        Args:
            normalized_items: Lista de items normalizados
            
        Returns:
            Tupla (num_items, num_subitems)
        """
        num_items = len(normalized_items)
        num_subitems = sum(len(item.get("subItems", [])) for item in normalized_items)
        return num_items, num_subitems
    
    @classmethod
    def validate_structure(cls, normalized_items: List[Dict], expected_items: int = None) -> Dict:
        """
        Valida la estructura normalizada.
        
        Args:
            normalized_items: Lista de items normalizados
            expected_items: Número esperado de items (opcional)
            
        Returns:
            Diccionario con resultado de validación
        """
        num_items, num_subitems = cls.count_items_and_subitems(normalized_items)
        
        validation = {
            "valid": True,
            "num_items": num_items,
            "num_subitems": num_subitems,
            "warnings": [],
            "errors": []
        }
        
        # Verificar si hay items esperados
        if expected_items is not None and num_items != expected_items:
            validation["warnings"].append(
                f"Número de items ({num_items}) no coincide con lo esperado ({expected_items})"
            )
        
        # Verificar que items tengan ID y descripción
        for i, item in enumerate(normalized_items):
            if not item.get("id"):
                validation["errors"].append(f"Item en posición {i} no tiene ID")
                validation["valid"] = False
            if not item.get("description"):
                validation["warnings"].append(f"Item '{item.get('id')}' no tiene descripción")
        
        return validation


# Función de conveniencia para uso rápido
def normalize_award_items(award: Dict, tender: Dict = None) -> List[Dict]:
    """
    Función de conveniencia para normalizar items de un award.
    
    Args:
        award: Diccionario del award
        tender: Diccionario del tender (opcional)
        
    Returns:
        Lista de lotes con estructura normalizada
    """
    tender_lots = tender.get("lots", []) if tender else None
    return AwardItemNormalizer.build_lot_structure(award, tender_lots)
