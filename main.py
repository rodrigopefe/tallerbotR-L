"""
main.py
Servidor FastAPI — punto de entrada de la aplicación.

Rutas:
  GET  /webhook  → verificación de Meta (una sola vez al configurar)
  POST /webhook  → recibe mensajes entrantes de WhatsApp
  GET  /         → health check
"""
import logging
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
from bot import manejar_mensaje
from config import VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Refrigeracion&LavadorasLG", version="1.0.0")


# ── Health check ─────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "bot": "TallerBot activo 🔧"}


# ── Verificación del webhook (Meta lo llama 1 vez) ────────

@app.get("/webhook")
async def verificar_webhook(
    hub_mode: str       = Query(None, alias="hub.mode"),
    hub_token: str      = Query(None, alias="hub.verify_token"),
    hub_challenge: str  = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        logger.info("✅ Webhook verificado por Meta")
        return PlainTextResponse(content=hub_challenge)

    logger.warning("❌ Intento de verificación fallido")
    raise HTTPException(status_code=403, detail="Token inválido")


# ── Recepción de mensajes ─────────────────────────────────

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    try:
        body = await request.json()
        logger.info(f"📩 Payload recibido: {body}")

        entry    = body.get("entry", [{}])[0]
        changes  = entry.get("changes", [{}])[0]
        value    = changes.get("value", {})
        messages = value.get("messages", [])

        # Diagnóstico — muestra token y phone_id cargados
        print(f"🔍 Token cargado: {WHATSAPP_TOKEN[:20] if WHATSAPP_TOKEN else 'VACÍO'}...")
        print(f"🔍 Phone Number ID: {PHONE_NUMBER_ID if PHONE_NUMBER_ID else 'VACÍO'}")

        if not messages:
            return {"status": "ok"}

        mensaje_data = messages[0]
        telefono     = mensaje_data.get("from", "")
        tipo         = mensaje_data.get("type", "")

        print(f"📱 Mensaje de: {telefono} | Tipo: {tipo}")

        if tipo == "text":
            texto = mensaje_data.get("text", {}).get("body", "").strip()
            print(f"💬 Texto recibido: {texto}")
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
        logger.error(f"❌ Error procesando mensaje: {e}", exc_info=True)
        print(f"❌ ERROR DETALLADO: {e}")
        return {"status": "error"}
