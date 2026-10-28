"""Estilo visual compartido. Los iconos usan la sintaxis :material/nombre: de Streamlit."""
import streamlit as st

CSS = """
<style>
  .block-container { padding-top: 1.6rem; max-width: 1200px; }
  h1, h2, h3 { letter-spacing: -0.01em; }
  [data-testid="stMetric"] {
      background: #FFFFFF; border: 1px solid #F3D9B8; border-radius: 14px;
      padding: 14px 18px; box-shadow: 0 1px 2px rgba(120, 60, 10, .06);
  }
  [data-testid="stSidebar"] { border-right: 1px solid #F3D9B8; }
  .stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 600; }
  div[data-testid="stForm"] { border: 1px solid #F3D9B8; border-radius: 14px; background: #FFFFFF; }
  .chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600; }
  .chip-ok   { background:#DCFCE7; color:#166534; }
  .chip-warn { background:#FEF3C7; color:#92400E; }
  .chip-bad  { background:#FEE2E2; color:#991B1B; }
</style>
"""


def aplicar_estilo() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def titulo(icono: str, texto: str, subtitulo: str | None = None) -> None:
    st.markdown(f"# :material/{icono}: {texto}")
    if subtitulo:
        st.caption(subtitulo)


def mxn(valor: float) -> str:
    return f"${valor:,.2f}"
