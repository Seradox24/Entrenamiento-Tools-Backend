# Identity

La app `identity` autentica al usuario contra Moodle y administra credenciales
propias de SOM para el launcher y las experiencias Unreal Engine. Es una API
JSON independiente y no utiliza los templates ni las sesiones web de Django.

Documentacion:

- [Arquitectura y diagrama de sesiones](SESSION_FLOW.md)
- [Guia de uso de endpoints](ENDPOINTS.md)
- [Web services consultivos de Moodle](MOODLE_WEBSERVICES.md)

Principios de seguridad:

- La contrasena se usa solamente para autenticar contra Moodle y no se guarda.
- El token real de Moodle se descarta despues de consultar
  `core_webservice_get_site_info`.
- SOM guarda hashes SHA-256 de sus tokens, nunca sus valores originales.
- El ID de Moodle identifica al usuario, pero nunca sustituye la autenticacion.
- Cada inicio de una aplicacion genera un lanzamiento y credenciales nuevas.
- El token xAPI solo representa al usuario y lanzamiento al cual fue asignado.
- Una identidad suspendida o eliminada invalida todas sus credenciales.

El futuro endpoint LRS debe utilizar
`identity.authentication.ExperienceTokenAuthentication`. Esta autenticacion
obtiene el `MoodleUser` desde el token y actualiza la actividad del lanzamiento;
el LRS no debe confiar en un ID de usuario proporcionado por Unreal.
