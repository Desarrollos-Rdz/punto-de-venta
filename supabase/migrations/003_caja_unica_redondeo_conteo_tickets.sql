-- =====================================================================
-- 003: caja unica de la tienda, redondeo en efectivo, conteo fisico
--      semanal y almacenamiento de tickets digitales
-- =====================================================================

-- ---------- Caja unica: solo una caja abierta en toda la tienda ----------
drop index if exists un_turno_abierto_por_usuario;
create unique index un_turno_abierto_tienda on turnos_caja ((true)) where estado = 'abierto';

-- ---------- Redondeo en efectivo ----------
alter table config_tienda
  add column if not exists redondeo_efectivo numeric(4,2) not null default 1
      check (redondeo_efectivo in (0, 0.5, 1)),
  add column if not exists redondeo_modo text not null default 'cercano'
      check (redondeo_modo in ('cercano', 'abajo'));

-- redondeo = total cobrado - (subtotal - descuento). Negativo si se cobra de menos.
alter table ventas add column if not exists redondeo numeric(12,2) not null default 0;

-- nombre (aleatorio) del PDF del ticket digital en Storage; null si no se ha generado
alter table ventas add column if not exists ticket_archivo text;

drop function if exists registrar_venta(uuid, uuid, jsonb, jsonb, numeric, text, text);

create or replace function registrar_venta(
  p_turno_id         uuid,
  p_usuario_id       uuid,
  p_items            jsonb,
  p_pagos            jsonb,
  p_descuento        numeric default 0,
  p_cliente_email    text default null,
  p_cliente_telefono text default null,
  p_redondeo         numeric default 0
) returns table (venta_id uuid, folio bigint, total numeric)
language plpgsql
set search_path = public
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
  if abs(p_redondeo) > 1 then
    raise exception 'El redondeo no puede ser mayor a $1.00';
  end if;

  insert into ventas (turno_id, usuario_id, subtotal, descuento, redondeo, total,
                      cliente_email, cliente_telefono)
  values (p_turno_id, p_usuario_id, 0, p_descuento, p_redondeo, 0,
          p_cliente_email, p_cliente_telefono)
  returning id, ventas.folio into v_venta_id, v_folio;

  for v_item in select * from jsonb_array_elements(p_items) loop
    select * into v_prod from productos
      where id = (v_item->>'producto_id')::uuid and activo for update;
    if not found then
      raise exception 'Producto no disponible';
    end if;

    v_cant    := (v_item->>'cantidad')::numeric;
    v_precio  := coalesce((v_item->>'precio_unitario')::numeric, v_prod.precio_venta);
    v_importe := round(v_cant * v_precio, 2);

    if v_prod.stock < v_cant then
      raise exception 'Stock insuficiente para %', v_prod.nombre;
    end if;

    insert into venta_items (venta_id, producto_id, nombre, cantidad,
                             precio_unitario, costo_unitario, importe)
    values (v_venta_id, v_prod.id, v_prod.nombre, v_cant, v_precio, v_prod.costo, v_importe);

    update productos set stock = stock - v_cant, actualizado_en = now() where id = v_prod.id;

    insert into movimientos_inventario (producto_id, tipo, cantidad, costo_unitario, usuario_id, referencia)
    values (v_prod.id, 'salida_venta', -v_cant, v_prod.costo, p_usuario_id, 'venta #' || v_folio);

    v_subtotal := v_subtotal + v_importe;
  end loop;

  v_total := v_subtotal - p_descuento + p_redondeo;
  if v_total <= 0 then
    raise exception 'El total de la venta debe ser mayor a cero';
  end if;

  for v_pago in select * from jsonb_array_elements(p_pagos) loop
    v_recibido := nullif(v_pago->>'recibido', '')::numeric;
    insert into pagos (venta_id, metodo, monto, efectivo_recibido, cambio)
    values (v_venta_id, (v_pago->>'metodo')::metodo_pago, (v_pago->>'monto')::numeric, v_recibido,
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

revoke execute on function registrar_venta(uuid, uuid, jsonb, jsonb, numeric, text, text, numeric)
  from public, anon, authenticated;

-- ---------- Corte: se agrega el total de redondeos del turno ----------
create or replace view v_corte_turno with (security_invoker = true) as
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
  t.efectivo_contado,
  coalesce((select sum(v2.redondeo) from ventas v2
             where v2.turno_id = t.id and v2.estado = 'completada'), 0) as redondeos
from turnos_caja t
left join ventas v on v.turno_id = t.id
left join pagos  p on p.venta_id = v.id
group by t.id;

-- ---------- Conteo fisico (semanal): sistema vs. lo que realmente hay ----------
create table conteos_inventario (
  id           bigserial primary key,
  estado       text not null default 'abierto' check (estado in ('abierto', 'aplicado', 'cancelado')),
  creado_por   uuid references usuarios(id),
  creado_en    timestamptz not null default now(),
  aplicado_por uuid references usuarios(id),
  aplicado_en  timestamptz,
  notas        text
);
create unique index un_conteo_abierto on conteos_inventario ((true)) where estado = 'abierto';

create table conteo_items (
  id             bigserial primary key,
  conteo_id      bigint not null references conteos_inventario(id) on delete cascade,
  producto_id    uuid not null references productos(id),
  nombre         text not null,
  unidad         text not null,
  costo_unitario numeric(12,2) not null,
  stock_sistema  numeric(12,3) not null,
  stock_contado  numeric(12,3),
  diferencia     numeric(12,3) generated always as (stock_contado - stock_sistema) stored,
  clasificacion  text check (clasificacion in ('merma', 'faltante', 'sobrante')),
  nota           text,
  unique (conteo_id, producto_id)
);
create index on conteo_items (conteo_id);

alter table conteos_inventario enable row level security;
alter table conteo_items       enable row level security;

create or replace function iniciar_conteo(p_usuario_id uuid) returns bigint
language plpgsql set search_path = public as $$
declare v_id bigint;
begin
  insert into conteos_inventario (creado_por) values (p_usuario_id) returning id into v_id;
  insert into conteo_items (conteo_id, producto_id, nombre, unidad, costo_unitario, stock_sistema)
    select v_id, id, nombre, unidad, costo, stock from productos where activo;
  return v_id;
end;
$$;

-- Ajusta el inventario con la diferencia contada. Si hubo ventas despues de iniciar el
-- conteo se respetan: stock = stock actual + (contado - sistema al iniciar).
create or replace function aplicar_conteo(p_conteo_id bigint, p_usuario_id uuid) returns void
language plpgsql set search_path = public as $$
declare
  i       conteo_items%rowtype;
  v_nuevo numeric(12,3);
  v_clase text;
begin
  perform 1 from conteos_inventario where id = p_conteo_id and estado = 'abierto' for update;
  if not found then
    raise exception 'El conteo no existe o ya fue aplicado';
  end if;

  for i in select * from conteo_items
            where conteo_id = p_conteo_id and stock_contado is not null and diferencia <> 0 loop
    update productos set stock = stock + i.diferencia, actualizado_en = now()
      where id = i.producto_id returning stock into v_nuevo;
    if v_nuevo < 0 then
      raise exception 'El ajuste deja en negativo a %', i.nombre;
    end if;

    v_clase := coalesce(i.clasificacion, case when i.diferencia < 0 then 'faltante' else 'sobrante' end);
    insert into movimientos_inventario (producto_id, tipo, cantidad, costo_unitario, usuario_id, referencia)
    values (i.producto_id,
            (case when v_clase = 'merma' then 'merma' else 'ajuste' end)::tipo_mov_inv,
            i.diferencia, i.costo_unitario, p_usuario_id,
            'conteo #' || p_conteo_id || ' (' || v_clase || ')');
  end loop;

  update conteos_inventario
     set estado = 'aplicado', aplicado_por = p_usuario_id, aplicado_en = now()
   where id = p_conteo_id;
end;
$$;

revoke execute on function iniciar_conteo(uuid)          from public, anon, authenticated;
revoke execute on function aplicar_conteo(bigint, uuid)  from public, anon, authenticated;

-- ---------- Tickets digitales (PDF) ----------
-- Bucket publico: los archivos tienen nombre aleatorio e imposible de adivinar.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('tickets', 'tickets', true, 1048576, array['application/pdf'])
on conflict (id) do nothing;
