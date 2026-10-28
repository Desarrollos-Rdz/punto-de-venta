"""Datos de la tienda (una sola fila)."""
from utils.db import get_db


def obtener() -> dict:
    return get_db().table("config_tienda").select("*").eq("id", 1).single().execute().data


def guardar(datos: dict) -> None:
    get_db().table("config_tienda").update(datos).eq("id", 1).execute()
