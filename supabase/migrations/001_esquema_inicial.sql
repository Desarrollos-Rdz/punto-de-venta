-- =====================================================================
-- Punto de venta: quesos, pollo y abarrotes
-- Migracion 001: esquema inicial
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------- Tipos ----------
create type rol_usuario      as enum ('admin', 'supervisor', 'cajero', 'almacenista');
create type tipo_venta       as enum ('peso', 'pieza');
create type metodo_pago      as enum ('efectivo', 'tarjeta');
create type estado_venta     as enum ('completada', 'cancelada');
create type tipo_mov_inv     as enum ('entrada', 'salida_venta', 'ajuste', 'merma', 'cancelacion');
create type tipo_mov_caja    as enum ('ingreso', 'retiro');
create type estado_turno     as enum ('abierto', 'cerrado');

-- ---------- Usuarios (autenticacion propia, hash bcrypt) ----------
create table usuarios (
  id            uuid primary key default gen_random_uuid(),
  usuario       text not null unique,
  nombre        text not null,
  email         text,
  password_hash text not null,
  rol           rol_usuario not null default 'cajero',
  activo        boolean not null default true,
  creado_en     timestamptz not null default now()
);

-- ---------- Configuracion de la tienda (una sola fila) ----------
create table config_tienda (
  id              int primary key default 1 check (id = 1),
  nombre          text not null default 'Mi Tienda',
  direccion       text,
  telefono        text,
  rfc             text,
  leyenda_ticket  text default 'Gracias por su compra',
  moneda          text not null default 'MXN'
);
insert into config_tienda (id) values (1);

-- ---------- Categorias ----------
create table categorias (
  id      serial primary key,
  nombre  text not null unique,
  icono   text default 'category',   -- nombre de icono Material
  activa  boolean not null default true
);
insert into categorias (nombre, icono) values
  ('Quesos',    'lunch_dining'),
  ('Pollo',     'set_meal'),
  ('Abarrotes', 'shopping_basket');

-- ---------- Productos ----------
create table productos (
  id             uuid primary key default gen_random_uuid(),
  codigo_barras  text unique,                        -- opcional, listo para lector
  nombre         text not null,
  categoria_id   int references categorias(id),
  tipo_venta     tipo_venta not null default 'pieza',
  unidad         text not null default 'pza',        -- 'kg' o 'pza'
  costo          numeric(12,2) not null default 0 check (costo >= 0),
  precio_venta   numeric(12,2) not null default 0 check (precio_venta >= 0),
  utilidad_unit  numeric(12,2) generated always as (precio_venta - costo) stored,
  margen_pct     numeric(8,2)  generated always as (
                   case when precio_venta > 0
                        then round((precio_venta - costo) / precio_venta * 100, 2)
                        else 0 end) stored,
  stock          numeric(12,3) not null default 0,
  stock_minimo   numeric(12,3) not null default 0,
  activo         boolean not null default true,
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);
create index on productos (nombre);
create index on productos (categoria_id);

-- ---------- Movimientos de inventario (auditoria) ----------
create table movimientos_inventario (
  id             bigserial primary key,
  producto_id    uuid not null references productos(id),
  tipo           tipo_mov_inv not null,
  cantidad       numeric(12,3) not null,            -- positivo suma, negativo resta
  costo_unitario numeric(12,2),
  usuario_id     uuid references usuarios(id),
  referencia     text,                               -- folio de venta, nota, etc.
  creado_en      timestamptz not null default now()
);
create index on movimientos_inventario (producto_id, creado_en desc);

-- ---------- Turnos / caja ----------
create table turnos_caja (
  id                 uuid primary key default gen_random_uuid(),
  usuario_id         uuid not null references usuarios(id),
  estado             estado_turno not null default 'abierto',
  fondo_inicial      numeric(12,2) not null default 0,
  abierto_en         timestamptz not null default now(),
  cerrado_en         timestamptz,
  efectivo_contado   numeric(12,2),
  notas_cierre       text
);
create unique index un_turno_abierto_por_usuario
  on turnos_caja (usuario_id) where estado = 'abierto';

create table movimientos_caja (
  id         bigserial primary key,
  turno_id   uuid not null references turnos_caja(id),
  tipo       tipo_mov_caja not null,
  monto      numeric(12,2) not null check (monto > 0),
  concepto   text not null,
  usuario_id uuid references usuarios(id),
  creado_en  timestamptz not null default now()
);

-- ---------- Ventas ----------
create table ventas (
  id                 uuid primary key default gen_random_uuid(),
  folio              bigserial unique,
  turno_id           uuid not null references turnos_caja(id),
  usuario_id         uuid not null references usuarios(id),
  subtotal           numeric(12,2) not null,
  descuento          numeric(12,2) not null default 0,
  total              numeric(12,2) not null,
  estado             estado_venta not null default 'completada',
  cliente_email      text,
  cliente_telefono   text,
  creado_en          timestamptz not null default now(),
  cancelada_en       timestamptz,
  cancelada_por      uuid references usuarios(id),
  motivo_cancelacion text
);
create index on ventas (creado_en desc);
create index on ventas (turno_id);

create table venta_items (
  id              bigserial primary key,
  venta_id        uuid not null references ventas(id) on delete cascade,
  producto_id     uuid not null references productos(id),
  nombre          text not null,                    -- copia al momento de la venta
  cantidad        numeric(12,3) not null check (cantidad > 0),
  precio_unitario numeric(12,2) not null,
  costo_unitario  numeric(12,2) not null,
  importe         numeric(12,2) not null
);
create index on venta_items (venta_id);

-- Un pago por metodo (permite pago mixto efectivo + tarjeta)
create table pagos (
  id                 bigserial primary key,
  venta_id           uuid not null references ventas(id) on delete cascade,
  metodo             metodo_pago not null,
  monto              numeric(12,2) not null check (monto > 0),
  efectivo_recibido  numeric(12,2),
  cambio             numeric(12,2)
);
create index on pagos (venta_id);

-- ---------- Funcion: registrar venta de forma atomica ----------
-- p_items: [{"producto_id": "...", "cantidad": 1.250, "precio_unitario": 120.00}]
-- p_pagos: [{"metodo": "efectivo", "monto": 100, "recibido": 200}, {"metodo": "tarjeta", "monto": 50}]
create or replace function registrar_venta(
  p_turno_id         uuid,
  p_usuario_id       uuid,
  p_items            jsonb,
  p_pagos            jsonb,
  p_descuento        numeric default 0,
  p_cliente_email    text default null,
  p_cliente_telefono text default null
) returns table (venta_id uuid, folio bigint, total numeric)
language plpgsql
as $$
declare
  v_venta_id  uuid;
  v_folio     bigint;
  v_subtotal  numeric(12,2) := 0;
  v_total     numeric(12,2);
  v_pagado    numeric(12,2) := 0;
  v_item      jsonb;
  v_pago      jsonb;
  v_prod      productos%rowtype;
  v_cant      numeric(12,3);
  v_precio    numeric(12,2);
  v_importe   numeric(12,2);
  v_recibido  numeric(12,2);
begin
  if not exists (select 1 from turnos_caja where id = p_turno_id and estado = 'abierto') then
    raise exception 'El turno de caja no esta abierto';
  end if;
  if jsonb_array_length(p_items) = 0 then
    raise exception 'La venta no tiene productos';
  end if;

  insert into ventas (turno_id, usuario_id, subtotal, descuento, total,
                      cliente_email, cliente_telefono)
  values (p_turno_id, p_usuario_id, 0, p_descuento, 0,
          p_cliente_email, p_cliente_telefono)
  returning id, ventas.folio into v_venta_id, v_folio;

  for v_item in select * from jsonb_array_elements(p_items) loop
    select * into v_prod from productos
      where id = (v_item->>'producto_id')::uuid and activo for update;
    if not found then
      raise exception 'Producto no disponible';
    end if;

    v_cant   := (v_item->>'cantidad')::numeric;
    v_precio := coalesce((v_item->>'precio_unitario')::numeric, v_prod.precio_venta);
    v_importe := round(v_cant * v_precio, 2);

    if v_prod.stock < v_cant then
      raise exception 'Stock insuficiente para %', v_prod.nombre;
    end if;

    insert into venta_items (venta_id, producto_id, nombre, cantidad,
                             precio_unitario, costo_unitario, importe)
    values (v_venta_id, v_prod.id, v_prod.nombre, v_cant,
            v_precio, v_prod.costo, v_importe);

    update productos set stock = stock - v_cant, actualizado_en = now()
      where id = v_prod.id;

    insert into movimientos_inventario (producto_id, tipo, cantidad,
                                        costo_unitario, usuario_id, referencia)
    values (v_prod.id, 'salida_venta', -v_cant, v_prod.costo,
            p_usuario_id, 'venta #' || v_folio);

    v_subtotal := v_subtotal + v_importe;
  end loop;

  v_total := v_subtotal - p_descuento;
  if v_total < 0 then
    raise exception 'El descuento excede el subtotal';
  end if;

  for v_pago in select * from jsonb_array_elements(p_pagos) loop
    v_recibido := nullif(v_pago->>'recibido', '')::numeric;
    insert into pagos (venta_id, metodo, monto, efectivo_recibido, cambio)
    values (v_venta_id,
            (v_pago->>'metodo')::metodo_pago,
            (v_pago->>'monto')::numeric,
            v_recibido,
            case when v_recibido is not null
                 then greatest(v_recibido - (v_pago->>'monto')::numeric, 0) end);
    v_pagado := v_pagado + (v_pago->>'monto')::numeric;
  end loop;

  if v_pagado <> v_total then
    raise exception 'Los pagos (%) no coinciden con el total (%)', v_pagado, v_total;
  end if;

  update ventas set subtotal = v_subtotal, total = v_total where id = v_venta_id;

  return query select v_venta_id, v_folio, v_total;
end;
$$;

-- ---------- Funcion: cancelar venta (regresa stock) ----------
create or replace function cancelar_venta(
  p_venta_id uuid, p_usuario_id uuid, p_motivo text
) returns void
language plpgsql
as $$
declare
  v_item venta_items%rowtype;
  v_folio bigint;
begin
  select folio into v_folio from ventas
    where id = p_venta_id and estado = 'completada' for update;
  if not found then
    raise exception 'La venta no existe o ya fue cancelada';
  end if;

  for v_item in select * from venta_items where venta_id = p_venta_id loop
    update productos set stock = stock + v_item.cantidad, actualizado_en = now()
      where id = v_item.producto_id;
    insert into movimientos_inventario (producto_id, tipo, cantidad,
                                        costo_unitario, usuario_id, referencia)
    values (v_item.producto_id, 'cancelacion', v_item.cantidad,
            v_item.costo_unitario, p_usuario_id, 'cancelacion venta #' || v_folio);
  end loop;

  update ventas
     set estado = 'cancelada', cancelada_en = now(),
         cancelada_por = p_usuario_id, motivo_cancelacion = p_motivo
   where id = p_venta_id;
end;
$$;

-- ---------- Vista: resumen de corte por turno ----------
create or replace view v_corte_turno as
select
  t.id as turno_id,
  t.usuario_id,
  t.abierto_en,
  t.cerrado_en,
  t.estado,
  t.fondo_inicial,
  coalesce(sum(p.monto) filter (where p.metodo = 'efectivo' and v.estado = 'completada'), 0) as ventas_efectivo,
  coalesce(sum(p.monto) filter (where p.metodo = 'tarjeta'  and v.estado = 'completada'), 0) as ventas_tarjeta,
  coalesce((select sum(monto) from movimientos_caja m where m.turno_id = t.id and m.tipo = 'ingreso'), 0) as ingresos_extra,
  coalesce((select sum(monto) from movimientos_caja m where m.turno_id = t.id and m.tipo = 'retiro'),  0) as retiros,
  t.efectivo_contado
from turnos_caja t
left join ventas v on v.turno_id = t.id
left join pagos  p on p.venta_id = v.id
group by t.id;

-- ---------- Seguridad ----------
-- La app usa la llave de servicio desde el servidor de Streamlit.
-- Se activa RLS sin politicas publicas: la llave anonima no puede leer nada.
alter table usuarios               enable row level security;
alter table config_tienda          enable row level security;
alter table categorias             enable row level security;
alter table productos              enable row level security;
alter table movimientos_inventario enable row level security;
alter table turnos_caja            enable row level security;
alter table movimientos_caja       enable row level security;
alter table ventas                 enable row level security;
alter table venta_items            enable row level security;
alter table pagos                  enable row level security;

revoke execute on function registrar_venta(uuid, uuid, jsonb, jsonb, numeric, text, text) from public, anon, authenticated;
revoke execute on function cancelar_venta(uuid, uuid, text) from public, anon, authenticated;
alter view v_corte_turno set (security_invoker = true);
