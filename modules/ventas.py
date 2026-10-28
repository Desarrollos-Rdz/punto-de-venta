"""Registro de ventas."""
from decimal import Decimal, ROUND_HALF_UP
from utils.db import get_db


def importe(cantidad: float, precio: float) -> float:
    """Mismo redondeo que la base de datos (mitad hacia arriba, 2 decimales)."""
    return float((Decimal(str(cantidad)) * Decimal(str(precio))).quantize(Decimal("0.01"), ROUND_HALF_UP))


def buscar_por_codigo(codigo: str) -> dict | None:
    res = (get_db().table("productos").select("*")
           .eq("codigo_barras", codigo.strip()).eq("activo", True).limit(1).execute())
    return res.data[0] if res.data else None


def registrar_venta(turno_id: str, usuario_id: str, items: list[dict], pagos: list[dict],
                    descuento: float = 0.0, email: str | None = None,
                    telefono: str | None = None) -> dict:
    """Llama a la funcion SQL que descuenta stock y guarda todo en una sola transaccion."""
    res = get_db().rpc("registrar_venta", {
        "p_turno_id": turno_id,
        "p_usuario_id": usuario_id,
        "p_items": [{"producto_id": i["producto_id"], "cantidad": i["cantidad"],
                     "precio_unitario": i["precio_unitario"]} for i in items],
        "p_pagos": pagos,
        "p_descuento": descuento,
        "p_cliente_email": email or None,
        "p_cliente_telefono": telefono or None,
    }).execute()
    return res.data[0]
