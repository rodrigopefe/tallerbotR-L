"""
bot.py
Lógica central del chatbot — Refrigeración y Lavadoras LG
- Saludo personalizado con historial de últimos 3 servicios
- Solo servicios con cargo pueden agendar
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

# ── Mensajes fijos ────────────────────────────────────────

MSG_BIENVENIDA_NUEVO = (
    "Hola! Soy el asistente de *Refrigeracion y Lavadoras LG*.\n\n"
    "Como puedo ayudarte?"
)

MSG_AGENTE = (
    "En un momento uno de nuestros tecnicos te atiende.\n"
    "Horario de atencion: lunes a viernes 9am-5pm, sabados 9am-2pm."
)

MSG_ESPERA_COTIZACION = (
    "Listo, recibimos tu solicitud.\n\n"
    "Un tecnico revisara la disponibilidad y precio de la refaccion "
    "y te respondera en este chat a la brevedad.\n\n"
    "Si es fuera de horario, te contactamos en cuanto abramos "
    "(lun-vie 9am-5pm, sab 9am-2pm)."
)

MSG_ESPERA_GARANTIA = (
    "Listo, recibimos tu solicitud.\n\n"
    "Un tecnico revisara el estado de tu garantia y te respondera "
    "en este chat en los proximos minutos.\n\n"
    "Si es fuera de horario, te contactamos en cuanto abramos "
    "(lun-vie 9am-5pm, sab 9am-2pm)."
)

MENU_OPCIONES = [
    {"id": "agendar",     "title": "Agendar cita",         "description": "Servicio con cargo a domicilio"},
    {"id": "cotizar",     "title": "Cotizar",               "description": "Revision de equipo o refaccion"},
    {"id": "seguimiento", "title": "Seguimiento",           "description": "Revisa tu servicio o garantia"},
    {"id": "faq",         "title": "Preguntas frecuentes",  "description": "Garantias, marcas, tiempos"},
    {"id": "agente",      "title": "Hablar con tecnico",    "description": "Atencion personalizada"},
]

FAQ_RESPUESTAS = {
    "garantia": "Ofrecemos *3 meses de garantia* en todas nuestras reparaciones (refacciones y mano de obra).",
    "marcas": "Trabajamos con *todas las marcas*: Mabe, Whirlpool, LG, Samsung, Electrolux, Acros y mas.",
    "tiempo": "El tiempo depende del diagnostico. Reparaciones menores: mismo dia. Mayores: 1-3 dias habiles.",
    "costo": "Refrigeradores: *$550 MXN*. Otros aparatos: *$450 MXN*. Incluye diagnostico y mano de obra.",
    "horario": "Atendemos lunes a viernes de 9am a 5pm y sabados de 9am a 2pm.",
}

GARANTIAS_VALIDAS = {"lg", "milenia", "assurant", "garanplus", "supra"}

# Número del taller para notificaciones
NUMERO_TALLER = "522201330759"

ESTADOS_TEXTO = {
    "pendiente":           "Pendiente de visita",
    "en_diagnostico":      "En diagnostico",
    "esperando_refaccion": "Esperando refaccion",
    "listo":               "Listo para entregar",
    "entregado":           "Entregado",
}


# ── Utilidad: normalizar número México ───────────────────

def _normalizar_telefono(telefono: str) -> str:
    if telefono.startswith("5212") and len(telefono) == 13:
        telefono = "52" + telefono[3:]
        print(f"Numero normalizado: {telefono}")
    return telefono


# ── Utilidad: precio por aparato ─────────────────────────

def _precio_por_aparato(aparato: str) -> str:
    aparato_lower = aparato.lower()
    if "refri" in aparato_lower or "refriger" in aparato_lower:
        return "$550.00"
    return "$450.00"


# ── Utilidad: notificar al taller ────────────────────────

async def _notificar_taller_garantia(datos: dict) -> None:
    print("\n" + "="*50)
    print("NUEVA CONSULTA DE GARANTIA")
    print(f"  Garantia:  {datos.get('garantia', '-').upper()}")
    print(f"  Cliente:   {datos.get('nombre', '-')}")
    print(f"  Folio:     {datos.get('folio_garantia', '-')}")
    print(f"  Equipo:    {datos.get('equipo', '-')}")
    print(f"  Telefono:  {datos.get('telefono', '-')}")
    print("="*50 + "\n")


# ── Saludo personalizado con historial ────────────────────

async def _saludo_con_historial(telefono: str) -> None:
    """
    Busca historial del cliente y genera saludo personalizado.
    Si es cliente nuevo, saludo genérico.
    """
    historial = consultar_historial_cliente(telefono, limite=3)

    if not historial:
        # Cliente nuevo
        await send_list_menu(telefono, MSG_BIENVENIDA_NUEVO, MENU_OPCIONES)
        return

    # Cliente con historial — obtener nombre del último servicio
    nombre = historial[0].get("nombre", "").split()[0].capitalize() if historial else ""

    # Construir resumen de últimos servicios
    lineas = []
    for cita in historial:
        estado = ESTADOS_TEXTO.get(cita.get("estado", ""), "En proceso")
        folio  = cita.get("folio", "-")
        aparato = cita.get("aparato", "-")
        lineas.append(f"• {folio} — {aparato} — {estado}")

    servicios_texto = "\n".join(lineas)

    saludo = (
        f"Hola {nombre}, bienvenido de nuevo a *Refrigeracion y Lavadoras LG*.\n\n"
        f"Tus ultimos servicios:\n{servicios_texto}\n\n"
        f"Como puedo ayudarte hoy?"
    )

    await send_list_menu(telefono, saludo, MENU_OPCIONES)


# ── Manejador principal ───────────────────────────────────

async def manejar_mensaje(telefono: str, mensaje: str) -> None:
    telefono = _normalizar_telefono(telefono)
    mensaje  = mensaje.strip()
    estado   = obtener_estado_conversacion(telefono)
    flujo    = estado.get("flujo")

    # Palabras clave para reiniciar
    if mensaje.lower() in {"menu", "inicio", "hola", "hi", "buenas", "buenos dias",
                            "buenas tardes", "buenas noches", "empezar"}:
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
        "Que aparato necesitas reparar?\n"
        "(ej: lavadora, refrigerador, pantalla, estufa...)"
    )


async def _flujo_agendar(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "aparato")
    datos = estado.get("datos", {})

    if paso == "aparato":
        datos["aparato"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "falla", "datos": datos})
        await send_message(telefono,
            f"Anotado: *{mensaje}*.\n\nCual es el problema o falla que presenta?"
        )
    elif paso == "falla":
        datos["falla"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre", "datos": datos})
        await send_message(telefono, "A que nombre agendamos la cita?\n(nombre completo)")

    elif paso == "nombre":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "direccion", "datos": datos})
        await send_message(telefono,
            f"Perfecto, {mensaje}.\n\nCual es tu direccion completa?"
        )
    elif paso == "direccion":
        datos["direccion"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "ubicacion", "datos": datos})
        await send_message(telefono,
            "Hay alguna referencia para llegar?\n"
            "(ej: frente al mercado, entre calles, color de la casa...)\n"
            "Si no hay referencia escribe *no*"
        )
    elif paso == "ubicacion":
        datos["ubicacion"] = "" if mensaje.lower() == "no" else mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "telefono", "datos": datos})
        await send_message(telefono, "Cual es tu numero de telefono de contacto?")

    elif paso == "telefono":
        datos["telefono_contacto"] = mensaje
        guardar_estado_conversacion(telefono, {**estado, "paso": "fecha", "datos": datos})
        await send_message(telefono,
            "Que dia y hora te queda mejor?\n"
            "Horario disponible:\n"
            "Lunes a viernes: 9am - 5pm\n"
            "Sabados: 9am - 2pm"
        )
    elif paso == "fecha":
        datos["fecha"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "llamar_antes", "datos": datos})
        await send_interactive_menu(telefono,
            "Deseas que te llamemos 30 minutos antes de la visita?",
            [
                {"id": "llamar_si", "title": "Si, llamarme antes"},
                {"id": "llamar_no", "title": "No es necesario"},
            ]
        )
    elif paso == "llamar_antes":
        msg_lower = mensaje.lower()
        datos["observacion"] = "MARCAR 30 MIN ANTES" if (mensaje == "llamar_si" or "si" in msg_lower) else ""
        datos["cargo"] = _precio_por_aparato(datos.get("aparato", ""))

        folio = guardar_cita(telefono, datos)
        limpiar_conversacion(telefono)

        obs_texto = f"\nObservacion: {datos['observacion']}" if datos["observacion"] else ""
        await send_message(telefono,
            f"Cita agendada con exito!\n\n"
            f"No. Orden: *{folio}*\n"
            f"Nombre: {datos['nombre']}\n"
            f"Direccion: {datos['direccion']}\n"
            f"Telefono: {datos['telefono_contacto']}\n"
            f"Aparato: {datos['aparato']}\n"
            f"Falla: {datos['falla']}\n"
            f"Cita: {datos['fecha']}\n"
            f"Cargo: {datos['cargo']}{obs_texto}\n\n"
            f"Guarda tu numero de orden *{folio}* para dar seguimiento.\n"
            f"Un tecnico te confirmara la visita en breve."
        )


# ── Flujo: Seguimiento ────────────────────────────────────

async def _iniciar_seguimiento(telefono: str) -> None:
    print(f"Iniciando seguimiento para {telefono}")
    guardar_estado_conversacion(telefono, {
        "flujo": "seguimiento",
        "paso": "pregunta_garantia",
    })
    await send_interactive_menu(telefono,
        "Seguimiento de servicio\n\nTu servicio es de garantia?",
        [
            {"id": "seg_si_garantia", "title": "Si, es garantia"},
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
                        f"Encontre estos servicios activos:\n\n{lista}\n\n"
                        "De cual necesitas seguimiento? Escribe el numero de orden."
                    )
            else:
                await send_message(telefono,
                    "Escribe tu numero de orden para consultar tu servicio."
                )
            return

        if msg_lower in {"si", "si garantia", "garantia"}:
            await _iniciar_garantia(telefono)
            return

        if msg_lower in {"no", "no garantia", "normal", "servicio normal"}:
            guardar_estado_conversacion(telefono, {"flujo": "seguimiento", "paso": "folio_normal"})
            await send_message(telefono, "Escribe tu numero de orden para consultar tu servicio.")
            return

        await send_interactive_menu(telefono,
            "Tu servicio es de garantia?",
            [
                {"id": "seg_si_garantia", "title": "Si, es garantia"},
                {"id": "seg_no_garantia", "title": "No, servicio normal"},
            ]
        )

    elif paso == "folio_normal":
        cita = consultar_cita(mensaje.strip())
        if cita:
            await _mostrar_estado_cita(telefono, cita)
        else:
            await send_message(telefono,
                f"No encontre el numero de orden *{mensaje}*.\n"
                "Verifica que este escrito correctamente.\n"
                "Escribe *agente* para hablar con nosotros."
            )
        limpiar_conversacion(telefono)


async def _mostrar_estado_cita(telefono: str, cita: dict) -> None:
    estado_texto = ESTADOS_TEXTO.get(cita.get("estado", ""), "En proceso")
    await send_message(telefono,
        f"No. Orden: {cita['folio']}\n"
        f"Aparato: {cita.get('aparato', '-')}\n"
        f"Estado: {estado_texto}\n\n"
        "Necesitas algo mas? Escribe *menu* para ver opciones."
    )


# ── Flujo: Garantía ───────────────────────────────────────

async def _iniciar_garantia(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "garantia",
        "paso": "tipo_garantia",
        "datos": {"telefono": telefono},
    })
    await send_list_menu(telefono,
        "Consulta de garantia\n\nCon que garantia cuenta tu equipo?",
        [
            {"id": "garantia_lg",        "title": "LG",        "description": "Garantia oficial LG"},
            {"id": "garantia_milenia",   "title": "Milenia",   "description": "Garantia Milenia"},
            {"id": "garantia_assurant",  "title": "Assurant",  "description": "Garantia Assurant"},
            {"id": "garantia_garanplus", "title": "GaranPlus", "description": "Garantia GaranPlus"},
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
                "Por favor selecciona una opcion: LG, Milenia, Assurant, GaranPlus o Supra."
            )
            return
        datos["garantia"] = garantia
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre", "datos": datos})
        await send_message(telefono,
            f"Garantia {garantia.upper()} seleccionada.\n\nCual es tu nombre completo?"
        )

    elif paso == "nombre":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "folio_garantia", "datos": datos})
        await send_message(telefono,
            f"Gracias, {mensaje}.\n\nCual es tu numero de folio o reporte de garantia?"
        )

    elif paso == "folio_garantia":
        datos["folio_garantia"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "equipo", "datos": datos})
        await send_message(telefono,
            "Que equipo es y cual es el modelo?\n"
            "(ej: Lavadora LG WM1234, Refrigerador Samsung RT32)"
        )

    elif paso == "equipo":
        datos["equipo"] = mensaje.upper()
        await _notificar_taller_garantia(datos)
        guardar_garantia(datos)
        limpiar_conversacion(telefono)
        await send_message(telefono,
            f"Resumen de tu solicitud:\n\n"
            f"Garantia: {datos.get('garantia', '-').upper()}\n"
            f"Nombre: {datos.get('nombre', '-')}\n"
            f"Folio: {datos.get('folio_garantia', '-')}\n"
            f"Equipo: {datos.get('equipo', '-')}\n\n"
            f"{MSG_ESPERA_GARANTIA}"
        )


# ── Flujo: Cotizar ────────────────────────────────────────

async def _iniciar_cotizar(telefono: str) -> None:
    await send_interactive_menu(telefono,
        "Que tipo de cotizacion necesitas?",
        [
            {"id": "cotizar_revision",   "title": "Revision de equipo"},
            {"id": "cotizar_refaccion",  "title": "Cotizar refaccion"},
        ]
    )


async def _flujo_cotizar(telefono: str, mensaje: str, estado: dict) -> None:
    msg_lower = mensaje.lower()

    if mensaje == "cotizar_revision" or "revision" in msg_lower:
        limpiar_conversacion(telefono)
        await send_message(telefono,
            "Costos de revision de equipo a domicilio:\n\n"
            "Lavadora: *$450 MXN*\n"
            "Refrigerador: *$550 MXN*\n"
            "Pantalla / TV: *$450 MXN*\n"
            "Estufa: *$450 MXN*\n"
            "Secadora: *$450 MXN*\n\n"
            "El costo de revision incluye diagnostico y mano de obra. "
            "Si se requiere refaccion se cotiza aparte."
        )
        await send_interactive_menu(telefono,
            "Te gustaria agendar una visita de revision?",
            [
                {"id": "si_agendar", "title": "Si, agendar"},
                {"id": "no_gracias", "title": "No por ahora"},
            ]
        )
        return

    if mensaje == "cotizar_refaccion" or "refaccion" in msg_lower:
        await _iniciar_cotizar_refaccion(telefono)
        return

    # Si no reconoce, mostrar opciones de nuevo
    await send_interactive_menu(telefono,
        "Que tipo de cotizacion necesitas?",
        [
            {"id": "cotizar_revision",  "title": "Revision de equipo"},
            {"id": "cotizar_refaccion", "title": "Cotizar refaccion"},
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
        "Cotizacion de refaccion\n\nTienes el numero de parte de la refaccion?",
        [
            {"id": "tiene_numero_parte", "title": "Si, tengo el numero"},
            {"id": "no_numero_parte",    "title": "No, solo el modelo"},
        ]
    )


async def _flujo_cotizar_refaccion(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "numero_parte")
    datos = estado.get("datos", {"telefono": telefono})

    if paso == "numero_parte":
        if mensaje == "tiene_numero_parte":
            guardar_estado_conversacion(telefono, {**estado, "paso": "capturar_numero_parte", "datos": datos})
            await send_message(telefono, "Escribe el numero de parte de la refaccion:")
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
        await send_message(telefono, "Cual es tu nombre completo?")

    elif paso == "modelo_equipo":
        datos["modelo_equipo"] = mensaje.upper()
        datos["tiene_numero_parte"] = False
        guardar_estado_conversacion(telefono, {**estado, "paso": "nombre_cliente", "datos": datos})
        await send_message(telefono, "Cual es tu nombre completo?")

    elif paso == "nombre_cliente":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "telefono_cliente", "datos": datos})
        await send_message(telefono, "Cual es tu numero de telefono de contacto?")

    elif paso == "telefono_cliente":
        datos["telefono_contacto"] = mensaje
        limpiar_conversacion(telefono)

        # Armar mensaje para el taller
        if datos.get("tiene_numero_parte"):
            detalle = f"No. de parte: {datos.get('numero_parte', '-')}"
        else:
            detalle = f"Modelo/pieza: {datos.get('modelo_equipo', '-')}"

        msg_taller = (
            f"COTIZACION DE REFACCION\n"
            f"{'='*30}\n"
            f"Cliente: {datos.get('nombre', '-')}\n"
            f"Telefono: {datos.get('telefono_contacto', '-')}\n"
            f"{detalle}\n"
            f"{'='*30}\n"
            f"Responder al cliente por WhatsApp: {telefono}"
        )

        # Notificar al taller
        await send_message(NUMERO_TALLER, msg_taller)

        # Confirmar al cliente
        await send_message(telefono, MSG_ESPERA_COTIZACION)


# ── Transferir a técnico ─────────────────────────────────

async def _transferir_a_tecnico(telefono: str) -> None:
    guardar_estado_conversacion(telefono, {
        "flujo": "transferir",
        "paso": "nombre",
        "datos": {"telefono": telefono},
    })
    await send_message(telefono,
        "Con gusto te comunicamos con un tecnico.\n\n"
        "Cual es tu nombre completo?"
    )


async def _flujo_transferir(telefono: str, mensaje: str, estado: dict) -> None:
    paso  = estado.get("paso", "nombre")
    datos = estado.get("datos", {"telefono": telefono})

    if paso == "nombre":
        datos["nombre"] = mensaje.upper()
        guardar_estado_conversacion(telefono, {**estado, "paso": "telefono_contacto", "datos": datos})
        await send_message(telefono, "Cual es tu numero de telefono de contacto?")

    elif paso == "telefono_contacto":
        datos["telefono_contacto"] = mensaje
        limpiar_conversacion(telefono)

        # Notificar al taller
        msg_taller = (
            f"CLIENTE SOLICITA ATENCION PERSONALIZADA\n"
            f"{'='*30}\n"
            f"Nombre: {datos.get('nombre', '-')}\n"
            f"Telefono contacto: {datos.get('telefono_contacto', '-')}\n"
            f"WhatsApp: {telefono}\n"
            f"{'='*30}\n"
            f"Responder al cliente: {telefono}"
        )
        await send_message(NUMERO_TALLER, msg_taller)

        await send_message(telefono, MSG_AGENTE)


# ── Preguntas frecuentes ──────────────────────────────────

async def _responder_faq(telefono: str, mensaje: str) -> None:
    msg_lower = mensaje.lower()
    if "garantia" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["garantia"])
    elif "marca" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["marcas"])
    elif "tiempo" in msg_lower or "cuanto tarda" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["tiempo"])
    elif "costo" in msg_lower or "precio" in msg_lower or "cuanto" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["costo"])
    elif "horario" in msg_lower or "hora" in msg_lower:
        await send_message(telefono, FAQ_RESPUESTAS["horario"])
    else:
        respuesta = await responder([], mensaje)
        await send_message(telefono, respuesta)
