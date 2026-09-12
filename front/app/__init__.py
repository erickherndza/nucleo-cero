import os

from dotenv import load_dotenv
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .models import db

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=[])


def crear_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambiar-en-produccion")
    app.config["WORKER_TOKEN"] = os.environ.get("WORKER_TOKEN", "")
    app.config["DIRECTORIO_ARCHIVOS"] = os.environ.get("DIRECTORIO_ARCHIVOS", "./archivos")
    app.config["DIAS_RETENCION_ARCHIVOS"] = int(os.environ.get("DIAS_RETENCION_ARCHIVOS", "7"))
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024  # 256 MB, límite típico de shared hosting

    usuario = os.environ.get("MYSQL_USER", "")
    password = os.environ.get("MYSQL_PASSWORD", "")
    host = os.environ.get("MYSQL_HOST", "localhost")
    base_datos = os.environ.get("MYSQL_DATABASE", "")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{usuario}:{password}@{host}/{base_datos}?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 280}

    os.makedirs(app.config["DIRECTORIO_ARCHIVOS"], exist_ok=True)

    db.init_app(app)
    limiter.init_app(app)

    from .routes_public import bp_publico
    from .routes_worker import bp_worker

    app.register_blueprint(bp_publico)
    app.register_blueprint(bp_worker, url_prefix="/api")

    return app
