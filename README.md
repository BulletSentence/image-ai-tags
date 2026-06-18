# 🧼 image-ai-tags

Monólito Python (Flask) que recebe uma imagem por uma página web, **inspeciona**
e **remove os metadados/tags de IA** inseridos por geradores como Gemini,
ChatGPT/DALL·E, Adobe Firefly, etc.

O que é removido:

- **C2PA / "Content Credentials"** — manifests assinados em blocos JUMBF.
- **XMP / IPTC `DigitalSourceType`** — ex.: `trainedAlgorithmicMedia`, `compositeSynthetic`.
- **EXIF/XMP `Software` / `CreatorTool`** — ex.: "Gemini", "OpenAI", "Firefly".
- Todo o restante dos metadados EXIF/XMP/IPTC (limpeza completa).

> ⚠️ **Limitação:** marca d'água invisível embutida nos **pixels** (ex.: o
> **SynthID** do Google) **não** é metadado e **não** é removida — só sairia
> re-encodando/degradando a própria imagem.

---

## Pré-requisitos

### 1. Python 3.10+
Já instalado (3.12).

### 2. ExifTool (binário externo — instalar manualmente)

O projeto chama o `exiftool` via linha de comando. Escolha uma opção:

**Windows (recomendado — instalador/standalone):**
1. Baixe o "Windows Executable" em <https://exiftool.org>.
2. Extraia e **renomeie** `exiftool(-k).exe` para `exiftool.exe`.
3. Coloque numa pasta do `PATH` (ex.: `C:\Windows`) **ou** aponte via variável:
   ```powershell
   $env:EXIFTOOL_PATH = "C:\ferramentas\exiftool.exe"
   ```

**Via gerenciador de pacotes (se tiver):**
```powershell
winget install OliverBetz.ExifTool
# ou
choco install exiftool
```

Confirme:
```powershell
exiftool -ver
```

---

## Como rodar

```powershell
# 1. (opcional) ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. dependências Python
pip install -r requirements.txt

# 3. subir o app
python run.py
```

Acesse <http://127.0.0.1:5000>.

---

## Estrutura

```
image-ai-tags/
├── run.py                  # ponto de entrada (dev server)
├── requirements.txt        # deps Python (só Flask)
├── README.md
├── .gitignore
└── app/
    ├── __init__.py         # app factory + rotas (/, /inspect, /clean)
    ├── cleaner.py          # integração com ExifTool (inspeção + limpeza)
    └── templates/
        └── index.html      # front (HTML+CSS+JS inline)
```

## Rotas

| Método | Rota       | Descrição                                              |
|--------|------------|--------------------------------------------------------|
| GET    | `/`        | Página de upload.                                      |
| POST   | `/inspect` | Recebe `image`, devolve JSON com metadados + marcadores de IA detectados. |
| POST   | `/clean`   | Recebe `image`, devolve o arquivo limpo para download. |

A imagem original nunca é alterada — a limpeza é feita sobre uma cópia em diretório temporário, que é removida após o envio.
