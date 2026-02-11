from __future__ import annotations

import hashlib
import json

from django.db import transaction
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.dncp_integration.models import CompiledRelease, ImportRun, RawRelease
from apps.dncp_integration.services.api_client import DNCPApiClient
from apps.dncp_integration.services.import_mapper import ImportMapper


class Command(BaseCommand):
    help = "Importa releases crudos de DNCP y registra trazabilidad."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ocid",
            action="append",
            dest="ocids",
            help="OCID a importar (puede repetirse).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No guarda en la base de datos, solo valida.",
        )

    def handle(self, *args, **options):
        ocids = options.get("ocids") or []
        dry_run = options.get("dry_run")

        if not ocids:
            self.stderr.write("Debes proveer al menos un --ocid.")
            return

        client = DNCPApiClient()
        mapper = ImportMapper()
        run = None
        if not dry_run:
            run = ImportRun.objects.create(status=ImportRun.STATUS_RUNNING)

        imported = 0
        skipped = 0
        failed = 0
        last_error = None

        for ocid in ocids:
            try:
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
                if timezone.is_naive(release_date):
                    release_date = timezone.make_aware(release_date)

                payload_hash = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest()

                latest = RawRelease.objects.filter(ocid=ocid).order_by("-release_date").first()
                if latest and release_date <= latest.release_date:
                    skipped += 1
                    continue

                if not dry_run:
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

                imported += 1
            except Exception as exc:
                failed += 1
                last_error = str(exc)
                self.stderr.write(f"Error en OCID {ocid}: {exc}")

        if run:
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

        self.stdout.write(
            f"Importados: {imported} | Omitidos: {skipped} | Fallidos: {failed}"
        )

