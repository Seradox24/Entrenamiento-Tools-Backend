# Desarrollo continuo

Reglas del proyecto:

- Toda dependencia Python se instala dentro de `.venv`.
- Despues de instalar, actualizar o quitar paquetes Python, ejecutar `powershell -ExecutionPolicy Bypass -File .\scripts\update_requirements.ps1`.
- `requirements.txt` debe representar siempre el estado actual de `.venv`.
- Tailwind se compila localmente con npm. No usar Tailwind por CDN.
- Despues de cambiar clases Tailwind, ejecutar `npm.cmd run css:build` o dejar `npm.cmd run css:watch` activo.
- Mantener SQLite como base por defecto durante esta etapa.
- Para trabajo con imagenes usar las librerias instaladas: `Pillow`, `django-imagekit` y `django-cleanup`.

Comandos base:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm.cmd install
npm.cmd run css:build
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```
