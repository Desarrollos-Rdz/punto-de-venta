"""Administracion de usuarios."""
import re
import pandas as pd
from modules.auth import hash_password, verificar_password
from utils.db import get_db

MIN_PASSWORD = 8


def validar_password(pw: str) -> str | None:
    if len(pw) < MIN_PASSWORD:
        return f"La contrasena debe tener al menos {MIN_PASSWORD} caracteres."
    if pw.isalpha() or pw.isdigit():
        return "Combina letras y numeros en la contrasena."
    return None


def listar() -> pd.DataFrame:
    filas = (get_db().table("usuarios").select("id, usuario, nombre, email, rol, activo, creado_en")
             .order("creado_en").execute().data)
    return pd.DataFrame(filas)


def crear(usuario: str, nombre: str, email: str, rol: str, password: str) -> None:
    usuario = usuario.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,30}", usuario):
        raise ValueError("El usuario debe tener 3 a 30 caracteres: letras, numeros, punto, guion o guion bajo.")
    if err := validar_password(password):
        raise ValueError(err)
    existe = get_db().table("usuarios").select("id").eq("usuario", usuario).execute().data
    if existe:
        raise ValueError("Ese nombre de usuario ya existe.")
    get_db().table("usuarios").insert({
        "usuario": usuario, "nombre": nombre.strip(), "email": email.strip() or None,
        "rol": rol, "password_hash": hash_password(password)}).execute()


def _admins_activos(excluyendo: str | None = None) -> int:
    q = get_db().table("usuarios").select("id").eq("rol", "admin").eq("activo", True)
    if excluyendo:
        q = q.neq("id", excluyendo)
    return len(q.execute().data)


def actualizar(usuario_id: str, nombre: str, email: str, rol: str, activo: bool) -> None:
    # Siempre debe quedar al menos un administrador activo
    if (rol != "admin" or not activo) and _admins_activos(excluyendo=usuario_id) == 0:
        raise ValueError("Debe existir al menos un administrador activo.")
    get_db().table("usuarios").update({
        "nombre": nombre.strip(), "email": email.strip() or None, "rol": rol, "activo": activo,
    }).eq("id", usuario_id).execute()


def restablecer_password(usuario_id: str, nueva: str) -> None:
    if err := validar_password(nueva):
        raise ValueError(err)
    get_db().table("usuarios").update({"password_hash": hash_password(nueva)}).eq("id", usuario_id).execute()


def cambiar_mi_password(usuario_id: str, actual: str, nueva: str) -> None:
    fila = get_db().table("usuarios").select("password_hash").eq("id", usuario_id).single().execute().data
    if not verificar_password(actual, fila["password_hash"]):
        raise ValueError("La contrasena actual no es correcta.")
    restablecer_password(usuario_id, nueva)
