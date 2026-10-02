import io
import hmac
import os
import re
import secrets
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).resolve().parent
BG_DIR = BASE_DIR / "backgrounds"
FONT_DIR = BASE_DIR / "fonts"

BG = {
    "estrella": BG_DIR / "bg_estrella.png",
    "auto": BG_DIR / "bg_auto.png",
    "moto": BG_DIR / "bg_moto.png",
}

CURSO = {
    "estrella": "Ha completado el curso de E learning: Estrellas Amarillas",
    "auto": "Ha completado el curso de E learning: Primera vez Auto",
    "moto": "Ha completado el curso de E learning: Primera vez Moto",
}

TIPOS = [
    ("estrella", "Estrellas Amarillas"),
    ("auto", "Primera vez Auto"),
    ("moto", "Primera vez Moto"),
]

# Medido sobre el certificado original de Jonathan (imagen 1754x1241).
CENTER_X = 877
BANDAS = {
    "nombre": (500, 544),  # tinta original: 508-536
    "curso": (589, 633),   # tinta original: 597-625
    "fecha": (859, 906),   # tinta original: 867-898
}

app = Flask(__name__)
IS_VERCEL = os.environ.get("VERCEL") == "1"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or (
    None if IS_VERCEL else secrets.token_hex(32)
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = IS_VERCEL
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
DB_PATH = (
    Path(tempfile.gettempdir()) / "certificados.db"
    if IS_VERCEL else BASE_DIR / "instance" / "certificados.db"
)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Certificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    dni = db.Column(db.String(30), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    @property
    def curso(self):
        return CURSO[self.tipo]

    @property
    def tipo_nombre(self):
        return dict(TIPOS).get(self.tipo, self.tipo)


def credenciales_configuradas():
    return all(
        os.environ.get(name, "").strip()
        for name in ("SECRET_KEY", "ADMIN_EMAIL", "ADMIN_PHONE", "ADMIN_PASSWORD")
    )


def normalizar_telefono(valor):
    digitos = re.sub(r"\D", "", valor)
    if digitos.startswith("549") and len(digitos) > 10:
        return digitos[3:]
    if digitos.startswith("54") and len(digitos) > 10:
        return digitos[2:]
    return digitos


@app.context_processor
def contexto_csrf():
    return {"csrf_token": lambda: session.setdefault("csrf_token", secrets.token_urlsafe(32))}


@app.before_request
def proteger_aplicacion():
    auth_enabled = credenciales_configuradas()
    if IS_VERCEL and not auth_enabled:
        return "Falta configurar el acceso de administrador en las variables de entorno.", 503

    if auth_enabled and request.method == "POST":
        token = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not token or not expected or not hmac.compare_digest(token, expected):
            abort(400, description="La sesión expiró o el formulario no es válido. Volvé a cargar la página.")

    if not auth_enabled or request.endpoint in ("login", "static"):
        return None
    if not session.get("admin_authenticated"):
        return redirect(url_for("login", next=request.path))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if not credenciales_configuradas():
        return "El acceso de administrador no está configurado.", 503
    if session.get("admin_authenticated"):
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        admin_email = os.environ["ADMIN_EMAIL"].strip().casefold()
        admin_phone = normalizar_telefono(os.environ["ADMIN_PHONE"])
        admin_password = os.environ["ADMIN_PASSWORD"]

        valid_email = hmac.compare_digest(identifier.casefold(), admin_email)
        valid_phone = hmac.compare_digest(
            normalizar_telefono(identifier), admin_phone
        )
        valid_password = hmac.compare_digest(password, admin_password)
        valid = (valid_email or valid_phone) and valid_password
        if valid:
            destination = request.args.get("next", "")
            session.clear()
            session["admin_authenticated"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            if destination.startswith("/") and not destination.startswith("//"):
                return redirect(destination)
            return redirect(url_for("index"))

        flash("El correo, celular o contraseña no son correctos.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _buscar_fuente(nombre):
    """Busca la fuente primero en fonts/ y después en las fuentes de Windows."""
    for carpeta in (FONT_DIR, Path("C:/Windows/Fonts")):
        p = carpeta / nombre
        if p.exists():
            return p
    return None


def cargar_fuente(preferida, size, windows=None):
    """Carga la fuente; si falta, prueba con la equivalente de Windows (Times)."""
    path = _buscar_fuente(preferida)
    if path is None and windows:
        path = _buscar_fuente(windows)
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


def borrar_texto_viejo(img, y0, y1):
    """Blanquea SOLO la tinta oscura (el texto anterior) preservando el diseño:
    marca de agua, líneas curvas y el marco dorado quedan intactos."""
    x0, x1 = 100, 1654
    region = img.crop((x0, y0, x1, y1)).convert("L")
    mascara = region.point(lambda pixel: 255 if pixel < 150 else 0)
    mascara = mascara.filter(ImageFilter.MaxFilter(5))
    blanco = Image.new("RGB", region.size, "white")
    img.paste(blanco, (x0, y0), mascara)


def dibujar_linea(draw, segmentos, y_tinta):
    """Dibuja segmentos [(texto, fuente), ...] centrados en CENTER_X,
    con el borde superior de la tinta alineado a y_tinta (como el original)."""
    anchos, offsets = [], []
    for texto, fuente in segmentos:
        bb = draw.textbbox((0, 0), texto, font=fuente)
        anchos.append(bb[2] - bb[0])
        offsets.append(bb[1])
    total = sum(anchos)
    x = CENTER_X - total / 2
    for (texto, fuente), w, off in zip(segmentos, anchos, offsets):
        draw.text((x, y_tinta - off), texto, font=fuente, fill=(0, 0, 0))
        x += w


def dibujar_certificado(tipo, nombre, dni, fecha):
    if tipo not in BG:
        raise ValueError("Tipo de certificado inválido.")
    if not BG[tipo].exists():
        raise FileNotFoundError(f"No se encuentra el fondo: {BG[tipo]}")

    img = Image.open(BG[tipo]).convert("RGB")

    # Limpia únicamente la tinta del texto anterior, sin tocar el diseño.
    for b0, b1 in BANDAS.values():
        borrar_texto_viejo(img, b0, b1)

    draw = ImageDraw.Draw(img)

    f_nombre = cargar_fuente("LiberationSerif-Bold.ttf", 42, "timesbd.ttf")
    f_regular = cargar_fuente("DejaVuSerif.ttf", 40, "times.ttf")
    f_negrita = cargar_fuente("LiberationSerif-Bold.ttf", 40, "timesbd.ttf")
    f_fecha = cargar_fuente("LiberationSerif-Bold.ttf", 46, "timesbd.ttf")

    # Nombre + DNI (todo en negrita, como el original)
    dibujar_linea(draw, [(f"{nombre.strip()} DNI: {dni.strip()}", f_nombre)],
                  BANDAS["nombre"][0] + 8)

    # Curso: parte regular + "E learning: ..." en negrita (como el original)
    partes = CURSO[tipo].split("E learning:", 1)
    segmentos = [(partes[0], f_regular)]
    if len(partes) == 2:
        segmentos.append(("E learning:" + partes[1], f_negrita))
    dibujar_linea(draw, segmentos, BANDAS["curso"][0] + 8)

    # Fecha
    dibujar_linea(draw, [(fecha.strip(), f_fecha)], BANDAS["fecha"][0] + 8)

    return img


def generar_certificado(tipo, nombre, dni, fecha):
    img = dibujar_certificado(tipo, nombre, dni, fecha)
    output = io.BytesIO()
    img.save(output, "PDF", resolution=150.0)
    output.seek(0)
    return output


def generar_certificados(tipos, nombre, dni, fecha):
    imagenes = [dibujar_certificado(tipo, nombre, dni, fecha) for tipo in tipos]
    output = io.BytesIO()
    imagenes[0].save(
        output,
        "PDF",
        resolution=150.0,
        save_all=True,
        append_images=imagenes[1:],
    )
    output.seek(0)
    return output


def nombre_archivo(tipo, nombre, dni):
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre).strip("_")[:50] or "persona"
    return f"cert_{tipo}_{safe}_{dni}.pdf"


def fecha_valida(fecha):
    try:
        datetime.strptime(fecha, "%d-%m-%Y")
        return True
    except ValueError:
        return False


def validar_datos(nombre, dni, fecha):
    if not nombre:
        return "Ingresá el nombre completo."
    if not dni:
        return "Ingresá el DNI."
    if not fecha_valida(fecha):
        return "La fecha debe tener el formato DD-MM-AAAA. Ejemplo: 22-09-2026."
    return None


@app.route("/")
def index():
    certificados = Certificado.query.order_by(Certificado.created_at.desc()).limit(50).all()
    return render_template(
        "index.html",
        certificados=certificados,
        tipos=TIPOS,
        total=Certificado.query.count(),
    )


@app.route("/certificados/nuevo", methods=["GET", "POST"])
def nuevo_certificado():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        dni = request.form.get("dni", "").strip()
        fecha = request.form.get("fecha", "").strip()

        error = validar_datos(nombre, dni, fecha)
        if error:
            flash(error, "error")
            return redirect(url_for("nuevo_certificado"))

        if request.form.get("generar_todos"):
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre).strip("_")[:50] or "persona"
            pdf = generar_certificados([valor for valor, _ in TIPOS], nombre, dni, fecha)
            for valor, _ in TIPOS:
                db.session.add(Certificado(tipo=valor, nombre=nombre, dni=dni, fecha=fecha))
            db.session.commit()
            flash(f"Se generaron los 3 certificados de {nombre} en un PDF de 3 páginas.", "success")
            return send_file(
                pdf, mimetype="application/pdf", as_attachment=True,
                download_name=f"certificados_{safe}_{dni}.pdf",
            )

        # ---- Generación individual ----
        tipo = request.form.get("tipo", "").strip()
        if tipo not in BG:
            flash("Elegí un tipo de curso.", "error")
            return redirect(url_for("nuevo_certificado"))

        cert = Certificado(tipo=tipo, nombre=nombre, dni=dni, fecha=fecha)
        db.session.add(cert)
        db.session.commit()

        flash(f"Certificado de {nombre} creado correctamente.", "success")
        return redirect(url_for("descargar_certificado", cid=cert.id))

    fecha_hoy = datetime.now().strftime("%d-%m-%Y")
    return render_template("certificado_form.html", tipos=TIPOS, fecha_hoy=fecha_hoy)


@app.route("/certificados/<int:cid>/descargar")
def descargar_certificado(cid):
    cert = Certificado.query.get_or_404(cid)
    pdf = generar_certificado(cert.tipo, cert.nombre, cert.dni, cert.fecha)
    return send_file(pdf, mimetype="application/pdf", as_attachment=True,
                     download_name=nombre_archivo(cert.tipo, cert.nombre, cert.dni))


@app.route("/certificados/<int:cid>/ver")
def ver_certificado(cid):
    cert = Certificado.query.get_or_404(cid)
    pdf = generar_certificado(cert.tipo, cert.nombre, cert.dni, cert.fecha)
    return send_file(pdf, mimetype="application/pdf", as_attachment=False,
                     download_name=nombre_archivo(cert.tipo, cert.nombre, cert.dni))


@app.post("/certificados/<int:cid>/eliminar")
def eliminar_certificado(cid):
    cert = Certificado.query.get_or_404(cid)
    db.session.delete(cert)
    db.session.commit()
    flash("Certificado eliminado del historial.", "info")
    return redirect(url_for("index"))


@app.template_filter("fecha_hora")
def fecha_hora(value):
    return value.strftime("%d/%m/%Y %H:%M")


def inicializar():
    if not IS_VERCEL:
        (BASE_DIR / "instance").mkdir(exist_ok=True)
    with app.app_context():
        db.create_all()


inicializar()


if __name__ == "__main__":
    print("Sistema de Certificados Educación Vial")
    print("Abrí http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)