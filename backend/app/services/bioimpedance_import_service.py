from __future__ import annotations

import base64
import io
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

from ..core.config import settings
from .bioimpedance_metrics import METRIC_DEFINITIONS
from .supabase_user_service import SupabaseUserService


MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_FILES = 5
MAX_TOTAL_IMPORT_BYTES = 25 * 1024 * 1024
TEXT_MIN_CHARS = 80
IMAGE_FILE_TYPES = {"jpg", "jpeg", "png"}
JPEG_FILE_TYPES = {"jpg", "jpeg"}
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
    "image/png": "png",
}
BODY_COMPOSITION_TERMS = (
    "bioimped",
    "imc",
    "gordura",
    "muscul",
    "visceral",
    "metabol",
    "composicao corporal",
    "body fat",
    "muscle",
    "bmi",
)


@dataclass(frozen=True)
class ImportFile:
    content: bytes
    file_name: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    order_index: int


@dataclass(frozen=True)
class ExtractedImportFile:
    file: ImportFile
    extracted_text: str
    extraction_mode: str


class BioimpedanceImportService:
    def __init__(self) -> None:
        self.user_service = SupabaseUserService()
        self.supabase_url = self.user_service.supabase_url
        self.service_headers = self.user_service.service_headers

    async def process_pdf(self, token: str, file: UploadFile) -> dict:
        return await self.process_reports(token, [file])

    async def process_report(self, token: str, file: UploadFile) -> dict:
        return await self.process_reports(token, [file])

    async def process_reports(self, token: str, files: list[UploadFile]) -> dict:
        nutritionist = await self.user_service.assert_nutritionist(token)
        import_files = await self._read_import_files(files)
        import_id = str(uuid.uuid4())

        extracted_files: list[ExtractedImportFile] = []
        for import_file in import_files:
            extracted_files.append(await self._extract_file_text(import_file))

        consolidated_text = self._consolidate_file_texts(extracted_files)
        extraction_mode = self._batch_extraction_mode(extracted_files)

        payload = await self._extract_structured_payload(
            text=consolidated_text,
            ocr_images=[],
            extraction_mode=extraction_mode,
            file_type="multiple" if len(import_files) > 1 else import_files[0].file_type,
        )
        normalized = self._normalize_payload(payload, consolidated_text, import_files[0].file_type)

        if not self._has_useful_data(normalized):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Não foi possível extrair dados suficientes deste arquivo. "
                    "Envie uma imagem mais nitida ou revise os campos manualmente."
                ),
            )

        uploaded_files = []
        for extracted_file in extracted_files:
            import_file = extracted_file.file
            file_path = await self._upload_import_file(
                nutritionist_id=nutritionist["id"],
                import_id=import_id,
                file_name=import_file.file_name,
                content=import_file.content,
                mime_type=import_file.mime_type,
                file_type=import_file.file_type,
                order_index=import_file.order_index,
            )
            uploaded_files.append(
                {
                    "file_path": file_path,
                    "file_type": import_file.file_type,
                    "mime_type": import_file.mime_type,
                    "original_file_name": import_file.file_name,
                    "file_size_bytes": import_file.file_size_bytes,
                    "extracted_text": extracted_file.extracted_text,
                    "order_index": import_file.order_index,
                }
            )

        first_file = import_files[0]
        first_uploaded = uploaded_files[0]
        row = await self._create_import_row(
            import_id=import_id,
            nutritionist_id=nutritionist["id"],
            file_path=first_uploaded["file_path"],
            file_type=first_file.file_type,
            mime_type=first_file.mime_type,
            original_file_name=first_file.file_name,
            file_size_bytes=sum(item.file_size_bytes for item in import_files),
            extracted_payload=normalized,
        )
        file_rows = await self._create_import_file_rows(
            import_id=row["id"],
            uploaded_files=uploaded_files,
        )

        return {
            "import_id": row["id"],
            "source_type": row["source_type"],
            "file_type": row.get("file_type") or first_file.file_type,
            "mime_type": row.get("mime_type") or first_file.mime_type,
            "original_file_name": row.get("original_file_name") or first_file.file_name,
            "file_size_bytes": row.get("file_size_bytes") or sum(item.file_size_bytes for item in import_files),
            "file_path": row.get("file_url") or row.get("file_path"),
            "file_count": len(file_rows),
            "files": file_rows,
            "extraction_mode": extraction_mode,
            "patient": normalized["patient"],
            "metrics": normalized["metrics"],
            "measurement": normalized["measurement"],
            "confidence": normalized["confidence"],
            "warnings": normalized["warnings"],
            "autofill_fields": self._autofill_fields(normalized),
        }

    async def create_signed_url(self, token: str, import_id: str) -> dict:
        signed_urls = await self.create_file_signed_urls(token, import_id)
        first = signed_urls["files"][0] if signed_urls["files"] else None
        return {"signed_url": first.get("signed_url") if first else None}

    async def create_file_signed_urls(self, token: str, import_id: str) -> dict:
        nutritionist = await self.user_service.assert_nutritionist(token)
        import_rows = await self._supabase_request(
            "GET",
            "/rest/v1/patient_imports",
            params={
                "id": f"eq.{import_id}",
                "nutritionist_id": f"eq.{nutritionist['id']}",
                "select": "id,file_url",
                "limit": "1",
            },
        )
        import_row = import_rows[0] if import_rows else None
        if not import_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Importação não encontrada.",
            )

        file_rows = await self._supabase_request(
            "GET",
            "/rest/v1/patient_import_files",
            params={
                "import_id": f"eq.{import_id}",
                "select": "*",
                "order": "order_index.asc",
            },
        )
        if not file_rows and import_row.get("file_url"):
            file_rows = [
                {
                    "id": import_row["id"],
                    "file_url": import_row["file_url"],
                    "file_type": import_row.get("file_type"),
                    "original_file_name": import_row.get("original_file_name"),
                    "order_index": 0,
                }
            ]
        if not file_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivos importados não encontrados.",
            )

        signed_files = []
        for file_row in file_rows:
            file_path = file_row.get("file_url")
            if not file_path:
                continue
            response = await self._storage_request(
                "POST",
                f"/storage/v1/object/sign/patient-imports/{file_path}",
                json={"expiresIn": 3600},
            )
            signed_url = response.get("signedURL") or response.get("signedUrl")
            if signed_url and signed_url.startswith("/"):
                signed_url = f"{self.supabase_url}{signed_url}"
            signed_files.append({**file_row, "signed_url": signed_url})

        return {"files": signed_files}

    async def _read_import_files(self, files: list[UploadFile]) -> list[ImportFile]:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selecione pelo menos um arquivo para importar.",
            )
        if len(files) > MAX_IMPORT_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Envie no maximo {MAX_IMPORT_FILES} arquivos por importacao.",
            )

        import_files = [
            await self._read_import_file(file, order_index=index)
            for index, file in enumerate(files)
        ]
        total_size = sum(item.file_size_bytes for item in import_files)
        if total_size > MAX_TOTAL_IMPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="A importacao completa deve ter no maximo 25 MB.",
            )
        return import_files

    async def _read_import_file(self, file: UploadFile, *, order_index: int) -> ImportFile:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Arquivo vazio.")
        if len(content) > MAX_IMPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="O arquivo deve ter no maximo 10 MB.",
            )

        file_name = file.filename or "bioimpedancia"
        content_type = self._normalize_content_type(file.content_type)
        file_type = self._detect_file_type(
            content=content,
            file_name=file_name,
            content_type=content_type,
        )

        if file_type in IMAGE_FILE_TYPES:
            self._validate_image(content)

        return ImportFile(
            content=content,
            file_name=file_name,
            file_type=file_type,
            mime_type=self._content_type_for_file_type(file_type, content_type),
            file_size_bytes=len(content),
            order_index=order_index,
        )

    def _detect_file_type(
        self,
        *,
        content: bytes,
        file_name: str,
        content_type: str,
    ) -> str:
        extension_type = self._file_type_from_extension(file_name)
        mime_type = ALLOWED_MIME_TYPES.get(content_type)
        signature_type = self._file_type_from_signature(content)

        if extension_type is None and "." in file_name:
            self._raise_invalid_file_type()

        if content_type and content_type not in ALLOWED_MIME_TYPES and content_type != "application/octet-stream":
            self._raise_invalid_file_type()

        detected = signature_type or extension_type or mime_type
        if detected is None:
            self._raise_invalid_file_type()

        if extension_type and not self._file_types_match(extension_type, detected):
            self._raise_invalid_file_type()

        if mime_type and not self._file_types_match(mime_type, detected):
            self._raise_invalid_file_type()

        if signature_type and extension_type and extension_type in JPEG_FILE_TYPES:
            return extension_type

        return detected

    def _file_type_from_extension(self, file_name: str) -> str | None:
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        return extension if extension in ALLOWED_EXTENSIONS else None

    def _file_type_from_signature(self, content: bytes) -> str | None:
        if content.startswith(b"%PDF-"):
            return "pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if content.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        return None

    def _file_types_match(self, left: str, right: str) -> bool:
        if left in JPEG_FILE_TYPES and right in JPEG_FILE_TYPES:
            return True
        return left == right

    def _normalize_content_type(self, content_type: str | None) -> str:
        return (content_type or "").split(";", 1)[0].strip().lower()

    def _content_type_for_file_type(self, file_type: str, detected_content_type: str) -> str:
        if detected_content_type in ALLOWED_MIME_TYPES:
            return detected_content_type
        if file_type == "pdf":
            return "application/pdf"
        if file_type == "png":
            return "image/png"
        return "image/jpeg"

    def _raise_invalid_file_type(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato invalido. Envie apenas PDF, JPG, JPEG ou PNG.",
        )

    def _validate_image(self, content: bytes) -> None:
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A imagem enviada não é válida ou está corrompida.",
            ) from None

    async def _extract_file_text(self, import_file: ImportFile) -> ExtractedImportFile:
        if import_file.file_type == "pdf":
            text = self._extract_pdf_text(import_file.content)
            if len(text.strip()) >= TEXT_MIN_CHARS:
                return ExtractedImportFile(
                    file=import_file,
                    extracted_text=text,
                    extraction_mode="text",
                )

            rendered_pages = self._render_pdf_pages(import_file.content)
            if not rendered_pages:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Não foi possível ler o arquivo \"{import_file.file_name}\". "
                        "Envie uma imagem mais nitida ou revise os campos manualmente."
                    ),
                )
            return ExtractedImportFile(
                file=import_file,
                extracted_text=await self._ocr_images_to_text(import_file.file_name, rendered_pages),
                extraction_mode="ocr",
            )

        prepared_image = self._prepare_image_for_ocr(import_file.content)
        if not prepared_image:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Não foi possível ler o arquivo \"{import_file.file_name}\". "
                    "Envie uma imagem mais nitida ou revise os campos manualmente."
                ),
            )

        return ExtractedImportFile(
            file=import_file,
            extracted_text=await self._ocr_images_to_text(import_file.file_name, [prepared_image]),
            extraction_mode="ocr",
        )

    async def _ocr_images_to_text(self, file_name: str, images: list[dict[str, str]]) -> str:
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "OCR de imagem/PDF escaneado nao configurado. Configure "
                    "OPENAI_API_KEY/OPENAI_OCR_MODEL ou envie um PDF com texto selecionavel."
                ),
            )

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Transcreva fielmente todo texto legivel deste arquivo de relatorio "
                    f"de bioimpedancia ({file_name}). Retorne somente texto puro. "
                    "Nao invente campos, numeros ou unidades ausentes."
                ),
            }
        ]
        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image['mime_type']};base64,{image['data']}",
                    },
                }
            )

        payload = {
            "model": settings.openai_ocr_model,
            "messages": [
                {
                    "role": "developer",
                    "content": "Voce faz OCR fiel de relatorios. Nunca invente conteudo.",
                },
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_completion_tokens": 2200,
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=75) as client:
                response = await client.post(
                    settings.openai_base_url,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível analisar o arquivo agora. Tente novamente em instantes.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"IA/OCR rejeitou o arquivo \"{file_name}\": {response.text}",
            )

        message = response.json().get("choices", [{}])[0].get("message", {})
        return str(message.get("content") or "").strip()

    def _consolidate_file_texts(self, extracted_files: list[ExtractedImportFile]) -> str:
        sections = []
        for extracted_file in extracted_files:
            index = extracted_file.file.order_index + 1
            sections.append(
                "\n".join(
                    [
                        f"--- ARQUIVO {index}: {extracted_file.file.file_name} ---",
                        extracted_file.extracted_text.strip() or "[sem texto legivel extraido]",
                    ]
                )
            )
        return "\n\n".join(sections).strip()

    def _batch_extraction_mode(self, extracted_files: list[ExtractedImportFile]) -> str:
        modes = {item.extraction_mode for item in extracted_files}
        if modes == {"text"}:
            return "text"
        if modes == {"ocr"}:
            return "ocr"
        return "mixed"

    def _extract_pdf_text(self, content: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages[:8]]
        except Exception:
            return ""
        return "\n".join(pages).strip()

    def _render_pdf_pages(self, content: bytes) -> list[dict[str, str]]:
        try:
            import pypdfium2 as pdfium
        except Exception:
            return []

        images: list[dict[str, str]] = []
        try:
            document = pdfium.PdfDocument(content)
            for index in range(min(len(document), 3)):
                page = document[index]
                bitmap = page.render(scale=1.8)
                image = bitmap.to_pil().convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="PNG", optimize=True)
                images.append(
                    {
                        "mime_type": "image/png",
                        "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
                    }
                )
                page.close()
            document.close()
        except Exception:
            return []
        return images

    def _prepare_image_for_ocr(self, content: bytes) -> dict[str, str] | None:
        try:
            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)
            image.thumbnail((2600, 2600), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            return None

        return {
            "mime_type": "image/png",
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }

    async def _extract_structured_payload(
        self,
        *,
        text: str,
        ocr_images: list[dict[str, str]],
        extraction_mode: str,
        file_type: str,
    ) -> dict:
        if settings.openai_api_key:
            try:
                return await self._extract_with_openai(
                    text=text,
                    ocr_images=ocr_images,
                    extraction_mode=extraction_mode,
                    file_type=file_type,
                )
            except HTTPException:
                if extraction_mode == "ocr":
                    raise
            except Exception:
                pass

        if extraction_mode in {"ocr", "mixed"} and not text.strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "OCR de imagem/PDF escaneado nao configurado. Configure "
                    "OPENAI_API_KEY/OPENAI_OCR_MODEL ou envie um PDF com texto selecionavel."
                ),
            )

        return self._extract_with_regex(text)

    async def _extract_with_openai(
        self,
        *,
        text: str,
        ocr_images: list[dict[str, str]],
        extraction_mode: str,
        file_type: str,
    ) -> dict:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self._prompt_for_extraction(
                    text=text,
                    extraction_mode=extraction_mode,
                    file_type=file_type,
                ),
            }
        ]
        for image in ocr_images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image['mime_type']};base64,{image['data']}",
                    },
                }
            )

        payload = {
            "model": settings.openai_ocr_model,
            "messages": [
                {
                    "role": "developer",
                    "content": (
                        "Voce extrai dados de relatorios de bioimpedancia. "
                        "Retorne somente JSON valido. Nunca invente campos ausentes."
                    ),
                },
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_completion_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=75) as client:
                response = await client.post(
                    settings.openai_base_url,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível analisar o arquivo agora. Tente novamente em instantes.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"IA/OCR rejeitou o arquivo: {response.text}",
            )

        message = response.json().get("choices", [{}])[0].get("message", {})
        raw = message.get("content") or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.S)
            if not match:
                return {}
            return json.loads(match.group(0))

    def _prompt_for_extraction(self, *, text: str, extraction_mode: str, file_type: str) -> str:
        fields = ", ".join(METRIC_DEFINITIONS.keys())
        return f"""
Extraia dados reais de um relatorio de composicao corporal/bioimpedancia.

Regras criticas:
- Nunca invente email, senha, objetivo, telefone, endereco ou data de nascimento.
- Extraia birth_date somente se houver data de nascimento explicita no relatorio.
- Campos equivalentes de birth_date: data de nascimento, nascimento, nasc., born date, birth date, date of birth ou DOB.
- Se houver idade mas nao houver data de nascimento explicita, retorne somente age.
- Retorne birth_date no formato ISO YYYY-MM-DD quando existir claramente.
- Se houver "ID: Nome", use como full_name apenas se claramente for nome de pessoa.
- Nao calcule valores derivados. Use somente valores que aparecem no relatorio.
- Se um campo nao existir, use null ou omita.
- Normalize numeros com virgula/ponto e unidades.
- Retorne apenas JSON neste formato:
{{
  "patient": {{
    "full_name": null,
    "gender": null,
    "birth_date": null,
    "age": null,
    "height_cm": null,
    "notes": null
  }},
  "metrics": {{
    "{fields.split(', ')[0]}": null
  }},
  "measurement": {{
    "measured_at": null
  }},
  "confidence": {{}},
  "warnings": []
}}

Campos de metricas permitidos: {fields}.
Modo de extracao: {extraction_mode}.
Tipo de arquivo: {file_type}.

Texto extraido do arquivo:
<<<
{text[:12000]}
>>>
"""

    def _extract_with_regex(self, text: str) -> dict:
        normalized = self._normalize_text(text)

        def find_number(patterns: list[str]) -> float | None:
            for pattern in patterns:
                match = re.search(pattern, normalized, flags=re.I)
                if match:
                    return self._to_float(match.group(1))
            return None

        name = None
        match = re.search(r"\b(?:id|nome|paciente)\s*[:\-]\s*([a-zA-ZÀ-ÿ][^\n\r]{2,80})", text, re.I)
        if match:
            name = self._clean_name(match.group(1))

        gender = None
        match = re.search(r"\b(?:sexo|genero|gender)\s*[:\-]\s*(masculino|feminino|male|female|m|f)\b", text, re.I)
        if match:
            gender = self._normalize_gender(match.group(1))

        birth_date = self._extract_explicit_birth_date(text)

        payload = {
            "patient": {
                "full_name": name,
                "gender": gender,
                "birth_date": birth_date,
                "age": find_number([r"\bidade\s*[:\-]?\s*([0-9]{1,3})\b"]),
                "height_cm": find_number([r"\baltura\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\s*cm\b"]),
            },
            "metrics": {
                "weight_kg": find_number([r"\bpeso\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\s*kg\b"]),
                "bmi": find_number([r"\bimc\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\b", r"\bbmi\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\b"]),
                "body_fat_percent": find_number([r"gordura corporal\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\s*%", r"taxa de gordura corporal\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)"]),
                "muscle_mass_kg": find_number([r"\bmuscul[oa].*?\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\s*kg\b", r"massa muscular\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)\s*kg\b"]),
                "visceral_fat_level": find_number([r"gordura visceral\s*[:\-]?\s*([0-9]+(?:[\.,][0-9]+)?)"]),
                "basal_metabolic_rate": find_number([r"(?:taxa metabolica basal|tmb|bmr).*?\s*([0-9]{3,5})\s*kcal"]),
            },
            "measurement": {},
            "confidence": {},
            "warnings": ["Extração feita com leitura parcial. Revise os dados antes de salvar."],
        }
        return payload

    def _normalize_payload(self, payload: dict, raw_text: str, file_type: str) -> dict:
        patient = payload.get("patient") if isinstance(payload.get("patient"), dict) else {}
        metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
        measurement = payload.get("measurement") if isinstance(payload.get("measurement"), dict) else {}
        confidence = payload.get("confidence") if isinstance(payload.get("confidence"), dict) else {}
        warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []

        normalized_patient: dict[str, Any] = {}
        if patient.get("full_name"):
            normalized_patient["full_name"] = self._clean_name(str(patient["full_name"]))
        if patient.get("gender"):
            normalized_patient["gender"] = self._normalize_gender(str(patient["gender"]))
        birth_date = self._normalize_birth_date(patient.get("birth_date"))
        if birth_date:
            normalized_patient["birth_date"] = birth_date
        age = self._to_float(patient.get("age"))
        if age is not None and 0 < age < 120:
            normalized_patient["age"] = int(age)
            if not birth_date:
                warnings.append("O relatório contém idade, mas não contém data de nascimento explícita.")
        height = self._to_float(patient.get("height_cm"))
        if height is not None and 80 <= height <= 250:
            normalized_patient["height_cm"] = height
            metrics.setdefault("height_cm", height)
        if patient.get("notes"):
            normalized_patient["notes"] = str(patient["notes"]).strip()[:700]

        normalized_metrics: dict[str, float] = {}
        for key, (_, _, minimum, maximum) in METRIC_DEFINITIONS.items():
            value = self._to_float(metrics.get(key))
            if value is None:
                continue
            if minimum is not None and value < minimum:
                warnings.append(f"{key} removido por valor abaixo do esperado.")
                continue
            if maximum is not None and value > maximum:
                warnings.append(f"{key} removido por valor acima do esperado.")
                continue
            normalized_metrics[key] = round(value, 2)

        measured_at = measurement.get("measured_at")
        normalized_measurement = {}
        if measured_at:
            parsed = self._normalize_datetime(str(measured_at))
            if parsed:
                normalized_measurement["measured_at"] = parsed

        if raw_text and not self._looks_like_body_composition(raw_text) and len(normalized_metrics) < 2:
            warnings.append("O arquivo tem poucos sinais de relatório de bioimpedância.")

        if (normalized_patient or normalized_metrics) and len(normalized_metrics) < 4:
            warnings.append("Poucos dados foram encontrados. Revise os campos manualmente antes de salvar.")

        if file_type in IMAGE_FILE_TYPES and len(normalized_metrics) < 4:
            warnings.append("Se a imagem estiver desfocada ou cortada, envie uma versão mais nítida do relatório.")

        return {
            "patient": normalized_patient,
            "metrics": normalized_metrics,
            "measurement": normalized_measurement,
            "confidence": {
                key: min(max(float(value), 0), 1)
                for key, value in confidence.items()
                if isinstance(value, int | float)
            },
            "warnings": list(dict.fromkeys(str(item)[:180] for item in warnings if item)),
        }

    def _has_useful_data(self, payload: dict) -> bool:
        patient = payload.get("patient", {})
        metrics = payload.get("metrics", {})
        return bool(len(metrics) >= 2 or (patient.get("full_name") and len(metrics) >= 1))

    def _autofill_fields(self, payload: dict) -> list[str]:
        fields = []
        patient = payload.get("patient", {})
        if patient.get("full_name"):
            fields.append("fullName")
        if patient.get("gender"):
            fields.append("gender")
        if patient.get("birth_date"):
            fields.append("birthDate")
        if patient.get("notes"):
            fields.append("notes")
        return fields

    async def _upload_import_file(
        self,
        *,
        import_id: str,
        nutritionist_id: str,
        file_name: str,
        content: bytes,
        mime_type: str,
        file_type: str,
        order_index: int,
    ) -> str | None:
        fallback_name = f"bioimpedancia.{file_type}"
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", file_name).strip("-") or fallback_name
        path = f"bioimpedance-imports/{nutritionist_id}/{import_id}/{order_index + 1}-{safe_name[:80]}"
        await self._storage_request(
            "POST",
            f"/storage/v1/object/patient-imports/{path}",
            content=content,
            headers={"Content-Type": mime_type, "x-upsert": "false"},
        )
        return path

    async def _create_import_row(
        self,
        *,
        import_id: str,
        nutritionist_id: str,
        file_path: str | None,
        file_type: str,
        mime_type: str,
        original_file_name: str,
        file_size_bytes: int,
        extracted_payload: dict,
    ) -> dict:
        row_payload = {
            "id": import_id,
            "patient_id": None,
            "nutritionist_id": nutritionist_id,
            "file_url": file_path,
            "file_type": file_type,
            "mime_type": mime_type,
            "original_file_name": original_file_name,
            "file_size_bytes": file_size_bytes,
            "source_type": "bioimpedance_report",
            "extracted_payload": extracted_payload,
            "confidence_payload": extracted_payload.get("confidence", {}),
            "status": "processed",
        }
        response = await self._supabase_request(
            "POST",
            "/rest/v1/patient_imports",
            params={"select": "*"},
            headers={"Prefer": "return=representation"},
            json=row_payload,
        )
        return response[0]

    async def _create_import_file_rows(
        self,
        *,
        import_id: str,
        uploaded_files: list[dict[str, Any]],
    ) -> list[dict]:
        rows = [
            {
                "import_id": import_id,
                "file_url": item["file_path"],
                "file_type": item["file_type"],
                "mime_type": item["mime_type"],
                "original_file_name": item["original_file_name"],
                "file_size_bytes": item["file_size_bytes"],
                "extracted_text": item["extracted_text"],
                "order_index": item["order_index"],
            }
            for item in uploaded_files
        ]
        response = await self._supabase_request(
            "POST",
            "/rest/v1/patient_import_files",
            params={"select": "*"},
            headers={"Prefer": "return=representation"},
            json=rows,
        )
        return response or []

    async def _supabase_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        json: Any | None = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{self.supabase_url}{path}",
                    headers={**self.service_headers, **(headers or {})},
                    params=params,
                    json=json,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel conectar ao Supabase.",
            ) from None

        if response.status_code >= 400:
            error_body = self._response_json(response)
            if isinstance(error_body, dict) and error_body.get("code") == "PGRST204":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "A estrutura da tabela patient_imports esta desatualizada. "
                        "Execute as migrations do banco e recarregue o schema cache do Supabase."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Supabase rejeitou a importacao: {response.text}",
            )
        return response.json() if response.content else None

    async def _storage_request(
        self,
        method: str,
        path: str,
        *,
        content: bytes | None = None,
        json: Any | None = None,
        headers: dict | None = None,
    ) -> Any:
        request_headers = {
            "apikey": self.user_service.service_key,
            "Authorization": f"Bearer {self.user_service.service_key}",
            **(headers or {}),
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.request(
                    method,
                    f"{self.supabase_url}{path}",
                    headers=request_headers,
                    content=content,
                    json=json,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel acessar o Storage.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Storage rejeitou o arquivo: {response.text}",
            )
        return response.json() if response.content else {}

    def _response_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))

    def _looks_like_body_composition(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in BODY_COMPOSITION_TERMS)

    def _to_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, int | float):
            return float(value)
        cleaned = str(value).strip().replace(" ", "")
        cleaned = re.sub(r"[^0-9,\.\-]", "", cleaned)
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _clean_name(self, value: str) -> str | None:
        cleaned = re.split(r"\s{2,}|\||\t", value.strip())[0]
        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ' -]", "", cleaned).strip(" -")
        if len(cleaned) < 3 or any(char.isdigit() for char in cleaned):
            return None
        if cleaned.lower() in {"paciente", "cliente", "usuario", "avaliado"}:
            return None
        return " ".join(part.capitalize() for part in cleaned.split())

    def _normalize_gender(self, value: str) -> str | None:
        lowered = value.strip().lower()
        if lowered in {"m", "male", "masculino", "homem"}:
            return "Masculino"
        if lowered in {"f", "female", "feminino", "mulher"}:
            return "Feminino"
        return value.strip()[:40] or None

    def _extract_explicit_birth_date(self, text: str) -> str | None:
        patterns = [
            r"\b(?:data\s*(?:de)?\s*nascimento|nascimento|nasc\.?|dt\.?\s*nasc\.?|data\s*nasc\.?|born\s*date|birth\s*date|date\s*of\s*birth|dob)\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})",
            r"\b(?:data\s*(?:de)?\s*nascimento|nascimento|nasc\.?|dt\.?\s*nasc\.?|data\s*nasc\.?|born\s*date|birth\s*date|date\s*of\s*birth|dob)\s*[:\-]?\s*(\d{4}[\/\.]\d{1,2}[\/\.]\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return self._normalize_birth_date(match.group(1))
        return None

    def _normalize_birth_date(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None

        raw = raw[:24].strip()
        candidates: list[tuple[int, int, int]] = []
        iso_match = re.match(r"^(\d{4})[-\/\.](\d{1,2})[-\/\.](\d{1,2})$", raw)
        if iso_match:
            year, month, day = (int(part) for part in iso_match.groups())
            candidates.append((year, month, day))

        local_match = re.match(r"^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$", raw)
        if local_match:
            day, month, year = (int(part) for part in local_match.groups())
            if year < 100:
                year += 2000 if year <= 26 else 1900
            candidates.append((year, month, day))

        today = datetime.now(timezone.utc).date()
        for year, month, day in candidates:
            try:
                parsed = datetime(year, month, day, tzinfo=timezone.utc).date()
            except ValueError:
                continue
            if 1900 <= parsed.year <= today.year and parsed <= today:
                return parsed.isoformat()
        return None

    def _is_date(self, value: str) -> bool:
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value[:10]))

    def _normalize_datetime(self, value: str) -> str | None:
        raw = value.strip()
        candidates = [
            raw,
            raw.replace(" ", "T"),
        ]
        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.isoformat()
            except ValueError:
                continue
        match = re.search(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}):(\d{2}))?", raw)
        if match:
            day, month, year, hour, minute = match.groups()
            parsed = datetime(
                int(year),
                int(month),
                int(day),
                int(hour or 12),
                int(minute or 0),
                tzinfo=timezone.utc,
            )
            return parsed.isoformat()
        return None
