# Usuarios sincronizados desde Moodle

## Objetivo

`MoodleUser` mantiene una copia durable de la identidad observada en Moodle para
que SOM pueda relacionarla en el futuro con registros LRS, analitica u otros
procesos, incluso cuando la cuenta original haya sido suspendida o eliminada.

Este modelo pertenece exclusivamente a `moodle_integration`. No reemplaza al
usuario de autenticacion de Django y no accede a la base de datos de Moodle.
Toda su informacion proviene de eventos recibidos por el endpoint autorizado.

## Identidad

Un usuario se identifica mediante la combinacion:

- `site_url`: URL canonica de la instalacion Moodle, sin `/` final.
- `moodle_user_id`: ID numerico asignado por esa instalacion.

La base de datos aplica una restriccion unica sobre ambos campos. El ID de
Moodle no se usa por si solo porque dos instalaciones distintas pueden asignar
el mismo numero a usuarios diferentes.

## Informacion conservada

El modelo almacena:

| Campo | Uso |
| --- | --- |
| `moodle_user_id` | Identificador original de Moodle. |
| `site_url` | Instalacion Moodle de origen. |
| `username` | Nombre de usuario conocido mas reciente. |
| `idnumber` | Identificador institucional recibido desde Moodle. |
| `first_name`, `last_name` | Nombre conocido mas reciente. |
| `email` | Correo conocido mas reciente. |
| `raw_profile` | Combinacion acumulativa de los datos recibidos en `resource.user`. |
| `is_suspended` | Indica que la cuenta no debe considerarse activa. |
| `is_deleted` | Indica que Moodle notifico su eliminacion. |
| `suspended_at`, `deleted_at` | Fecha del evento que produjo cada estado. |
| `first_seen_at` | Primera vez que SOM registro al usuario. |
| `last_seen_at` | Fecha del evento de Moodle mas reciente aplicado al perfil. |
| `last_synced_at` | Ultima escritura local del registro. |
| `last_event` | Evento auditable que genero el estado actual. |

## Comportamiento por evento

| Evento | Comportamiento |
| --- | --- |
| `core\event\user_created` | Crea el usuario o actualiza sus datos conocidos. |
| `core\event\user_updated` | Actualiza solo los campos presentes y refleja `suspended` o `deleted`. |
| `core\event\user_deleted` | Conserva el perfil y marca `is_deleted=True` e `is_suspended=True`. |
| `core\event\user_enrolment_created` | Crea o actualiza el usuario incluido en la matricula. |
| `core\event\user_enrolment_deleted` | Actualiza datos conocidos, pero no suspende al usuario por quitar una matricula. |

Una actualizacion parcial nunca vacia automaticamente los campos ausentes. Por
ejemplo, si un evento contiene solamente `id` y `suspended`, el correo y el
nombre almacenados anteriormente se conservan.

## Suspensiones y eliminaciones

Los valores `suspended` y `deleted` pueden llegar como `0`, `1` o booleanos.

- `suspended=1` activa `is_suspended`.
- `suspended=0` reactiva al usuario si nunca fue eliminado.
- `deleted=1` o `user_deleted` activa permanentemente `is_deleted` y
  `is_suspended`.
- Una actualizacion posterior no reactiva a un usuario eliminado.

La base de datos incluye una restriccion que impide guardar la combinacion
`is_deleted=True` con `is_suspended=False`.

## Proteccion de datos

Los usuarios Moodle no se pueden eliminar desde:

- `MoodleUser.delete()`;
- `MoodleUser.objects.filter(...).delete()`;
- Django Admin.

El enlace `last_event` usa `PROTECT`, por lo que tampoco se puede eliminar el
evento que explica el estado actual del usuario mientras este lo referencia.
La intencion es preservar identificadores necesarios para correlacionar datos
historicos del LRS.

## Idempotencia y orden temporal

La recepcion mantiene la idempotencia original del webhook:

- el primer `event_id` devuelve `201` y aplica la sincronizacion;
- un reintento del mismo `event_id` devuelve `200`, incrementa su contador de
  entregas y no vuelve a modificar el perfil;
- un evento nuevo con `occurred_at` anterior a `last_seen_at` se conserva en la
  auditoria, pero no revierte el perfil actual.

El evento y la actualizacion del usuario se guardan en una misma transaccion.
Si la sincronizacion falla, Django responde con un error temporal y Moodle puede
reintentar la tarea sin dejar un evento parcialmente procesado.

## Migracion y datos anteriores

La migracion `0002_moodleuser` crea la tabla, sus indices y restricciones. Al
aplicarse, recorre los `MoodleEvent` existentes en orden cronologico y genera
los perfiles correspondientes. Esto permite desplegar el modelo sobre una
instalacion que ya haya recibido eventos sin perder ese historial.

El arranque normal de `compose.prod.yaml` ejecuta las migraciones antes de
iniciar Gunicorn.

## Auditoria

Los superusuarios pueden consultar los perfiles desde:

`/som/admin/moodle_integration/moodleuser/`

La vista permite buscar por ID, usuario, identificador institucional, nombre o
correo, y filtrar por sitio, suspension o eliminacion. Todos los campos son de
solo lectura.

## Ejemplos de consulta interna

Usuarios disponibles para procesos activos:

```python
from moodle_integration.models import MoodleUser

active_users = MoodleUser.objects.filter(
    is_suspended=False,
    is_deleted=False,
)
```

Resolver una identidad para correlacionarla con datos LRS:

```python
moodle_user = MoodleUser.objects.get(
    site_url="https://moodle.example.com",
    moodle_user_id=25,
)
```

Estos ejemplos son consultas internas de SOM. No representan acceso directo a
la base de datos externa de Moodle.
