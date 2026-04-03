# TallerBot 🔧
Chatbot de WhatsApp para taller de reparación de electrodomésticos.
Stack: WhatsApp Cloud API + FastAPI (Python) + OpenAI GPT-4o mini + Firebase

---

## Estructura del proyecto

```
tallerbot/
├── main.py          # Servidor FastAPI (punto de entrada)
├── bot.py           # Lógica de flujos y conversación
├── ai.py            # Integración OpenAI
├── whatsapp.py      # Envío de mensajes a Cloud API
├── database.py      # Firebase Firestore (citas y estados)
├── config.py        # Variables de entorno
├── requirements.txt
├── .env             # Tu archivo local (nunca subir a Git)
└── .env.example     # Plantilla de variables
```

---

## Instalación local

```bash
# 1. Clonar o crear la carpeta
cd tallerbot

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Copiar y llenar variables
cp .env.example .env
# Edita .env con tus tokens reales

# 5. Arrancar el servidor
uvicorn main:app --reload --port 8000
```

---

## Variables de entorno (.env)

| Variable | Dónde obtenerla |
|---|---|
| `WHATSAPP_TOKEN` | Meta for Developers → Tu App → WhatsApp → API Setup |
| `PHONE_NUMBER_ID` | Misma página, debajo del token |
| `VERIFY_TOKEN` | Tú lo inventas (ej: taller_bot_2024) |
| `OPENAI_API_KEY` | platform.openai.com → API Keys |
| `FIREBASE_CREDENTIALS` | Firebase Console → Configuración → Cuentas de servicio |

---

## Exponer el servidor local con Ngrok

Meta necesita una URL pública para enviar los mensajes.
Durante desarrollo usa Ngrok:

```bash
# Instalar Ngrok: https://ngrok.com/download
ngrok http 8000

# Copia la URL que aparece, ejemplo:
# https://abc123.ngrok-free.app
```

En Meta for Developers → Tu App → WhatsApp → Configuración:
- **URL del webhook:** `https://abc123.ngrok-free.app/webhook`
- **Token de verificación:** el que pusiste en VERIFY_TOKEN

---

## Deploy en Railway (producción)

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Crear proyecto y deploy
railway init
railway up

# 4. Agregar variables de entorno
# Railway Dashboard → Tu proyecto → Variables
# Pega cada variable del .env

# 5. Obtener URL pública
# Railway Dashboard → Tu proyecto → Settings → Domain
# Úsala como webhook URL en Meta
```

---

## Probar el bot

```bash
# Con el servidor corriendo y Ngrok activo,
# envía un mensaje al número de prueba de Meta.
# Verás los logs en la terminal:

# 📩 Payload recibido: {...}
# ✅ Mensaje procesado
```

---

## Estados de una cita

| Estado | Significado |
|---|---|
| `pendiente` | Recién agendada, espera confirmación del taller |
| `en_diagnostico` | El técnico ya revisó el aparato |
| `esperando_refaccion` | Se ordenó una pieza |
| `listo` | Reparación terminada, listo para entregar |
| `entregado` | Servicio completado |

Para cambiar el estado desde el taller, llama a:
```python
from database import actualizar_estado
actualizar_estado("TLR-A3X9", "listo")
```

---

## Escalar a múltiples clientes

Cada cliente (taller) necesita:
1. Su propio número de WhatsApp Business
2. Sus propias variables de entorno (PHONE_NUMBER_ID, WHATSAPP_TOKEN)
3. Su propia colección en Firebase o una base de datos separada

El código es el mismo — solo cambian las variables de entorno.
En Railway puedes crear un proyecto por cliente o usar variables por entorno.
