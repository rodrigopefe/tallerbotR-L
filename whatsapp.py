"""
whatsapp.py
Funciones para enviar mensajes a través de WhatsApp Cloud API.
"""
import httpx
from config import WHATSAPP_TOKEN, WHATSAPP_API_URL


async def send_message(to: str, text: str) -> dict:
    """Envía un mensaje de texto simple al número indicado."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    print(f"📤 Enviando mensaje a {to}")
    print(f"📤 URL: {WHATSAPP_API_URL}")
    print(f"📤 Token (primeros 20): {WHATSAPP_TOKEN[:20]}...")
    print(f"📤 Payload: {payload}")

    async with httpx.AsyncClient() as client:
        response = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
        result = response.json()
        print(f"📤 Status code: {response.status_code}")
        print(f"📤 WhatsApp API response: {result}")
        return result


async def send_interactive_menu(to: str, body: str, options: list[dict]) -> dict:
    """
    Envía un menú de botones interactivos (máx 3 opciones).
    options = [{"id": "1", "title": "Agendar cita"}, ...]
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    buttons = [
        {"type": "reply", "reply": {"id": opt["id"], "title": opt["title"]}}
        for opt in options[:3]
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": buttons},
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
        result = response.json()
        print(f"📤 Interactive menu response: {result}")
        return result


async def send_list_menu(to: str, body: str, options: list[dict]) -> dict:
    """
    Envía un menú de lista (hasta 10 opciones).
    options = [{"id": "1", "title": "Agendar cita", "description": "..."}, ...]
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    rows = [
        {
            "id": opt["id"],
            "title": opt["title"],
            "description": opt.get("description", ""),
        }
        for opt in options
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": "Ver opciones",
                "sections": [{"title": "¿Qué necesitas?", "rows": rows}],
            },
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
        result = response.json()
        print(f"📤 List menu response: {result}")
        return result
