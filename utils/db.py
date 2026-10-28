"""Conexion unica a Supabase (se reutiliza entre ejecuciones de Streamlit)."""
import streamlit as st
from supabase import create_client, Client


@st.cache_resource(show_spinner=False)
def get_db() -> Client:
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_key"])
