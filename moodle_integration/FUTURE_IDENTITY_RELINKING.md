# Feature futuro: reenlace de identidades Moodle

## Estado

**Planificado, no implementado.**

Este documento registra una posible funcionalidad futura. No describe tablas,
rutas ni acciones disponibles actualmente en SOM.

## Problema

Moodle puede eliminar una cuenta y crear otra para la misma persona. Cada
cuenta recibe un ID distinto y puede haber generado eventos, matriculas y datos
LRS diferentes antes de ser eliminada.

Ejemplo:

```text
Moodle ID 25  -> eliminado
Moodle ID 48  -> eliminado
Moodle ID 73  -> eliminado
Moodle ID 104 -> activo
```

SOM debe conservar los cuatro usuarios como cuentas historicas independientes,
pero permitir que un administrador indique que pertenecen a la misma persona.

## Decision de arquitectura

El reenlace se administrara en Django, no en el plugin de Moodle.

El plugin `local_som_observer` continuara limitado a observar y entregar
eventos. Django sera responsable de relacionar identidades porque esa decision
afecta datos historicos y futuros registros LRS propios de SOM.

No se modificaran IDs antiguos ni se moveran fisicamente sus eventos. Tampoco
se accedera directamente a la base de datos de Moodle.

## Modelo conceptual propuesto

### Identidad canonica

Crear una entidad estable, provisionalmente llamada `MoodleIdentity`, que
represente a una persona dentro de SOM.

Una identidad puede contener varias cuentas `MoodleUser`, pero una cuenta solo
puede pertenecer a una identidad canonica.

Campos iniciales sugeridos:

| Campo | Proposito |
| --- | --- |
| `id` | Identificador interno estable de SOM. |
| `created_at` | Fecha de creacion de la identidad. |
| `updated_at` | Ultima modificacion. |
| `current_user` | Cuenta Moodle vigente, si existe. |
| `notes` | Observacion administrativa opcional. |

### Historial de reenlaces

Crear una entidad inmutable, provisionalmente llamada `MoodleUserRelink`, para
registrar cada operacion administrativa.

Campos iniciales sugeridos:

| Campo | Proposito |
| --- | --- |
| `identity` | Identidad canonica afectada. |
| `previous_user` | Cuenta anterior reemplazada. |
| `new_user` | Nueva cuenta vigente. |
| `linked_at` | Fecha y hora de la operacion. |
| `linked_by` | Administrador de Django que realizo la accion. |
| `reason` | Motivo obligatorio del reenlace. |
| `is_active` | Indica si el enlace sigue vigente. |
| `invalidated_at` | Fecha de invalidacion por correccion. |
| `invalidated_by` | Administrador que corrigio el enlace. |

El historial no debe eliminarse. Si un reenlace fue incorrecto, se invalida y
se crea una nueva operacion para preservar la auditoria.

## Ejemplo de multiples recreaciones

```text
Identidad SOM 001

25  -> 48   (primer reenlace)
48  -> 73   (segundo reenlace)
73  -> 104  (tercer reenlace)

Cuenta vigente: 104
```

Las consultas no deberian recorrer esta cadena para resolver al usuario actual.
Todas las cuentas deben apuntar directamente a `MoodleIdentity 001`, que a su
vez identifica a `104` como cuenta vigente.

No se propone un limite de reenlaces. El historial puede crecer tantas veces
como Moodle recree la cuenta.

## Reglas de negocio

1. La cuenta anterior debe estar suspendida o eliminada.
2. La cuenta nueva debe estar activa y no eliminada.
3. Ambas cuentas deben pertenecer al mismo `site_url` de Moodle.
4. Una cuenta no puede reenlazarse consigo misma.
5. La cuenta nueva no puede pertenecer a otra identidad canonica.
6. Una identidad puede tener como maximo una cuenta vigente.
7. Un reenlace no debe modificar `moodle_user_id`, eventos ni payloads antiguos.
8. Los reenlaces no se crean automaticamente por username, correo o nombre.
9. Toda operacion requiere administrador, fecha y motivo.
10. La operacion completa debe ejecutarse en una transaccion y bloquear los
    registros involucrados para evitar reenlaces simultaneos.
11. Se deben impedir ciclos y cadenas inconsistentes.
12. Una cuenta marcada como eliminada nunca vuelve a ser la cuenta vigente.

## Flujo administrativo previsto

1. Moodle elimina o suspende la cuenta anterior.
2. El plugin envia el evento y SOM actualiza `MoodleUser`.
3. Moodle crea la cuenta reemplazante.
4. El plugin envia `user_created` y SOM registra la cuenta nueva.
5. Un administrador abre la identidad anterior en Django.
6. Selecciona una cuenta nueva elegible y escribe el motivo.
7. Django valida las reglas y solicita confirmacion.
8. Django registra `MoodleUserRelink` y actualiza `current_user`.
9. El historial queda disponible en modo de solo lectura.

La interfaz debe mostrar claramente los IDs, usernames, correos, sitios y
estados de ambas cuentas antes de confirmar.

## Integracion futura con LRS

Los registros LRS deben conservar la cuenta Moodle que realmente produjo cada
actividad. No se deben reescribir los IDs historicos despues de un reenlace.

Cuando se necesite una vista consolidada, el LRS resolvera la identidad
canonica asociada:

```text
Registro LRS -> MoodleUser original -> MoodleIdentity -> usuario vigente
```

Esto permitira simultaneamente:

- auditar que cuenta genero cada actividad;
- reunir actividades de varias cuentas de una misma persona;
- localizar la cuenta Moodle vigente;
- conservar datos aunque todas las cuentas hayan sido eliminadas.

La interfaz exacta con `lrs` se definira cuando esa app tenga modelos propios.
Hasta entonces no debe agregarse una dependencia desde `moodle_integration`
hacia `lrs`.

## Seguridad y permisos

- Solo superusuarios o un permiso administrativo especifico podran reenlazar.
- La operacion debe realizarse mediante POST con proteccion CSRF.
- El selector debe mostrar solamente cuentas elegibles.
- Los errores de validacion no deben realizar cambios parciales.
- Los reenlaces e invalidaciones deben quedar registrados en logs de auditoria.
- Ninguna API publica debe permitir reenlaces usando solamente el token del
  webhook de Moodle.

## Casos especiales

### Cuenta nueva eliminada antes del reenlace

No sera elegible. El administrador debera seleccionar otra cuenta activa.

### Cuenta vigente eliminada sin reemplazo

La identidad queda sin `current_user`; sus registros historicos permanecen
disponibles.

### Reenlace equivocado

El registro se invalida con motivo y administrador. No se elimina. Luego se
crea el reenlace correcto.

### Dos personas con el mismo correo o username

No se enlazan automaticamente. La coincidencia puede mostrarse como ayuda, pero
la decision siempre requiere confirmacion administrativa.

### Cuentas de instalaciones Moodle distintas

Por defecto no pueden compartir identidad mediante esta funcion. Si en el
futuro se necesita identidad entre sitios, debera disenarse y aprobarse como un
alcance separado.

## Pruebas necesarias

- Crear el primer reenlace entre una cuenta eliminada y una activa.
- Reenlazar una identidad tres o mas veces.
- Mantener una sola cuenta vigente por identidad.
- Rechazar una cuenta nueva ya asignada a otra identidad.
- Rechazar cuentas de sitios distintos.
- Rechazar origen activo, destino suspendido o destino eliminado.
- Rechazar autoenlace y ciclos.
- Conservar los eventos y perfiles de todas las cuentas.
- Invalidar un enlace sin eliminar su historial.
- Verificar concurrencia mediante transacciones simultaneas.
- Verificar permisos y proteccion CSRF del flujo administrativo.
- Consolidar datos LRS por identidad sin alterar el usuario de origen.

## Criterios de aceptacion futuros

La funcionalidad estara terminada cuando:

1. Todas las cuentas historicas permanezcan almacenadas e inmutables.
2. Una identidad admita cualquier cantidad de cuentas sucesivas.
3. Exista como maximo una cuenta vigente por identidad.
4. Cada reenlace sea auditable y reversible mediante invalidacion.
5. No puedan producirse cuentas compartidas, ciclos ni enlaces entre sitios.
6. Los registros LRS mantengan su origen y puedan consultarse consolidados.
7. La suite automatizada cubra reglas, permisos, concurrencia e historial.

## Fuera de alcance por ahora

- Implementar `MoodleIdentity` o `MoodleUserRelink`.
- Agregar pantallas o endpoints de reenlace.
- Modificar el plugin `local_som_observer`.
- Crear relaciones con modelos LRS que aun no existen.
- Inferir identidades automaticamente por datos personales.
