from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
import requests

from .services.api_client import DNCPApiClient
from .services.data_processor import DNCPDataProcessor


@require_http_methods(["GET"])
def home(request):
    """
    Página de inicio de SIGECOP.
    """
    context = {
        "app_name": "SIGECOP",
        "app_description": "Sistema de Gestión de Contrataciones Públicas",
    }
    return render(request, "home.html", context)


@require_http_methods(["GET"])
def dncp_list(request):
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

@require_http_methods(["GET"])
def dncp_detail(request, ocid):
    """
    Muestra detalles de un proceso de licitación desde DNCP.
    """
    try:
        # Inicializar cliente API
        client = DNCPApiClient()
        
        # Obtener datos del proceso
        data = client.get_record(ocid)
        records = data.get("records", [])
        
        if not records:
            messages.error(request, "No se encontraron datos para el OCID proporcionado")
            return redirect("dncp_integration:dncp_list")
        
        record = records[0]
        compiled_release = record.get("compiledRelease", {})
        tender = compiled_release.get("tender", {})
        awards = compiled_release.get("awards", [])
        
        # Procesar tender
        tender_data, awards_list = DNCPDataProcessor.process_record_detail(record)
        
        # Procesar lotes e items
        lotes = DNCPDataProcessor.process_tender_lots_and_items(tender)
        tender_data["lotes"] = lotes
        
        context = {
            "tender": tender_data,
            "awards": awards_list,
            "ocid": ocid,
        }
        
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Error de conexión con API DNCP: {str(e)}")
        return redirect("dncp_integration:dncp_list")
    except Exception as e:
        messages.error(request, f"Error procesando datos: {str(e)}")
        return redirect("dncp_integration:dncp_list")
    
    return render(request, "dncp_integration/dncp_detail.html", context)