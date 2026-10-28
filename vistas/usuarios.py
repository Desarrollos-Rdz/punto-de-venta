import streamlit as st
from modules import auth, usuarios
from utils.tiempo import serie_local
from utils.ui import titulo

auth.requerir("usuarios")
yo = auth.usuario_actual()
titulo("group", "Usuarios", "Crea cuentas y decide a que puede entrar cada persona")

ROLES = list(auth.ROLES_ETIQUETA)
st.caption("Administrador: todo  |  Supervisor: consulta inventario, caja y reportes y cancela ventas  |  "
           "Cajero: vende y maneja su caja  |  Almacenista: inventario")

tab_lista, tab_nuevo = st.tabs([":material/list: Usuarios", ":material/person_add: Nuevo usuario"])

with tab_nuevo:
    with st.form("nuevo_usuario", clear_on_submit=True):
        a, b = st.columns(2)
        usuario = a.text_input("Usuario (para iniciar sesion)", icon=":material/person:")
        nombre = b.text_input("Nombre completo")
        a, b = st.columns(2)
        email = a.text_input("Correo (opcional)")
        rol = b.selectbox("Rol", ROLES, index=ROLES.index("cajero"), format_func=auth.ROLES_ETIQUETA.get)
        pw = st.text_input("Contrasena temporal", type="password", icon=":material/key:",
                           help="Minimo 8 caracteres, con letras y numeros. La persona puede cambiarla en Configuracion.")
        if st.form_submit_button("Crear usuario", type="primary", icon=":material/check:"):
            if not usuario.strip() or not nombre.strip():
                st.error("Usuario y nombre son obligatorios.")
            else:
                try:
                    usuarios.crear(usuario, nombre, email, rol, pw)
                    st.toast(f"Usuario {usuario.strip().lower()} creado", icon=":material/check_circle:")
                except ValueError as e:
                    st.error(str(e))

with tab_lista:
    df = usuarios.listar()
    vista = df.copy()
    vista["rol"] = vista["rol"].map(auth.ROLES_ETIQUETA)
    vista["creado_en"] = serie_local(vista["creado_en"])
    st.dataframe(vista[["usuario", "nombre", "email", "rol", "activo", "creado_en"]], hide_index=True,
                 use_container_width=True,
                 column_config={"activo": st.column_config.CheckboxColumn("Activo"),
                                "creado_en": st.column_config.DatetimeColumn("Creado", format="DD/MM/YYYY")})

    st.subheader(":material/edit: Editar usuario")
    mapa = {f"{r['nombre']} ({r['usuario']})": r for _, r in df.iterrows()}
    sel = st.selectbox("Usuario", list(mapa))
    u = mapa[sel]
    es_yo = u["id"] == yo["id"]
    with st.form(f"editar_{u['id']}"):
        a, b = st.columns(2)
        nombre = a.text_input("Nombre", u["nombre"])
        email = b.text_input("Correo", u["email"] or "")
        a, b = st.columns(2)
        rol = a.selectbox("Rol", ROLES, index=ROLES.index(u["rol"]), format_func=auth.ROLES_ETIQUETA.get,
                          disabled=es_yo)
        activo = b.toggle("Activo", bool(u["activo"]), disabled=es_yo)
        if es_yo:
            st.caption("No puedes cambiar tu propio rol ni desactivarte.")
        if st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:"):
            try:
                usuarios.actualizar(u["id"], nombre, email, rol, activo)
                st.toast("Cambios guardados", icon=":material/check_circle:")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with st.expander(":material/lock_reset: Restablecer contrasena"):
        nueva = st.text_input("Nueva contrasena", type="password", key=f"rp_{u['id']}")
        if st.button("Restablecer", key=f"brp_{u['id']}", icon=":material/key:"):
            try:
                usuarios.restablecer_password(u["id"], nueva)
                st.toast("Contrasena actualizada", icon=":material/check_circle:")
            except ValueError as e:
                st.error(str(e))
