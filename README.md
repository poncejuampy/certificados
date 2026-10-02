# Sistema de Certificados de Educación Vial

Versión web local del generador de certificados.

## Qué hace

- Seleccionás **Estrellas Amarillas**, **Primera vez Auto** o **Primera vez Moto**.
- Cargás nombre completo, DNI y fecha.
- Genera el PDF automáticamente usando los fondos originales.
- Guarda un historial local en SQLite.
- Desde el panel podés volver a abrir, descargar o eliminar certificados.

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
