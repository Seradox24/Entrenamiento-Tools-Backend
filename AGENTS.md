# Contexto para agentes

- Proyecto base Django + Django REST Framework.
- El proyecto se ejecuta con `compose.prod.yaml`: Django/Gunicorn y PostgreSQL 16 en contenedores separados.
- PostgreSQL vive en el servicio privado `db`, persiste en un volumen Docker y no publica puertos al host.
- Toda la aplicacion se publica bajo el prefijo `/som/`.
- La unica configuracion de entorno es `.env.prod` en la raiz; es local, sensible y nunca se versiona.
- Moodle es un sistema externo ya existente. SOM se integrara exclusivamente mediante la API de Moodle y nunca accedera directamente a su base de datos.
- Tailwind debe trabajarse local con npm, nunca por CDN.
- Regla permanente: cuando cambien dependencias Python, ejecutar `powershell -ExecutionPolicy Bypass -File .\scripts\update_requirements.ps1` y dejar `requirements.txt` actualizado.
- Librerias de imagenes disponibles: `Pillow`, `django-imagekit`, `django-cleanup`.
