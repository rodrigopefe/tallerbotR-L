"""
config.py
Lee todas las variables de entorno y las expone como constantes.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── WhatsApp ────────────────────────────────────────────
WHATSAPP_TOKEN   = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID  = os.getenv("PHONE_NUMBER_ID", "")
VERIFY_TOKEN     = os.getenv("VERIFY_TOKEN", "taller_bot_2024")
WHATSAPP_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# ── OpenAI ──────────────────────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL     = "gpt-4o-mini"

# ── Firebase ────────────────────────────────────────────
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "firebase_credentials.json")
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON", "")

# ── App ─────────────────────────────────────────────────
APP_ENV = os.getenv("APP_ENV", "development")
