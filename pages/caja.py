import streamlit as st
from modules import auth, caja
from utils.pdf import corte_pdf
from utils.ui import titulo, mxn

auth.requerir("caja")
u = auth.usuario_actual()
titulo("payments", "Caja", "Apertura, movimientos de efectivo y corte")

if "corte_listo" in st.session_state:
    res, cajero, contado_f = st.session_state.pop("corte_listo")
    st.success("Caja cerrada.", icon=":material/check_circle:")
    st.download_button("Descargar corte en PDF", corte_pdf(res, cajero, contado_f),
                       "corte_de_caja.pdf", "application/pdf", icon=":material/picture_as_pdf:", on_click="ignore")

turno = caja.turno_abierto(u["id"])

# --------------------------------------------------------------- Abrir caja
if not turno:
    st.info("No tienes una caja abierta.", icon=":material/lock:")
    if u["rol"] in ("admin", "cajero"):
        with st.form("abrir"):
            fondo = st.number_input("Fondo inicial en efectivo ($)", min_value=0.0, step=50.0)
            if st.form_submit_button("Abrir caja", type="primary", icon=":material/lock_open:"):
                caja.abrir_turno(u["id"], fondo)
                st.rerun()
    hist = caja.historial_turnos()
    if not hist.empty:
        st.subheader(":material/history: Cortes anteriores")
        st.dataframe(hist[["abierto_en", "cerrado_en", "cajero", "estado", "fondo_inicial", "efectivo_contado"]],
                     hide_index=True, use_container_width=True)
    st.stop()

# ------------------------------------------------------------ Turno abierto
r = caja.resumen_turno(turno["id"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de ventas", mxn(r["total_ventas"]), f"{r['num_ventas']} ventas")
c2.metric("Efectivo", mxn(r["ventas_efectivo"]))
c3.metric("Tarjeta", mxn(r["ventas_tarjeta"]))
c4.metric("Efectivo esperado en caja", mxn(r["efectivo_esperado"]))

tab_mov, tab_ventas, tab_corte = st.tabs([
    ":material/swap_vert: Ingresos y retiros",
    ":material/receipt_long: Ventas del turno",
    ":material/fact_check: Corte de caja",
])

with tab_mov:
    with st.form("mov_caja", clear_on_submit=True):
        a, b, c = st.columns([1, 1, 2])
        tipo = a.radio("Tipo", ["retiro", "ingreso"], horizontal=True, format_func=str.capitalize)
        monto = b.number_input("Monto ($)", min_value=0.0, step=10.0)
        concepto = c.text_input("Concepto", placeholder="Pago a proveedor, cambio, etc.")
        if st.form_submit_button("Registrar", icon=":material/check:"):
            if monto <= 0 or not concepto.strip():
                st.error("Captura un monto y un concepto.")
            elif tipo == "retiro" and monto > r["efectivo_esperado"]:
                st.error("El retiro es mayor al efectivo disponible en caja.")
            else:
                caja.registrar_movimiento_caja(turno["id"], u["id"], tipo, monto, concepto.strip())
                st.rerun()
    mov = caja.movimientos_del_turno(turno["id"])
    if not mov.empty:
        st.dataframe(mov, hide_index=True, use_container_width=True)

with tab_ventas:
    vs = caja.ventas_del_turno(turno["id"])
    if vs.empty:
        st.caption("Todavia no hay ventas en este turno.")
    else:
        st.dataframe(vs, hide_index=True, use_container_width=True,
                     column_config={"total": st.column_config.NumberColumn("Total", format="$%.2f")})

with tab_corte:
    st.write(f"Fondo inicial: **{mxn(r['fondo_inicial'])}**  |  Ingresos: **{mxn(r['ingresos_extra'])}**  |  "
             f"Retiros: **{mxn(r['retiros'])}**")
    st.write(f"Utilidad estimada del turno: **{mxn(r['utilidad'])}**")
    contado = st.number_input("Efectivo contado en caja ($)", min_value=0.0, step=10.0)
    dif = round(contado - r["efectivo_esperado"], 2)
    if contado:
        if abs(dif) < 0.005:
            st.success("La caja cuadra.", icon=":material/check_circle:")
        elif dif > 0:
            st.warning(f"Sobrante de {mxn(dif)}", icon=":material/arrow_upward:")
        else:
            st.error(f"Faltante de {mxn(-dif)}", icon=":material/arrow_downward:")
    notas = st.text_area("Notas del corte (opcional)")
    if st.button("Cerrar caja y generar corte", type="primary", icon=":material/lock:"):
        caja.cerrar_turno(turno["id"], contado, notas)
        st.session_state["corte_listo"] = (r, u["nombre"], contado)
        st.rerun()
