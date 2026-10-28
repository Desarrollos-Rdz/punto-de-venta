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
| 5 | Usuarios y roles desde la app, cambio de contrasena, datos de la tienda y zona horaria, reportes (por dia, producto y cajero) en PDF y Excel, cancelacion de ventas | Listo |
| 6 | Lector de codigo de barras (USB) en Vender: cursor automatico, agrega al escanear, pesos por kilos; codigos internos para productos sin codigo | Listo |

## Roles

| Rol | Acceso |
|---|---|
| Administrador | Todo |
| Supervisor | Consulta de inventario, caja y reportes; cancela ventas de una caja abierta |
| Cajero | Vender y caja |
| Almacenista | Inventario |

## Puesta en marcha

1. Crea un proyecto gratuito en [supabase.com](https://supabase.com).
2. En el editor SQL ejecuta en orden los archivos de `supabase/migrations/` (001 y 002).
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

## Lector de codigo de barras

Cualquier lector USB funciona como teclado: en **Vender** el cursor ya queda en la casilla de codigo, asi que solo escanea.
Productos por pieza se agregan solos (escanear de nuevo suma una pieza); productos por peso se seleccionan y el cursor
pasa a los kilos. En **Inventario** puedes escanear el codigo al crear el producto o generar uno interno (900001...).
