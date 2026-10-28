-- Zona horaria de la tienda (las fechas se guardan en UTC y se muestran en esta zona)
alter table config_tienda add column if not exists zona_horaria text not null default 'America/Mexico_City';
