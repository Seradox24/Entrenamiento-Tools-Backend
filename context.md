# Contexto operativo de SOM LRS

## Alcance HTTP

Toda ruta publica de SOM comienza con `/som/`:

- `/som/`: inicio de sesion.
- `/som/home/`: panel autenticado.
- `/som/lrs/`: modulo LRS.
- `/som/api/`: API REST navegable.
- `/som/admin/`: administracion de Django.
- `/som/static/`: archivos estaticos recopilados.
- `/som/media/`: espacio reservado para archivos cargados.

La raiz `/` no pertenece a SOM. En el servidor, Nginx enviara solamente `/som/` hacia `127.0.0.1:8000`.

## Servidor objetivo

La referencia vigente es la [arquitectura saneada del servidor](https://169.58.128.68/arqui/architecture.md), actualizada el 11 de agosto de 2026.

- Ubuntu Server aloja Nginx como unico punto de entrada HTTP/HTTPS.
- Moodle 5.2.1, PHP-FPM y su PostgreSQL se ejecutan directamente en el host.
- `/` permanece reservado para Moodle y `/arqui/` para la documentacion publica.
- Nginx enviara `/som/` al contenedor Django publicado en `127.0.0.1:8000`.
- Portainer y Uptime Kuma mantienen sus puertos loopback actuales y no interfieren con SOM.
- Ollama permanece en `127.0.0.1:11434` del host. Un contenedor no debe asumir que su propio loopback llega al host; una futura integracion necesitara una interfaz interna controlada.

En `.env.prod` del servidor, `ALLOWED_HOSTS` debe incluir `169.58.128.68` y `CSRF_TRUSTED_ORIGINS` debe incluir `https://169.58.128.68`.

El servidor HTTPS debe usar una `SECRET_KEY` aleatoria de al menos 50 caracteres y configurar `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True` y `CSRF_COOKIE_SECURE=True`. HSTS debe habilitarse solamente despues de comprobar de forma estable el dominio y TLS.

## Contenedores

Existe una unica definicion: `compose.prod.yaml`. Se usa tanto en pruebas como en el servidor.

- `web`: Django, Gunicorn, migraciones, `collectstatic` y WhiteNoise.
- `db`: PostgreSQL 16.14 exclusivo de SOM.
- `postgres_data`: volumen persistente de PostgreSQL.
- `som_internal`: red privada entre Django y PostgreSQL.
- `som_egress`: red de salida disponible solo para Django y destinada a futuras integraciones HTTP.

El servicio `db` no declara `ports`; no puede accederse directamente desde el host ni desde Internet. Django lo resuelve por DNS interno mediante `DATABASE_HOST=db`.

## Moodle existente

Moodle y su PostgreSQL ya existen fuera de este Compose y no forman parte del ciclo de vida de SOM. No se agregara acceso directo a la base de datos de Moodle.

La futura app `moodle_integration` consumira exclusivamente endpoints autorizados de la API de Moodle desde el contenedor `web`. Esta separacion evita compartir credenciales, tablas o migraciones entre ambos sistemas.

## Entorno

La unica fuente de configuracion es `.env.prod`, ubicada en la raiz del proyecto y excluida de Git y de la imagen Docker. Compose inyecta sus variables en `web` y `db`; `settings.py` tambien la reconoce cuando Django se ejecuta directamente desde la raiz.

Claves requeridas:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_HOST` con valor `db`
- `DATABASE_PORT` con valor `5432`
- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `SECURE_HSTS_SECONDS`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `SECURE_HSTS_PRELOAD`

El archivo se crea manualmente en cada entorno. Sus valores no deben copiarse a documentación, commits o imágenes.

## Arranque

```powershell
docker compose -f compose.prod.yaml up -d --build
```

El orden de arranque es:

1. PostgreSQL inicia y supera su healthcheck.
2. Django ejecuta `migrate --noinput`.
3. Django ejecuta `collectstatic --noinput`.
4. Gunicorn inicia en `0.0.0.0:8000` dentro del contenedor.
5. Docker publica el servicio solamente en `127.0.0.1:8000` del host.

Configuracion prevista para Nginx:

```nginx
location /som/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
