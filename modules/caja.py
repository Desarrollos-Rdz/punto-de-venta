"""Turnos de caja: apertura, movimientos y corte."""
import pandas as pd
from utils.db import get_db
from utils.tiempo import serie_local


def turno_abierto(usuario_id: str) -> dict | None:
    res = (get_db().table("turnos_caja").select("*")
           .eq("usuario_id", usuario_id).eq("estado", "abierto").limit(1).execute())
    return res.data[0] if res.data else None


def abrir_turno(usuario_id: str, fondo_inicial: float) -> dict:
    return get_db().table("turnos_caja").insert(
        {"usuario_id": usuario_id, "fondo_inicial": fondo_inicial}).execute().data[0]


def registrar_movimiento_caja(turno_id: str, usuario_id: str, tipo: str,
                              monto: float, concepto: str) -> None:
    get_db().table("movimientos_caja").insert({
        "turno_id": turno_id, "usuario_id": usuario_id,
        "tipo": tipo, "monto": monto, "concepto": concepto}).execute()


def resumen_turno(turno_id: str) -> dict:
    """Totales del turno. 'efectivo_esperado' = fondo + ventas en efectivo + ingresos - retiros."""
    r = get_db().table("v_corte_turno").select("*").eq("turno_id", turno_id).single().execute().data
    v = {k: float(r[k]) for k in ("fondo_inicial", "ventas_efectivo", "ventas_tarjeta",
                                   "ingresos_extra", "retiros")}
    v["efectivo_esperado"] = round(
        v["fondo_inicial"] + v["ventas_efectivo"] + v["ingresos_extra"] - v["retiros"], 2)
    v["total_ventas"] = round(v["ventas_efectivo"] + v["ventas_tarjeta"], 2)

    ventas = (get_db().table("ventas").select("id, total, estado")
              .eq("turno_id", turno_id).execute().data)
    completadas = [x for x in ventas if x["estado"] == "completada"]
    v["num_ventas"] = len(completadas)
    v["num_canceladas"] = len(ventas) - len(completadas)

    # utilidad = importe - costo, solo de ventas completadas
    ids = [x["id"] for x in completadas]
    utilidad = 0.0
    if ids:
        items = (get_db().table("venta_items").select("cantidad, costo_unitario, importe")
                 .in_("venta_id", ids).execute().data)
        utilidad = sum(float(i["importe"]) - float(i["cantidad"]) * float(i["costo_unitario"])
                       for i in items)
    v["utilidad"] = round(utilidad, 2)
    v["abierto_en"], v["estado"] = r["abierto_en"], r["estado"]
    return v


def cerrar_turno(turno_id: str, efectivo_contado: float, notas: str | None) -> None:
    get_db().table("turnos_caja").update({
        "estado": "cerrado", "cerrado_en": "now()",
        "efectivo_contado": efectivo_contado, "notas_cierre": notas or None,
    }).eq("id", turno_id).execute()


def movimientos_del_turno(turno_id: str) -> pd.DataFrame:
    filas = (get_db().table("movimientos_caja").select("creado_en, tipo, monto, concepto")
             .eq("turno_id", turno_id).order("creado_en", desc=True).execute().data)
    df = pd.DataFrame(filas)
    if not df.empty:
        df["creado_en"] = serie_local(df["creado_en"])
    return df


def ventas_del_turno(turno_id: str) -> pd.DataFrame:
    filas = (get_db().table("ventas")
             .select("folio, creado_en, total, estado, pagos(metodo, monto)")
             .eq("turno_id", turno_id).order("folio", desc=True).execute().data)
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["creado_en"] = serie_local(df["creado_en"])
    df["pago"] = df["pagos"].apply(lambda ps: " + ".join(sorted({p["metodo"] for p in ps})))
    df["total"] = df["total"].astype(float)
    return df.drop(columns=["pagos"])


def historial_turnos(limite: int = 30) -> pd.DataFrame:
    filas = (get_db().table("turnos_caja")
             .select("id, abierto_en, cerrado_en, estado, fondo_inicial, efectivo_contado, usuarios(nombre)")
             .order("abierto_en", desc=True).limit(limite).execute().data)
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["cajero"] = df["usuarios"].apply(lambda u: u["nombre"] if u else "")
    df["abierto_en"] = serie_local(df["abierto_en"])
    df["cerrado_en"] = serie_local(df["cerrado_en"])
    return df.drop(columns=["usuarios"])
