"""
database.py - VERSION CON FIREBASE FIRESTORE
Numero de orden: solo numeros (ej: 26041601)
Formato: AAMMDDXX donde XX es consecutivo del dia
"""
import json
import random
import string
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Leer variables directamente con os.environ
FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS", "firebase_credentials.json")

print(f"Firebase JSON presente: {bool(FIREBASE_CREDENTIALS_JSON)}")
print(f"Firebase JSON longitud: {len(FIREBASE_CREDENTIALS_JSON)}")

# Inicializa Firebase solo una vez
if not firebase_admin._apps:
    if FIREBASE_CREDENTIALS_JSON and len(FIREBASE_CREDENTIALS_JSON) > 10:
        try:
            cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("Firebase inicializado desde variable de entorno")
        except Exception as e:
            print(f"Error inicializando Firebase desde variable: {e}")
            raise
    else:
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
            print("Firebase inicializado desde archivo local")
        except Exception as e:
            print(f"Error inicializando Firebase desde archivo: {e}")
            raise

db = firestore.client()


def _generar_numero_orden() -> str:
    """
    Genera número de orden solo numérico.
    Formato: AAMMDDXXX donde XXX es consecutivo del día.
    Ejemplo: 26041601 = año 26, mes 04, día 16, orden 01 del día.
    """
    hoy = datetime.now()
    prefijo = hoy.strftime("%y%m%d")

    # Buscar cuántas órdenes hay hoy para el consecutivo
    try:
        inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        docs = (
            db.collection("citas")
            .where("fecha_creacion", ">=", inicio_dia)
            .stream()
        )
        count = sum(1 for _ in docs) + 1
    except Exception:
        count = random.randint(1, 99)

    return f"{prefijo}{count:02d}"


# ── Citas ────────────────────────────────────────────────

def guardar_cita(telefono: str, datos: dict) -> str:
    """Guarda una nueva cita y devuelve el número de orden."""
    numero_orden = _generar_numero_orden()
    doc = {
        **datos,
        "folio": numero_orden,
        "telefono": telefono,
        "estado": "pendiente",
        "fecha_creacion": datetime.now().isoformat(),
        "fecha_actualizacion": datetime.now().isoformat(),
    }
    db.collection("citas").document(numero_orden).set(doc)
    print(f"Cita guardada: {numero_orden} - {datos.get('aparato')} para {datos.get('nombre')}")
    return numero_orden


def consultar_cita(folio: str) -> dict | None:
    doc = db.collection("citas").document(folio.strip()).get()
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
        print(f"Error consultando citas: {e}")
        return []


def actualizar_estado(folio: str, nuevo_estado: str) -> bool:
    ref = db.collection("citas").document(folio)
    doc = ref.get()
    if not doc.exists:
        return False
    ref.update({
        "estado": nuevo_estado,
        "fecha_actualizacion": datetime.now().isoformat(),
    })
    print(f"Orden {folio} -> estado: {nuevo_estado}")
    return True


def guardar_garantia(datos: dict) -> str:
    """Guarda una consulta de garantía en Firestore."""
    folio = f"GAR{datetime.now().strftime('%y%m%d%H%M%S')}"
    doc = {
        **datos,
        "folio_interno": folio,
        "fecha_creacion": datetime.now().isoformat(),
        "atendido": False,
    }
    db.collection("garantias").document(folio).set(doc)
    print(f"Garantia guardada: {folio}")
    return folio


def obtener_citas_del_dia(fecha: str = None) -> list[dict]:
    """
    Obtiene todas las citas de un día específico.
    fecha: string en formato 'YYYY-MM-DD', si es None usa hoy.
    Usado para el correo automático diario.
    """
    if not fecha:
        fecha = datetime.now().strftime("%Y-%m-%d")

    try:
        inicio = f"{fecha}T00:00:00"
        fin    = f"{fecha}T23:59:59"
        docs = (
            db.collection("citas")
            .where("fecha_creacion", ">=", inicio)
            .where("fecha_creacion", "<=", fin)
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        print(f"Error obteniendo citas del dia: {e}")
        return []


# ── Conversaciones ───────────────────────────────────────

def guardar_estado_conversacion(telefono: str, estado: dict) -> None:
    try:
        db.collection("conversaciones").document(telefono).set({
            **estado,
            "ultima_actividad": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"Error guardando conversacion: {e}")


def obtener_estado_conversacion(telefono: str) -> dict:
    try:
        doc = db.collection("conversaciones").document(telefono).get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        print(f"Error obteniendo conversacion: {e}")
        return {}


def limpiar_conversacion(telefono: str) -> None:
    try:
        db.collection("conversaciones").document(telefono).delete()
    except Exception as e:
        print(f"Error limpiando conversacion: {e}")
