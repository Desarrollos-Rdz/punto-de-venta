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


def corte_pdf(resumen: dict, cajero: str, efectivo_contado: float | None,
              tienda: str = "Mi Tienda") -> bytes:
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, _txt(f"Corte de caja - {tienda}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _txt(f"Cajero: {cajero}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Generado: {datetime.now():%d/%m/%Y %H:%M}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def fila(txt, valor, negrita=False):
        pdf.set_font("Helvetica", "B" if negrita else "", 11)
        pdf.cell(120, 8, _txt(txt), border="B")
        pdf.cell(60, 8, valor, border="B", align="R", new_x="LMARGIN", new_y="NEXT")

    fila("Fondo inicial", f"${resumen['fondo_inicial']:,.2f}")
    fila("Ventas en efectivo", f"${resumen['ventas_efectivo']:,.2f}")
    fila("Ventas con tarjeta", f"${resumen['ventas_tarjeta']:,.2f}")
    fila("Ingresos extra", f"${resumen['ingresos_extra']:,.2f}")
    fila("Retiros", f"-${resumen['retiros']:,.2f}")
    fila("Efectivo esperado en caja", f"${resumen['efectivo_esperado']:,.2f}", True)
    if efectivo_contado is not None:
        fila("Efectivo contado", f"${efectivo_contado:,.2f}", True)
        fila("Diferencia", f"${efectivo_contado - resumen['efectivo_esperado']:,.2f}", True)
    pdf.ln(4)
    fila("Total de ventas", f"${resumen['total_ventas']:,.2f}", True)
    fila("Numero de ventas", str(resumen["num_ventas"]))
    fila("Ventas canceladas", str(resumen["num_canceladas"]))
    fila("Utilidad estimada", f"${resumen['utilidad']:,.2f}")
    return bytes(pdf.output())
