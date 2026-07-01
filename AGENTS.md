# Contexto para agentes

- Proyecto base Django + Django REST Framework.
- Base de datos actual: SQLite.
- Variables locales en `.env`; mantener `.env.example` sincronizado cuando cambien las claves.
- Tailwind debe trabajarse local con npm, nunca por CDN.
- Regla permanente: cuando cambien dependencias Python, ejecutar `powershell -ExecutionPolicy Bypass -File .\scripts\update_requirements.ps1` y dejar `requirements.txt` actualizado.
- Librerias de imagenes disponibles: `Pillow`, `django-imagekit`, `django-cleanup`.
