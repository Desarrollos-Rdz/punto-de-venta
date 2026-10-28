"""Datos del ticket, PDF y enlace de WhatsApp."""
import re
from urllib.parse import quote
from fpdf import FPDF
from utils.db import get_db


def obtener_ticket(venta_id: str) -> dict:
    db = get_db()
    v = db.table("ventas").select("*, usuarios!ventas_usuario_id_fkey(nombre)").eq("id", venta_id).single().execute().data
    items = db.table("venta_items").select("*").eq("venta_id", venta_id).order("id").execute().data
    pagos = db.table("pagos").select("*").eq("venta_id", venta_id).execute().data
    tienda = db.table("config_tienda").select("*").eq("id", 1).single().execute().data
    return {"venta": v, "items": items, "pagos": pagos, "tienda": tienda}


def _l1(s) -> str:
    return str(s).encode("latin-1", "replace").decode("latin-1")


def _fecha(v: dict) -> str:
    return v["creado_en"][:16].replace("T", " ")


def ticket_texto(t: dict) -> str:
    """Version en texto plano, lista para WhatsApp."""
    v, tienda = t["venta"], t["tienda"]
    lineas = [f"*{tienda['nombre']}*"]
    if tienda.get("direccion"):
        lineas.append(tienda["direccion"])
    lineas += [f"Ticket #{v['folio']}  {_fecha(v)}", "-" * 28]
    for i in t["items"]:
        lineas.append(f"{i['nombre']}\n  {float(i['cantidad']):g} x ${float(i['precio_unitario']):,.2f} = ${float(i['importe']):,.2f}")
    lineas.append("-" * 28)
    if float(v["descuento"]):
        lineas.append(f"Descuento: -${float(v['descuento']):,.2f}")
    lineas.append(f"*TOTAL: ${float(v['total']):,.2f}*")
    for p in t["pagos"]:
        lineas.append(f"{p['metodo'].capitalize()}: ${float(p['monto']):,.2f}")
        if p.get("cambio"):
            lineas.append(f"Cambio: ${float(p['cambio']):,.2f}")
    lineas.append(tienda.get("leyenda_ticket") or "Gracias por su compra")
    return "\n".join(lineas)


def enlace_whatsapp(telefono: str, texto: str) -> str | None:
    """wa.me exige el numero solo con digitos y codigo de pais (Mexico = 52)."""
    d = re.sub(r"\D", "", telefono or "")
    if len(d) == 10:
        d = "52" + d
    elif len(d) == 12 and d.startswith("52"):
        pass
    elif len(d) == 13 and d.startswith("521"):
        d = "52" + d[3:]
    else:
        return None
    return f"https://wa.me/{d}?text={quote(texto)}"


def ticket_pdf(t: dict) -> bytes:
    v, tienda = t["venta"], t["tienda"]
    alto = 90 + 12 * len(t["items"]) + 8 * len(t["pagos"])
    pdf = FPDF(format=(80, alto))
    pdf.set_margins(4, 4, 4)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    ancho = 72

    def centrado(txt, tam=9, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", tam)
        pdf.multi_cell(ancho, 4.5, _l1(txt), align="C", new_x="LMARGIN", new_y="NEXT")

    def par(izq, der, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        pdf.cell(ancho - 24, 5, _l1(izq))
        pdf.cell(24, 5, _l1(der), align="R", new_x="LMARGIN", new_y="NEXT")

    centrado(tienda["nombre"], 12, True)
    for campo in ("direccion", "telefono"):
        if tienda.get(campo):
            centrado(tienda[campo], 8)
    pdf.ln(1)
    centrado(f"Ticket #{v['folio']}   {_fecha(v)}", 8)
    centrado(f"Atendio: {(v.get('usuarios') or {}).get('nombre', '')}", 8)
    pdf.ln(1)
    pdf.cell(ancho, 0.1, "", border="T", new_x="LMARGIN", new_y="NEXT")

    for i in t["items"]:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(ancho, 4.5, _l1(i["nombre"]), new_x="LMARGIN", new_y="NEXT")
        par(f"  {float(i['cantidad']):g} x ${float(i['precio_unitario']):,.2f}", f"${float(i['importe']):,.2f}")
    pdf.cell(ancho, 0.1, "", border="T", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    if float(v["descuento"]):
        par("Descuento", f"-${float(v['descuento']):,.2f}")
    par("TOTAL", f"${float(v['total']):,.2f}", True)
    for p in t["pagos"]:
        par(p["metodo"].capitalize(), f"${float(p['monto']):,.2f}")
        if p.get("cambio"):
            par("Cambio", f"${float(p['cambio']):,.2f}")
    pdf.ln(3)
    centrado(tienda.get("leyenda_ticket") or "Gracias por su compra", 8)
    return bytes(pdf.output())
