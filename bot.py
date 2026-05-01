"""
bot.py
Lógica central del chatbot — Refrigeración y Lavadoras LG
- Saludo personalizado con historial de últimos 3 servicios
- Confirmación de costo antes de agendar
- Flujo de dirección detallado
- Garantías solo hacen seguimiento
- Formato folio: DDMMAA-XXXX
- Horarios: lun-vie 9am-5pm, sáb 9am-2pm
"""
from whatsapp import send_message, send_list_menu, send_interactive_menu
from database import (
    guardar_cita,
    consultar_cita,
    consultar_cita_por_telefono,
    consultar_historial_cliente,
    guardar_estado_conversacion,
    obtener_estado_conversacion,
    limpiar_conversacion,
    guardar_garantia,
)
from ai import responder, detectar_intencion

# ── Constantes ────────────────────────────────────────────

NUMERO_TALLER = "522201330759"

MSG_BIENVENIDA_NUEVO = (
    "¡Hola! Soy el asistente de *Refrigeración y Lavadoras LG*.\n\n"
    "¿Cómo puedo ayudarte?"
)

MSG_AGENTE = (
    "En un momento uno de nuestros técnicos te atiende.\n"
    "Horario de atención: lunes a viernes 9am-5pm, sábados 9am-2pm."
)

MSG_ESPERA_GARANTIA = (
    "Listo, recibimos tu solicitud.\n\n"
    "Un técnico revisará el estado de tu garantía y te responderá "
    "en este chat en los próximos minutos.\n\n"
    "Si es fuera de horario, te contactamos en cuanto abramos "
    "(lun-vie 9am-5pm, sáb 9am-2pm)."
)

MSG_ESPERA_COTIZACION = (
    "Listo, recibimos tu solicitud.\n\n"
    "Un técnico revisará la disponibilidad y precio de la refacción "
    "y te responderá en este chat a la brevedad.\n\n"
    "Si es fuera de horario, te contactamos en cuanto abramos "
    "(lun-vie 9am-5pm, sáb 9am-2pm)."
)

MSG_DESPEDIDA = (
    "Gracias por contactarnos. Quedamos a tus órdenes.\n"
    "¡Que tengas un excelente día! *Refrigeración y Lavadoras LG*."
)

MENU_OPCIONES = [
    {"id": "agendar",     "title": "Agendar cita",        "description": "Servicio con cargo a domicilio"},
    {"id": "cotizar",     "title": "Cotizar",              "description": "Revisión de equipo o refacción"},
    {"id": "seguimiento", "title": "Seguimiento",          "description": "Revisa tu servicio o garantía"},
    {"id": "faq",         "title": "Preguntas frecuentes", "description": "Garantías, marcas, tiempos"},
    {"id": "agente",      "title": "Hablar con técnico",   "description": "Atención personalizada"},
]

FAQ_RESPUESTAS = {
    "garantia": "Ofrecemos *3 meses de garantía* en todas nuestras reparaciones (refacciones y mano de obra).",
    "marcas": "Trabajamos con *todas las marcas*: Mabe, Whirlpool, LG, Samsung, Electrolux, Acros y más.",
    "tiempo": "El tiempo depende del diagnóstico. Reparaciones menores: mismo día. Mayores: 1-3 días hábiles.",
    "costo": "Revisión a domicilio en Puebla:\n• Lavadora: $450 MXN\n• Refrigerador: $550 MXN\n• Aire acondicionado: $750 MXN\n• Otros aparatos: $450 MXN",
    "horario": "Atendemos lunes a viernes de 9am a 5pm y sábados de 9am a 2pm.",
}

GARANTIAS_VALIDAS = {"lg", "milenia", "assurant", "garanplus", "supra"}

ESTADOS_TEXTO = {
    "pendiente":           "Pendiente de visita",
    "en_diagnostico":      "En diagnóstico",
    "esperando_refaccion": "Esperando refacción",
    "listo":               "Listo para entregar",
    "entregado":           "Entregado",
}

PALABRAS_DESPEDIDA = {
    "ok", "gracias", "ok gracias", "hasta luego", "adios", "adiós", "bye",
    "muchas gracias", "listo", "de acuerdo", "perfecto", "excelente",
    "okey", "👍", "entendido", "ya", "bien"
}

PALABRAS_SALUDO = {
    "menu", "menú", "inicio", "hola", "hi", "buenas", "buenos dias",
    "buenos días", "buenas tardes", "buenas noches", "empezar"
}


# ── Utilidades ────────────────────────────────────────────

def _normalizar_telefono(telefono: str) -> str:
    if telefono.startswith("5212") and len(telefono) == 13:
        telefono = "52" + telefono[3:]
        print(f"Número normalizado: {telefono}")
    return telefono


def _precio_por_aparato(aparato: str) -> str:
    aparato_lower = aparato.lower()
    if "refri" in aparato_lower or "refriger" in aparato_lower:
        return "$550.00"
    if "aire" in aparato_lower or "minisplit" in aparato_lower or "a/c" in aparato_lower:
        return "$750.00"
    return "$450.00"


def _nombre_precio_por_aparato(aparato: str) -> str:
    aparato_lower = aparato.lower()
    if "refri" in aparato_lower or "refriger" in aparato_lower:
        return "Refrigerador: *$550 MXN*"
    if "aire" in aparato_lower or "minisplit" in aparato_lower or "a/c" in aparato_lower:
        return "Aire acondicionado: *$750 MXN*"
    return f"{aparato.capitalize()}: *$450 MXN*"


async def _notificar_taller_garantia(datos: dict) -> None:
    print("\n" + "="*50)
    print("NUEVA CONSULTA DE GARANTÍA")
    print(f"  Garantía:  {datos.get('garantia', '-').upper()}")
    print(f"  Cliente:   {datos.get('nombre', '-')}")
    print(f"  Folio:     {datos.get('folio_garantia', '-')}")
    print(f"  Equipo:    {datos.get('equipo', '-')}")
    print(f"  Teléfono:  {datos.get('telefono', '-')}")
    print("="*50 + "\n")


# ── Saludo personalizado ──────────────────────────────────

async def _saludo_con_historial(telefono: str) -> None:
    historial = consultar_historial_cliente(telefono, limite=3)

    if not historial:
        await send_list_menu(telefono, MSG_BIENVENIDA_NUEVO, MENU_OPCIONES)
        return

    nombre = historial[0].get("nombre", "").split()[0].capitalize() if historial else ""

    lineas = []
    for cita in historial:
        estado  = ESTADOS_TEXTO.get(cita.get("estado", ""), "En proceso")
        folio   = cita.get("folio", "-")
        aparato = cita.get("aparato", "-")
        lineas.append(f"• {folio} — {aparato} — {estado}")

    servicios_texto = "\n".join(lineas)
    saludo = (
        f"¡Hola {nombre}! Bienvenido de nuevo a *Refrigeración y Lavadoras LG*.\n\n"
        f"Tus últimos servicios:\n{servicios_texto}\n\n"
        f"¿Cómo puedo ayudarte hoy?"
    )
    await send_list_menu(telefono, saludo, MENU_OPCIONES)


# ── Manejador principal ───────────────────────────────────

async def manejar_mensaje(telefono: str, mensaje: str) -> None:
    telefono = _normalizar_telefono(telefono)
    mensaje  = mensaje.strip()
    estado   = obtener_estado_conversacion(telefono)
    flujo    = estado.get("flujo")

    # Palabras de despedida
    if mensaje.lower() in PALABRAS_DESPEDIDA and not flujo:
        await send_message(telefono, MSG_DESPEDIDA)
        limpiar_conversacion(telefono)
        return

    # Palabras de saludo / reinicio
    if mensaje.lower() in PALABRAS_SALUDO:
        await _saludo_con_historial(telefono)
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
    if flujo == "cotizar_refaccion":
        await _flujo_cotizar_refaccion(telefono, mensaje, estado)
        return
    if flujo == "transferir":
        await _flujo_transferir(telefono, mensaje, estado)
        return

    # Detectar intención con IA
    intencion = await detectar_intencion(mensaje)

    if intencion == "saludo":
        await _saludo_con_historial(telefono)
    elif intencion == "agendar":
        await _iniciar_agendar(telefono)
    elif intencion == "cotizar":
        await _iniciar_cotizar(telefono)
    elif intencion == "seguimiento":
        await _iniciar_seguimiento(telefono)
    elif intencion == "faq":
        await _responder_faq(telefono, mensaje)
    elif intencion == "agente":
        await _transferir_a_tecnico(telefono)
    else:
        hist = estado.get("historial", [])
        respuesta = await responder(hist, mensaje)
        hist.append({"role": "user", "content": mensaje})
        hist.append({"role": "assistant", "content": respuesta})
        guardar_estado_conversacion(telefono, {**estado, "historial": hist[-10:]})
        await send_message(telefono, respuesta)


# ── Menú principal ────────────────────────────────────────

async def _mostrar_menu(telefono: str) -> None:
    await _saludo_con_historial(telefono)


# ── Flujo: Agendar cita ───────────────────────────────────

async def _iniciar_agendar(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "agendar",
        "paso": "aparato",
        "datos": {},
    })
    await send_message(telefono,
        "Vamos a agendar tu cita de servicio.\n\n"
        "¿Qué aparato necesitas reparar?\n"
        "(ej: lavadora, refrigerador, pantalla, estufa, aire acondicionado...)"
    )


async def _flujo_agendar(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "aparato")
    datos = estado.get("datos", {})

    # Validar que el mensaje no esté vacío
    if not mensaje.strip():
        await send_message(telefono, "Por favor escribe una respuesta para continuar.")
        return

    if paso == "aparato":
        datos["aparato"] = mensaje.upper()
        precio = _precio_por_aparato(mensaje)
        precio_texto = _nombre_precio_por_aparato(mensaje)
        datos["cargo"] = precio
        guardar_estado_conversacion(telefono, {**estado, "paso": "confirmar_costo", "datos": datos})
        await send_interactive_menu(telefono,
            f"El costo de revisión a domicilio dentro de la ciudad de Puebla es:\n\n"
            f"{precio_texto}\n\n"
            f"Este costo incluye diagnóstico y mano de obra.\n\n"
            f"¿Deseas continuar con el agendado?",
            [
                {"id": "confirmar_si", "title": "Sí, continuar"},
                {"id": "confirmar_no", "title": "No, cancelar"},
            ]
        )

    elif paso == "confirmar_costo":
        msg_lower = mensaje.lower()
        if mensaje == "confirmar_no" or "no" in msg_lower:
            limpiar_conversacion(telefono)
            await send_message(telefono,
                "Entendido, no hay problema.\n"
                "Si cambias de opinión escribe *menú* para ver las opciones."
            )
            return
        if mensaje != "confirmar_si" and "si" not in msg_lower and "sí" not in msg_lower:
            await send_interactive_menu(telefono,
                "¿Deseas continuar con el agendado?",
                [
                    {"id": "confirmar_si", "title": "Sí, continuar"},
                    {"id": "confirmar_no", "title": "No, cancelar"},
                ]
            )
            return
        guardar_estado_conversacion(telefono, {**estado, "paso": "falla", "datos": datos})
        await send_message(telefono, "¿Cuál es el problema o falla que presenta el equipo?")

    elif paso == "falla":
        datos["falla"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre", "datos": datos})
        await send_message(telefono, "¿A qué nombre agendamos la cita?\n(nombre completo)")

    elif paso == "nombre":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "calle", "datos": datos})
        await send_message(telefono, f"Perfecto, {mensaje}.\n\n¿Cuál es tu calle?")

    elif paso == "calle":
        datos["calle"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "numero_casa", "datos": datos})
        await send_message(telefono, "¿Cuál es el número de tu casa o departamento?")

    elif paso == "numero_casa":
        datos["numero_casa"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "entre_calles", "datos": datos})
        await send_message(telefono,
            "¿Entre qué calles se encuentra?\n"
            "(ej: entre 5 de Mayo y Reforma)"
        )

    elif paso == "entre_calles":
        datos["entre_calles"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "colonia", "datos": datos})
        await send_message(telefono, "¿Cuál es tu colonia?")

    elif paso == "colonia":
        datos["colonia"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "color_fachada", "datos": datos})
        await send_message(telefono, "¿De qué color es la fachada de tu casa?")

    elif paso == "color_fachada":
        datos["color_fachada"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "ubicacion", "datos": datos})
        await send_message(telefono,
            "¿Hay alguna referencia adicional para llegar?\n"
            "(ej: frente al mercado, junto a la farmacia...)\n"
            "Si no hay, escribe *no*"
        )

    elif paso == "ubicacion":
        datos["ubicacion"] = "" if mensaje.lower() == "no" else mensaje.upper()

        # Construir dirección completa
        direccion = (
            f"{datos.get('calle', '')} {datos.get('numero_casa', '')}, "
            f"Col. {datos.get('colonia', '')}"
        )
        datos["direccion"] = direccion

        guardar_estado_conversacion(telefono, {**estado, "paso": "telefono", "datos": datos})
        await send_message(telefono, "¿Cuál es tu número de teléfono de contacto?")

    elif paso == "telefono":
        datos["telefono_contacto"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "fecha", "datos": datos})
        await send_message(telefono,
            "¿Qué día y hora te queda mejor?\n"
            "Horario disponible:\n"
            "Lunes a viernes: 9am - 5pm\n"
            "Sábados: 9am - 2pm"
        )

    elif paso == "fecha":
        datos["fecha"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "llamar_antes", "datos": datos})
        await send_interactive_menu(telefono,
            "¿Deseas que te llamemos 30 minutos antes de la visita?",
            [
                {"id": "llamar_si", "title": "Sí, llamarme antes"},
                {"id": "llamar_no", "title": "No es necesario"},
            ]
        )

    elif paso == "llamar_antes":
        msg_lower = mensaje.lower()
        datos["observacion"] = "MARCAR 30 MIN ANTES" if (mensaje == "llamar_si" or "si" in msg_lower or "sí" in msg_lower) else ""

        folio = guardar_cita(telefono, datos)
        limpiar_conversacion(telefono)

        obs_texto = f"\nObservación: {datos['observacion']}" if datos["observacion"] else ""
        entre = datos.get('entre_calles', '')
        color = datos.get('color_fachada', '')
        ubic  = datos.get('ubicacion', '')

        dir_completa = (
            f"{datos.get('calle', '')} {datos.get('numero_casa', '')}\n"
            f"              Entre: {entre}\n"
            f"              Col. {datos.get('colonia', '')}\n"
            f"              Fachada: {color}"
        )
        if ubic:
            dir_completa += f"\n              Ref: {ubic}"

        # Confirmación al cliente
        await send_message(telefono,
            f"¡Cita agendada con éxito!\n\n"
            f"No. Orden: *{folio}*\n"
            f"Nombre: {datos['nombre']}\n"
            f"Dirección: {dir_completa}\n"
            f"Teléfono: {datos['telefono_contacto']}\n"
            f"Aparato: {datos['aparato']}\n"
            f"Falla: {datos['falla']}\n"
            f"Cita: {datos['fecha']}\n"
            f"Cargo: {datos['cargo']}{obs_texto}\n\n"
            f"Guarda tu número de orden *{folio}* para dar seguimiento.\n"
            f"Un técnico te confirmará la visita en breve."
        )

        # Notificación al taller
        obs_taller = f"\nObservación: {datos['observacion']}" if datos["observacion"] else ""
        msg_taller = (
            f"NUEVA CITA AGENDADA\n"
            f"{'='*30}\n"
            f"No. Orden: {folio}\n"
            f"Nombre: {datos['nombre']}\n"
            f"Calle: {datos.get('calle', '-')} {datos.get('numero_casa', '')}\n"
            f"Entre: {datos.get('entre_calles', '-')}\n"
            f"Colonia: {datos.get('colonia', '-')}\n"
            f"Fachada: {datos.get('color_fachada', '-')}\n"
            f"Referencia: {datos.get('ubicacion', '-')}\n"
            f"Teléfono: {datos['telefono_contacto']}\n"
            f"Aparato: {datos['aparato']}\n"
            f"Falla: {datos['falla']}\n"
            f"Cita: {datos['fecha']}\n"
            f"Cargo: {datos['cargo']}{obs_taller}\n"
            f"{'='*30}\n"
            f"WhatsApp cliente: {telefono}"
        )
        await send_message(NUMERO_TALLER, msg_taller)


# ── Flujo: Seguimiento ────────────────────────────────────

async def _iniciar_seguimiento(telefono: str) -> None:
    print(f"Iniciando seguimiento para {telefono}")
    guardar_estado_conversacion(telefono, {
        "flujo": "seguimiento",
        "paso": "pregunta_garantia",
    })
    await send_interactive_menu(telefono,
        "Seguimiento de servicio\n\n¿Tu servicio es de garantía?",
        [
            {"id": "seg_si_garantia", "title": "Sí, es garantía"},
            {"id": "seg_no_garantia", "title": "No, servicio normal"},
        ]
    )


async def _flujo_seguimiento(telefono: str, mensaje: str, estado: dict) -> None:
    paso = estado.get("paso", "pregunta_garantia")

    if paso == "pregunta_garantia":
        msg_lower = mensaje.lower().strip()

        if mensaje == "seg_si_garantia":
            await _iniciar_garantia(telefono)
            return

        if mensaje == "seg_no_garantia":
            guardar_estado_conversacion(telefono, {"flujo": "seguimiento", "paso": "folio_normal"})
            citas = consultar_cita_por_telefono(telefono)
            if citas:
                if len(citas) == 1:
                    await _mostrar_estado_cita(telefono, citas[0])
                    limpiar_conversacion(telefono)
                else:
                    lista = "\n".join([f"Orden {c['folio']} - {c['aparato']}" for c in citas])
                    await send_message(telefono,
                        f"Encontré estos servicios activos:\n\n{lista}\n\n"
                        "¿De cuál necesitas seguimiento? Escribe el número de orden."
                    )
            else:
                await send_message(telefono,
                    "Escribe tu número de orden para consultar tu servicio."
                )
            return

        if msg_lower in {"si", "sí", "si garantia", "sí garantía", "garantia", "garantía"}:
            await _iniciar_garantia(telefono)
            return

        if msg_lower in {"no", "no garantia", "normal", "servicio normal"}:
            guardar_estado_conversacion(telefono, {"flujo": "seguimiento", "paso": "folio_normal"})
            await send_message(telefono, "Escribe tu número de orden para consultar tu servicio.")
            return

        await send_interactive_menu(telefono,
            "¿Tu servicio es de garantía?",
            [
                {"id": "seg_si_garantia", "title": "Sí, es garantía"},
                {"id": "seg_no_garantia", "title": "No, servicio normal"},
            ]
        )

    elif paso == "folio_normal":
        cita = consultar_cita(mensaje.strip())
        if cita:
            await _mostrar_estado_cita(telefono, cita)
        else:
            await send_message(telefono,
                f"No encontré el número de orden *{mensaje}*.\n"
                "Verifica que esté escrito correctamente.\n"
                "Escribe *agente* para hablar con nosotros."
            )
        limpiar_conversacion(telefono)


async def _mostrar_estado_cita(telefono: str, cita: dict) -> None:
    estado_texto = ESTADOS_TEXTO.get(cita.get("estado", ""), "En proceso")
    await send_message(telefono,
        f"No. Orden: {cita['folio']}\n"
        f"Aparato: {cita.get('aparato', '-')}\n"
        f"Estado: {estado_texto}\n\n"
        "¿Necesitas algo más? Escribe *menú* para ver opciones."
    )


# ── Flujo: Garantía ───────────────────────────────────────

async def _iniciar_garantia(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "garantia",
        "paso": "tipo_garantia",
        "datos": {"telefono": telefono},
    })
    await send_list_menu(telefono,
        "Consulta de garantía\n\n¿Con qué garantía cuenta tu equipo?",
        [
            {"id": "garantia_lg",        "title": "LG",        "description": "Garantía oficial LG"},
            {"id": "garantia_milenia",   "title": "Milenia",   "description": "Garantía Milenia"},
            {"id": "garantia_assurant",  "title": "Assurant",  "description": "Garantía Assurant"},
            {"id": "garantia_garanplus", "title": "GaranPlus", "description": "Garantía GaranPlus"},
            {"id": "garantia_supra",     "title": "Supra",     "description": "Garantía Supra"},
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
                "Por favor selecciona una opción: LG, Milenia, Assurant, GaranPlus o Supra."
            )
            return
        datos["garantia"] = garantia
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre", "datos": datos})
        await send_message(telefono,
            f"Garantía {garantia.upper()} seleccionada.\n\n¿Cuál es tu nombre completo?"
        )

    elif paso == "nombre":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "folio_garantia", "datos": datos})
        await send_message(telefono,
            f"Gracias, {mensaje}.\n\n¿Cuál es tu número de folio o reporte de garantía?"
        )

    elif paso == "folio_garantia":
        datos["folio_garantia"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "equipo", "datos": datos})
        await send_message(telefono,
            "¿Qué equipo es y cuál es el modelo?\n"
            "(ej: Lavadora LG WM1234, Refrigerador Samsung RT32)"
        )

    elif paso == "equipo":
        datos["equipo"] = mensaje.upper()
        await _notificar_taller_garantia(datos)
        guardar_garantia(datos)
        limpiar_conversacion(telefono)
        await send_message(telefono,
            f"Resumen de tu solicitud:\n\n"
            f"Garantía: {datos.get('garantia', '-').upper()}\n"
            f"Nombre: {datos.get('nombre', '-')}\n"
            f"Folio: {datos.get('folio_garantia', '-')}\n"
            f"Equipo: {datos.get('equipo', '-')}\n\n"
            f"{MSG_ESPERA_GARANTIA}"
        )


# ── Flujo: Cotizar ────────────────────────────────────────

async def _iniciar_cotizar(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {"flujo": "cotizar", "paso": "tipo"})
    await send_interactive_menu(telefono,
        "¿Qué tipo de cotización necesitas?",
        [
            {"id": "cotizar_revision",  "title": "Revisión de equipo"},
            {"id": "cotizar_refaccion", "title": "Cotizar refacción"},
        ]
    )


async def _flujo_cotizar(telefono: str, mensaje: str, estado: dict) -> None:
    msg_lower = mensaje.lower()

    if mensaje == "cotizar_revision" or "revision" in msg_lower or "revisión" in msg_lower:
        limpiar_conversacion(telefono)
        await send_message(telefono,
            "Costos de revisión de equipo a domicilio en Puebla:\n\n"
            "• Lavadora: *$450 MXN*\n"
            "• Refrigerador: *$550 MXN*\n"
            "• Aire acondicionado: *$750 MXN*\n"
            "• Pantalla / TV: *$450 MXN*\n"
            "• Estufa: *$450 MXN*\n"
            "• Secadora: *$450 MXN*\n\n"
            "El costo incluye diagnóstico y mano de obra. "
            "Si se requiere refacción se cotiza aparte."
        )
        await send_interactive_menu(telefono,
            "¿Te gustaría agendar una visita de revisión?",
            [
                {"id": "si_agendar", "title": "Sí, agendar"},
                {"id": "no_gracias", "title": "No por ahora"},
            ]
        )
        return

    if mensaje == "cotizar_refaccion" or "refaccion" in msg_lower or "refacción" in msg_lower:
        await _iniciar_cotizar_refaccion(telefono)
        return

    await send_interactive_menu(telefono,
        "¿Qué tipo de cotización necesitas?",
        [
            {"id": "cotizar_revision",  "title": "Revisión de equipo"},
            {"id": "cotizar_refaccion", "title": "Cotizar refacción"},
        ]
    )


# ── Flujo: Cotizar refacción ──────────────────────────────

async def _iniciar_cotizar_refaccion(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "cotizar_refaccion",
        "paso": "numero_parte",
        "datos": {"telefono": telefono},
    })
    await send_interactive_menu(telefono,
        "Cotización de refacción\n\n¿Tienes el número de parte de la refacción?",
        [
            {"id": "tiene_numero_parte", "title": "Sí, tengo el número"},
            {"id": "no_numero_parte",    "title": "No, solo el modelo"},
        ]
    )


async def _flujo_cotizar_refaccion(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "numero_parte")
    datos = estado.get("datos", {"telefono": telefono})

    if not mensaje.strip() and paso not in {"numero_parte"}:
        await send_message(telefono, "Por favor escribe una respuesta para continuar.")
        return

    if paso == "numero_parte":
        if mensaje == "tiene_numero_parte":
            guardar_estado_conversacion(telefono, {**estado, "paso": "capturar_numero_parte", "datos": datos})
            await send_message(telefono, "Escribe el número de parte de la refacción:")
        elif mensaje == "no_numero_parte":
            guardar_estado_conversacion(telefono, {**estado, "paso": "modelo_equipo", "datos": datos})
            await send_message(telefono,
                "Escribe el modelo de tu equipo y la pieza que necesitas.\n"
                "(ej: Lavadora LG WM1234 - bomba de agua)"
            )
        return

    elif paso == "capturar_numero_parte":
        datos["numero_parte"] = mensaje.upper()
        datos["tiene_numero_parte"] = True
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre_cliente", "datos": datos})
        await send_message(telefono, "¿Cuál es tu nombre completo?")

    elif paso == "modelo_equipo":
        datos["modelo_equipo"] = mensaje.upper()
        datos["tiene_numero_parte"] = False
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre_cliente", "datos": datos})
        await send_message(telefono, "¿Cuál es tu nombre completo?")

    elif paso == "nombre_cliente":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "telefono_cliente", "datos": datos})
        await send_message(telefono, "¿Cuál es tu número de teléfono de contacto?")

    elif paso == "telefono_cliente":
        datos["telefono_contacto"] = mensaje
        limpiar_conversacion(telefono)

        detalle = f"No. de parte: {datos.get('numero_parte', '-')}" if datos.get("tiene_numero_parte") else f"Modelo/pieza: {datos.get('modelo_equipo', '-')}"

        msg_taller = (
            f"COTIZACIÓN DE REFACCIÓN\n"
            f"{'='*30}\n"
            f"Cliente: {datos.get('nombre', '-')}\n"
            f"Teléfono: {datos.get('telefono_contacto', '-')}\n"
            f"{detalle}\n"
            f"{'='*30}\n"
            f"Responder al cliente: {telefono}"
        )
        await send_message(NUMERO_TALLER, msg_taller)
        await send_message(telefono, MSG_ESPERA_COTIZACION)


# ── Flujo: Transferir a técnico ───────────────────────────

async def _transferir_a_tecnico(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "transferir",
        "paso": "nombre",
        "datos": {"telefono": telefono},
    })
    await send_message(telefono,
        "Con gusto te comunicamos con un técnico.\n\n"
        "¿Cuál es tu nombre completo?"
    )


async def _flujo_transferir(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "nombre")
    datos = estado.get("datos", {"telefono": telefono})

    if not mensaje.strip():
        await send_message(telefono, "Por favor escribe una respuesta para continuar.")
        return

    if paso == "nombre":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "telefono_contacto", "datos": datos})
        await send_message(telefono, "¿Cuál es tu número de teléfono de contacto?")

    elif paso == "telefono_contacto":
        datos["telefono_contacto"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "tema", "datos": datos})
        await send_message(telefono,
            "¿Sobre qué tema necesitas ayuda?\n"
            "(ej: garantía, refacción, reparación, otro...)"
        )

    elif paso == "tema":
        datos["tema"] = mensaje.upper()
        limpiar_conversacion(telefono)

        msg_taller = (
            f"CLIENTE SOLICITA ATENCIÓN PERSONALIZADA\n"
            f"{'='*30}\n"
            f"Nombre: {datos.get('nombre', '-')}\n"
            f"Teléfono contacto: {datos.get('telefono_contacto', '-')}\n"
            f"Tema: {datos.get('tema', '-')}\n"
            f"WhatsApp: {telefono}\n"
            f"{'='*30}\n"
            f"Responder al cliente: {telefono}"
        )
        await send_message(NUMERO_TALLER, msg_taller)
        await send_message(telefono, MSG_AGENTE)


# ── Preguntas frecuentes ──────────────────────────────────

async def _responder_faq(telefono: str, mensaje: str) -> None:
    msg_lower = mensaje.lower()
    if "garantia" in msg_lower or "garantía" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["garantia"])
    elif "marca" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["marcas"])
    elif "tiempo" in msg_lower or "cuanto tarda" in msg_lower or "cuánto tarda" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["tiempo"])
    elif "costo" in msg_lower or "precio" in msg_lower or "cuanto" in msg_lower or "cuánto" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["costo"])
    elif "horario" in msg_lower or "hora" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["horario"])
    else:
        respuesta = await responder([], mensaje)
        await send_message(telefono, respuesta)
