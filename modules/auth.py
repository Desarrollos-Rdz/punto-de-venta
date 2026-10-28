"""Autenticacion propia (bcrypt) y control de acceso por rol."""
import bcrypt
import streamlit as st
from utils.db import get_db

# Paginas permitidas por rol (nombres = clave de cada pagina en app.py)
PERMISOS = {
    "admin":       ["inicio", "pos", "inventario", "caja", "reportes", "usuarios", "configuracion"],
    "supervisor":  ["inicio", "inventario", "caja", "reportes", "configuracion"],
    "cajero":      ["inicio", "pos", "caja", "configuracion"],
    "almacenista": ["inicio", "inventario", "configuracion"],
}

ROLES_ETIQUETA = {
    "admin": "Administrador",
    "supervisor": "Supervisor",
    "cajero": "Cajero",
    "almacenista": "Almacenista",
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def iniciar_sesion(usuario: str, password: str) -> bool:
    intentos = st.session_state.get("intentos_login", 0)
    if intentos >= 5:
        st.error("Demasiados intentos. Recarga la pagina para volver a intentar.")
        return False

    res = (
        get_db().table("usuarios")
        .select("id, usuario, nombre, email, rol, password_hash, activo")
        .eq("usuario", usuario.strip().lower())
        .limit(1)
        .execute()
    )
    fila = res.data[0] if res.data else None
    if not fila or not fila["activo"] or not verificar_password(password, fila["password_hash"]):
        st.session_state["intentos_login"] = intentos + 1
        return False

    fila.pop("password_hash")
    st.session_state["usuario"] = fila
    st.session_state["intentos_login"] = 0
    return True


def usuario_actual() -> dict | None:
    return st.session_state.get("usuario")


def cerrar_sesion() -> None:
    for k in ("usuario", "carrito", "turno"):
        st.session_state.pop(k, None)


def tiene_acceso(pagina: str) -> bool:
    u = usuario_actual()
    return bool(u) and pagina in PERMISOS.get(u["rol"], [])


def requerir(pagina: str) -> None:
    """Llamar al inicio de cada pagina: detiene la ejecucion si no hay permiso."""
    if not tiene_acceso(pagina):
        st.error("No tienes permiso para ver esta seccion.", icon=":material/lock:")
        st.stop()


def puede_editar(rol_requerido: tuple[str, ...] = ("admin", "almacenista")) -> bool:
    u = usuario_actual()
    return bool(u) and u["rol"] in rol_requerido
