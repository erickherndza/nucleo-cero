import hmac
from functools import wraps

from flask import current_app, jsonify, request


def requiere_token_worker(f):
    """Protege una ruta comparando `Authorization: Bearer <token>` contra
    WORKER_TOKEN con `hmac.compare_digest` (nunca `==`, para evitar timing
    attacks).
    """

    @wraps(f)
    def envoltura(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            return jsonify({"error": "Falta token de autorización"}), 401

        token_recibido = cabecera[len("Bearer "):]
        token_esperado = current_app.config["WORKER_TOKEN"]

        if not token_esperado or not hmac.compare_digest(token_recibido, token_esperado):
            return jsonify({"error": "Token inválido"}), 403

        return f(*args, **kwargs)

    return envoltura
