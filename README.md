# Sistema de Certificados de Educación Vial

Versión web local del generador de certificados.

## Qué hace

- Seleccionás **Estrellas Amarillas**, **Primera vez Auto** o **Primera vez Moto**.
- Cargás nombre completo, DNI y fecha.
- Genera el PDF automáticamente usando los fondos originales.
- Guarda un historial local en SQLite.
- Desde el panel podés volver a abrir, descargar o eliminar certificados.
- El despliegue en Vercel exige iniciar sesión con un único usuario administrador.

## Instalación

Necesitás Python 3.10 o superior.

### Windows

Abrí CMD dentro de esta carpeta:

```bash
pip install -r requirements.txt
python app.py
```

Después abrí:

http://localhost:5000

### Linux / macOS

```bash
pip3 install -r requirements.txt
python3 app.py
```

Después abrí:

http://localhost:5000

## Cursos

Los valores internos se mantienen exactamente como pidió el sistema original:

- `estrella` → Ha completado el curso de E learning: Estrellas Amarillas
- `auto` → Ha completado el curso de E learning: Primera vez Auto
- `moto` → Ha completado el curso de E learning: Primera vez Moto

## Nota

El archivo `instance/certificados.db` se crea solo al ejecutar el sistema. No hace falta crearlo manualmente.

## Despliegue en Vercel

El proyecto está preparado para que Vercel detecte la aplicación Flask en `app.py`.
En **Project Settings → Environment Variables**, configurá estas variables para
Production y Preview:

- `SECRET_KEY`: una clave aleatoria larga, distinta de la contraseña. Se puede
  generar con `python -c "import secrets; print(secrets.token_hex(32))"`.
- `ADMIN_EMAIL`: correo autorizado para iniciar sesión.
- `ADMIN_PHONE`: celular autorizado; se compara por sus dígitos.
- `ADMIN_PASSWORD`: contraseña nueva y exclusiva para esta aplicación.

Configurá las cuatro variables como secretos en Vercel; no las agregues al
repositorio ni las pegues en el código. La app no permite el acceso en Vercel
hasta que las cuatro estén configuradas. El inicio de sesión exige correo,
celular y contraseña, y protege también los PDF, el historial y las acciones
del panel.

El historial SQLite se guarda en el almacenamiento temporal de cada instancia de
Vercel: puede reiniciarse y no se comparte de manera persistente entre
instancias. Los certificados se generan en memoria y se descargan como PDF.
