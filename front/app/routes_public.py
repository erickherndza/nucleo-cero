import hashlib
import os
import secrets

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_from_directory, url_for

from . import limiter
from .mailer import notificar_trabajo_recibido
from .models import Archivo, Trabajo, db

bp_publico = Blueprint("publico", __name__)

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng", ".cr2", ".nef", ".arw"}


def _extension_valida(nombre: str) -> bool:
    return os.path.splitext(nombre)[1].lower() in EXTENSIONES_PERMITIDAS


@bp_publico.route("/")
def index():
    return render_template("index.html")


@bp_publico.route("/subir", methods=["POST"])
@limiter.limit("10 per hour")
def subir():
    email = request.form.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Email inválido"}), 400

    try:
        factor = float(request.form.get("factor", "2.0"))
    except ValueError:
        factor = 2.0
    factor = max(1.0, min(factor, 2.0))

    enlace_externo = request.form.get("enlace_externo", "").strip()
    archivos_subidos = request.files.getlist("archivos")
    archivos_validos = [a for a in archivos_subidos if a.filename and _extension_valida(a.filename)]

    if not archivos_validos and not enlace_externo:
        return jsonify({"error": "Debes adjuntar al menos un archivo o pegar un enlace externo"}), 400

    token_publico = secrets.token_hex(16)
    trabajo = Trabajo(token_publico=token_publico, cliente_email=email, estado="pendiente", factor=factor)
    db.session.add(trabajo)
    db.session.flush()  # asigna trabajo.id sin cerrar la transacción

    directorio_trabajo = os.path.join(current_app.config["DIRECTORIO_ARCHIVOS"], token_publico)
    if archivos_validos:
        os.makedirs(directorio_trabajo, exist_ok=True)

    for archivo in archivos_validos:
        nombre_seguro = os.path.basename(archivo.filename)
        ruta_destino = os.path.join(directorio_trabajo, nombre_seguro)
        archivo.save(ruta_destino)

        sha256 = hashlib.sha256()
        with open(ruta_destino, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                sha256.update(chunk)

        db.session.add(
            Archivo(
                trabajo_id=trabajo.id,
                tipo="origen",
                nombre=nombre_seguro,
                ruta=ruta_destino,
                bytes=os.path.getsize(ruta_destino),
                sha256=sha256.hexdigest(),
            )
        )

    if enlace_externo:
        # v1: el cliente subió el burst a Drive/WeTransfer. No hay descarga
        # automática; queda registrado para que el operador lo baje a mano.
        trabajo.params_json = f'{{"enlace_externo": {enlace_externo!r}}}'
        if not archivos_validos:
            trabajo.estado = "pendiente"

    db.session.commit()

    url_estado = url_for("publico.estado", token=token_publico, _external=True)
    notificar_trabajo_recibido(email, token_publico, url_estado)

    return jsonify({"token_publico": token_publico, "url_estado": url_estado}), 201


@bp_publico.route("/estado/<token>")
def estado(token):
    trabajo = Trabajo.query.filter_by(token_publico=token).first_or_404()
    archivos_resultado = [a for a in trabajo.archivos if a.tipo in ("resultado", "informe")]
    return render_template("estado.html", trabajo=trabajo, archivos=archivos_resultado)


@bp_publico.route("/descargar/<token>/<int:archivo_id>")
def descargar(token, archivo_id):
    trabajo = Trabajo.query.filter_by(token_publico=token).first_or_404()
    archivo = Archivo.query.filter_by(id=archivo_id, trabajo_id=trabajo.id).first_or_404()

    if archivo.tipo not in ("resultado", "informe"):
        abort(403)

    directorio, nombre = os.path.split(archivo.ruta)
    return send_from_directory(directorio, nombre, as_attachment=True, download_name=archivo.nombre)
