import streamlit as st
from modules import auth, caja, productos, ventas
from utils.ui import titulo, mxn

auth.requerir("pos")
u = auth.usuario_actual()
titulo("point_of_sale", "Vender")

turno = caja.turno_abierto(u["id"])
if not turno:
    st.warning("Para vender primero debes abrir tu caja.", icon=":material/lock_open:")
    st.page_link("pages/caja.py", label="Ir a Caja", icon=":material/payments:")
    st.stop()

df = productos.listar_productos()
if df.empty:
    st.info("No hay productos en el inventario.", icon=":material/inventory_2:")
    st.stop()

carrito: list[dict] = st.session_state.setdefault("carrito", [])
etiquetas = {f"{r['nombre']}  -  {mxn(r['precio_venta'])}/{r['unidad']}": r for _, r in df.iterrows()}


def agregar(prod, cantidad: float, precio: float | None = None) -> None:
    precio = float(prod["precio_venta"]) if precio is None else precio
    en_carrito = sum(i["cantidad"] for i in carrito if i["producto_id"] == prod["id"])
    if en_carrito + cantidad > float(prod["stock"]) + 1e-9:
        st.toast(f"Stock insuficiente de {prod['nombre']} (hay {float(prod['stock']):g} {prod['unidad']})",
                 icon=":material/warning:")
        return
    for i in carrito:
        if i["producto_id"] == prod["id"] and i["precio_unitario"] == precio:
            i["cantidad"] = round(i["cantidad"] + cantidad, 3)
            return
    carrito.append({"producto_id": prod["id"], "nombre": prod["nombre"], "unidad": prod["unidad"],
                    "cantidad": round(cantidad, 3), "precio_unitario": precio})


def al_escanear() -> None:
    codigo = st.session_state.get("pos_codigo", "").strip()
    st.session_state["pos_codigo"] = ""
    if not codigo:
        return
    p = ventas.buscar_por_codigo(codigo)
    if not p:
        st.toast(f"Codigo {codigo} no encontrado", icon=":material/error:")
    elif p["tipo_venta"] == "pieza":
        agregar(p, 1)
    else:   # por peso: se deja seleccionado para capturar el peso
        for etiqueta, r in etiquetas.items():
            if r["id"] == p["id"]:
                st.session_state["pos_sel"] = etiqueta


izq, der = st.columns([1.15, 1], gap="large")

# ------------------------------------------------------------ Agregar producto
with izq:
    st.text_input("Codigo de barras", key="pos_codigo", on_change=al_escanear,
                  icon=":material/barcode_scanner:", placeholder="Escanea o escribe el codigo y presiona Enter")
    cat = st.pills("Categoria", ["Todas"] + sorted(df["categoria"].unique()), default="Todas",
                   label_visibility="collapsed") or "Todas"
    opciones = [e for e, r in etiquetas.items() if cat == "Todas" or r["categoria"] == cat]
    sel = st.selectbox("Producto", opciones, key="pos_sel", index=None,
                       placeholder="Busca por nombre...")

    if sel:
        p = etiquetas[sel]
        st.caption(f"Disponible: {float(p['stock']):g} {p['unidad']}")
        if p["tipo_venta"] == "peso":
            modo = st.radio("Capturar por", ["Peso (kg)", "Monto ($)"], horizontal=True)
            if modo == "Peso (kg)":
                cant = st.number_input("Kilos", min_value=0.0, step=0.05, format="%.3f", key="pos_kg")
            else:
                monto = st.number_input("Cuanto quiere el cliente ($)", min_value=0.0, step=5.0, key="pos_monto")
                cant = round(monto / float(p["precio_venta"]), 3) if p["precio_venta"] else 0.0
                st.caption(f"Equivale a {cant:.3f} kg")
            label_btn = "Agregar"
        else:
            cant = st.number_input("Piezas", min_value=1.0, step=1.0, value=1.0, key="pos_pzas")
            label_btn = "Agregar"
        if st.button(label_btn, type="primary", icon=":material/add_shopping_cart:",
                     disabled=cant <= 0, use_container_width=True):
            agregar(p, float(cant))
            st.rerun()

# ------------------------------------------------------------------- Carrito
with der:
    st.subheader(":material/shopping_cart: Carrito")
    if not carrito:
        st.caption("Aun no hay productos.")
    for idx, it in enumerate(carrito):
        c1, c2, c3 = st.columns([3, 1.6, 0.7], vertical_alignment="center")
        c1.markdown(f"**{it['nombre']}**  \n{it['cantidad']:g} {it['unidad']} x {mxn(it['precio_unitario'])}")
        c2.markdown(f"**{mxn(ventas.importe(it['cantidad'], it['precio_unitario']))}**")
        if c3.button("", icon=":material/delete:", key=f"del_{idx}", help="Quitar"):
            carrito.pop(idx)
            st.rerun()

    subtotal = round(sum(ventas.importe(i["cantidad"], i["precio_unitario"]) for i in carrito), 2)
    descuento = 0.0
    if carrito:
        descuento = st.number_input("Descuento ($)", min_value=0.0, max_value=float(subtotal), step=1.0)
    total = round(subtotal - descuento, 2)
    st.metric("Total a cobrar", mxn(total))

    if carrito:
        metodo = st.radio("Forma de pago", ["efectivo", "tarjeta", "mixto"], horizontal=True,
                          format_func=str.capitalize)
        pagos, valido = [], True
        if metodo == "efectivo":
            recibido = st.number_input("Efectivo recibido ($)", min_value=0.0, step=10.0, value=float(total))
            cambio = round(recibido - total, 2)
            st.info(f"Cambio: **{mxn(max(cambio, 0))}**", icon=":material/paid:")
            valido = recibido >= total
            pagos = [{"metodo": "efectivo", "monto": total, "recibido": recibido}]
        elif metodo == "tarjeta":
            pagos = [{"metodo": "tarjeta", "monto": total}]
        else:
            ef = st.number_input("Parte en efectivo ($)", min_value=0.0, max_value=float(total), step=10.0)
            recibido = st.number_input("Efectivo recibido ($)", min_value=0.0, step=10.0, value=float(ef))
            tj = round(total - ef, 2)
            st.info(f"Tarjeta: **{mxn(tj)}**  |  Cambio: **{mxn(max(recibido - ef, 0))}**", icon=":material/paid:")
            valido = 0 < ef < total and recibido >= ef
            pagos = [{"metodo": "efectivo", "monto": ef, "recibido": recibido},
                     {"metodo": "tarjeta", "monto": tj}]

        with st.expander(":material/mail: Enviar ticket al cliente (opcional)"):
            email = st.text_input("Correo electronico")
            tel = st.text_input("Telefono / WhatsApp (con lada)")

        if st.button("Cobrar", type="primary", icon=":material/check_circle:",
                     disabled=not valido or total <= 0, use_container_width=True):
            try:
                r = ventas.registrar_venta(turno["id"], u["id"], carrito, pagos, descuento, email, tel)
                st.session_state["ultima_venta"] = {"folio": r["folio"], "total": float(r["total"])}
                st.session_state["carrito"] = []
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo registrar la venta: {e}", icon=":material/error:")
        if st.button("Vaciar carrito", icon=":material/remove_shopping_cart:", use_container_width=True):
            st.session_state["carrito"] = []
            st.rerun()

if ult := st.session_state.pop("ultima_venta", None):
    st.toast(f"Venta #{ult['folio']} registrada por {mxn(ult['total'])}", icon=":material/check_circle:")
