from pathlib import Path
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.procurement.models import ExpenseObject


class Command(BaseCommand):
    help = "Importa objetos de gasto desde un dump SQL con bloque COPY de uoc_objetogasto."

    def add_arguments(self, parser):
        parser.add_argument("sql_file", type=str, help="Ruta al archivo SQL (ej: ../uoc_fpuna/objetogasto.sql)")
        parser.add_argument(
            "--encoding",
            choices=["auto", "utf-8", "cp1252", "latin-1"],
            default="auto",
            help="Codificacion de lectura del SQL. Use cp1252/latin-1 para dumps legacy.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analiza e informa resultados sin escribir en la base de datos.",
        )
        parser.add_argument(
            "--normalize-text",
            action="store_true",
            help="Normaliza texto Unicode (NFC) y espacios para mejorar tildes y caracteres especiales.",
        )

    def handle(self, *args, **options):
        sql_path = Path(options["sql_file"]).expanduser().resolve()
        dry_run = options["dry_run"]
        selected_encoding = options["encoding"]
        normalize_text = options["normalize_text"]

        if not sql_path.exists():
            raise CommandError(f"Archivo no encontrado: {sql_path}")

        rows = self._parse_copy_rows(sql_path, selected_encoding, normalize_text)
        if not rows:
            self.stdout.write(self.style.WARNING("No se encontraron filas para importar."))
            return

        created = 0
        updated = 0

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry-run OK. Filas detectadas: {len(rows)}"))
            self.stdout.write(f"  Encoding usado: {self._last_encoding_used}")
            sample = list(rows.items())[:5]
            for code, description in sample:
                self.stdout.write(f"  - {code}: {description[:80]}")
            return

        with transaction.atomic():
            for code, description in rows.items():
                obj, was_created = ExpenseObject.objects.update_or_create(
                    code=code,
                    defaults={
                        "description": description,
                        "is_active": True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS("Importacion completada."))
        self.stdout.write(f"  Encoding usado: {self._last_encoding_used}")
        self.stdout.write(f"  Total procesados: {len(rows)}")
        self.stdout.write(f"  Creados: {created}")
        self.stdout.write(f"  Actualizados: {updated}")

    _last_encoding_used = "unknown"

    def _read_text(self, sql_path: Path, selected_encoding: str):
        raw = sql_path.read_bytes()

        if selected_encoding != "auto":
            self._last_encoding_used = selected_encoding
            return raw.decode(selected_encoding)

        for candidate in ("utf-8", "cp1252", "latin-1"):
            try:
                decoded = raw.decode(candidate)
                self._last_encoding_used = candidate
                return decoded
            except UnicodeDecodeError:
                continue

        raise CommandError("No se pudo decodificar el archivo SQL con utf-8/cp1252/latin-1.")

    def _parse_copy_rows(self, sql_path: Path, selected_encoding: str, normalize_text: bool):
        lines = self._read_text(sql_path, selected_encoding).splitlines()

        copy_header_index = None
        for idx, line in enumerate(lines):
            if line.startswith("COPY public.uoc_objetogasto"):
                copy_header_index = idx
                break

        if copy_header_index is None:
            raise CommandError("No se encontro bloque COPY public.uoc_objetogasto en el archivo SQL.")

        header = lines[copy_header_index]
        columns_start = header.find("(")
        columns_end = header.find(")")
        if columns_start == -1 or columns_end == -1:
            raise CommandError("No se pudieron detectar columnas en la cabecera COPY.")

        columns = [col.strip() for col in header[columns_start + 1 : columns_end].split(",")]
        try:
            code_idx = columns.index("codigo")
            desc_idx = columns.index("descripcion")
        except ValueError as exc:
            raise CommandError("La cabecera COPY no contiene columnas esperadas codigo/descripcion.") from exc

        result = {}
        for line in lines[copy_header_index + 1 :]:
            if line.strip() == "\\.":
                break
            if not line.strip():
                continue

            parts = line.split("\t")
            max_index = max(code_idx, desc_idx)
            if len(parts) <= max_index:
                continue

            code = self._clean_field(parts[code_idx], normalize_text)
            description = self._clean_field(parts[desc_idx], normalize_text)
            if not code:
                continue

            result[code] = description

        return result

    @staticmethod
    def _clean_field(raw_value: str, normalize_text: bool):
        value = (raw_value or "").strip()
        if value == r"\N":
            return ""

        # Algunos dumps historicos traen comilla residual al final en descripcion.
        if value.endswith('"'):
            value = value[:-1].rstrip()

        if normalize_text:
            value = unicodedata.normalize("NFC", value)
            value = " ".join(value.split())

        return value
