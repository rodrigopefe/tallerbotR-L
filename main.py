"""
main.py
Servidor FastAPI — Refrigeración y Lavadoras LG

Rutas:
  GET  /webhook       → verificación de Meta
  POST /webhook       → recibe mensajes de WhatsApp
  GET  /              → health check
  GET  /panel         → panel web del técnico
  POST /actualizar    → actualiza estado de una cita y notifica al cliente
  GET  /test-correo   → prueba manual del correo diario

Tarea programada:
  Correo automático a las 5pm hora México con citas pendientes
"""
import logging
import asyncio
import json
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from bot import manejar_mensaje
from config import VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID
from whatsapp import send_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Tarea programada: correo a las 5pm México ─────────────

async def tarea_correo_diario():
    correo_enviado_hoy = None
    while True:
        ahora = datetime.utcnow()
        hoy   = ahora.strftime("%Y-%m-%d")
        if ahora.hour == 23 and ahora.minute == 0 and correo_enviado_hoy != hoy:
            try:
                from email_service import enviar_correo_diario
                await enviar_correo_diario()
                correo_enviado_hoy = hoy
                logger.info("Correo diario enviado correctamente")
            except Exception as e:
                logger.error(f"Error enviando correo diario: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(tarea_correo_diario())
    logger.info("Tarea de correo diario iniciada")
    yield
    task.cancel()


app = FastAPI(
    title="TallerBot - Refrigeracion y Lavadoras LG",
    version="3.0.0",
    lifespan=lifespan
)


# ── Health check ─────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "bot": "TallerBot activo", "version": "3.0.0"}


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


# ── Panel web del técnico ─────────────────────────────────

@app.get("/panel", response_class=HTMLResponse)
async def panel_tecnico():
    from database import db
    try:
        docs  = db.collection("citas").where("estado", "!=", "entregado").stream()
        citas = [d.to_dict() for d in docs]
        citas.sort(key=lambda x: x.get("fecha_creacion", ""), reverse=True)
    except Exception as e:
        citas = []
        logger.error(f"Error obteniendo citas: {e}")

    def badge(estado):
        colores = {
            "pendiente":           ("background:#FAEEDA;color:#633806", "Pendiente"),
            "en_diagnostico":      ("background:#E6F1FB;color:#0C447C", "En diagnostico"),
            "esperando_refaccion": ("background:#FCEBEB;color:#791F1F", "Esperando refaccion"),
            "listo":               ("background:#EAF3DE;color:#27500A", "Listo para entregar"),
            "entregado":           ("background:#EAF3DE;color:#27500A", "Entregado"),
        }
        s, t = colores.get(estado, ("background:#F1EFE8;color:#444441", estado))
        return f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;{s}">{t}</span>'

    def tarjeta(cita):
        folio   = cita.get("folio", "-")
        nombre  = cita.get("nombre", "-")
        tel     = cita.get("telefono_contacto", cita.get("telefono", "-"))
        aparato = cita.get("aparato", "-")
        falla   = cita.get("falla", "-")
        dir_    = cita.get("direccion", "-")
        ubic    = cita.get("ubicacion", "")
        fecha   = cita.get("fecha", "-")
        obs     = cita.get("observacion", "")
        cargo   = cita.get("cargo", "")
        estado  = cita.get("estado", "pendiente")
        wa      = cita.get("telefono", "")

        obs_html  = f'<div style="background:#FAEEDA;border-radius:6px;padding:6px 10px;font-size:12px;color:#633806;margin-bottom:10px">{obs}</div>' if obs else ""
        ubic_html = f'<div class="field"><label>Referencia</label><span>{ubic}</span></div>' if ubic else ""

        return f"""
<div class="card" id="card-{folio}">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--bg2);border-bottom:0.5px solid var(--br)">
    <span style="font-size:14px;font-weight:500">{folio}</span>
    <span id="badge-{folio}">{badge(estado)}</span>
  </div>
  <div style="padding:14px">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
      <div class="field"><label>Nombre</label><span>{nombre}</span></div>
      <div class="field"><label>Telefono</label><span>{tel}</span></div>
      <div class="field"><label>Aparato</label><span>{aparato}</span></div>
      <div class="field"><label>Falla</label><span>{falla}</span></div>
      <div class="field"><label>Direccion</label><span>{dir_}</span></div>
      {ubic_html}
      <div class="field"><label>Cita</label><span>{fecha}</span></div>
      <div class="field"><label>Cargo</label><span>{cargo}</span></div>
    </div>
    {obs_html}
    <select id="sel-{folio}" style="width:100%;padding:7px 10px;border:0.5px solid var(--br);border-radius:8px;font-size:13px;background:var(--bg1);color:var(--txt);margin-bottom:8px">
      <option value="pendiente" {"selected" if estado=="pendiente" else ""}>Pendiente de visita</option>
      <option value="en_diagnostico" {"selected" if estado=="en_diagnostico" else ""}>En diagnostico</option>
      <option value="esperando_refaccion" {"selected" if estado=="esperando_refaccion" else ""}>Esperando refaccion</option>
      <option value="listo" {"selected" if estado=="listo" else ""}>Listo para entregar</option>
      <option value="entregado" {"selected" if estado=="entregado" else ""}>Entregado</option>
    </select>
    <button onclick="actualizar('{folio}','{wa}')"
      style="width:100%;padding:9px;border:0.5px solid #1D9E75;border-radius:8px;font-size:13px;background:#E1F5EE;color:#085041;cursor:pointer;font-weight:500">
      Actualizar estado y notificar cliente
    </button>
    <div id="msg-{folio}" style="display:none;margin-top:8px;padding:8px 12px;border-radius:8px;font-size:12px"></div>
  </div>
</div>"""

    cards_html = "\n".join([tarjeta(c) for c in citas]) if citas else \
        '<p style="text-align:center;color:var(--txt2);padding:40px">No hay servicios activos</p>'

    total = len(citas)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel Tecnico - Refrigeracion y Lavadoras LG</title>
<style>
  :root{{--bg1:#fff;--bg2:#f8f8f6;--txt:#1a1a1a;--txt2:#888;--br:rgba(0,0,0,0.15)}}
  @media(prefers-color-scheme:dark){{:root{{--bg1:#1c1c1e;--bg2:#2c2c2e;--txt:#f0f0f0;--txt2:#888;--br:rgba(255,255,255,0.15)}}}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg2);color:var(--txt);padding:16px;max-width:600px;margin:0 auto}}
  .header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;padding-bottom:12px;border-bottom:0.5px solid var(--br)}}
  .header h1{{font-size:16px;font-weight:500}}
  .header p{{font-size:12px;color:var(--txt2);margin-top:3px}}
  .card{{background:var(--bg1);border:0.5px solid var(--br);border-radius:12px;overflow:hidden;margin-bottom:12px}}
  .field label{{font-size:11px;color:var(--txt2);display:block;margin-bottom:2px}}
  .field span{{font-size:13px;color:var(--txt)}}
  .refresh{{padding:6px 14px;border:0.5px solid var(--br);border-radius:8px;font-size:12px;background:var(--bg2);color:var(--txt);cursor:pointer}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>Panel del Tecnico</h1>
    <p>Refrigeracion y Lavadoras LG</p>
  </div>
  <div style="display:flex;align-items:center;gap:8px">
    <span style="background:#FAEEDA;color:#633806;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500">{total} activos</span>
    <button class="refresh" onclick="location.reload()">Actualizar</button>
  </div>
</div>
{cards_html}
<script>
async function actualizar(folio, wa) {{
  const sel = document.getElementById('sel-' + folio);
  const msg = document.getElementById('msg-' + folio);
  const btn = sel.nextElementSibling;
  btn.disabled = true;
  btn.textContent = 'Actualizando...';
  try {{
    const r = await fetch('/actualizar', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{folio, estado: sel.value, telefono: wa}})
    }});
    const data = await r.json();
    if (data.ok) {{
      msg.style.display = 'block';
      msg.style.background = '#EAF3DE';
      msg.style.color = '#27500A';
      msg.textContent = 'Estado actualizado. Cliente notificado por WhatsApp.';
      document.getElementById('badge-' + folio).innerHTML = data.badge;
    }} else {{
      msg.style.display = 'block';
      msg.style.background = '#FCEBEB';
      msg.style.color = '#791F1F';
      msg.textContent = 'Error: ' + (data.error || 'intenta de nuevo');
    }}
  }} catch(e) {{
    msg.style.display = 'block';
    msg.style.background = '#FCEBEB';
    msg.style.color = '#791F1F';
    msg.textContent = 'Error de conexion';
  }}
  btn.disabled = false;
  btn.textContent = 'Actualizar estado y notificar cliente';
}}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


# ── Endpoint actualizar estado ────────────────────────────

ESTADOS_MENSAJE = {
    "pendiente":           "Tu servicio esta pendiente de visita. Te confirmamos pronto. Refrigeracion y Lavadoras LG.",
    "en_diagnostico":      "Tu equipo esta en diagnostico. Te avisamos cuando tengamos el resultado. Refrigeracion y Lavadoras LG.",
    "esperando_refaccion": "Tu equipo requiere una refaccion. En cuanto llegue continuamos la reparacion. Refrigeracion y Lavadoras LG.",
    "listo":               "Tu equipo esta listo para entregar. Puedes pasar a recogerlo o coordinamos la entrega. Refrigeracion y Lavadoras LG.",
    "entregado":           "Tu servicio ha sido completado. Gracias por confiar en nosotros. Refrigeracion y Lavadoras LG.",
}

BADGES_HTML = {
    "pendiente":           '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:#FAEEDA;color:#633806">Pendiente</span>',
    "en_diagnostico":      '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:#E6F1FB;color:#0C447C">En diagnostico</span>',
    "esperando_refaccion": '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:#FCEBEB;color:#791F1F">Esperando refaccion</span>',
    "listo":               '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:#EAF3DE;color:#27500A">Listo para entregar</span>',
    "entregado":           '<span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;background:#EAF3DE;color:#27500A">Entregado</span>',
}


@app.post("/actualizar")
async def actualizar_estado_cita(request: Request):
    try:
        data     = await request.json()
        folio    = data.get("folio", "").strip()
        estado   = data.get("estado", "").strip()
        telefono = data.get("telefono", "").strip()

        if not folio or not estado:
            return JSONResponse({"ok": False, "error": "Faltan datos"})

        from database import actualizar_estado
        ok = actualizar_estado(folio, estado)

        if not ok:
            return JSONResponse({"ok": False, "error": f"No se encontro el folio {folio}"})

        # Notificar al cliente por WhatsApp
        if telefono:
            mensaje_cliente = ESTADOS_MENSAJE.get(estado, f"El estado de tu servicio {folio} fue actualizado.")
            try:
                await send_message(telefono, f"Hola! Actualizacion de tu servicio *{folio}*:\n\n{mensaje_cliente}")
            except Exception as e:
                logger.error(f"Error notificando cliente: {e}")

        badge_html = BADGES_HTML.get(estado, "")
        return JSONResponse({"ok": True, "badge": badge_html})

    except Exception as e:
        logger.error(f"Error actualizando estado: {e}")
        return JSONResponse({"ok": False, "error": str(e)})


# ── Endpoint prueba de correo ─────────────────────────────

@app.get("/test-correo")
async def test_correo():
    try:
        from email_service import enviar_correo_diario
        resultado = await enviar_correo_diario()
        return {"status": "ok" if resultado else "error", "mensaje": "Correo enviado" if resultado else "Error al enviar"}
    except Exception as e:
        return {"status": "error", "detalle": str(e)}
