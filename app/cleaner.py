"""
Inspeção e limpeza de metadados de imagens usando ExifTool.

Os geradores de imagem por IA (Gemini, ChatGPT/DALL-E, Adobe Firefly, etc.)
inserem marcadores em vários lugares dos metadados:

- C2PA / "Content Credentials": manifests assinados embutidos em blocos JUMBF.
- XMP `DigitalSourceType` = trainedAlgorithmicMedia / compositeSynthetic.
- IPTC `DigitalSourceType`.
- EXIF/XMP `Software` / `CreatorTool` (ex.: "Gemini", "OpenAI", "Firefly").
- XMP `Credit` (ex.: "Made with Google AI").

LIMITAÇÃO IMPORTANTE: marca d'água invisível embutida nos PIXELS (ex.: o
SynthID do Google) NÃO é metadado e NÃO é removida aqui — só sairia
re-encodando/degradando a própria imagem.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

# Permite apontar para um exiftool fora do PATH via variável de ambiente.
EXIFTOOL_PATH = os.environ.get("EXIFTOOL_PATH", "exiftool")


class ExifToolNotFound(RuntimeError):
    """Disparado quando o binário do ExifTool não é encontrado."""


# Padrões (case-insensitive) que indicam origem por IA, buscados nos
# valores E nos nomes das tags retornadas pelo ExifTool.
AI_VALUE_MARKERS = (
    "trainedalgorithmicmedia",
    "compositesynthetic",
    "algorithmicmedia",
    "gemini",
    "imagen",
    "made with google ai",
    "openai",
    "dall-e",
    "dall·e",
    "chatgpt",
    "gpt-4",
    "stable diffusion",
    "midjourney",
    "firefly",
    "adobe firefly",
    "generative",
    "ai-generated",
    "synthid",
)

# Tags cujo simples PRESENÇA já é um marcador de IA / proveniência C2PA.
AI_TAG_MARKERS = (
    "c2pa",
    "contentcredential",
    "jumbf",
    "digitalsourcetype",
    "claim_generator",
    "claimgenerator",
)


def find_exiftool() -> str:
    """Retorna o caminho do exiftool ou levanta ExifToolNotFound."""
    resolved = shutil.which(EXIFTOOL_PATH)
    if not resolved:
        raise ExifToolNotFound(
            "ExifTool não encontrado. Instale o binário (veja o README) "
            "ou defina a variável de ambiente EXIFTOOL_PATH apontando para ele."
        )
    return resolved


def is_available() -> bool:
    try:
        find_exiftool()
        return True
    except ExifToolNotFound:
        return False


@dataclass
class MetadataReport:
    """Resultado da inspeção de uma imagem."""

    all_tags: dict = field(default_factory=dict)
    ai_markers: list = field(default_factory=list)  # [{tag, value, reason}]

    @property
    def has_ai_markers(self) -> bool:
        return len(self.ai_markers) > 0


def _run(args: list[str]) -> subprocess.CompletedProcess:
    exe = find_exiftool()
    return subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def inspect(image_path: str) -> MetadataReport:
    """Lê todos os metadados e identifica marcadores de IA."""
    # -G1: agrupa por família (XMP-iptcExt, IPTC, etc.) | -j: JSON | -a: duplicadas
    proc = _run(["-G1", "-j", "-a", "-u", image_path])
    if proc.returncode != 0 or not proc.stdout.strip():
        return MetadataReport()

    data = json.loads(proc.stdout)
    tags: dict = data[0] if data else {}
    tags.pop("SourceFile", None)

    markers: list[dict] = []
    for tag, value in tags.items():
        text = str(value).lower()
        tag_l = tag.lower()

        matched_reason = None
        if any(m in tag_l for m in AI_TAG_MARKERS):
            matched_reason = "tag de proveniência/IA"
        else:
            hit = next((m for m in AI_VALUE_MARKERS if m in text), None)
            if hit:
                matched_reason = f"valor contém '{hit}'"

        if matched_reason:
            markers.append({"tag": tag, "value": value, "reason": matched_reason})

    return MetadataReport(all_tags=tags, ai_markers=markers)


def clean(input_path: str, output_path: str) -> None:
    """
    Remove TODOS os metadados (EXIF/XMP/IPTC) e os manifests C2PA/JUMBF,
    gravando o resultado em output_path. A imagem original não é tocada.
    """
    shutil.copyfile(input_path, output_path)

    # -all=          remove todos os metadados (EXIF/XMP/IPTC, text chunks de PNG, etc.)
    # -trailer:all=  remove dados anexados depois da imagem (alguns manifests C2PA)
    # -m             ignora avisos menores para não abortar a limpeza à toa
    # O -all= também apaga os blocos JUMBF onde vive o Content Credentials/C2PA.
    proc = _run(
        ["-all=", "-trailer:all=", "-m", "-overwrite_original", output_path]
    )
    # Se a versão mais agressiva falhar (formato exótico), tenta só o -all=.
    if proc.returncode != 0:
        proc = _run(["-all=", "-m", "-overwrite_original", output_path])
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().replace("\n", " ")
            raise RuntimeError(
                f"ExifTool não conseguiu limpar a imagem: {detail or 'erro desconhecido'}"
            )
