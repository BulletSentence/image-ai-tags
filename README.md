# image-ai-tags

A small Python monolith (Flask, front and back in the same project) that takes
an image through a web page, **inspects** it, and **removes the AI provenance
metadata** that generators such as Gemini, ChatGPT/DALL-E, and Adobe Firefly
embed into images they create or edit.

What gets removed:

- **C2PA / "Content Credentials"** — signed manifests stored in JUMBF blocks.
- **XMP / IPTC `DigitalSourceType`** — e.g. `trainedAlgorithmicMedia`, `compositeSynthetic`.
- **EXIF/XMP `Software` / `CreatorTool` / `Creator` / `Credit`** — e.g. "Gemini", "OpenAI", "Firefly", "Made with Google AI".
- Everything else in the EXIF/XMP/IPTC blocks (a full metadata strip).
- **Optionally (deep clean):** a best-effort attempt to disrupt invisible
  pixel watermarks — see ["Deep clean"](#deep-clean-invisible-watermarks) below.

The original file is never modified: cleaning runs on a copy in a temporary
directory, which is deleted after the response is sent.

---

## How it works

1. **Inspect** — reads all metadata with `exiftool -G1 -j -a` and flags AI
   markers: C2PA/JUMBF tags, `DigitalSourceType`, and `Software`/`CreatorTool`
   values containing known AI tool names.
2. **Clean** — strips all metadata with `exiftool -all= -trailer:all= -m`
   (this also removes the JUMBF blocks that hold C2PA/Content Credentials) and
   returns the file for download.
3. **Deep clean (optional)** — before stripping metadata, re-processes the
   pixels (geometric crop + resample + noise + recompression) to try to break
   invisible watermarks. Uses Pillow + numpy.

The metadata work is delegated to the **ExifTool** command-line binary, invoked
through `subprocess`. The optional pixel re-processing uses Pillow and numpy.

---

## Deep clean (invisible watermarks)

Some generators also embed an **invisible watermark directly in the pixels**
(not in metadata). The optional "deep clean" re-encodes the pixels to try to
disrupt it. Be realistic about what this can and cannot do — these numbers were
measured against the robust `dwtDctSvd` watermark from the
`invisible-watermark` library (the one Stable Diffusion/SDXL use):

| Strength | Technique | Breaks SD/SDXL watermark? | Quality (PSNR) |
|----------|-----------|---------------------------|----------------|
| `leve`   | mild noise + recompress | no (gentle, fragile marks only) | ~44 dB |
| `medio`  | ~3% border crop + resample + noise | **yes** | ~31 dB |
| `forte`  | ~5% crop + noise + blur + low-quality recompress | **yes** | ~30 dB |

Key findings from testing and the literature:

- Noise/resampling at quality-preserving levels do **not** break robust
  frequency watermarks. The effective lever is a small **geometric crop**
  (it desynchronizes the watermark's embedding grid) plus recompression.
- **SynthID (Google) is not the same as the SD watermark.** It is a proprietary,
  learned watermark trained adversarially so that any cheap removal also
  destroys the image, and there is **no public local detector** to verify
  removal. This tool's deep clean **may not remove SynthID** — treat it as
  best-effort, not a guarantee.
- The only approach with a real shot at SynthID is **diffusion regeneration**
  (SDXL/ControlNet img2img), which needs a heavy ML stack (torch + diffusers +
  a multi-GB model + GPU), is lossy, non-deterministic, and leaves forensic
  traces. That is intentionally **out of scope** for this lightweight app.

Sources: [Is SynthID Removable? (aifreeapi)](https://www.aifreeapi.com/en/posts/synthid-watermark-removable),
[remove-ai-watermarks (GitHub)](https://github.com/wiltodelta/remove-ai-watermarks),
[Forging and Removing Latent-Noise Diffusion Watermarks (arXiv)](https://arxiv.org/pdf/2504.20111),
[SynthID-Image: watermarking at internet scale (arXiv)](https://arxiv.org/pdf/2510.09263).

---

## Requirements

### 1. Python 3.10+

### 2. ExifTool (external binary, installed manually)

The app calls the `exiftool` command. Pick one option:

**Windows (standalone executable):**
1. Download the "Windows Executable" from https://exiftool.org.
2. Extract it and rename `exiftool(-k).exe` to `exiftool.exe`.
3. Put it on a folder in your `PATH` (e.g. `C:\Windows`), or point the app at it
   with an environment variable:
   ```powershell
   $env:EXIFTOOL_PATH = "C:\exiftool-13.59_64\exiftool.exe"
   ```

**Via a package manager (if available):**
```powershell
winget install OliverBetz.ExifTool
# or
choco install exiftool
```

Verify:
```powershell
exiftool -ver
```

> The app resolves ExifTool from the `EXIFTOOL_PATH` environment variable, or
> from `exiftool` on the `PATH` if that variable is not set. The home page shows
> a warning when the binary cannot be found.

---

## Setup and run

**PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:EXIFTOOL_PATH = "C:\exiftool-13.59_64\exiftool.exe"
python run.py
```

**Git Bash:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt

export EXIFTOOL_PATH="C:\exiftool-13.59_64\exiftool.exe"
python run.py
```

Then open http://127.0.0.1:5000.

> If you set `EXIFTOOL_PATH` as a permanent user environment variable, new
> terminals will pick it up automatically and the `export`/`$env:` line is no
> longer needed.

---

## Project layout

```
image-ai-tags/
  run.py                 entry point (dev server)
  requirements.txt       Python dependencies (Flask, Pillow, numpy)
  README.md
  .gitignore
  app/
    __init__.py          app factory and routes (/, /inspect, /clean)
    cleaner.py           ExifTool integration (inspect and clean)
    watermark.py         best-effort pixel re-processing (deep clean)
    templates/
      index.html         frontend (HTML + CSS + JS, inline)
```

## Routes

| Method | Route      | Description                                                            |
|--------|------------|------------------------------------------------------------------------|
| GET    | `/`        | Upload page.                                                           |
| POST   | `/inspect` | Receives `image`, returns JSON with all metadata and detected AI markers. |
| POST   | `/clean`   | Receives `image` (+ optional `deep=1` and `strength=leve\|medio\|forte`), returns the cleaned file as a download. |

## Technologies

- **Backend:** Python 3.10+, Flask
- **Metadata engine:** ExifTool (external binary, called via `subprocess`)
- **Pixel re-processing (deep clean):** Pillow + numpy
- **Frontend:** HTML, CSS, and vanilla JavaScript served through a Jinja2 template

## Supported formats

JPEG, PNG, WEBP, TIFF. Maximum upload size: 50 MB. (Metadata-only clean also
works on HEIC/HEIF; the deep clean needs a format Pillow can re-encode.)
