"""
ai.py
Integración con OpenAI GPT-4o mini.
El bot entiende lenguaje natural y extrae datos estructurados de los mensajes.
"""
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── System prompt del taller ─────────────────────────────
SYSTEM_PROMPT = """
Eres el asistente virtual de un taller de reparación de electrodomésticos.
Tu nombre es "Refrigeracion&LavadorasLG".

SERVICIOS QUE OFRECE EL TALLER:
- Reparación de lavadoras (todas las marcas)
- Reparación de refrigeradores
- Reparación de pantallas / televisores
- Reparación de estufas y microondas
- Reparación de secadoras

PRECIOS ORIENTATIVOS:
- Diagnóstico a domicilio: $550 Refrigeradores - 450 Lavadoras,secadoras,pantallas,etc. MXN 
- Reparaciones menores: $300–600 MXN
- Reparaciones mayores: $600–1,500 MXN
- Garantía en reparaciones: 1 meses en refacciones y mano de obra

HORARIOS:
- Lunes a viernes: 9am – 7pm
- Sábados: 9am – 3pm
- Domingos: cerrado

REGLAS IMPORTANTES:
1. Siempre habla en español, de forma amigable y profesional.
2. Si el cliente menciona un aparato y una falla, extrae esa información.
3. Si el cliente quiere agendar, pide: nombre completo, colonia/dirección, fecha y hora preferida.
4. Si el cliente da un folio (formato TLR-XXXX), consulta su servicio.
5. Si no sabes algo específico del negocio, di que un técnico le confirmará.
6. Nunca inventes precios exactos, da rangos.
7. Mantén respuestas cortas (máx 3 oraciones). WhatsApp no es email.
8. Si el usuario escribe "menu" o "inicio", regresa al menú principal.
"""


async def responder(historial: list[dict], mensaje_usuario: str) -> str:
    """
    Genera una respuesta con contexto de la conversación completa.

    historial = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "Hola, ¿en qué te ayudo?"},
        ...
    ]
    """
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
    mensajes.extend(historial)
    mensajes.append({"role": "user", "content": mensaje_usuario})

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=mensajes,
        max_tokens=300,         # respuestas cortas para WhatsApp
        temperature=0.4,        # más consistente, menos creativo
    )
    return response.choices[0].message.content.strip()


async def extraer_datos_cita(texto: str) -> dict:
    """
    Extrae datos estructurados de un mensaje para crear una cita.
    Devuelve un dict con los campos encontrados.
    """
    prompt = f"""
Extrae los datos de esta solicitud de cita en formato JSON.
Si algún dato no está presente, ponlo como null.

Mensaje: "{texto}"

Responde SOLO con JSON, sin explicación:
{{
  "nombre": "...",
  "aparato": "...",
  "falla": "...",
  "direccion": "...",
  "fecha": "...",
  "hora": "..."
}}
"""
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0,
        response_format={"type": "json_object"},
    )
    import json
    return json.loads(response.choices[0].message.content)


async def detectar_intencion(mensaje: str) -> str:
    """
    Detecta qué quiere hacer el usuario.
    Devuelve: 'agendar' | 'cotizar' | 'seguimiento' | 'faq' | 'agente' | 'saludo' | 'otro'
    """
    prompt = f"""
Clasifica la intención de este mensaje de WhatsApp.
Solo responde con UNA de estas palabras exactas:
agendar | cotizar | seguimiento | faq | agente | saludo | otro

Mensaje: "{mensaje}"
"""
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
    )
    intencion = response.choices[0].message.content.strip().lower()
    opciones_validas = {"agendar", "cotizar", "seguimiento", "faq", "agente", "saludo", "otro"}
    return intencion if intencion in opciones_validas else "otro"
