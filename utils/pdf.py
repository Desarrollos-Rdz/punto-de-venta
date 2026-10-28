"""Generacion de PDFs (inventario, tickets). Usa fuentes base: sin emojis ni simbolos raros."""
from datetime import datetime
from fpdf import FPDF
import pandas as pd


def _txt(s) -> str:
    return str(s).encode("latin-1", "replace").decode("latin-1")


def inventario_pdf(df: pd.DataFrame, tienda: str = "Mi Tienda") -> bytes:
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, _txt(f"Inventario - {tienda}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generado: {datetime.now():%d/%m/%Y %H:%M}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    cols = [("Producto", 90, "nombre"), ("Categoria", 32, "categoria"), ("Unidad", 18, "unidad"),
            ("Costo", 26, "costo"), ("Precio", 26, "precio_venta"), ("Margen %", 22, "margen_pct"),
            ("Stock", 24, "stock"), ("Minimo", 24, "stock_minimo")]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(253, 235, 211)
    for titulo, ancho, _ in cols:
        pdf.cell(ancho, 7, titulo, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for _, r in df.iterrows():
        bajo = r["stock"] <= r["stock_minimo"]
        pdf.set_text_color(185, 28, 28) if bajo else pdf.set_text_color(0, 0, 0)
        for _, ancho, campo in cols:
            v = r[campo]
            if campo in ("costo", "precio_venta"):
                v = f"${v:,.2f}"
            elif campo in ("stock", "stock_minimo"):
                v = f"{v:,.3f}".rstrip("0").rstrip(".")
            elif campo == "margen_pct":
                v = f"{v:.1f}"
            pdf.cell(ancho, 6, _txt(v)[: int(ancho / 1.9)], border=1)
        pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, "Filas en rojo: stock en o por debajo del minimo.")
    return bytes(pdf.output())
