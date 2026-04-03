"""
bot.py
Lógica central del chatbot — Refrigeración y Lavadoras LG
Incluye flujo de garantías (LG, Milenia, Assurant, GaranPlus)
"""
from whatsapp import send_message, send_list_menu, send_interactive_menu
from database import (
    guardar_cita,
    consultar_cita,
    consultar_cita_por_telefono,
    guardar_estado_conversacion,
    obtener_estado_conversacion,
    limpiar_conversacion,
)
from ai import responder, detectar_intencion

# ── Mensajes fijos ────────────────────────────────────────

MSG_BIENVENIDA = (
    "👋 ¡Hola! Soy el asistente de *Refrigeración y Lavadoras LG*.\n\n"
    "Puedo ayudarte con:"
)

MSG_AGENTE = (
    "📞 En un momento uno de nuestros técnicos te atiende.\n"
    "Horario de atención: lunes a viernes 9am–7pm, sábados 9am–3pm."
)

MSG_ESPERA_GARANTIA = (
    "✅ Listo, recibimos tu solicitud.\n\n"
    "Un técnico revisará el estado de tu garantía y te responderá "
    "en este chat en los próximos minutos.\n\n"
    "Si es fuera de horario, te contactamos en cuanto abramos "
    "*(lun-vie 9am–7pm, sáb 9am–3pm)*. 🔧"
)

MENU_OPCIONES = [
    {"id": "agendar",      "title": "📅 Agendar cita",        "description": "Programa una visita a domicilio"},
    {"id": "cotizar",      "title": "💰 Cotizar reparación",   "description": "Conoce el costo estimado"},
    {"id": "seguimiento",  "title": "🔍 Seguimiento",          "description": "Revisa el estado de tu servicio"},
    {"id": "faq",          "title": "❓ Preguntas frecuentes", "description": "Garantías, marcas, tiempos"},
    {"id": "agente",       "title": "👤 Hablar con técnico",   "description": "Atención personalizada"},
]

FAQ_RESPUESTAS = {
    "garantia": "🛡️ Ofrecemos *1 mes de garantía* en todas nuestras reparaciones (refacciones y mano de obra).",
    "marcas": "🔧 Trabajamos con *todas las marcas*: Mabe, Whirlpool, LG, Samsung, Electrolux, Acros y más.",
    "tiempo": "⏱️ El tiempo depende del diagnóstico. Reparaciones menores: mismo día. Mayores: 1–3 días hábiles.",
    "costo": "💵 El diagnóstico a domicilio cuesta $550 MX Refrigeradores y $450 MX Lavadoras, Pantallas, Hornos, Etc.",
}

GARANTIAS_VALIDAS = {"lg", "milenia", "assurant", "garanplus", "supra"}


# ── Utilidad: normalizar número México ───────────────────

def _normalizar_telefono(telefono: str) -> str:
    if telefono.startswith("5212") and len(telefono) == 13:
        telefono = "52" + telefono[3:]
        print(f"📱 Número normalizado: {telefono}")
    return telefono


# ── Utilidad: notificar al taller ────────────────────────

async def _notificar_taller_garantia(datos: dict) -> None:
    """
    Notifica al taller cuando llega una consulta de garantía.
    Por ahora imprime en consola.
    Próximo paso: conectar a correo o Firebase.
    """
    print("\n" + "="*50)
    print("🔔 NUEVA CONSULTA DE GARANTÍA")
    print(f"  Garantía:  {datos.get('garantia', '—').upper()}")
    print(f"  Cliente:   {datos.get('nombre', '—')}")
    print(f"  Folio:     {datos.get('folio_garantia', '—')}")
    print(f"  Equipo:    {datos.get('equipo', '—')}")
    print(f"  Teléfono:  {datos.get('telefono', '—')}")
    print("="*50 + "\n")


# ── Manejador principal ───────────────────────────────────

async def manejar_mensaje(telefono: str, mensaje: str) -> None:
    telefono = _normalizar_telefono(telefono)
    mensaje  = mensaje.strip()
    estado   = obtener_estado_conversacion(telefono)
    flujo    = estado.get("flujo")

    # Palabras clave para reiniciar en cualquier momento
    if mensaje.lower() in {"menu", "inicio", "hola", "hi", "buenas", "buenos dias",
                            "buenas tardes", "buenas noches", "empezar"}:
        await _mostrar_menu(telefono)
        limpiar_conversacion(telefono)
        return

    # Flujos activos
    if flujo == "agendar":
        await _flujo_agendar(telefono, mensaje, estado)
        return

    if flujo == "seguimiento":
        await _flujo_seguimiento(telefono, mensaje, estado)
        return

    if flujo == "garantia":
        await _flujo_garantia(telefono, mensaje, estado)
        return

    if flujo == "cotizar":
        await _flujo_cotizar(telefono, mensaje, estado)
        return

    # Detección directa de IDs del menú principal (sin pasar por IA)
    # Estos IDs llegan exactos cuando el cliente toca una opción del menú de lista
    ACCIONES_DIRECTAS = {
        "agendar":     _iniciar_agendar,
        "cotizar":     _iniciar_cotizar,
        "seguimiento": _iniciar_seguimiento,
        "faq":         None,
        "agente":      None,
        "si_agendar":  _iniciar_agendar,
        "no_gracias":  None,
    }

    if mensaje in ACCIONES_DIRECTAS:
        if mensaje == "agendar" or mensaje == "si_agendar":
            await _iniciar_agendar(telefono)
        elif mensaje == "cotizar":
            await _iniciar_cotizar(telefono)
        elif mensaje == "seguimiento":
            await _iniciar_seguimiento(telefono)
        elif mensaje == "faq":
            await send_message(telefono,
                "❓ *Preguntas frecuentes*\n\n"
                "Puedes preguntarme sobre:\n"
                "• Garantías de reparación\n"
                "• Marcas que trabajamos\n"
                "• Tiempo de reparación\n"
                "• Costo de diagnóstico\n\n"
                "¿Sobre qué quieres saber?"
            )
        elif mensaje == "agente":
            await send_message(telefono, MSG_AGENTE)
        elif mensaje == "no_gracias":
            await send_message(telefono,
                "De acuerdo, quedamos a tus órdenes. 😊\n"
                "Escribe *menu* si necesitas algo más."
            )
        return

    # Sin flujo activo: detecta intención con IA
    intencion = await detectar_intencion(mensaje)

    if intencion == "saludo":
        await _mostrar_menu(telefono)
    elif intencion == "agendar":
        await _iniciar_agendar(telefono)
    elif intencion == "cotizar":
        await _iniciar_cotizar(telefono)
    elif intencion == "seguimiento":
        await _iniciar_seguimiento(telefono)
    elif intencion == "faq":
        await _responder_faq(telefono, mensaje)
    elif intencion == "agente":
        await send_message(telefono, MSG_AGENTE)
    else:
        historial = estado.get("historial", [])
        respuesta = await responder(historial, mensaje)
        historial.append({"role": "user", "content": mensaje})
        historial.append({"role": "assistant", "content": respuesta})
        guardar_estado_conversacion(telefono, {**estado, "historial": historial[-10:]})
        await send_message(telefono, respuesta)


# ── Menú principal ────────────────────────────────────────

async def _mostrar_menu(telefono: str) -> None:
    await send_list_menu(telefono, MSG_BIENVENIDA, MENU_OPCIONES)


# ── Flujo: Seguimiento (con bifurcación a garantía) ──────

async def _iniciar_seguimiento(telefono: str) -> None:
    print(f"🔍 Iniciando seguimiento para {telefono}")
    guardar_estado_conversacion(telefono, {
        "flujo": "seguimiento",
        "paso": "pregunta_garantia",
    })
    await send_interactive_menu(telefono,
        "Seguimiento de servicio\n\n¿Tu servicio es de garantia?",
        [
            {"id": "seg_si_garantia", "title": "Si, es garantia"},
            {"id": "seg_no_garantia", "title": "No, servicio normal"},
        ]
    )


async def _flujo_seguimiento(telefono: str, mensaje: str, estado: dict) -> None:
    paso = estado.get("paso", "pregunta_garantia")

    if paso == "pregunta_garantia":
        # Evaluar primero por ID exacto del botón, luego por texto libre
        es_garantia = mensaje == "seg_si_garantia"
        es_normal   = mensaje == "seg_no_garantia"

        if not es_garantia and not es_normal:
            msg_lower = mensaje.lower()
            es_garantia = any(p in msg_lower for p in ["si", "sí", "garantia", "garantía"])
            es_normal   = any(p in msg_lower for p in ["no", "normal"])

        if es_garantia:
            await _iniciar_garantia(telefono)
            return

        if es_normal:
            # Sin garantía: pedir folio de servicio primero
            guardar_estado_conversacion(telefono, {
                "flujo": "seguimiento",
                "paso": "folio_sin_garantia",
                "datos": {},
            })
            await send_message(telefono,
                "🔍 Por favor escribe tu *folio de servicio*.\n"
                "(formato: TLR-XXXX)"
            )
            return

        # Respuesta no reconocida: volver a preguntar
        await send_interactive_menu(telefono,
            "¿Tu servicio es de garantia?",
            [
                {"id": "seg_si_garantia", "title": "Si, es garantia"},
                {"id": "seg_no_garantia", "title": "No, servicio normal"},
            ]
        )

    elif paso == "folio_sin_garantia":
        datos = estado.get("datos", {})
        datos["folio_servicio"] = mensaje.upper().strip()
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre_sin_garantia", "datos": datos})
        await send_message(telefono,
            "¿Cuál es tu *nombre completo*?"
        )

    elif paso == "nombre_sin_garantia":
        datos = estado.get("datos", {})
        datos["nombre"] = mensaje
        folio = datos.get("folio_servicio", "")

        # Buscar la cita por folio
        cita = consultar_cita(folio)
        if cita:
            await _mostrar_estado_cita(telefono, cita)
        else:
            await send_message(telefono,
                f"❌ No encontré el folio *{folio}*.\n"
                "Verifica que esté escrito correctamente (ej: TLR-A3X9).\n"
                "Escribe *agente* para hablar con nosotros."
            )
        limpiar_conversacion(telefono)

    elif paso == "folio_normal":
        cita = consultar_cita(mensaje.upper().strip())
        if cita:
            await _mostrar_estado_cita(telefono, cita)
        else:
            await send_message(telefono,
                f"❌ No encontré el folio *{mensaje}*.\n"
                "Verifica que esté escrito correctamente (ej: TLR-A3X9).\n"
                "Escribe *agente* para hablar con nosotros."
            )
        limpiar_conversacion(telefono)


async def _mostrar_estado_cita(telefono: str, cita: dict) -> None:
    estados_emoji = {
        "pendiente":           "⏳ Pendiente de visita",
        "en_diagnostico":      "🔧 En diagnóstico",
        "esperando_refaccion": "📦 Esperando refacción",
        "listo":               "✅ ¡Listo para entregar!",
        "entregado":           "🎉 Entregado",
    }
    estado_texto = estados_emoji.get(cita.get("estado", ""), "🔄 En proceso")
    await send_message(telefono,
        f"📋 *Folio:* {cita['folio']}\n"
        f"🔧 *Aparato:* {cita.get('aparato', '—')}\n"
        f"📊 *Estado:* {estado_texto}\n\n"
        "¿Necesitas algo más? Escribe *menu* para ver opciones."
    )


# ── Flujo: Garantía ───────────────────────────────────────

async def _iniciar_garantia(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "garantia",
        "paso": "tipo_garantia",
        "datos": {"telefono": telefono},
    })
    await send_list_menu(telefono,
        "Consulta de garantia\n\n¿Con que garantia cuenta tu equipo?",
        [
            {"id": "garantia_lg",        "title": "LG",        "description": "Garantia oficial LG"},
            {"id": "garantia_milenia",   "title": "Milenia",   "description": "Garantia Extendida Milenia"},
            {"id": "garantia_assurant",  "title": "Assurant",  "description": "Garantia Extendida Assurant"},
            {"id": "garantia_garanplus", "title": "GaranPlus", "description": "Garantia Extendida GaranPlus"},
            {"id": "garantia_supra",     "title": "Supra",     "description": "Garantia Supra"},
        ]
    )


async def _flujo_garantia(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "tipo_garantia")
    datos = estado.get("datos", {"telefono": telefono})

    if paso == "tipo_garantia":
        garantia  = None
        msg_lower = mensaje.lower().replace("garantia_", "")
        for g in GARANTIAS_VALIDAS:
            if g in msg_lower:
                garantia = g
                break

        if not garantia:
            await send_message(telefono,
                "Por favor selecciona una opción: "
                "*LG*, *Milenia*, *Assurant* o *GaranPlus*."
            )
            return

        datos["garantia"] = garantia
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre", "datos": datos})
        await send_message(telefono,
            f"✅ Garantía *{garantia.upper()}* seleccionada.\n\n"
            "¿Cuál es tu nombre completo?"
        )

    elif paso == "nombre":
        datos["nombre"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "folio_garantia", "datos": datos})
        await send_message(telefono,
            f"Gracias, *{mensaje}*. 😊\n\n"
            "¿Cuál es tu folio de servicio de garantía?"
        )

    elif paso == "folio_garantia":
        datos["folio_garantia"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "equipo", "datos": datos})
        await send_message(telefono,
            "¿Qué equipo es y cuál es el modelo?\n"
            "(ej: Lavadora LG WM1234, Refrigerador Samsung RT32)"
        )

    elif paso == "equipo":
        datos["equipo"] = mensaje
        await _notificar_taller_garantia(datos)
        limpiar_conversacion(telefono)
        await send_message(telefono,
            f"📋 *Resumen de tu solicitud:*\n\n"
            f"🛡️ *Garantía:* {datos.get('garantia', '—').upper()}\n"
            f"👤 *Nombre:* {datos.get('nombre', '—')}\n"
            f"🔖 *Folio:* {datos.get('folio_garantia', '—')}\n"
            f"🔧 *Equipo:* {datos.get('equipo', '—')}\n\n"
            f"{MSG_ESPERA_GARANTIA}"
        )


# ── Flujo: Agendar cita ───────────────────────────────────

async def _iniciar_agendar(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "agendar",
        "paso": "aparato",
        "datos": {},
    })
    await send_message(telefono,
        "📅 *Vamos a agendar tu cita.*\n\n"
        "¿Qué aparato necesitas reparar?\n"
        "(ej: lavadora, refrigerador, pantalla, estufa...)"
    )


async def _flujo_agendar(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "aparato")
    datos = estado.get("datos", {})

    if paso == "aparato":
        datos["aparato"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "falla", "datos": datos})
        await send_message(telefono,
            f"✅ Anotado: *{mensaje}*.\n\n"
            "¿Cuál es el problema o falla que presenta?"
        )
    elif paso == "falla":
        datos["falla"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre", "datos": datos})
        await send_message(telefono, "¿A qué nombre agendamos la cita?")
    elif paso == "nombre":
        datos["nombre"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "direccion", "datos": datos})
        await send_message(telefono,
            f"Perfecto, {mensaje}. 😊\n\n"
            "¿Cuál es tu dirección o colonia?"
        )
    elif paso == "direccion":
        datos["direccion"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "fecha", "datos": datos})
        await send_message(telefono,
            "¿Qué día y hora te queda mejor?\n"
            "(ej: mañana martes a las 10am)"
        )
    elif paso == "fecha":
        datos["fecha"] = mensaje
        folio = guardar_cita(telefono, datos)
        limpiar_conversacion(telefono)
        await send_message(telefono,
            f"🎉 *¡Cita agendada con éxito!*\n\n"
            f"📋 *Folio:* {folio}\n"
            f"🔧 *Aparato:* {datos['aparato']}\n"
            f"⚠️ *Falla:* {datos['falla']}\n"
            f"📍 *Dirección:* {datos['direccion']}\n"
            f"📅 *Fecha/hora:* {datos['fecha']}\n\n"
            f"Guarda tu folio *{folio}* para dar seguimiento.\n"
            f"Un técnico te confirmará la visita en breve. ✅"
        )


# ── Flujo: Cotizar ────────────────────────────────────────

async def _iniciar_cotizar(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {"flujo": "cotizar", "paso": "aparato"})
    await send_message(telefono,
        "💰 *Cotización de reparación*\n\n"
        "¿Qué aparato necesitas reparar?\n"
        "(ej: lavadora, refrigerador, pantalla...)"
    )


async def _flujo_cotizar(telefono: str, mensaje: str, estado: dict) -> None:
    paso = estado.get("paso", "aparato")
    if paso == "aparato":
        guardar_estado_conversacion(telefono, {**estado, "paso": "falla", "aparato": mensaje})
        await send_message(telefono,
            f"Entendido, *{mensaje}*. ¿Cuál es la falla o problema?"
        )
    elif paso == "falla":
        aparato   = estado.get("aparato", "el aparato")
        consulta  = f"El cliente tiene un {aparato} con este problema: {mensaje}. Da una cotización orientativa."
        respuesta = await responder([], consulta)
        limpiar_conversacion(telefono)
        await send_message(telefono, respuesta)
        await send_interactive_menu(telefono,
            "¿Te gustaría agendar una visita para diagnóstico exacto?",
            [
                {"id": "si_agendar", "title": "✅ Sí, agendar"},
                {"id": "no_gracias", "title": "❌ No por ahora"},
            ]
        )


# ── Preguntas frecuentes ──────────────────────────────────

async def _responder_faq(telefono: str, mensaje: str) -> None:
    msg_lower = mensaje.lower()
    if "garantia" in msg_lower or "garantía" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["garantia"])
    elif "marca" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["marcas"])
    elif "tiempo" in msg_lower or "cuanto tarda" in msg_lower or "cuánto tarda" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["tiempo"])
    elif "costo" in msg_lower or "precio" in msg_lower or "cuánto" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["costo"])
    else:
        respuesta = await responder([], mensaje)
        await send_message(telefono, respuesta)
