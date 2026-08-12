# Web services Moodle disponibles para SOM

Moodle está publicado en la raíz del servidor y SOM bajo `/som/`. Por eso las
consultas REST de Moodle utilizan:

```text
https://169.58.128.68/webservice/rest/server.php
```

El servicio `t_launcher` dispone de:

| Función | Uso previsto |
|---|---|
| `core_webservice_get_site_info` | Validar token y obtener ID, nombre e imagen del usuario autenticado. |
| `core_enrol_get_users_courses` | Obtener matrículas activas del usuario. |
| `core_course_get_courses_by_field` | Resolver cursos por ID, IDs, shortname, idnumber, categoría o sección. |
| `core_course_get_contents` | Obtener secciones y actividades de un curso. |
| `core_completion_get_course_completion_status` | Consultar finalización general y criterios. |
| `core_completion_get_activities_completion_status` | Consultar finalización por actividad y relacionarla mediante `cmid`. |

Ejemplo base en PowerShell:

```powershell
curl.exe --silent --show-error --request POST `
  "https://169.58.128.68/webservice/rest/server.php" `
  --data-urlencode "wstoken=$env:MOODLE_WS_TOKEN" `
  --data-urlencode "wsfunction=core_webservice_get_site_info" `
  --data-urlencode "moodlewsrestformat=json"
```

Para matrículas:

```powershell
curl.exe --silent --show-error --request POST `
  "https://169.58.128.68/webservice/rest/server.php" `
  --data-urlencode "wstoken=$env:MOODLE_WS_TOKEN" `
  --data-urlencode "wsfunction=core_enrol_get_users_courses" `
  --data-urlencode "moodlewsrestformat=json" `
  --data-urlencode "userid=42" `
  --data-urlencode "returnusercount=0"
```

Para contenido, conviene excluir los listados de archivos:

```powershell
curl.exe --silent --show-error --request POST `
  "https://169.58.128.68/webservice/rest/server.php" `
  --data-urlencode "wstoken=$env:MOODLE_WS_TOKEN" `
  --data-urlencode "wsfunction=core_course_get_contents" `
  --data-urlencode "moodlewsrestformat=json" `
  --data-urlencode "courseid=123" `
  --data-urlencode "options[0][name]=excludecontents" `
  --data-urlencode "options[0][value]=1"
```

Para finalización general o por actividad se envían `courseid` y `userid` a
las dos funciones `core_completion_*` correspondientes.

Limitaciones relevantes:

- Estas funciones reflejan el estado actual, no un historial LRS completo.
- `core_enrol_get_users_courses` devuelve solamente matrículas activas.
- Las funciones de finalización requieren un usuario activo y permisos en el
  contexto del curso.
- SOM debe conservar sus statements o snapshots antes de una eliminación.
- `MOODLE_WEBHOOK_TOKEN`, los tokens de `identity` y los tokens reales de
  Moodle son credenciales distintas y nunca deben reutilizar el mismo valor.

Referencias oficiales:

- [Cliente REST de Moodle](https://docs.moodle.org/dev/Creating_a_web_service_client)
- [Configuración de web services](https://docs.moodle.org/502/en/How_to_enable_web_services_for_ordinary_users)
- [API de finalización](https://phpdoc.moodledev.io/main/db/d12/classcore__completion__external.html)
- [API de cursos](https://phpdoc.moodledev.io/main/d4/d98/classcore__course__external.html)
- [API de matrículas](https://phpdoc.moodledev.io/main/d6/d09/classcore__enrol__external.html)
