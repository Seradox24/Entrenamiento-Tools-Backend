# Endpoints de Identity para Launcher y Unreal

## Configuracion

Variables de `.env.prod`:

```dotenv
MOODLE_BASE_URL=https://169.58.128.68
MOODLE_SERVICE_SHORTNAME=t_launcher
MOODLE_HTTP_TIMEOUT_SECONDS=10
IDENTITY_ACCESS_TOKEN_TTL_SECONDS=900
IDENTITY_REFRESH_TOKEN_TTL_SECONDS=43200
IDENTITY_LAUNCH_TICKET_TTL_SECONDS=60
IDENTITY_XAPI_IDLE_TTL_SECONDS=3600
IDENTITY_XAPI_MAX_TTL_SECONDS=28800
IDENTITY_LOGIN_RATE=5/minute
```

Los tiempos están expresados en segundos. El timeout por inactividad xAPI no
puede superar su duración máxima. Tras cambiar el entorno hay que recrear el
servicio `web` para que Django vuelva a leerlo; no es necesario reconstruir la
imagen si solamente cambiaron valores del `.env.prod`.

Todos los endpoints usan JSON y están publicados bajo:

```text
https://SERVIDOR/som/identity/
```

## 1. Login del launcher

```http
POST /som/identity/moodle/login/
Content-Type: application/json
```

```json
{
  "username": "student",
  "password": "secret"
}
```

Respuesta `200`:

```json
{
  "status": "ok",
  "user": {
    "moodle_user_id": 42,
    "username": "student",
    "name": "Student Example",
    "first_name": "Student",
    "last_name": "Example",
    "email": "student@example.com",
    "profile_image_url": "https://169.58.128.68/pluginfile.php/..."
  },
  "launcher_session_id": "9daf81d1-35b1-46bf-b04e-7bd19049bc17",
  "access_token": "som_la_...",
  "token_type": "Bearer",
  "access_token_expires_in": 899,
  "access_token_expires_at": "2026-08-12T05:15:00+00:00",
  "refresh_token": "som_lr_...",
  "refresh_token_expires_in": 43199,
  "refresh_token_expires_at": "2026-08-12T17:00:00+00:00"
}
```

El launcher debe mantener el access token solamente en memoria y guardar el
refresh token mediante Windows Credential Manager u otro almacén seguro del
sistema operativo.

Errores particulares:

- `401 invalid_credentials`: Moodle rechazó usuario o contraseña.
- `403 identity_not_registered`: Moodle autenticó al usuario, pero aún no existe
  un `MoodleUser` sincronizado en SOM.
- `403 identity_inactive`: el registro local está suspendido o eliminado.
- `502 invalid_moodle_response`: Moodle respondió con un formato inesperado.
- `503 moodle_unavailable`: no se pudo conectar con Moodle.
- `503 identity_not_configured`: faltan variables o permisos del servicio.

## 2. Renovar la sesión del launcher

Debe llamarse antes de que venza el access token. No requiere que el access
token anterior continúe vigente.

```http
POST /som/identity/token/refresh/
Content-Type: application/json
```

```json
{
  "refresh_token": "som_lr_..."
}
```

Respuesta `200`: contiene un access token nuevo y un refresh token nuevo con el
mismo formato del login. El launcher debe reemplazar atómicamente el refresh
anterior y no volver a utilizarlo.

Error `401 invalid_refresh_token`: el token venció, fue revocado, ya fue usado o
la identidad dejó de estar activa. El launcher debe borrar sus credenciales y
mostrar nuevamente el login.

## 3. Crear un lanzamiento al presionar Iniciar

```http
POST /som/identity/launches/
Authorization: Bearer som_la_...
Content-Type: application/json
```

```json
{
  "application_id": "simulador-seguridad"
}
```

Respuesta `201`:

```json
{
  "status": "ok",
  "launch_id": "4e89500e-79e9-468c-a260-12bcaf57cfc4",
  "application_id": "simulador-seguridad",
  "launch_ticket": "som_lt_...",
  "ticket_expires_at": "2026-08-12T05:01:00+00:00"
}
```

Cada clic debe llamar este endpoint. Si ya existe un lanzamiento abierto de la
misma aplicación dentro de la sesión, queda cerrado como `replaced` y su token
xAPI deja de funcionar.

El launcher inicia Unreal entregándole únicamente:

- URL base de SOM.
- `launch_id`.
- `launch_ticket`.

No debe entregarle el access token ni el refresh token del launcher. Evitar el
ticket en una línea de comandos visible para otros procesos; se recomienda un
pipe local, entrada estándar o IPC protegido. El ticket dura 60 segundos y solo
puede utilizarse una vez.

## 4. Intercambiar el ticket desde Unreal

Esta es la primera comunicación directa Unreal → Django.

```http
POST /som/identity/launches/exchange/
Content-Type: application/json
```

```json
{
  "launch_id": "4e89500e-79e9-468c-a260-12bcaf57cfc4",
  "launch_ticket": "som_lt_..."
}
```

Respuesta `200`:

```json
{
  "status": "ok",
  "launch_id": "4e89500e-79e9-468c-a260-12bcaf57cfc4",
  "application_id": "simulador-seguridad",
  "user": {
    "moodle_user_id": 42,
    "username": "student",
    "name": "Student Example",
    "first_name": "Student",
    "last_name": "Example",
    "email": "student@example.com",
    "profile_image_url": null
  },
  "xapi_access_token": "som_xapi_...",
  "token_type": "Bearer",
  "idle_timeout_seconds": 3600,
  "absolute_expires_at": "2026-08-12T13:00:00+00:00"
}
```

Error `401 invalid_launch_ticket`: ticket incorrecto, vencido, usado,
reemplazado o vinculado a otra ejecución.

## 5. Envíos xAPI futuros

El endpoint LRS todavía no forma parte de esta implementación. Cuando se
agregue, Unreal deberá enviar en cada solicitud:

```http
Authorization: Bearer som_xapi_...
X-Experience-API-Version: 1.0.3
Content-Type: application/json
```

El endpoint debe usar `ExperienceTokenAuthentication`. Django obtiene desde la
credencial el usuario, la aplicación y el `launch_id`; no debe aceptar un
`moodle_user_id` del cliente como prueba de identidad.

Cada uso válido renueva el vencimiento por inactividad hasta el máximo absoluto
de la experiencia.

## 6. Heartbeat de Unreal

Sirve cuando la experiencia puede pasar largos períodos sin producir un
statement xAPI.

```http
POST /som/identity/launches/{launch_id}/heartbeat/
Authorization: Bearer som_xapi_...
```

Respuesta `200`:

```json
{
  "status": "ok",
  "launch_id": "4e89500e-79e9-468c-a260-12bcaf57cfc4",
  "idle_expires_at": "2026-08-12T06:00:00+00:00",
  "absolute_expires_at": "2026-08-12T13:00:00+00:00"
}
```

Una frecuencia razonable con timeout de una hora es cada 10–15 minutos. No es
necesario enviarlo inmediatamente después de cada statement porque cada
solicitud xAPI autenticada también actualizará la actividad.

## 7. Cierre normal de Unreal

```http
POST /som/identity/launches/{launch_id}/close/
Authorization: Bearer som_xapi_...
```

Respuesta `200`:

```json
{
  "status": "ok",
  "detail": "Experiencia cerrada."
}
```

Después de esta llamada el token xAPI ya no es válido. Si Unreal termina de
forma inesperada, Django lo cerrará cuando supere el límite de inactividad.

## 8. Logout del launcher

```http
POST /som/identity/logout/
Authorization: Bearer som_la_...
```

Revoca toda la sesión: access tokens, refresh tokens y lanzamientos abiertos.
Cerrar solamente la ventana de Unreal no debe llamar este endpoint.

## Reglas para el cliente

1. Si una llamada del launcher devuelve `401`, intentar una sola renovación.
2. Si la renovación funciona, repetir la operación con el access token nuevo.
3. Si la renovación falla, borrar credenciales y solicitar login.
4. Solicitar un lanzamiento nuevo en cada clic en `Iniciar`.
5. Unreal nunca debe recibir el refresh token del launcher.
6. Ante pérdida de red, Unreal debe encolar statements conservando UUID y
   timestamp originales.
7. Un `401` del LRS significa que el token xAPI terminó; sin un nuevo
   lanzamiento no debe atribuir registros utilizando solamente el ID Moodle.
