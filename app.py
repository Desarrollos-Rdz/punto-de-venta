"""Punto de venta - Quesos, pollo y abarrotes.
Punto de entrada: login + navegacion filtrada por rol."""
from pathlib import Path
import streamlit as st
from modules import auth
from utils.ui import aplicar_estilo

st.set_page_config(page_title="Punto de venta", page_icon=":material/storefront:", layout="wide")
aplicar_estilo()

# clave -> (archivo, titulo, icono)
PAGINAS = {
    "inicio":        ("pages/inicio.py",        "Inicio",         ":material/home:"),
    "pos":           ("pages/pos.py",           "Vender",         ":material/point_of_sale:"),
    "inventario":    ("pages/inventario.py",    "Inventario",     ":material/inventory_2:"),
    "caja":          ("pages/caja.py",          "Caja",           ":material/payments:"),
    "reportes":      ("pages/reportes.py",      "Reportes",       ":material/bar_chart:"),
    "usuarios":      ("pages/usuarios.py",      "Usuarios",       ":material/group:"),
    "configuracion": ("pages/configuracion.py", "Configuracion",  ":material/settings:"),
}


def pantalla_login() -> None:
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown("# :material/storefront: Punto de venta")
        st.caption("Inicia sesion para continuar")
        with st.form("login"):
            usuario = st.text_input("Usuario", icon=":material/person:")
            password = st.text_input("Contrasena", type="password", icon=":material/key:")
            enviar = st.form_submit_button("Entrar", type="primary", use_container_width=True,
                                           icon=":material/login:")
        if enviar:
            if auth.iniciar_sesion(usuario, password):
                st.rerun()
            elif st.session_state.get("intentos_login", 0) < 5:
                st.error("Usuario o contrasena incorrectos.", icon=":material/error:")


usuario = auth.usuario_actual()
if not usuario:
    pantalla_login()
    st.stop()

permitidas = auth.PERMISOS.get(usuario["rol"], [])
paginas = [
    st.Page(archivo, title=titulo, icon=icono, url_path=clave, default=(clave == "inicio"))
    for clave, (archivo, titulo, icono) in PAGINAS.items()
    if clave in permitidas and Path(archivo).exists()
]

with st.sidebar:
    st.markdown(f"**:material/account_circle: {usuario['nombre']}**")
    st.caption(auth.ROLES_ETIQUETA[usuario["rol"]])
    if st.button("Cerrar sesion", icon=":material/logout:", use_container_width=True):
        auth.cerrar_sesion()
        st.rerun()

st.navigation(paginas).run()
