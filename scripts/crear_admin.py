"""Crea (o restablece) el usuario administrador inicial.

Uso:
    python scripts/crear_admin.py admin "Nombre Completo"
Pide la contrasena por teclado. Lee la conexion de .streamlit/secrets.toml.
"""
import getpass
import sys
import tomllib
from pathlib import Path

import bcrypt
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

secrets = tomllib.loads(Path(".streamlit/secrets.toml").read_text())["supabase"]
db = create_client(secrets["url"], secrets["service_key"])

usuario = (sys.argv[1] if len(sys.argv) > 1 else "admin").strip().lower()
nombre = sys.argv[2] if len(sys.argv) > 2 else "Administrador"
password = getpass.getpass("Contrasena (minimo 8 caracteres): ")
if len(password) < 8:
    sys.exit("La contrasena es muy corta.")

hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
db.table("usuarios").upsert(
    {"usuario": usuario, "nombre": nombre, "rol": "admin",
     "password_hash": hashed, "activo": True},
    on_conflict="usuario",
).execute()
print(f"Listo: usuario '{usuario}' creado/actualizado como administrador.")
