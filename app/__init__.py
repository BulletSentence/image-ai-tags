"""Fábrica do app Flask (monólito: front + back no mesmo projeto)."""

from __future__ import annotations

import os
import tempfile
import uuid

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
)
from werkzeug.utils import secure_filename

from . import cleaner

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "tiff", "tif", "heic", "heif"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # Diretório temporário próprio do processo para uploads/saídas.
    work_dir = os.path.join(tempfile.gettempdir(), "image-ai-tags")
    os.makedirs(work_dir, exist_ok=True)
    app.config["WORK_DIR"] = work_dir

    @app.get("/")
    def index():
        return render_template("index.html", exiftool_ok=cleaner.is_available())

    @app.post("/inspect")
    def inspect():
        path = _save_upload()
        try:
            report = cleaner.inspect(path)
            return jsonify(
                {
                    "has_ai_markers": report.has_ai_markers,
                    "ai_markers": report.ai_markers,
                    "total_tags": len(report.all_tags),
                    "all_tags": report.all_tags,
                }
            )
        finally:
            _safe_remove(path)

    @app.post("/clean")
    def clean():
        path = _save_upload()
        deep = request.form.get("deep") in ("1", "true", "on")
        strength = request.form.get("strength", "medio")
        base, ext = os.path.splitext(os.path.basename(path))
        out_path = os.path.join(app.config["WORK_DIR"], f"{base}_clean{ext}")
        try:
            cleaner.clean(path, out_path, deep=deep, strength=strength)
        except cleaner.ExifToolNotFound as err:
            _safe_remove(path); _safe_remove(out_path)
            return jsonify({"error": str(err)}), 503
        except Exception as err:
            _safe_remove(path); _safe_remove(out_path)
            return jsonify({"error": str(err)}), 500

        try:
            original_name = secure_filename(request.files["image"].filename)
            name, ext2 = os.path.splitext(original_name)
            download_name = f"{name or 'imagem'}_limpa{ext2 or ext}"
            response = send_file(out_path, as_attachment=True, download_name=download_name)
            # Remove os arquivos temporários depois que a resposta for enviada.
            response.call_on_close(lambda: (_safe_remove(out_path), _safe_remove(path)))
            return response
        except Exception:
            _safe_remove(path); _safe_remove(out_path)
            raise

    @app.errorhandler(cleaner.ExifToolNotFound)
    def _no_exiftool(err):
        return jsonify({"error": str(err)}), 503

    def _save_upload() -> str:
        if "image" not in request.files:
            abort(400, "Nenhum arquivo enviado (campo 'image').")
        file = request.files["image"]
        if not file.filename:
            abort(400, "Nome de arquivo vazio.")
        if not _allowed(file.filename):
            abort(400, "Extensão não suportada.")
        safe = secure_filename(file.filename)
        unique = f"{uuid.uuid4().hex}_{safe}"
        path = os.path.join(app.config["WORK_DIR"], unique)
        file.save(path)
        return path

    return app


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
