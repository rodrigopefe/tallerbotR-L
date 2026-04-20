"""
email_service.py
Correo automático diario con resumen de servicios agendados.
Se envía a las 5pm con los servicios del día siguiente.

Variables de entorno necesarias en Railway:
  EMAIL_USER    → tu correo Gmail (ej: tallerbot@gmail.com)
  EMAIL_PASS    → contraseña de aplicación de Gmail (no tu password normal)
  EMAIL_DESTINO → correo destino (rodrigo.pefe@live.com)
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from database import obtener_citas_del_dia

# ── Configuración ─────────────────────────────────────────
CORREO_ORIGEN  = os.environ.get("EMAIL_USER", "")
CORREO_PASS    = os.environ.get("EMAIL_PASS", "")
CORREO_DESTINO = os.environ.get("EMAIL_DESTINO", "rodrigo.pefe@live.com")


def _formato_orden(cita: dict) -> str:
    """Genera el bloque de texto de una orden en el formato del taller."""
    obs    = cita.get("observacion", "")
    cargo  = cita.get("cargo", "")

    separador = "-" * 60
    lineas = [
        f"NOMBRE    | {cita.get('nombre', '-')}",
        f"DIRECCION | {cita.get('direccion', '-')}",
        f"UBICACION | {cita.get('ubicacion', '-')}",
        f"TELEFONO  | {cita.get('telefono_contacto', cita.get('telefono', '-'))}",
        f"APARATO   | {cita.get('aparato', '-')} / {cita.get('falla', '-')}",
        f"OBSERV.   | {obs}",
        f"CITA      | {cita.get('fecha', '-')}    {cargo}",
    ]
    return f"No. ORDEN: {cita.get('folio', '-')}\n{separador}\n" + "\n".join(lineas) + f"\n{separador}\n"


def _generar_cuerpo_correo(citas: list[dict], fecha_display: str) -> str:
    """Genera el cuerpo completo del correo."""
    if not citas:
        return (
            f"REFRIGERACION Y LAVADORAS LG\n"
            f"SERVICIOS PARA: {fecha_display}\n"
            f"{'='*60}\n\n"
            f"No hay servicios agendados para este dia.\n"
        )

    encabezado = (
        f"REFRIGERACION Y LAVADORAS LG\n"
        f"SERVICIOS AGENDADOS PARA: {fecha_display}\n"
        f"Total de ordenes: {len(citas)}\n"
        f"{'='*60}\n\n"
    )
    bloques = "\n".join([_formato_orden(c) for c in citas])
    pie = f"\n{'='*60}\nGenerado automaticamente por TallerBot"

    return encabezado + bloques + pie


async def enviar_correo_diario():
    """
    Envía el correo con los servicios agendados para mañana.
    Se llama automáticamente a las 5pm desde main.py.
    """
    if not CORREO_ORIGEN or not CORREO_PASS:
        print("Correo no configurado - faltan EMAIL_USER o EMAIL_PASS en variables de entorno")
        return False

    manana        = datetime.now() + timedelta(days=1)
    fecha_manana  = manana.strftime("%Y-%m-%d")
    fecha_display = manana.strftime("%d/%m/%Y")

    citas  = obtener_citas_del_dia(fecha_manana)
    cuerpo = _generar_cuerpo_correo(citas, fecha_display)

    msg = MIMEMultipart()
    msg["From"]    = CORREO_ORIGEN
    msg["To"]      = CORREO_DESTINO
    msg["Subject"] = f"Servicios {fecha_display} - Refrigeracion y Lavadoras LG ({len(citas)} ordenes)"
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(CORREO_ORIGEN, CORREO_PASS)
            servidor.sendmail(CORREO_ORIGEN, CORREO_DESTINO, msg.as_string())
        print(f"Correo enviado a {CORREO_DESTINO} - {len(citas)} servicios para {fecha_display}")
        return True
    except Exception as e:
        print(f"Error enviando correo: {e}")
        return False
