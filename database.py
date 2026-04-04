"""
database.py - VERSION CON FIREBASE FIRESTORE
Lee credenciales desde variable de entorno (producción en Render)
o desde archivo local (desarrollo en tu PC).
"""
import json
import random
import string
import tempfile
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_CREDENTIALS, FIREBASE_CREDENTIALS_JSON

# Inicializa Firebase solo una vez
if not firebase_admin._apps:
    if FIREBASE_CREDENTIALS_JSON:
        # Producción: lee desde variable de entorno (Render)
        cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
        print("✅ Firebase inicializado desde variable de entorno")
    else:
        # Desarrollo: lee desde archivo local
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        print("✅ Firebase inicializado desde archivo local")
    firebase_admin.initialize_app(cred)

db = firestore.client()


def _generar_folio() -> str:
    """Genera un folio único tipo TLR-A3X9."""
    letras = random.choices(string.ascii_uppercase, k=2)
    numeros = random.choices(string.digits, k=2)
    sufijo = "".join(letras + numeros)
    return f"TLR-{sufijo}"


# ── Citas ────────────────────────────────────────────────

def guardar_cita(telefono: str, datos: dict) -> str:
    """Guarda una nueva cita en Firestore y devuelve el folio."""
    folio = _generar_folio()
    doc = {
        **datos,
        "folio": folio,
        "telefono": telefono,
        "estado": "pendiente",
        "fecha_creacion": datetime.now().isoformat(),
        "fecha_actualizacion": datetime.now().isoformat(),
    }
    db.collection("citas").document(folio).set(doc)
    print(f"✅ Cita guardada en Firebase: {folio} — {datos.get('aparato')} para {datos.get('nombre')}")
    return folio


def consultar_cita(folio: str) -> dict | None:
    """Busca una cita por folio. Devuelve None si no existe."""
    doc = db.collection("citas").document(folio.upper().strip()).get()
    return doc.to_dict() if doc.exists else None


def consultar_cita_por_telefono(telefono: str) -> list[dict]:
    """Devuelve todas las citas activas de un número de teléfono."""
    try:
        docs = (
            db.collection("citas")
            .where("telefono", "==", telefono)
            .where("estado", "!=", "entregado")
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        print(f"⚠️ Error consultando citas por teléfono: {e}")
        return []


def actualizar_estado(folio: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de una cita. Usado por el técnico del taller."""
    ref = db.collection("citas").document(folio.upper())
    doc = ref.get()
    if not doc.exists:
        return False
    ref.update({
        "estado": nuevo_estado,
        "fecha_actualizacion": datetime.now().isoformat(),
    })
    print(f"🔄 Folio {folio} → estado: {nuevo_estado}")
    return True


def guardar_garantia(datos: dict) -> str:
    """Guarda una consulta de garantía en Firestore."""
    folio = f"GAR-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    doc = {
        **datos,
        "folio_interno": folio,
        "fecha_creacion": datetime.now().isoformat(),
        "atendido": False,
    }
    db.collection("garantias").document(folio).set(doc)
    print(f"🛡️ Garantía guardada en Firebase: {folio}")
    return folio


# ── Conversaciones ───────────────────────────────────────

def guardar_estado_conversacion(telefono: str, estado: dict) -> None:
    """Persiste el estado de la conversación en Firestore."""
    try:
        db.collection("conversaciones").document(telefono).set({
            **estado,
            "ultima_actividad": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"⚠️ Error guardando conversación: {e}")


def obtener_estado_conversacion(telefono: str) -> dict:
    """Obtiene el estado actual de la conversación."""
    try:
        doc = db.collection("conversaciones").document(telefono).get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        print(f"⚠️ Error obteniendo conversación: {e}")
        return {}


def limpiar_conversacion(telefono: str) -> None:
    """Resetea la conversación cuando termina el flujo."""
    try:
        db.collection("conversaciones").document(telefono).delete()
    except Exception as e:
        print(f"⚠️ Error limpiando conversación: {e}")
