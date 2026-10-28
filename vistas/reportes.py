from datetime import timedelta
import streamlit as st
from modules import auth, reportes, tienda
from utils.pdf import reporte_pdf
from utils.tiempo import hoy_local
from utils.ui import titulo, mxn

auth.requerir("reportes")
u = auth.usuario_actual()
titulo("bar_chart", "Reportes", "Ventas, productos, cajeros y utilidad")

hoy = hoy_local()
atajos = {"Hoy": (hoy, hoy), "Ayer": (hoy - timedelta(1), hoy - timedelta(1)),
          "Ultimos 7 dias": (hoy - timedelta(6), hoy), "Ultimos 30 dias": (hoy - timedelta(29), hoy),
          "Este mes": (hoy.replace(day=1), hoy), "Personalizado": None}
a, b = st.columns([1, 2])
opcion = a.selectbox("Periodo", list(atajos), index=2)
if atajos[opcion]:
    desde, hasta = atajos[opcion]
else:
    rango = b.date_input("Rango de fechas", (hoy - timedelta(6), hoy), max_value=hoy)
    if len(rango) != 2:
        st.info("Elige la fecha de inicio y la de fin.")
        st.stop()
    desde, hasta = rango

ventas = reportes.ventas_rango(desde, hasta)
items = reportes.items_rango(desde, hasta)
res = reportes.resumen(ventas, items)
dias = reportes.por_dia(ventas, items)
prods = reportes.por_producto(items)
cajeros = reportes.por_cajero(ventas)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total vendido", mxn(res["total"]), f"{res['num_ventas']} ventas")
c2.metric("Ticket promedio", mxn(res["ticket_promedio"]))
c3.metric("Utilidad estimada", mxn(res["utilidad"]))
c4.metric("Efectivo / Tarjeta", f"{mxn(res['efectivo'])} / {mxn(res['tarjeta'])}")

rango_txt = f"{desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
d1, d2, _ = st.columns([1, 1, 3])
d1.download_button("Descargar PDF", reporte_pdf(rango_txt, res, dias, prods, cajeros, tienda.obtener()["nombre"]),
                   "reporte_ventas.pdf", "application/pdf", icon=":material/picture_as_pdf:", on_click="ignore")
d2.download_button("Descargar Excel", reportes.excel(res, dias, prods, cajeros, ventas), "reporte_ventas.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   icon=":material/table_view:", on_click="ignore")

tab_dia, tab_prod, tab_caj, tab_ven = st.tabs([
    ":material/calendar_month: Por dia", ":material/inventory_2: Productos",
    ":material/badge: Cajeros", ":material/receipt_long: Ventas y cancelaciones"])

with tab_dia:
    if dias.empty:
        st.info("No hay ventas en este periodo.")
    else:
        st.bar_chart(dias.set_index("fecha")["total"], color="#C2410C")
        st.dataframe(dias, hide_index=True, use_container_width=True,
                     column_config={"total": st.column_config.NumberColumn("Total", format="$%.2f")})

with tab_prod:
    if prods.empty:
        st.info("No hay ventas en este periodo.")
    else:
        st.bar_chart(prods.head(10).set_index("producto")["importe"], color="#C2410C", horizontal=True)
        st.dataframe(prods, hide_index=True, use_container_width=True,
                     column_config={"cantidad": st.column_config.NumberColumn("Cantidad", format="%.3f"),
                                    "importe": st.column_config.NumberColumn("Importe", format="$%.2f"),
                                    "utilidad": st.column_config.NumberColumn("Utilidad", format="$%.2f")})

with tab_caj:
    if cajeros.empty:
        st.info("No hay ventas en este periodo.")
    else:
        st.dataframe(cajeros, hide_index=True, use_container_width=True,
                     column_config={"total": st.column_config.NumberColumn("Total", format="$%.2f")})

with tab_ven:
    if ventas.empty:
        st.info("No hay ventas en este periodo.")
    else:
        st.dataframe(ventas[["folio", "fecha_hora", "cajero", "pago", "total", "estado", "motivo_cancelacion"]]
                     .sort_values("folio", ascending=False),
                     hide_index=True, use_container_width=True,
                     column_config={"fecha_hora": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                                    "total": st.column_config.NumberColumn("Total", format="$%.2f"),
                                    "motivo_cancelacion": "Motivo"})
        if u["rol"] in ("admin", "supervisor"):
            st.subheader(":material/cancel: Cancelar una venta")
            st.caption("Solo se pueden cancelar ventas de una caja que sigue abierta. "
                       "El inventario se regresa automaticamente.")
            cancelables = ventas[(ventas["estado"] == "completada") & ventas["turno_abierto"]]
            if cancelables.empty:
                st.caption("No hay ventas cancelables en este periodo.")
            else:
                mapa = {f"#{r['folio']}  {r['fecha_hora']:%d/%m %H:%M}  {mxn(r['total'])}  ({r['cajero']})": r
                        for _, r in cancelables.sort_values("folio", ascending=False).iterrows()}
                elegida = st.selectbox("Venta", list(mapa))
                motivo = st.text_input("Motivo de la cancelacion")
                if st.button("Cancelar venta", icon=":material/delete:", type="primary"):
                    if not motivo.strip():
                        st.error("Escribe el motivo.")
                    else:
                        try:
                            reportes.cancelar(mapa[elegida]["id"], u["id"], motivo.strip())
                            st.toast("Venta cancelada y stock devuelto", icon=":material/check_circle:")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo cancelar: {e}")
