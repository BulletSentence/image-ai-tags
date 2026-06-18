# image-ai-tags

A small Python monolith (Flask, front and back in the same project) that takes
an image through a web page, **inspects** it, and **removes the AI provenance
metadata** that generators such as Gemini, ChatGPT/DALL-E, and Adobe Firefly
embed into images they create or edit.

<img width="1143" height="890" alt="image" src="https://github.com/user-attachments/assets/0da39df0-21ae-41fd-a299-4aba8bf985fc" />


What gets removed:

- **C2PA / "Content Credentials"** — signed manifests stored in JUMBF blocks.
- **XMP / IPTC `DigitalSourceType`** — e.g. `trainedAlgorithmicMedia`, `compositeSynthetic`.
- **EXIF/XMP `Software` / `CreatorTool` / `Creator` / `Credit`** — e.g. "Gemini", "OpenAI", "Firefly", "Made with Google AI".
- Everything else in the EXIF/XMP/IPTC blocks (a full metadata strip).

> **Limitation:** an invisible watermark embedded in the **pixels** (for example
> Google's **SynthID**) is not metadata and is **not** removed here. Stripping
> metadata cannot touch it — that would require re-encoding/degrading the image
> itself.

The original file is never modified: cleaning runs on a copy in a temporary
directory, which is deleted after the response is sent.

---

## How it works

1. **Inspect** — reads all metadata with `exiftool -G1 -j -a` and flags AI
   markers: C2PA/JUMBF tags, `DigitalSourceType`, and `Software`/`CreatorTool`
   values containing known AI tool names.
2. **Clean** — runs `exiftool -all= -trailer:all= --jumbf:all` on a copy and
   returns the stripped file for download.

The metadata work is delegated to the **ExifTool** command-line binary, invoked
through `subprocess`. There is no Python imaging dependency.

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
  requirements.txt       Python dependencies (Flask only)
  README.md
  .gitignore
  app/
    __init__.py          app factory and routes (/, /inspect, /clean)
    cleaner.py           ExifTool integration (inspect and clean)
    templates/
      index.html         frontend (HTML + CSS + JS, inline)
```

## Routes

| Method | Route      | Description                                                            |
|--------|------------|------------------------------------------------------------------------|
| GET    | `/`        | Upload page.                                                           |
| POST   | `/inspect` | Receives `image`, returns JSON with all metadata and detected AI markers. |
| POST   | `/clean`   | Receives `image`, returns the cleaned file as a download.             |

## Technologies

- **Backend:** Python 3.10+, Flask
- **Metadata engine:** ExifTool (external binary, called via `subprocess`)
- **Frontend:** HTML, CSS, and vanilla JavaScript served through a Jinja2 template

## Supported formats

JPEG, PNG, WEBP, TIFF, HEIC/HEIF. Maximum upload size: 50 MB.
