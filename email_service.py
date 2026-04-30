"""
email_service.py
Correo automatico diario usando SendGrid API.
Se envia a las 5pm hora Mexico con todos los servicios activos (no entregados).
"""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from database import db

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
CORREO_ORIGEN    = os.environ.get("EMAIL_USER", "tallerlg.bot@gmail.com")
CORREO_DESTINO   = os.environ.get("EMAIL_DESTINO", "rodrigo.pefe@live.com")

ESTADOS_LABEL = {
    "pendiente":           "Pendiente de visita",
    "en_diagnostico":      "En diagnostico",
    "esperando_refaccion": "Esperando refaccion",
    "listo":               "Listo para entregar",
}


def _obtener_citas_activas() -> list:
    """Obtiene todas las citas que no esten entregadas."""
    try:
        docs = db.collection("citas").where("estado", "!=", "entregado").stream()
        citas = [d.to_dict() for d in docs]
        citas.sort(key=lambda x: x.get("fecha_creacion", ""))
        return citas
    except Exception as e:
        print(f"Error obteniendo citas activas: {e}")
        return []


def _formato_orden(cita: dict) -> str:
    obs    = cita.get("observacion", "")
    cargo  = cita.get("cargo", "")
    estado = ESTADOS_LABEL.get(cita.get("estado", ""), cita.get("estado", "-"))
    sep    = "-" * 60
    lineas = [
        f"NOMBRE    | {cita.get('nombre', '-')}",
        f"DIRECCION | {cita.get('direccion', '-')}",
        f"UBICACION | {cita.get('ubicacion', '-')}",
        f"TELEFONO  | {cita.get('telefono_contacto', cita.get('telefono', '-'))}",
        f"APARATO   | {cita.get('aparato', '-')} / {cita.get('falla', '-')}",
        f"OBSERV.   | {obs}",
        f"CITA      | {cita.get('fecha', '-')}    {cargo}",
        f"ESTADO    | {estado}",
    ]
    return f"No. ORDEN: {cita.get('folio', '-')}\n{sep}\n" + "\n".join(lineas) + f"\n{sep}\n"


def _generar_cuerpo(citas: list, fecha_display: str) -> str:
    if not citas:
        return (
            f"REFRIGERACION Y LAVADORAS LG\n"
            f"RESUMEN DIARIO: {fecha_display}\n"
            f"{'='*60}\n\n"
            f"No hay servicios activos.\n"
        )

    # Agrupar por estado
    grupos = {}
    for cita in citas:
        estado = ESTADOS_LABEL.get(cita.get("estado", ""), cita.get("estado", "-"))
        if estado not in grupos:
            grupos[estado] = []
        grupos[estado].append(cita)

    encabezado = (
        f"REFRIGERACION Y LAVADORAS LG\n"
        f"RESUMEN DIARIO: {fecha_display}\n"
        f"Total de servicios activos: {len(citas)}\n"
    )

    # Resumen por estado
    resumen = ""
    for estado, lista in grupos.items():
        resumen += f"  {estado}: {len(lista)}\n"

    separador = f"{'='*60}\n\n"
    bloques   = "\n".join([_formato_orden(c) for c in citas])
    pie       = f"\n{'='*60}\nGenerado automaticamente por TallerBot"

    return encabezado + resumen + separador + bloques + pie


async def enviar_correo_diario():
    print(f"Iniciando envio de correo via SendGrid...")
    print(f"SENDGRID_API_KEY configurado: {bool(SENDGRID_API_KEY)}")

    if not SENDGRID_API_KEY:
        print("ERROR: Falta SENDGRID_API_KEY")
        return False

    fecha_display = datetime.now().strftime("%d/%m/%Y")

    print(f"Obteniendo citas activas...")
    citas = _obtener_citas_activas()
    print(f"Citas activas encontradas: {len(citas)}")

    cuerpo = _generar_cuerpo(citas, fecha_display)
    asunto = f"Resumen {fecha_display} - Refrigeracion y Lavadoras LG ({len(citas)} servicios activos)"

    payload = {
        "personalizations": [{"to": [{"email": CORREO_DESTINO}], "subject": asunto}],
        "from": {"email": CORREO_ORIGEN, "name": "Refrigeracion y Lavadoras LG"},
        "content": [{"type": "text/plain", "value": cuerpo}]
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
