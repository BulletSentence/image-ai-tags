"""
Re-processamento de pixels (best-effort) para perturbar marcas d'água invisíveis.

IMPORTANTE — leia antes de criar expectativa:
  Marcas d'água ROBUSTAS, como o SynthID do Google, são treinadas
  adversarialmente para sobreviver justamente a ruído, recompressão e
  redimensionamento. Este módulo NÃO promete removê-las — e provavelmente
  não as remove. O que ele faz bem é destruir marcas FRÁGEIS/ingênuas
  (LSB, a lib `invisible-watermark` do SD/SDXL, marcas de frequência simples)
  e garantir que a imagem seja totalmente re-codificada.

  O único método com chance real contra o SynthID é regeneração via difusão
  (SDXL/ControlNet img2img), que é pesado (GPU + modelo de vários GB), com
  perda e deixa rastros forenses. Fica fora do escopo deste app leve.

A técnica aqui combina, conforme a intensidade:
  - reamostragem (downscale + upscale): desincroniza marcas espaciais/frequência;
  - ruído gaussiano de baixa amplitude;
  - leve blur;
  - recompressão (JPEG/WEBP).
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# intensidade -> parâmetros. Quanto mais forte, mais dano à marca e à qualidade.
#
# Medições (contra a marca robusta dwtDctSvd do Stable Diffusion):
#   - ruído/reamostragem em níveis suaves NÃO quebram marcas robustas;
#   - o recorte de borda + resize ("crop") desincroniza a grade do watermark
#     e é o ataque mais eficaz por unidade de qualidade perdida;
#   - recompressão (JPEG) abaixo de ~q55 também derruba.
# Por isso "medio" e "forte" recortam uma borda (leve zoom) — é o que dá a elas
# chance real contra marcas robustas. "leve" é gentil e só pega marcas frágeis.
PRESETS = {
    "leve":  {"crop": 0.00, "resample": 1.00, "noise": 1.5, "blur": 0.0, "quality": 92},
    "medio": {"crop": 0.03, "resample": 1.00, "noise": 2.0, "blur": 0.0, "quality": 80},
    "forte": {"crop": 0.05, "resample": 1.00, "noise": 3.5, "blur": 0.3, "quality": 62},
}


def disrupt(input_path: str, output_path: str, strength: str = "medio") -> None:
    """
    Lê input_path, re-processa os pixels e grava em output_path.
    Mantém o formato/extensão de saída (definidos por output_path).
    """
    cfg = PRESETS.get(strength, PRESETS["medio"])

    im = Image.open(input_path)
    src_fmt = (im.format or "").upper()
    # "Assa" a orientação do EXIF nos pixels (já que os metadados serão removidos).
    im = ImageOps.exif_transpose(im) or im

    # Separa canal alfa (se houver) para preservá-lo.
    alpha = None
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        alpha = im.getchannel("A")
        im = im.convert("RGB")
    else:
        im = im.convert("RGB")

    w, h = im.size

    # 0) Recorte de borda + resize de volta (desincroniza a grade do watermark).
    #    É o ataque geométrico mais eficaz; causa um leve zoom na imagem.
    if cfg.get("crop", 0) > 0:
        mx, my = int(w * cfg["crop"]), int(h * cfg["crop"])
        if w - 2 * mx > 8 and h - 2 * my > 8:
            im = im.crop((mx, my, w - mx, h - my)).resize((w, h), Image.BICUBIC)

    # 1) Reamostragem (desincroniza marcas no domínio espacial/frequência).
    if cfg["resample"] != 1.0:
        sw = max(1, round(w * cfg["resample"]))
        sh = max(1, round(h * cfg["resample"]))
        im = im.resize((sw, sh), Image.BICUBIC).resize((w, h), Image.BICUBIC)

    # 2) Ruído gaussiano de baixa amplitude.
    arr = np.asarray(im, dtype=np.float32)
    if cfg["noise"] > 0:
        arr = arr + np.random.normal(0.0, cfg["noise"], arr.shape).astype(np.float32)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr, mode="RGB")

    # 3) Leve blur (só nas intensidades mais altas).
    if cfg["blur"] > 0:
        out = out.filter(ImageFilter.GaussianBlur(cfg["blur"]))

    # Reanexa o alfa, se existia.
    if alpha is not None:
        out = out.convert("RGBA")
        out.putalpha(alpha)

    _save(out, output_path, src_fmt, cfg["quality"])


def _save(img: Image.Image, output_path: str, src_fmt: str, quality: int) -> None:
    ext = os.path.splitext(output_path)[1].lower()

    if ext in (".jpg", ".jpeg"):
        img.convert("RGB").save(output_path, "JPEG", quality=quality, subsampling=1)
    elif ext == ".png":
        img.save(output_path, "PNG", optimize=True)
    elif ext == ".webp":
        img.save(output_path, "WEBP", quality=quality, method=4)
    elif ext in (".tif", ".tiff"):
        img.convert("RGB").save(output_path, "TIFF")
    else:
        # fallback: tenta pelo formato de origem, senão PNG
        fmt = src_fmt if src_fmt in ("JPEG", "PNG", "WEBP", "TIFF") else "PNG"
        if fmt == "JPEG":
            img.convert("RGB").save(output_path, "JPEG", quality=quality)
        else:
            img.save(output_path, fmt)
