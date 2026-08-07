# Entrenamiento-Tools-Backend

Base Django para SOM LRS con interfaz web y API REST.

## API REST

La API usa Django REST Framework con autenticacion de sesion y HTTP Basic.
La administracion de proyectos esta disponible solo para superusuarios.

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `GET` | `/api/` | Raiz navegable de la API |
| `GET` | `/api/health/` | Estado publico del servicio |
| `GET`, `POST` | `/api/projects/` | Listar o crear proyectos |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/projects/<id>/` | Consultar, modificar o eliminar un proyecto |

Con el servidor en ejecucion, un superusuario puede usar la API navegable desde
`http://127.0.0.1:8000/api/` o autenticarse con HTTP Basic desde un cliente REST.
