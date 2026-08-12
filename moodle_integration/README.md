# Moodle integration

Esta app recibe eventos enviados por `local_som_observer` sin acceder a la base
de datos de Moodle ni importar codigo de otras apps del proyecto.

## Endpoint

`POST /som/moodle_integration/events/`

La solicitud debe usar `Content-Type: application/json` y el encabezado
`Authorization: Bearer <token>`. El proceso que ejecuta Django debe definir
`MOODLE_WEBHOOK_TOKEN`; su valor debe coincidir con el configurado en Moodle y
nunca debe guardarse en Git.

## Entrega e idempotencia

- `201`: el evento fue validado y almacenado.
- `200`: `event_id` ya existia; se registro una nueva entrega sin duplicar el
  evento.
- `400`: JSON o contrato invalido, o evento no soportado.
- `401`: token ausente o incorrecto.
- `503`: el backend no tiene configurado `MOODLE_WEBHOOK_TOKEN`.

`MoodleEvent` funciona como bandeja durable. El endpoint no ejecuta tareas
pesadas: guarda el payload con auditoria y deja el registro en estado
`received` para que un procesador en segundo plano pueda consumirlo en el
futuro. Los registros pueden consultarse, sin modificarlos, desde Django Admin.

## Usuarios Moodle

Cada evento proyecta `resource.user` en `MoodleUser`, identificado de forma
unica por el sitio Moodle y el ID del usuario. Las actualizaciones parciales
conservan la informacion conocida, y los eventos antiguos no revierten el
estado actual si llegan fuera de orden.

Los usuarios nunca se eliminan fisicamente. `user_deleted`, `deleted=1` y
`suspended=1` se reflejan mediante `is_deleted` e `is_suspended`, conservando
el perfil para usos posteriores como LRS. Tanto el modelo como Django Admin
bloquean su eliminacion.

El contrato detallado del modelo, sus estados y reglas de sincronizacion se
encuentra en [`USERS.md`](USERS.md).
