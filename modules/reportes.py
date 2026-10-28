"""Consultas y calculos para reportes."""
from datetime import date
from io import BytesIO
import pandas as pd
from utils.db import get_db
from utils.tiempo import rango_utc, serie_local


def _paginar(construir, tam: int = 1000) -> list[dict]:
    filas, i = [], 0
    while True:
        lote = construir().range(i, i + tam - 1).execute().data
        filas += lote
        if len(lote) < tam:
            return filas
        i += tam


def ventas_rango(desde: date, hasta: date) -> pd.DataFrame:
    ini, fin = rango_utc(desde, hasta)
    filas = _paginar(lambda: (
        get_db().table("ventas")
        .select("id, folio, creado_en, total, descuento, estado, turno_id, motivo_cancelacion, "
                "usuarios!ventas_usuario_id_fkey(nombre), pagos(metodo, monto), turnos_caja(estado)")
        .gte("creado_en", ini).lte("creado_en", fin).order("folio")))
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["fecha_hora"] = serie_local(df["creado_en"])
    df["fecha"] = df["fecha_hora"].dt.date
    df["total"] = df["total"].astype(float)
    df["descuento"] = df["descuento"].astype(float)
    df["cajero"] = df["usuarios"].apply(lambda u: u["nombre"] if u else "")
    df["pago"] = df["pagos"].apply(lambda ps: " + ".join(sorted({p["metodo"] for p in ps})))
    df["efectivo"] = df["pagos"].apply(lambda ps: sum(float(p["monto"]) for p in ps if p["metodo"] == "efectivo"))
    df["tarjeta"] = df["pagos"].apply(lambda ps: sum(float(p["monto"]) for p in ps if p["metodo"] == "tarjeta"))
    df["turno_abierto"] = df["turnos_caja"].apply(lambda t: bool(t) and t["estado"] == "abierto")
    return df.drop(columns=["usuarios", "pagos", "turnos_caja", "creado_en"])


def items_rango(desde: date, hasta: date) -> pd.DataFrame:
    """Renglones de ventas completadas en el rango."""
    ini, fin = rango_utc(desde, hasta)
    filas = _paginar(lambda: (
        get_db().table("venta_items")
        .select("nombre, cantidad, costo_unitario, importe, ventas!inner(creado_en, estado)")
        .eq("ventas.estado", "completada")
        .gte("ventas.creado_en", ini).lte("ventas.creado_en", fin).order("id")))
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["cantidad"] = df["cantidad"].astype(float)
    df["importe"] = df["importe"].astype(float)
    df["costo"] = df["cantidad"] * df["costo_unitario"].astype(float)
    df["utilidad"] = df["importe"] - df["costo"]
    return df.drop(columns=["ventas", "costo_unitario"])


def resumen(ventas: pd.DataFrame, items: pd.DataFrame) -> dict:
    ok = ventas[ventas["estado"] == "completada"] if not ventas.empty else ventas
    total = float(ok["total"].sum()) if not ok.empty else 0.0
    n = len(ok)
    return {
        "total": round(total, 2),
        "num_ventas": n,
        "ticket_promedio": round(total / n, 2) if n else 0.0,
        "efectivo": round(float(ok["efectivo"].sum()), 2) if n else 0.0,
        "tarjeta": round(float(ok["tarjeta"].sum()), 2) if n else 0.0,
        "utilidad": round(float(items["utilidad"].sum()), 2) if not items.empty else 0.0,
        "canceladas": int((ventas["estado"] == "cancelada").sum()) if not ventas.empty else 0,
    }


def por_dia(ventas: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    if ventas.empty:
        return pd.DataFrame(columns=["fecha", "ventas", "total"])
    ok = ventas[ventas["estado"] == "completada"]
    d = ok.groupby("fecha").agg(ventas=("folio", "count"), total=("total", "sum")).reset_index()
    return d


def por_producto(items: pd.DataFrame) -> pd.DataFrame:
    if items.empty:
        return pd.DataFrame(columns=["producto", "cantidad", "importe", "utilidad"])
    g = items.groupby("nombre").agg(cantidad=("cantidad", "sum"), importe=("importe", "sum"),
                                    utilidad=("utilidad", "sum")).reset_index()
    g = g.rename(columns={"nombre": "producto"}).sort_values("importe", ascending=False)
    return g.round(2)


def por_cajero(ventas: pd.DataFrame) -> pd.DataFrame:
    if ventas.empty:
        return pd.DataFrame(columns=["cajero", "ventas", "total"])
    ok = ventas[ventas["estado"] == "completada"]
    return (ok.groupby("cajero").agg(ventas=("folio", "count"), total=("total", "sum"))
            .reset_index().sort_values("total", ascending=False).round(2))


def cancelar(venta_id: str, usuario_id: str, motivo: str) -> None:
    get_db().rpc("cancelar_venta", {"p_venta_id": venta_id, "p_usuario_id": usuario_id,
                                    "p_motivo": motivo}).execute()


def excel(res: dict, dias: pd.DataFrame, prods: pd.DataFrame, cajeros: pd.DataFrame,
          ventas: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame({"Concepto": ["Total vendido", "Numero de ventas", "Ticket promedio", "Efectivo",
                                   "Tarjeta", "Utilidad estimada", "Ventas canceladas"],
                      "Valor": [res["total"], res["num_ventas"], res["ticket_promedio"], res["efectivo"],
                                res["tarjeta"], res["utilidad"], res["canceladas"]]}
                     ).to_excel(w, sheet_name="Resumen", index=False)
        dias.to_excel(w, sheet_name="Por dia", index=False)
        prods.to_excel(w, sheet_name="Productos", index=False)
        cajeros.to_excel(w, sheet_name="Cajeros", index=False)
        if not ventas.empty:
            ventas[["folio", "fecha_hora", "cajero", "pago", "total", "estado"]].to_excel(w, sheet_name="Ventas", index=False)
    return buf.getvalue()
