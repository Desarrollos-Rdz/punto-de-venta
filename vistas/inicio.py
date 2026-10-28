import streamlit as st
from modules import auth, productos
from utils.ui import titulo, mxn

auth.requerir("inicio")
u = auth.usuario_actual()
titulo("home", f"Hola, {u['nombre'].split()[0]}", "Resumen rapido de tu tienda")

df = productos.listar_productos()
if df.empty:
    st.info("Aun no hay productos. Agrega el primero desde Inventario.", icon=":material/inventory_2:")
    st.stop()

bajo = df[df["stock"] <= df["stock_minimo"]]
valor_costo = float((df["stock"] * df["costo"]).sum())
valor_venta = float((df["stock"] * df["precio_venta"]).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Productos activos", len(df))
c2.metric("Stock bajo", len(bajo))
c3.metric("Inventario a costo", mxn(valor_costo))
c4.metric("Inventario a precio de venta", mxn(valor_venta))

if len(bajo):
    st.subheader(":material/warning: Por reabastecer")
    st.dataframe(bajo[["nombre", "categoria", "stock", "stock_minimo", "unidad"]],
                 hide_index=True, use_container_width=True)
