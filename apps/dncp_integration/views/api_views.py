import hashlib
import json
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods
import requests

from apps.dncp_integration.services.api_client import DNCPApiClient
from apps.dncp_integration.services.data_processor import DNCPDataProcessor
from apps.dncp_integration.services.import_mapper import ImportMapper
from apps.dncp_integration.models import CompiledRelease, ImportRun, RawRelease


def _get_error_message(status_code):
    """
    Retorna un mensaje amigable según el código de error HTTP.
    """
    error_messages = {
        400: "La solicitud es inválida. Verifica los parámetros de búsqueda.",
        401: "No tienes autorización para acceder a la API DNCP.",
        403: "Acceso denegado a la API DNCP.",
        404: "Los datos solicitados no fueron encontrados.",
        500: "El servidor de DNCP está experimentando problemas. Intenta más tarde.",
        502: "Problema de conexión con el servidor de DNCP. Intenta más tarde.",
        503: "El servidor de DNCP no está disponible. Intenta más tarde.",
        504: "El servidor de DNCP tardó demasiado en responder. Intenta más tarde.",
    }
    return error_messages.get(status_code, f"Error de conexión con la API DNCP ({status_code}).")


@require_http_methods(["GET"])
def home(request):
    """
    Pagina de inicio de SIGECOP.
    """
    context = {
        "app_name": "SIGECOP",
        "app_description": "Sistema de Gestion de Contrataciones Publicas",
    }
    return render(request, "home.html", context)


@require_http_methods(["GET"])
def dncp_list(request):
    """
    Lista procesos de licitacion de la FPUNA desde la API DNCP.
    """
    try:
        client = DNCPApiClient()

        params = {
            "items_per_page": 100,
            "parties.identifier.id": "1369",
            "tender.procuringEntity.name": "Facultad Politecnica / Universidad Nacional de Asunción",
            "page": 1,
        }

        licitaciones = []
        ocid_list = []

        while True:
            data = client.search_processes(params)
            records = data.get("records", [])

            processed, ocids = DNCPDataProcessor.process_process_list(records)
            licitaciones.extend(processed)
            ocid_list.extend(ocids)

            pagination = data.get("pagination", {})
            if pagination.get("current_page", 1) >= pagination.get("total_pages", 1):
                break

            params["page"] += 1

        licitaciones = sorted(
            licitaciones,
            key=lambda x: int(x.get("id") or 0),
            reverse=True,
        )

        request.session["ocid_list"] = ocid_list

        latest_import_run = (
            ImportRun.objects.filter(source=ImportRun.SOURCE_HTTP).order_by("-started_at").first()
        )

        context = {
            "licitaciones": licitaciones,
            "total": len(licitaciones),
            "latest_import_run": latest_import_run,
        }

    except requests.exceptions.RequestException as exc:
        status_code = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
        error_msg = _get_error_message(status_code) if status_code else "No pudimos conectar con la API DNCP. Por favor, intenta nuevamente."
        messages.warning(request, error_msg)
        context = {"licitaciones": [], "total": 0, "latest_import_run": None}
    except Exception as exc:
        messages.warning(request, "Ocurrió un error al procesar los datos. Por favor, intenta nuevamente.")
        context = {"licitaciones": [], "total": 0, "latest_import_run": None}

    return render(request, "dncp_integration/dncp_list.html", context)


@require_http_methods(["GET"])
def dncp_detail(request, ocid):
    """
    Muestra detalles de un proceso de licitacion desde DNCP.
    """
    try:
        client = DNCPApiClient()

        data = client.get_record(ocid)
        records = data.get("records", [])

        if not records:
            messages.error(request, "No se encontraron datos para el OCID proporcionado")
            return redirect("dncp_api:dncp_list")

        record = records[0]
        compiled_release = record.get("compiledRelease", {})
        tender = compiled_release.get("tender", {})

        tender_data, awards_list = DNCPDataProcessor.process_record_detail(record)

        lotes = DNCPDataProcessor.process_tender_lots_and_items(tender)
        tender_data["lotes"] = lotes

        context = {
            "tender": tender_data,
            "awards": awards_list,
            "ocid": ocid,
        }

    except requests.exceptions.RequestException as exc:
        status_code = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
        error_msg = _get_error_message(status_code) if status_code else "No pudimos conectar con la API DNCP."
        messages.warning(request, error_msg)
        return redirect("dncp_api:dncp_list")
    except Exception as exc:
        messages.warning(request, "Ocurrió un error al procesar los datos.")
        return redirect("dncp_api:dncp_list")

    return render(request, "dncp_integration/dncp_detail.html", context)


def _parse_ocids(raw_value):
    if not raw_value:
        return []
    parts = raw_value.replace("\n", ",").replace("\r", ",").split(",")
    ocids = []
    for part in parts:
        value = part.strip()
        if value:
            ocids.append(value)
    return ocids


def _import_ocid(client, mapper, ocid, run):
    payload = client.get_record(ocid)
    records = payload.get("records", [])
    if not records:
        raise ValueError("Respuesta sin records")

    compiled_release = records[0].get("compiledRelease", {})
    release_id = compiled_release.get("id")
    release_date_raw = compiled_release.get("date")
    release_date = parse_datetime(release_date_raw) if release_date_raw else None
    if release_date is None:
        raise ValueError("release.date invalido o ausente")
    if timezone.is_aware(release_date):
        release_date = timezone.make_naive(release_date)

    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    latest = RawRelease.objects.filter(ocid=ocid).order_by("-release_date").first()
    if latest and release_date <= latest.release_date:
        return "skipped"

    with transaction.atomic():
        raw_release = RawRelease.objects.create(
            ocid=ocid,
            release_id=release_id or "",
            release_date=release_date,
            payload=payload,
            payload_hash=payload_hash,
            import_run=run,
        )

        compiled_release_obj, _ = CompiledRelease.objects.update_or_create(
            ocid=ocid,
            defaults={
                "release_id": release_id or "",
                "date": release_date,
                "raw_release": raw_release,
                "last_synced_at": timezone.now(),
                "import_run": run,
            },
        )

        mapper.persist(compiled_release_obj, compiled_release)

    return "imported"


def _build_date_bounds(start_date, end_date):
    if not start_date:
        return None, None
    return start_date, end_date or None


def _parse_iso_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _in_date_range(value, start_date, end_date):
    if value is None:
        return False
    if start_date and value < start_date:
        return False
    if end_date and value > end_date:
        return False
    return True


@login_required
@require_http_methods(["POST"])
def dncp_import(request):
    raw_ocid = request.POST.get("ocid", "")
    raw_ocids = request.POST.get("ocids", "")
    ocids = _parse_ocids(raw_ocid) + _parse_ocids(raw_ocids)
    ocids = list(dict.fromkeys(ocids))

    if not ocids:
        messages.error(request, "Debes proporcionar al menos un OCID")
        return redirect("dncp_api:dncp_list")

    client = DNCPApiClient()
    mapper = ImportMapper()
    run = ImportRun.objects.create(status=ImportRun.STATUS_RUNNING, source=ImportRun.SOURCE_HTTP)

    imported = 0
    skipped = 0
    failed = 0
    last_error = None

    for ocid in ocids:
        try:
            result = _import_ocid(client, mapper, ocid, run)
            if result == "imported":
                imported += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            last_error = str(exc)

    run.total_records = len(ocids)
    run.imported_records = imported
    run.skipped_records = skipped
    run.failed_records = failed
    run.last_error = last_error
    run.finished_at = timezone.now()
    if failed:
        run.status = ImportRun.STATUS_PARTIAL if imported else ImportRun.STATUS_FAILED
    else:
        run.status = ImportRun.STATUS_SUCCESS
    run.save(update_fields=[
        "total_records",
        "imported_records",
        "skipped_records",
        "failed_records",
        "last_error",
        "finished_at",
        "status",
    ])

    if failed and imported == 0:
        messages.error(request, "No se pudo importar ningun OCID. Revisa los errores.")
    elif failed:
        messages.warning(request, f"Importados: {imported} | Omitidos: {skipped} | Fallidos: {failed}")
    else:
        messages.success(request, f"Importados: {imported} | Omitidos: {skipped}")

    if raw_ocid:
        return redirect("dncp_api:dncp_detail", ocid=raw_ocid)
    return redirect("dncp_api:dncp_list")


@login_required
@require_http_methods(["POST"])
def dncp_import_bulk(request):
    start_date = request.POST.get("start_date") or ""
    end_date = request.POST.get("end_date") or ""
    year = request.POST.get("year") or ""

    if year:
        try:
            year_value = int(year)
            if year_value < 2010 or year_value > 2030:
                messages.warning(request, "El año debe estar entre 2010 y 2030")
                return redirect("dncp_api:dncp_list")
            start_date = date(year_value, 1, 1).isoformat()
            end_date = date(year_value, 12, 31).isoformat()
        except (ValueError, TypeError):
            messages.warning(request, "El año proporcionado no es válido")
            return redirect("dncp_api:dncp_list")

    if not start_date:
        messages.warning(request, "Debes proporcionar una fecha de inicio o un año")
        return redirect("dncp_api:dncp_list")

    client = DNCPApiClient()
    mapper = ImportMapper()
    run = ImportRun.objects.create(status=ImportRun.STATUS_RUNNING, source=ImportRun.SOURCE_HTTP)

    start_dt, end_dt = _build_date_bounds(start_date, end_date)
    params = {
        "items_per_page": 100,
        "parties.identifier.id": "1369",
        "tender.procuringEntity.name": "Facultad Politecnica / Universidad Nacional de Asunción",
        "page": 1,
    }
    start_date_obj = date.fromisoformat(start_dt) if start_dt else None
    end_date_obj = date.fromisoformat(end_dt) if end_dt else None

    ocids = []
    max_pages = 50
    try:
        while True:
            if params["page"] > max_pages:
                messages.warning(request, "Se alcanzo el limite de paginas para evitar una importacion excesiva.")
                break
            data = client.search_processes(params)
            records = data.get("records", [])
            for record in records:
                ocid = record.get("ocid")
                tender = record.get("compiledRelease", {}).get("tender", {})
                start_value = tender.get("tenderPeriod", {}).get("startDate")
                start_value_date = _parse_iso_date(start_value)
                if ocid and _in_date_range(start_value_date, start_date_obj, end_date_obj):
                    ocids.append(ocid)
            pagination = data.get("pagination", {})
            if pagination.get("current_page", 1) >= pagination.get("total_pages", 1):
                break
            params["page"] += 1
    except requests.exceptions.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
        error_msg = _get_error_message(status_code) if status_code else "Error en la búsqueda de la API DNCP."
        run.status = ImportRun.STATUS_FAILED
        run.last_error = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "last_error", "finished_at"])
        messages.warning(request, error_msg)
        return redirect("dncp_api:dncp_list")

    ocids = list(dict.fromkeys(ocids))
    if not ocids:
        run.status = ImportRun.STATUS_FAILED
        run.last_error = "Sin resultados para el rango indicado"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "last_error", "finished_at"])
        messages.warning(request, "No se encontraron procesos en el rango indicado")
        return redirect("dncp_api:dncp_list")

    imported = 0
    skipped = 0
    failed = 0
    last_error = None

    for ocid in ocids:
        try:
            result = _import_ocid(client, mapper, ocid, run)
            if result == "imported":
                imported += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            last_error = str(exc)

    run.total_records = len(ocids)
    run.imported_records = imported
    run.skipped_records = skipped
    run.failed_records = failed
    run.last_error = last_error
    run.finished_at = timezone.now()
    if failed:
        run.status = ImportRun.STATUS_PARTIAL if imported else ImportRun.STATUS_FAILED
    else:
        run.status = ImportRun.STATUS_SUCCESS
    run.save(update_fields=[
        "total_records",
        "imported_records",
        "skipped_records",
        "failed_records",
        "last_error",
        "finished_at",
        "status",
    ])

    if failed and imported == 0:
        messages.error(request, "No se pudo importar ningun OCID del rango indicado")
    elif failed:
        messages.warning(request, f"Importados: {imported} | Omitidos: {skipped} | Fallidos: {failed}")
    else:
        messages.success(request, f"Importados: {imported} | Omitidos: {skipped}")

    return redirect("dncp_api:dncp_list")
