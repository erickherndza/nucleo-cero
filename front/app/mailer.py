import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def enviar_correo(destinatario: str, asunto: str, cuerpo: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    if not host:
        logger.warning("SMTP no configurado; se omite el correo a %s", destinatario)
        return False

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = os.environ.get("SMTP_FROM", "noreply@localhost")
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)

    puerto = int(os.environ.get("SMTP_PORT", "587"))
    usuario = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")

    try:
        with smtplib.SMTP(host, puerto, timeout=15) as servidor:
            servidor.starttls()
            if usuario and password:
                servidor.login(usuario, password)
            servidor.send_message(mensaje)
        return True
    except Exception:
        logger.exception("No se pudo enviar el correo a %s", destinatario)
        return False


def notificar_trabajo_recibido(destinatario: str, token_publico: str, url_estado: str) -> None:
    enviar_correo(
        destinatario,
        "Hemos recibido tus fotos — UppImagenScale",
        f"Tu trabajo fue recibido correctamente.\n\n"
        f"Puedes seguir su estado en:\n{url_estado}\n\n"
        f"Referencia: {token_publico}",
    )


def notificar_trabajo_listo(destinatario: str, token_publico: str, url_estado: str) -> None:
    enviar_correo(
        destinatario,
        "Tu resultado está listo — UppImagenScale",
        f"Tu trabajo terminó de procesarse.\n\n"
        f"Descárgalo desde:\n{url_estado}\n\n"
        f"Referencia: {token_publico}",
    )


def notificar_trabajo_con_error(destinatario: str, token_publico: str, error_msg: str) -> None:
    enviar_correo(
        destinatario,
        "Hubo un problema con tu trabajo — UppImagenScale",
        f"No pudimos completar tu trabajo (referencia {token_publico}).\n\n"
        f"Detalle: {error_msg}\n\n"
        f"Contáctanos si necesitas ayuda.",
    )
