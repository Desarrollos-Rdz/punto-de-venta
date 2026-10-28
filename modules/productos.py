"""Logica de negocio de productos e inventario."""
from decimal import Decimal
import pandas as pd
from utils.db import get_db
from utils.tiempo import serie_local


def listar_categorias() -> list[dict]:
    return get_db().table("categorias").select("*").eq("activa", True).order("id").execute().data


def listar_productos(solo_activos: bool = True) -> pd.DataFrame:
    q = get_db().table("productos").select("*, categorias(nombre)")
    if solo_activos:
        q = q.eq("activo", True)
    filas = q.order("nombre").execute().data
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["categoria"] = df["categorias"].apply(lambda c: c["nombre"] if c else "")
    df = df.drop(columns=["categorias"])
    for col in ("costo", "precio_venta", "utilidad_unit", "margen_pct", "stock", "stock_minimo"):
        df[col] = df[col].astype(float)
    return df


def calcular_margen(costo: float, precio: float) -> tuple[float, float]:
    """Devuelve (utilidad por unidad, margen % sobre precio de venta)."""
    utilidad = precio - costo
    margen = (utilidad / precio * 100) if precio > 0 else 0.0
    return round(utilidad, 2), round(margen, 2)


def precio_sugerido(costo: float, margen_deseado_pct: float) -> float:
    """Precio de venta para lograr un margen deseado sobre el precio."""
    if margen_deseado_pct >= 100:
        return 0.0
    return round(costo / (1 - margen_deseado_pct / 100), 2)


def guardar_producto(datos: dict, producto_id: str | None = None) -> None:
    datos = {k: (None if v == "" else v) for k, v in datos.items()}
    db = get_db()
    if producto_id:
        db.table("productos").update(datos | {"actualizado_en": "now()"}).eq("id", producto_id).execute()
    else:
        db.table("productos").insert(datos).execute()


def desactivar_producto(producto_id: str) -> None:
    get_db().table("productos").update({"activo": False}).eq("id", producto_id).execute()


def registrar_movimiento(producto_id: str, tipo: str, cantidad: float,
                         usuario_id: str, costo: float | None = None,
                         referencia: str | None = None) -> None:
    """Entrada, merma o ajuste. 'cantidad' ya lleva su signo (+ suma, - resta)."""
    db = get_db()
    actual = db.table("productos").select("stock").eq("id", producto_id).single().execute().data
    nuevo = float(actual["stock"]) + cantidad
    if nuevo < 0:
        raise ValueError("El movimiento deja el stock en negativo.")
    cambios = {"stock": nuevo, "actualizado_en": "now()"}
    if tipo == "entrada" and costo is not None:
        cambios["costo"] = costo          # actualiza el ultimo costo de compra
    db.table("productos").update(cambios).eq("id", producto_id).execute()
    db.table("movimientos_inventario").insert({
        "producto_id": producto_id, "tipo": tipo, "cantidad": cantidad,
        "costo_unitario": costo, "usuario_id": usuario_id, "referencia": referencia,
    }).execute()


def listar_movimientos(limite: int = 200) -> pd.DataFrame:
    filas = (
        get_db().table("movimientos_inventario")
        .select("creado_en, tipo, cantidad, costo_unitario, referencia, productos(nombre), usuarios(nombre)")
        .order("creado_en", desc=True).limit(limite).execute().data
    )
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["producto"] = df["productos"].apply(lambda p: p["nombre"] if p else "")
    df["usuario"] = df["usuarios"].apply(lambda u: u["nombre"] if u else "")
    df["creado_en"] = serie_local(df["creado_en"])
    return df.drop(columns=["productos", "usuarios"])
