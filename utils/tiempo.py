"""Fechas: la base guarda UTC; aqui se convierten a la zona horaria de la tienda."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils.db import get_db

ZONA_POR_DEFECTO = "America/Mexico_City"


@st.cache_data(ttl=60, show_spinner=False)
def zona_tienda() -> str:
    try:
        fila = get_db().table("config_tienda").select("zona_horaria").eq("id", 1).single().execute().data
        return fila["zona_horaria"] or ZONA_POR_DEFECTO
    except Exception:
        return ZONA_POR_DEFECTO


def a_local(valor, zona: str | None = None):
    """Convierte un texto/fecha UTC a datetime local (sin zona) para mostrar."""
    zona = zona or zona_tienda()
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    ts = pd.to_datetime(valor, utc=True)
    return ts.tz_convert(ZoneInfo(zona)).tz_localize(None)


def serie_local(serie: pd.Series, zona: str | None = None) -> pd.Series:
    zona = zona or zona_tienda()
    s = pd.to_datetime(serie, utc=True, errors="coerce")
    return s.dt.tz_convert(ZoneInfo(zona)).dt.tz_localize(None)


def rango_utc(desde: date, hasta: date, zona: str | None = None) -> tuple[str, str]:
    """Dias completos en hora local -> limites en UTC (ISO) para consultar la base."""
    z = ZoneInfo(zona or zona_tienda())
    ini = datetime.combine(desde, time.min, tzinfo=z).astimezone(timezone.utc)
    fin = datetime.combine(hasta, time.max, tzinfo=z).astimezone(timezone.utc)
    return ini.isoformat(), fin.isoformat()


def hoy_local(zona: str | None = None) -> date:
    return datetime.now(ZoneInfo(zona or zona_tienda())).date()
