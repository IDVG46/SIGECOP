from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib import messages
import requests

from .services.api_client import DNCPApiClient
from .services.data_processor import DNCPDataProcessor


@require_http_methods(["GET"])
def procesos_licitacion(request):
    """
    Lista procesos de licitación de la FPUNA desde la API DNCP.
    """
    try:
        # Inicializar cliente API
        client = DNCPApiClient()
        
        # Parámetros de búsqueda
        params = {
            "items_per_page": 100,
            "parties.identifier.id": "1369",  # ID FPUNA
            "tender.procuringEntity.name": "Facultad Politecnica / Universidad Nacional de Asunción", # Nombre Convocante
            "page": 1
        }
        
        licitaciones = []
        ocid_list = []
        all_records = []
        
        # Paginación
        while True:
            data = client.search_processes(params)
            records = data.get("records", [])
            all_records.extend(records)
            
            # Procesar registros actuales
            processed, ocids = DNCPDataProcessor.process_process_list(records)
            licitaciones.extend(processed)
            ocid_list.extend(ocids)
            
            # Verificar si hay más páginas
            pagination = data.get("pagination", {})
            if pagination.get("current_page", 1) >= pagination.get("total_pages", 1):
                break
            
            params["page"] += 1
        
        # Ordenar por ID descendente
        licitaciones = sorted(
            licitaciones,
            key=lambda x: int(x.get("id") or 0),
            reverse=True
        )
        
        # Guardar en sesión para uso posterior
        request.session["ocid_list"] = ocid_list
        
        context = {
            "licitaciones": licitaciones,
            "total": len(licitaciones),
        }
        
    except requests.exceptions.RequestException as e:
        messages.error(
            request,
            f"Error de conexión con API DNCP: {str(e)}"
        )
        context = {"licitaciones": [], "error": str(e)}
    except Exception as e:
        messages.error(
            request,
            f"Error procesando datos: {str(e)}"
        )
        context = {"licitaciones": [], "error": str(e)}
    
    return render(request, "dncp_integration/dncp_list.html", context)