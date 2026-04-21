"""
email_service.py
Correo automatico diario usando SendGrid API.
Se envia a las 5pm con los servicios del dia siguiente.
"""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from database import obtener_citas_del_dia

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
CORREO_ORIGEN    = os.environ.get("EMAIL_USER", "tallerlg.bot@gmail.com")
CORREO_DESTINO   = os.environ.get("EMAIL_DESTINO", "rodrigo.pefe@live.com")


def _formato_orden(cita: dict) -> str:
    obs   = cita.get("observacion", "")
    cargo = cita.get("cargo", "")
    sep   = "-" * 60
    lineas = [
        f"NOMBRE    | {cita.get('nombre', '-')}",
        f"DIRECCION | {cita.get('direccion', '-')}",
        f"UBICACION | {cita.get('ubicacion', '-')}",
        f"TELEFONO  | {cita.get('telefono_contacto', cita.get('telefono', '-'))}",
        f"APARATO   | {cita.get('aparato', '-')} / {cita.get('falla', '-')}",
        f"OBSERV.   | {obs}",
        f"CITA      | {cita.get('fecha', '-')}    {cargo}",
    ]
    return f"No. ORDEN: {cita.get('folio', '-')}\n{sep}\n" + "\n".join(lineas) + f"\n{sep}\n"


def _generar_cuerpo(citas: list, fecha_display: str) -> str:
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
    print(f"Iniciando envio de correo via SendGrid...")
    print(f"SENDGRID_API_KEY configurado: {bool(SENDGRID_API_KEY)}")
    print(f"CORREO_ORIGEN: {CORREO_ORIGEN}")
    print(f"CORREO_DESTINO: {CORREO_DESTINO}")

    if not SENDGRID_API_KEY:
        print("ERROR: Falta SENDGRID_API_KEY")
        return False

    manana        = datetime.now() + timedelta(days=1)
    fecha_manana  = manana.strftime("%Y-%m-%d")
    fecha_display = manana.strftime("%d/%m/%Y")

    print(f"Obteniendo citas para: {fecha_manana}")
    citas  = obtener_citas_del_dia(fecha_manana)
    print(f"Citas encontradas: {len(citas)}")

    cuerpo = _generar_cuerpo(citas, fecha_display)
    asunto = f"Servicios {fecha_display} - Refrigeracion y Lavadoras LG ({len(citas)} ordenes)"

    # Payload SendGrid
    payload = {
        "personalizations": [{
            "to": [{"email": CORREO_DESTINO}],
            "subject": asunto
        }],
        "from": {
            "email": CORREO_ORIGEN,
            "name": "Refrigeracion y Lavadoras LG"
        },
        "content": [{
            "type": "text/plain",
            "value": cuerpo
        }]
    }

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"Correo enviado exitosamente. Status: {response.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR SendGrid HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"ERROR general: {e}")
        return False
