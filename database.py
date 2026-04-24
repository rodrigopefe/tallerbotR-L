"""
database.py - VERSION CON FIREBASE FIRESTORE
Folio formato: DDMMAA-XXXX (ej: 260423-1000)
Consecutivo global desde 1000, nunca se repite.
"""
import json
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS", "firebase_credentials.json")

print(f"Firebase JSON presente: {bool(FIREBASE_CREDENTIALS_JSON)}")
print(f"Firebase JSON longitud: {len(FIREBASE_CREDENTIALS_JSON)}")

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


def _generar_folio() -> str:
    """
    Genera folio formato DDMMAA-XXXX.
    Consecutivo global desde 1000, guardado en Firebase.
    Ejemplo: 260423-1000
    """
    hoy = datetime.now().strftime("%d%m%y")

    # Documento contador en Firebase
    contador_ref = db.collection("config").document("contador_folios")

    @firestore.transactional
    def incrementar(transaction):
        doc = contador_ref.get(transaction=transaction)
        if doc.exists:
            nuevo = doc.get("ultimo") + 1
        else:
            nuevo = 1000
        transaction.set(contador_ref, {"ultimo": nuevo})
        return nuevo

    transaction = db.transaction()
    consecutivo = incrementar(transaction)
    return f"{hoy}-{consecutivo}"


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
    print(f"Cita guardada: {folio} - {datos.get('aparato')} para {datos.get('nombre')}")
    return folio


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
        print(f"Error consultando citas activas: {e}")
        return []


def consultar_historial_cliente(telefono: str, limite: int = 3) -> list[dict]:
    """
    Obtiene los últimos N servicios del cliente (incluyendo entregados).
    Ordenados del más reciente al más antiguo.
    """
    try:
        docs = (
            db.collection("citas")
            .where("telefono", "==", telefono)
            .order_by("fecha_creacion", direction=firestore.Query.DESCENDING)
            .limit(limite)
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        print(f"Error consultando historial: {e}")
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
