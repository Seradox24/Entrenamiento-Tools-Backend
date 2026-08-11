# Desarrollo continuo

Reglas del proyecto:

- Toda dependencia Python se instala dentro de `.venv`.
- Despues de instalar, actualizar o quitar paquetes Python, ejecutar `powershell -ExecutionPolicy Bypass -File .\scripts\update_requirements.ps1`.
- `requirements.txt` debe representar siempre el estado actual de `.venv`.
- Tailwind se compila localmente con npm. No usar Tailwind por CDN.
- Despues de cambiar clases Tailwind, ejecutar `npm.cmd run css:build` o dejar `npm.cmd run css:watch` activo.
- Desarrollo y servidor usan el mismo archivo `compose.prod.yaml`.
- PostgreSQL se ejecuta en el servicio privado `db` y persiste en el volumen `postgres_data`.
- `.env.prod` debe existir en la raiz, pero nunca se agrega a Git.
- Para trabajo con imagenes usar las librerias instaladas: `Pillow`, `django-imagekit` y `django-cleanup`.

Levantar el sistema:

```powershell
npm.cmd install
npm.cmd run css:build
docker compose -f compose.prod.yaml up --build
```

Ejecutarlo en segundo plano:

```powershell
docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml logs -f web
```

Detenerlo sin eliminar los datos PostgreSQL:

```powershell
docker compose -f compose.prod.yaml down
```

Las migraciones y `collectstatic` se ejecutan automaticamente antes de iniciar Gunicorn.

Para administrar Django dentro del contenedor:

```powershell
docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
docker compose -f compose.prod.yaml exec web python manage.py check
docker compose -f compose.prod.yaml exec web python manage.py test
```
