import streamlit as st
from zoneinfo import ZoneInfo
from modules import auth, tienda, usuarios
from utils.tiempo import zona_tienda
from utils.ui import titulo

auth.requerir("configuracion")
yo = auth.usuario_actual()
titulo("settings", "Configuracion")

ZONAS = ["America/Mexico_City", "America/Matamoros", "America/Monterrey", "America/Cancun",
         "America/Chihuahua", "America/Hermosillo", "America/Tijuana"]

if yo["rol"] == "admin":
    st.subheader(":material/storefront: Datos de la tienda")
    t = tienda.obtener()
    with st.form("tienda"):
        a, b = st.columns(2)
        nombre = a.text_input("Nombre de la tienda", t["nombre"])
        telefono = b.text_input("Telefono", t.get("telefono") or "")
        direccion = st.text_input("Direccion", t.get("direccion") or "")
        a, b = st.columns(2)
        rfc = a.text_input("RFC (opcional)", t.get("rfc") or "")
        zona_actual = t.get("zona_horaria") or "America/Mexico_City"
        zona = b.selectbox("Zona horaria", ZONAS if zona_actual in ZONAS else [zona_actual] + ZONAS,
                           index=(ZONAS.index(zona_actual) if zona_actual in ZONAS else 0))
        leyenda = st.text_input("Leyenda al pie del ticket", t.get("leyenda_ticket") or "")
        if st.form_submit_button("Guardar", type="primary", icon=":material/save:"):
            ZoneInfo(zona)
            tienda.guardar({"nombre": nombre.strip() or "Mi Tienda", "telefono": telefono.strip() or None,
                            "direccion": direccion.strip() or None, "rfc": rfc.strip() or None,
                            "zona_horaria": zona, "leyenda_ticket": leyenda.strip() or None})
            zona_tienda.clear()
            st.toast("Datos guardados", icon=":material/check_circle:")

st.subheader(":material/key: Cambiar mi contrasena")
with st.form("mi_password", clear_on_submit=True):
    actual = st.text_input("Contrasena actual", type="password")
    nueva = st.text_input("Nueva contrasena", type="password")
    repetir = st.text_input("Repite la nueva contrasena", type="password")
    if st.form_submit_button("Cambiar contrasena", type="primary", icon=":material/lock_reset:"):
        if nueva != repetir:
            st.error("Las contrasenas nuevas no coinciden.")
        else:
            try:
                usuarios.cambiar_mi_password(yo["id"], actual, nueva)
                st.toast("Contrasena actualizada", icon=":material/check_circle:")
            except ValueError as e:
                st.error(str(e))
