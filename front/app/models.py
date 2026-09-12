from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

ESTADOS_VALIDOS = ("pendiente", "reclamado", "procesando", "listo", "error")
MINUTOS_TIMEOUT_TRABAJO = 120  # un trabajo reclamado/procesando por más de esto vuelve a pendiente


class Trabajo(db.Model):
    __tablename__ = "trabajos"

    id = db.Column(db.Integer, primary_key=True)
    token_publico = db.Column(db.CHAR(32), nullable=False, unique=True)
    cliente_email = db.Column(db.String(255), nullable=False)
    estado = db.Column(db.Enum(*ESTADOS_VALIDOS), nullable=False, default="pendiente")
    factor = db.Column(db.Numeric(3, 1), nullable=False, default=2.0)
    params_json = db.Column(db.Text)
    worker_id = db.Column(db.String(64))
    intentos = db.Column(db.SmallInteger, nullable=False, default=0)
    error_msg = db.Column(db.Text)
    metricas_json = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    iniciado_en = db.Column(db.DateTime)
    terminado_en = db.Column(db.DateTime)
    purgar_en = db.Column(db.DateTime)

    archivos = db.relationship("Archivo", backref="trabajo", cascade="all, delete-orphan")

    def a_dict_publico(self):
        return {
            "token_publico": self.token_publico,
            "estado": self.estado,
            "factor": float(self.factor),
            "error_msg": self.error_msg if self.estado == "error" else None,
            "creado_en": self.creado_en.isoformat(),
            "terminado_en": self.terminado_en.isoformat() if self.terminado_en else None,
        }

    def a_dict_worker(self):
        return {
            "id": self.id,
            "token_publico": self.token_publico,
            "factor": float(self.factor),
            "archivos": [a.a_dict() for a in self.archivos if a.tipo == "origen"],
        }


class Archivo(db.Model):
    __tablename__ = "archivos"

    id = db.Column(db.Integer, primary_key=True)
    trabajo_id = db.Column(db.Integer, db.ForeignKey("trabajos.id", ondelete="CASCADE"), nullable=False)
    tipo = db.Column(db.Enum("origen", "resultado", "informe"), nullable=False)
    nombre = db.Column(db.String(255), nullable=False)
    ruta = db.Column(db.String(512), nullable=False)
    bytes = db.Column(db.BigInteger, nullable=False)
    sha256 = db.Column(db.CHAR(64))
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def a_dict(self):
        return {"id": self.id, "nombre": self.nombre, "tipo": self.tipo, "bytes": self.bytes}


def reclamar_siguiente_trabajo(worker_id: str):
    """Reclama atómicamente el trabajo pendiente más antiguo.

    Usa un UPDATE condicionado seguido de un SELECT del que quedó marcado
    con este worker_id, evitando que dos workers tomen el mismo trabajo.
    """
    resultado = db.session.execute(
        db.text(
            """
            UPDATE trabajos
               SET estado = 'reclamado', worker_id = :wid, iniciado_en = NOW(), intentos = intentos + 1
             WHERE estado = 'pendiente'
             ORDER BY creado_en ASC
             LIMIT 1
            """
        ),
        {"wid": worker_id},
    )
    db.session.commit()

    if resultado.rowcount == 0:
        return None

    trabajo = (
        Trabajo.query.filter_by(worker_id=worker_id, estado="reclamado")
        .order_by(Trabajo.iniciado_en.desc())
        .first()
    )
    return trabajo


def liberar_trabajos_atascados():
    """Un trabajo en reclamado/procesando por más de MINUTOS_TIMEOUT_TRABAJO
    vuelve a pendiente: el Mac pudo apagarse a mitad de proceso.
    """
    limite = datetime.utcnow() - timedelta(minutes=MINUTOS_TIMEOUT_TRABAJO)
    atascados = Trabajo.query.filter(
        Trabajo.estado.in_(("reclamado", "procesando")), Trabajo.iniciado_en < limite
    ).all()
    for trabajo in atascados:
        trabajo.estado = "pendiente"
        trabajo.worker_id = None
    if atascados:
        db.session.commit()
    return len(atascados)
