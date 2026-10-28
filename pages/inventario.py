import streamlit as st
from modules import auth, productos
from utils.pdf import inventario_pdf
from utils.ui import titulo, mxn

auth.requerir("inventario")
u = auth.usuario_actual()
puede_editar = auth.puede_editar(("admin", "almacenista"))

titulo("inventory_2", "Inventario", "Productos, existencias, costos y margen de utilidad")

categorias = productos.listar_categorias()
nombres_cat = {c["nombre"]: c["id"] for c in categorias}

tab_cat, tab_nuevo, tab_mov, tab_hist = st.tabs([
    ":material/list_alt: Catalogo",
    ":material/add_box: Producto",
    ":material/move_to_inbox: Entradas y ajustes",
    ":material/history: Movimientos",
])

# ------------------------------------------------------------------ Catalogo
with tab_cat:
    df = productos.listar_productos()
    if df.empty:
        st.info("Todavia no hay productos registrados.", icon=":material/info:")
    else:
        f1, f2, f3 = st.columns([2, 1.2, 1])
        buscar = f1.text_input("Buscar por nombre o codigo de barras", icon=":material/search:")
        cat = f2.selectbox("Categoria", ["Todas"] + list(nombres_cat))
        solo_bajo = f3.toggle("Solo stock bajo")

        vista = df
        if buscar:
            b = buscar.strip().lower()
            vista = vista[vista["nombre"].str.lower().str.contains(b, na=False)
                          | vista["codigo_barras"].fillna("").str.contains(b, na=False)]
        if cat != "Todas":
            vista = vista[vista["categoria"] == cat]
        if solo_bajo:
            vista = vista[vista["stock"] <= vista["stock_minimo"]]

        st.dataframe(
            vista[["nombre", "categoria", "unidad", "costo", "precio_venta",
                   "utilidad_unit", "margen_pct", "stock", "stock_minimo", "codigo_barras"]],
            hide_index=True, use_container_width=True,
            column_config={
                "nombre": "Producto", "categoria": "Categoria", "unidad": "Unidad",
                "costo": st.column_config.NumberColumn("Costo", format="$%.2f"),
                "precio_venta": st.column_config.NumberColumn("Precio venta", format="$%.2f"),
                "utilidad_unit": st.column_config.NumberColumn("Utilidad", format="$%.2f"),
                "margen_pct": st.column_config.NumberColumn("Margen", format="%.1f%%"),
                "stock": st.column_config.NumberColumn("Stock", format="%.3f"),
                "stock_minimo": st.column_config.NumberColumn("Minimo", format="%.3f"),
                "codigo_barras": "Codigo de barras",
            },
        )
        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button("Descargar PDF", inventario_pdf(vista), "inventario.pdf",
                           "application/pdf", icon=":material/picture_as_pdf:")
        d2.download_button("Descargar CSV", vista.to_csv(index=False).encode("utf-8-sig"),
                           "inventario.csv", "text/csv", icon=":material/table_view:")

# ------------------------------------------------------- Crear / editar producto
with tab_nuevo:
    if not puede_editar:
        st.info("Tu rol solo permite consultar el inventario.", icon=":material/lock:")
    else:
        df_all = productos.listar_productos()
        opciones = {"Nuevo producto": None}
        if not df_all.empty:
            opciones |= {r["nombre"]: r["id"] for _, r in df_all.iterrows()}
        elegido = st.selectbox("Producto a editar", list(opciones), key="sel_prod")
        pid = opciones[elegido]
        actual = df_all[df_all["id"] == pid].iloc[0].to_dict() if pid else {}

        sufijo = pid or "nuevo"   # reinicia los campos al cambiar de producto
        a, b = st.columns(2)
        nombre = a.text_input("Nombre", actual.get("nombre", ""), key=f"n_{sufijo}")
        cat_nombre = b.selectbox(
            "Categoria", list(nombres_cat), key=f"c_{sufijo}",
            index=list(nombres_cat).index(actual["categoria"]) if actual.get("categoria") in nombres_cat else 0)

        a, b, c = st.columns(3)
        tipo = a.radio("Se vende por", ["peso", "pieza"], horizontal=True, key=f"t_{sufijo}",
                       index=0 if actual.get("tipo_venta") == "peso" else 1,
                       format_func=lambda x: "Peso (kg)" if x == "peso" else "Pieza")
        unidad = "kg" if tipo == "peso" else "pza"
        costo = b.number_input(f"Costo de compra por {unidad}", min_value=0.0, step=1.0,
                               value=float(actual.get("costo", 0.0)), key=f"co_{sufijo}")
        precio = c.number_input(f"Precio de venta por {unidad}", min_value=0.0, step=1.0,
                                value=float(actual.get("precio_venta", 0.0)), key=f"p_{sufijo}")

        utilidad, margen = productos.calcular_margen(costo, precio)
        m1, m2, m3 = st.columns(3)
        m1.metric("Utilidad por " + unidad, mxn(utilidad))
        m2.metric("Margen sobre precio", f"{margen:.1f}%")
        m3.metric("Ganancia sobre costo", f"{(utilidad / costo * 100) if costo else 0:.1f}%")
        if precio and precio < costo:
            st.warning("El precio de venta es menor al costo: venderias con perdida.", icon=":material/warning:")

        with st.expander(":material/calculate: Calcular precio a partir de un margen deseado"):
            deseado = st.slider("Margen deseado (%)", 5, 80, 25, key=f"m_{sufijo}")
            st.write(f"Precio sugerido: **{mxn(productos.precio_sugerido(costo, deseado))}** por {unidad}")

        a, b, c = st.columns(3)
        stock_min = a.number_input("Stock minimo (alerta)", min_value=0.0, step=1.0,
                                   value=float(actual.get("stock_minimo", 0.0)), key=f"sm_{sufijo}")
        stock_ini = b.number_input("Existencia inicial", min_value=0.0, step=1.0,
                                   value=float(actual.get("stock", 0.0)), key=f"si_{sufijo}",
                                   disabled=bool(pid), help="Para productos existentes usa la pestana Entradas y ajustes.")
        codigo = c.text_input("Codigo de barras (opcional)", actual.get("codigo_barras") or "",
                              key=f"cb_{sufijo}", icon=":material/barcode_scanner:",
                              help="Con un lector USB basta con hacer clic aqui y escanear.")

        g1, g2, _ = st.columns([1, 1, 3])
        if g1.button("Guardar", type="primary", icon=":material/save:", key=f"g_{sufijo}"):
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                datos = {"nombre": nombre.strip(), "categoria_id": nombres_cat[cat_nombre],
                         "tipo_venta": tipo, "unidad": unidad, "costo": costo,
                         "precio_venta": precio, "stock_minimo": stock_min,
                         "codigo_barras": codigo.strip()}
                if not pid:
                    datos["stock"] = stock_ini
                try:
                    productos.guardar_producto(datos, pid)
                    st.toast("Producto guardado", icon=":material/check_circle:")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar: {e}")
        if pid and g2.button("Desactivar", icon=":material/delete:", key=f"d_{sufijo}"):
            productos.desactivar_producto(pid)
            st.toast("Producto desactivado", icon=":material/check_circle:")
            st.rerun()

# ------------------------------------------------------ Entradas y ajustes
with tab_mov:
    if not puede_editar:
        st.info("Tu rol solo permite consultar el inventario.", icon=":material/lock:")
    else:
        df_all = productos.listar_productos()
        if df_all.empty:
            st.info("Primero crea un producto.")
        else:
            mapa = {f"{r['nombre']} (stock: {r['stock']:g} {r['unidad']})": r for _, r in df_all.iterrows()}
            sel = st.selectbox("Producto", list(mapa), key="mov_prod")
            p = mapa[sel]
            tipo_mov = st.radio("Tipo de movimiento", ["entrada", "merma", "ajuste"], horizontal=True,
                                format_func={"entrada": "Entrada de mercancia", "merma": "Merma",
                                             "ajuste": "Ajuste (corregir existencia)"}.get)
            a, b = st.columns(2)
            cantidad = a.number_input(f"Cantidad ({p['unidad']})", min_value=0.0, step=1.0, key="mov_cant")
            costo_nuevo = None
            if tipo_mov == "entrada":
                costo_nuevo = b.number_input(f"Costo de compra por {p['unidad']}", min_value=0.0,
                                             value=float(p["costo"]), step=1.0, key="mov_costo",
                                             help="Se actualiza el costo del producto con este valor.")
            nota = st.text_input("Nota (proveedor, motivo, etc.)", key="mov_nota")
            if st.button("Registrar movimiento", type="primary", icon=":material/check:"):
                if cantidad <= 0 and tipo_mov != "ajuste":
                    st.error("Indica una cantidad mayor a cero.")
                else:
                    if tipo_mov == "ajuste":
                        delta = cantidad - float(p["stock"])    # cantidad = existencia real contada
                    else:
                        delta = cantidad if tipo_mov == "entrada" else -cantidad
                    try:
                        productos.registrar_movimiento(p["id"], tipo_mov if tipo_mov != "merma" else "merma",
                                                       delta, u["id"], costo_nuevo, nota or None)
                        st.toast("Movimiento registrado", icon=":material/check_circle:")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            if tipo_mov == "ajuste":
                st.caption("En un ajuste captura la existencia real contada; el sistema calcula la diferencia.")

# -------------------------------------------------------------- Movimientos
with tab_hist:
    hist = productos.listar_movimientos()
    if hist.empty:
        st.info("Aun no hay movimientos.")
    else:
        st.dataframe(hist[["creado_en", "producto", "tipo", "cantidad", "costo_unitario", "referencia", "usuario"]],
                     hide_index=True, use_container_width=True)
