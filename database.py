"""
database.py - VERSION CON FIREBASE FIRESTORE
Lee credenciales desde variable de entorno (producción en Railway/Render)
o desde archivo local (desarrollo en tu PC).
"""
import json
import random
import string
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Leer variables directamente con os.getenv
FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS", "firebase_credentials.json")

print(f"🔍 FIREBASE_CREDENTIALS_JSON presente: {bool(FIREBASE_CREDENTIALS_JSON)}")
print(f"🔍 FIREBASE_CREDENTIALS_JSON longitud: {len(FIREBASE_CREDENTIALS_JSON)}")
print(f"🔍 FIREBASE_CREDENTIALS: {FIREBASE_CREDENTIALS}")

# Inicializa Firebase solo una vez
if not firebase_admin._apps:
    if FIREBASE_CREDENTIALS_JSON and len(FIREBASE_CREDENTIALS_JSON) > 10:
        try:
            cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase inicializado desde variable de entorno")
        except Exception as e:
            print(f"❌ Error inicializando Firebase desde variable: {e}")
            raise
    else:
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase inicializado desde archivo local")
        except Exception as e:
            print(f"❌ Error inicializando Firebase desde archivo: {e}")
            raise

db = firestore.client()


def _generar_folio() -> str:
    letras = random.choices(string.ascii_uppercase, k=2)
    numeros = random.choices(string.digits, k=2)
    sufijo = "".join(letras + numeros)
    return f"TLR-{sufijo}"


# ── Citas ────────────────────────────────────────────────

def guardar_cita(telefono: str, datos: dict) -> str:
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
    print(f"✅ Cita guardada: {folio}")
    return folio


def consultar_cita(folio: str) -> dict | None:
    doc = db.collection("citas").document(folio.upper().strip()).get()
    return doc.to_dict() if doc.exists else None


def consultar_cita_por_telefono(telefono: str) -> list[dict]:
    try:
        docs = (
            db.collection("citas")
            .where("telefono", "==", telefono)
            .where("estado", "!=", "entregado")
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        print(f"⚠️ Error consultando citas: {e}")
        return []


def actualizar_estado(folio: str, nuevo_estado: str) -> bool:
    ref = db.collection("citas").document(folio.upper())
    doc = ref.get()
    if not doc.exists:
        return False
    ref.update({
        "estado": nuevo_estado,
        "fecha_actualizacion": datetime.now().isoformat(),
    })
    return True


def guardar_garantia(datos: dict) -> str:
    folio = f"GAR-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    doc = {
        **datos,
        "folio_interno": folio,
        "fecha_creacion": datetime.now().isoformat(),
        "atendido": False,
    }
    db.collection("garantias").document(folio).set(doc)
    return folio


# ── Conversaciones ───────────────────────────────────────

def guardar_estado_conversacion(telefono: str, estado: dict) -> None:
    try:
        db.collection("conversaciones").document(telefono).set({
            **estado,
            "ultima_actividad": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"⚠️ Error guardando conversación: {e}")


def obtener_estado_conversacion(telefono: str) -> dict:
    try:
        doc = db.collection("conversaciones").document(telefono).get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        print(f"⚠️ Error obteniendo conversación: {e}")
        return {}


def limpiar_conversacion(telefono: str) -> None:
    try:
        db.collection("conversaciones").document(telefono).delete()
    except Exception as e:
        print(f"⚠️ Error limpiando conversación: {e}")
