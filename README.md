# Punto de venta: quesos, pollo y abarrotes

Aplicacion web de punto de venta hecha con **Streamlit + Supabase**, pensada para correr con planes gratuitos.

## Estado del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Esquema de base de datos, login con roles, inventario (costo, precio, margen automatico, peso/pieza, codigo de barras opcional), PDF y CSV de inventario | Listo |
| 2 | Pantalla de venta (carrito, peso o monto, codigo de barras, efectivo/tarjeta/mixto, cambio) | Listo |
| 3 | Apertura y corte de caja, retiros e ingresos, PDF del corte | Listo |
| 4 | Ticket en PDF (80 mm) y envio por WhatsApp con enlace wa.me | Listo |
| 4b | Envio de tickets por correo con Resend | En espera: requiere dominio propio verificado |
| 5 | Usuarios y permisos desde la app, reportes, configuracion de tienda | Pendiente |
| 6 | Lector de codigo de barras en la pantalla de venta | Pendiente |

## Roles

| Rol | Acceso |
|---|---|
| Administrador | Todo |
| Supervisor | Consulta de inventario, caja y reportes |
| Cajero | Vender y caja |
| Almacenista | Inventario |

## Puesta en marcha

1. Crea un proyecto gratuito en [supabase.com](https://supabase.com).
2. En el editor SQL ejecuta `supabase/migrations/001_esquema_inicial.sql`.
3. Copia `.streamlit/secrets.example.toml` a `.streamlit/secrets.toml` y completa la URL y la llave de servicio (Project Settings > API).
4. Instala y crea el administrador:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/crear_admin.py admin "Tu Nombre"
streamlit run app.py
```

5. Para publicar: Streamlit Community Cloud, apuntando a `app.py` y pegando el contenido de `secrets.toml` en Settings > Secrets.

## Seguridad

- Las contrasenas se guardan con bcrypt.
- Las tablas tienen RLS activo sin politicas publicas; solo el servidor de Streamlit accede con la llave de servicio.
- Nunca subas `.streamlit/secrets.toml` a GitHub (ya esta en `.gitignore`).

## Iconos

La interfaz usa iconos Material de Streamlit (`:material/nombre:`), sin emojis.
