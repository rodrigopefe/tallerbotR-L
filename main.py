"""
main.py
Servidor FastAPI — Refrigeración y Lavadoras LG

Rutas:
  GET  /webhook  → verificación de Meta
  POST /webhook  → recibe mensajes de WhatsApp
  GET  /         → health check

Tarea programada:
  Correo automático a las 5pm con servicios del día siguiente
"""
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
from bot import manejar_mensaje
from config import VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Tarea programada: correo a las 5pm ───────────────────

async def tarea_correo_diario():
    """Revisa cada minuto si son las 5pm para enviar el correo."""
    correo_enviado_hoy = None
    while True:
        ahora = datetime.now()
        hoy = ahora.strftime("%Y-%m-%d")

        # Enviar a las 17:00 (5pm) una vez por día
        if ahora.hour == 17 and ahora.minute == 0 and correo_enviado_hoy != hoy:
            try:
                from email_service import enviar_correo_diario
                await enviar_correo_diario()
                correo_enviado_hoy = hoy
                logger.info("Correo diario enviado correctamente")
            except Exception as e:
                logger.error(f"Error enviando correo diario: {e}")

        await asyncio.sleep(60)  # Revisar cada minuto


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arrancar tarea de correo en segundo plano
    task = asyncio.create_task(tarea_correo_diario())
    logger.info("Tarea de correo diario iniciada")
    yield
    task.cancel()


app = FastAPI(title="TallerBot - Refrigeracion y Lavadoras LG", version="2.0.0", lifespan=lifespan)


# ── Health check ─────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "bot": "TallerBot activo", "version": "2.0.0"}


# ── Verificación del webhook ──────────────────────────────

@app.get("/webhook")
async def verificar_webhook(
    hub_mode: str      = Query(None, alias="hub.mode"),
    hub_token: str     = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        logger.info("Webhook verificado por Meta")
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Token invalido")


# ── Recepción de mensajes ─────────────────────────────────

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    try:
        body = await request.json()
        logger.info(f"Payload recibido: {body}")

        entry    = body.get("entry", [{}])[0]
        changes  = entry.get("changes", [{}])[0]
        value    = changes.get("value", {})
        messages = value.get("messages", [])

        print(f"Token cargado: {WHATSAPP_TOKEN[:20] if WHATSAPP_TOKEN else 'VACIO'}...")
        print(f"Phone Number ID: {PHONE_NUMBER_ID if PHONE_NUMBER_ID else 'VACIO'}")

        if not messages:
            return {"status": "ok"}

        mensaje_data = messages[0]
        telefono     = mensaje_data.get("from", "")
        tipo         = mensaje_data.get("type", "")

        print(f"Mensaje de: {telefono} | Tipo: {tipo}")

        if tipo == "text":
            texto = mensaje_data.get("text", {}).get("body", "").strip()
            print(f"Texto recibido: {texto}")
            if texto:
                await manejar_mensaje(telefono, texto)

        elif tipo == "interactive":
            interactive = mensaje_data.get("interactive", {})
            inter_type  = interactive.get("type", "")

            if inter_type == "button_reply":
                opcion_id = interactive["button_reply"]["id"]
                await manejar_mensaje(telefono, opcion_id)

            elif inter_type == "list_reply":
                opcion_id = interactive["list_reply"]["id"]
                await manejar_mensaje(telefono, opcion_id)

        else:
            logger.info(f"Tipo de mensaje no manejado: {tipo}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)
        print(f"ERROR DETALLADO: {e}")
        return {"status": "error"}


# ── Endpoint prueba de correo ─────────────────────────────

@app.get("/test-correo")
async def test_correo():
    """Endpoint temporal para probar el correo manualmente."""
    try:
        from email_service import enviar_correo_diario
        resultado = await enviar_correo_diario()
        return {"status": "ok" if resultado else "error", "mensaje": "Correo enviado" if resultado else "Error al enviar"}
    except Exception as e:
        return {"status": "error", "detalle": str(e)}
