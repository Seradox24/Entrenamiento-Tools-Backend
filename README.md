# Entrenamiento-Tools-Backend

SOM LRS es una aplicacion Django + Django REST Framework desplegada con Gunicorn y PostgreSQL en Docker.

Toda la aplicacion vive bajo el prefijo `/som/`. PostgreSQL permanece privado dentro de la red Docker y no publica puertos al host.

## Ejecucion

Crear manualmente `.env.prod` en la raiz y ejecutar:

```powershell
docker compose -f compose.prod.yaml up -d --build
```

El arranque espera a PostgreSQL, aplica migraciones, ejecuta `collectstatic` e inicia Gunicorn. Los archivos estaticos son servidos por WhiteNoise.

## API REST

La API usa Django REST Framework con autenticacion de sesion y HTTP Basic.
La administracion de proyectos esta disponible solo para superusuarios.

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `GET` | `/som/api/` | Raiz navegable de la API |
| `GET` | `/som/api/health/` | Estado publico del servicio |
| `GET`, `POST` | `/som/api/projects/` | Listar o crear proyectos |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/som/api/projects/<id>/` | Consultar, modificar o eliminar un proyecto |
| `GET` | `/som/lrs/` | Raiz autenticada del modulo LRS |

Con el servidor en ejecucion, un superusuario puede usar la API navegable desde
`http://127.0.0.1:8000/som/api/` o autenticarse con HTTP Basic desde un cliente REST.

La configuracion operativa y los limites de integracion estan documentados en `context.md`.
