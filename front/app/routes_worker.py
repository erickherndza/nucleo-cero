import hashlib
import os
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from .auth import requiere_token_worker
from .mailer import notificar_trabajo_con_error, notificar_trabajo_listo
from .models import Archivo, Trabajo, db, liberar_trabajos_atascados, reclamar_siguiente_trabajo

bp_worker = Blueprint("worker", __name__)

ESTADOS_QUE_PUEDE_FIJAR_WORKER = ("procesando", "listo", "error")


@bp_worker.route("/trabajos/siguiente", methods=["POST"])
@requiere_token_worker
def siguiente_trabajo():
    liberar_trabajos_atascados()

    datos = request.get_json(silent=True) or {}
    worker_id = datos.get("worker_id", "desconocido")

    trabajo = reclamar_siguiente_trabajo(worker_id)
    if trabajo is None:
        return "", 204

    return jsonify(trabajo.a_dict_worker())


@bp_worker.route("/archivos/<int:archivo_id>/descargar", methods=["GET"])
@requiere_token_worker
def descargar_archivo(archivo_id):
    archivo = Archivo.query.filter_by(id=archivo_id, tipo="origen").first_or_404()
    directorio, nombre = os.path.split(archivo.ruta)
    respuesta = send_from_directory(directorio, nombre, as_attachment=True, download_name=archivo.nombre)
    if archivo.sha256:
        respuesta.headers["X-SHA256"] = archivo.sha256
    return respuesta


@bp_worker.route("/trabajos/<int:trabajo_id>/estado", methods=["POST"])
@requiere_token_worker
def actualizar_estado(trabajo_id):
    trabajo = Trabajo.query.get_or_404(trabajo_id)
    datos = request.get_json(silent=True) or {}
    estado = datos.get("estado")
    mensaje = datos.get("mensaje", "")

    if estado not in ESTADOS_QUE_PUEDE_FIJAR_WORKER:
        return jsonify({"error": f"Estado no permitido: {estado}"}), 400

    trabajo.estado = estado
    if estado == "error":
        trabajo.error_msg = mensaje
        trabajo.terminado_en = datetime.utcnow()
        notificar_trabajo_con_error(trabajo.cliente_email, trabajo.token_publico, mensaje)

    db.session.commit()
    return jsonify({"ok": True})


@bp_worker.route("/trabajos/<int:trabajo_id>/resultado", methods=["POST"])
@requiere_token_worker
def subir_resultado(trabajo_id):
    trabajo = Trabajo.query.get_or_404(trabajo_id)

    archivo_resultado = request.files.get("resultado")
    archivo_informe = request.files.get("informe")
    if archivo_resultado is None or archivo_informe is None:
        return jsonify({"error": "Se requieren los archivos 'resultado' e 'informe'"}), 400

    directorio_trabajo = os.path.join(current_app.config["DIRECTORIO_ARCHIVOS"], trabajo.token_publico)
    os.makedirs(directorio_trabajo, exist_ok=True)

    for campo, archivo, tipo, sha_esperado in (
        ("resultado", archivo_resultado, "resultado", request.form.get("sha256_resultado")),
        ("informe", archivo_informe, "informe", request.form.get("sha256_informe")),
    ):
        nombre_seguro = os.path.basename(archivo.filename)
        ruta_destino = os.path.join(directorio_trabajo, nombre_seguro)
        archivo.save(ruta_destino)

        sha256 = hashlib.sha256()
        with open(ruta_destino, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                sha256.update(chunk)
        sha_calculado = sha256.hexdigest()

        if sha_esperado and sha_esperado != sha_calculado:
            return jsonify({"error": f"SHA256 no coincide para {campo}"}), 400

        db.session.add(
            Archivo(
                trabajo_id=trabajo.id,
                tipo=tipo,
                nombre=nombre_seguro,
                ruta=ruta_destino,
                bytes=os.path.getsize(ruta_destino),
                sha256=sha_calculado,
            )
        )

    dias_retencion = current_app.config["DIAS_RETENCION_ARCHIVOS"]
    trabajo.metricas_json = request.form.get("metricas_json", "{}")
    trabajo.estado = "listo"
    trabajo.terminado_en = datetime.utcnow()
    trabajo.purgar_en = trabajo.terminado_en + timedelta(days=dias_retencion)
    db.session.commit()

    from flask import url_for

    url_estado = url_for("publico.estado", token=trabajo.token_publico, _external=True)
    notificar_trabajo_listo(trabajo.cliente_email, trabajo.token_publico, url_estado)

    return jsonify({"ok": True})
