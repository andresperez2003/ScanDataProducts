# Spec 001: Cimientos y autenticación

**Estado:** aprobada
**Fecha:** 2026-09-18 · decisiones de §8 cerradas el 2026-09-18 · revisada el 2026-09-18 (D-1 y D-3) · revisada el 2026-09-19 (D-5, RN-4; D-4 retirada: sin bloqueo por intentos)

> Aquí no se menciona ningún lenguaje, librería, tabla ni endpoint. Solo comportamiento
> observable. Las decisiones técnicas (algoritmo de hash, formato de sesión, esquema de
> tablas) van en `plan.md`.

## 1. Problema

El sistema guardará datos de trazabilidad de varias empresas distintas. Sin un mecanismo
de acceso y separación desde el primer día, cualquier feature posterior se construirá sobre
un modelo que no puede aislar información, y corregirlo después obliga a rehacer todas las
consultas y migrar los datos existentes.

## 2. Objetivo

Una persona puede registrar su empresa, entrar con sus credenciales y usar la aplicación,
con la garantía de que nunca verá ni podrá modificar datos de otra empresa.

## 3. Fuera de alcance

- Recuperación de contraseña olvidada.
- Invitar o dar de alta usuarios adicionales dentro de una empresa.
- Roles o permisos diferenciados dentro de una empresa.
- Edición del perfil y cambio de contraseña (van en la spec 005).
- Verificación de correo o cualquier dato de contacto.
- Autenticación con terceros.
- Bloqueo o limitación de intentos de inicio de sesión fallidos, por usuario o por origen (decisión del 2026-09-19, ver D-4).

## 4. Historias de usuario

### HU-1: Registrar una empresa y su primer usuario

Como persona que quiere usar el sistema, quiero registrar mi empresa y crear mi cuenta
para empezar a llevar la trazabilidad de mis productos.

**Criterios de aceptación**

- **CA-1.1** Dado que no existe ninguna empresa con el nombre indicado, cuando envío nombre de empresa, usuario y contraseña válidos, entonces se crea la empresa, se crea mi usuario asociado a ella, y quedo con la sesión iniciada.
- **CA-1.2** Dado que ya existe una empresa con ese nombre, cuando intento registrarme con él, entonces el registro se rechaza indicando que el nombre ya está en uso, y no se crea ningún usuario ni empresa.
- **CA-1.3** Dado un formulario con cualquier campo vacío, cuando lo envío, entonces el registro se rechaza y se indica qué campo falta, sin crear nada.
- **CA-1.4** Dada una contraseña que no cumple los requisitos de §6 RN-4, cuando la envío, entonces el registro se rechaza indicando qué requisito incumple.
- **CA-1.5** Dado un registro exitoso, cuando consulto los datos almacenados, entonces la contraseña no aparece en ninguna forma que permita recuperarla.
- **CA-1.6** Dado un registro exitoso, cuando reviso los registros de actividad del sistema, entonces la contraseña no aparece en ellos en ninguna forma.

### HU-2: Iniciar sesión

Como usuario registrado, quiero entrar con mi usuario y contraseña para acceder a los
datos de mi empresa, sin tener que recordar ni indicar el nombre de la empresa.

**Criterios de aceptación**

- **CA-2.1** Dadas un usuario y una contraseña correctos de un usuario activo, cuando inicio sesión, entonces quedo autenticado y el sistema sabe a qué empresa pertenezco, sin haber indicado el nombre de la empresa.
- **CA-2.2** Dada una contraseña incorrecta, cuando intento entrar, entonces el acceso se rechaza con un mensaje que no revela si el usuario existe.
- **CA-2.3** Dado un usuario que no existe, cuando intento entrar, entonces recibo exactamente el mismo mensaje y el mismo comportamiento observable que en CA-2.2, incluido el tiempo de respuesta.
- **CA-2.4** Dado un usuario deshabilitado, cuando intento entrar con credenciales correctas, entonces el acceso se rechaza con el mismo mensaje genérico de CA-2.2.

### HU-3: Mantener y cerrar la sesión

Como usuario autenticado, quiero que mi sesión se mantenga mientras trabajo y poder cerrarla cuando termine.

**Criterios de aceptación**

- **CA-3.1** Dada una sesión iniciada, cuando recargo la aplicación, entonces sigo autenticado sin volver a introducir credenciales.
- **CA-3.2** Dada una sesión iniciada, cuando cierro sesión, entonces pierdo el acceso a las áreas protegidas y la sesión no puede reutilizarse.
- **CA-3.3** Dada una sesión sin actividad durante 8 horas, cuando intento usar la aplicación, entonces se me pide iniciar sesión de nuevo.
- **CA-3.4** Dado que no tengo sesión, cuando intento acceder a un área protegida, entonces se me redirige al inicio de sesión sin exponer ningún dato.
- **CA-3.5** Dada una sesión creada hace 15 días, sin importar cuánta actividad haya tenido en ese lapso, cuando intento usar la aplicación, entonces se me pide iniciar sesión de nuevo.

### HU-4: Aislamiento entre empresas

Como usuario de una empresa, necesito la garantía de que ningún usuario de otra empresa
puede ver ni modificar mis datos, y que yo no puedo ver los suyos.

**Criterios de aceptación**

- **CA-4.1** Dado un usuario de la empresa A y un recurso de la empresa B, cuando el usuario A solicita ese recurso por su identificador, entonces recibe una respuesta de "no encontrado", indistinguible de la que recibiría si el recurso no existiera.
- **CA-4.2** Dado un usuario de la empresa A, cuando lista cualquier tipo de recurso, entonces el resultado contiene únicamente recursos de la empresa A, incluso si el listado está vacío para él y lleno para la empresa B.
- **CA-4.3** Dado un usuario de la empresa A, cuando intenta indicar explícitamente otra empresa en cualquier parte de una petición, entonces el sistema ignora ese dato y opera sobre la empresa A.
- **CA-4.4** Dado un usuario de la empresa A, cuando modifica o deshabilita un recurso indicando el identificador de un recurso de la empresa B, entonces la operación falla como "no encontrado" y el recurso de B no cambia.

## 5. Casos borde

| Caso | Comportamiento esperado |
| --- | --- |
| Nombre de empresa que solo difiere en mayúsculas o espacios sobrantes (`Acme S.A.` vs `  acme s.a. `) | Se considera el mismo nombre: se rechaza como duplicado. El nombre se almacena tal como lo escribió el usuario. |
| Nombre de usuario que solo difiere en mayúsculas | Se considera el mismo usuario: se rechaza como duplicado en todo el sistema. |
| Dos registros simultáneos con el mismo nombre de empresa | Solo uno tiene éxito. El otro recibe el error de duplicado, no un error interno. |
| Contraseña de 200 caracteres que cumple RN-4 | Se acepta y funciona al iniciar sesión. |
| Contraseña con un espacio en cualquier posición, incluidos inicio y final | Se rechaza (RN-4). No se recorta para hacerla válida. |
| Contraseña con `ñ` o letra acentuada (`Contraseña#2026`) | Se rechaza (RN-4): esas letras no cuentan como permitidas. |
| Contraseña con un símbolo fuera de la lista (`MiClave-2026#`) | Se rechaza (RN-4), aunque también contenga uno de la lista. |
| Sesión usada después de cerrar sesión | Rechazada. No sirve reenviar la misma credencial de sesión. |
| Dos sesiones abiertas del mismo usuario en dispositivos distintos | Ambas son válidas. Cerrar una no cierra la otra. |
| Usuario deshabilitado con sesión activa | Su sesión deja de funcionar en la siguiente petición. |
| Petición de modificación sin la protección contra falsificación de peticiones | Rechazada, aunque la sesión sea válida. |

## 6. Reglas de negocio

- **RN-1** Una empresa tiene uno o más usuarios. Un usuario pertenece a exactamente una empresa y esa pertenencia no cambia nunca.
- **RN-2** El nombre de empresa es único en todo el sistema, comparado sin distinguir mayúsculas ni espacios sobrantes.
- **RN-3** El nombre de usuario es único **en todo el sistema**, comparado sin distinguir mayúsculas. Dos usuarios de empresas distintas no pueden compartir nombre. En consecuencia, las credenciales de acceso son dos: nombre de usuario y contraseña. El nombre de la empresa se pide **solo en el registro**, para crear o identificar la empresa a la que ese usuario quedará asociado; no participa en el inicio de sesión.
- **RN-4** Una contraseña válida cumple todos estos requisitos:
  - tiene al menos 12 caracteres;
  - contiene al menos una letra mayúscula (`A`–`Z`), una minúscula (`a`–`z`) y un número (`0`–`9`);
  - contiene al menos un carácter especial de esta lista cerrada: `#` `$` `%` `&` `*` `_` `@`;
  - no contiene ningún otro carácter: ni espacios, ni letras con acento o `ñ`, ni símbolos fuera de la lista anterior.
- **RN-5** Las contraseñas nunca se almacenan, registran ni transmiten de forma que permita recuperarlas.
- **RN-6** Todo mensaje de fallo de autenticación es idéntico, sin importar la causa.
- **RN-7** Ni empresas ni usuarios se borran: se deshabilitan. Un usuario deshabilitado no puede iniciar sesión y sus sesiones activas dejan de ser válidas. Los registros que creó se conservan intactos, con su autoría.
- **RN-8** Toda operación sobre datos de negocio ocurre dentro del ámbito de la empresa del usuario autenticado. La empresa nunca se determina a partir de datos enviados por el cliente.
- **RN-9** Un recurso de otra empresa es indistinguible de un recurso inexistente, en el mensaje y en el código de respuesta.

## 7. Requisitos no funcionales

| Aspecto | Requisito medible |
| --- | --- |
| Seguridad | El almacenamiento de contraseñas resiste un volcado de la base de datos: conocer el contenido almacenado no permite obtener la contraseña en un tiempo razonable. |
| Seguridad | La credencial de sesión no es accesible desde código ejecutado en la página. |
| Seguridad | Toda operación que modifica estado requiere una prueba de que la petición se originó en la propia aplicación. |
| Rendimiento | Iniciar sesión responde en menos de 1 segundo en el percentil 95, incluyendo el coste deliberado del cálculo de verificación de la contraseña. |
| Rendimiento | Una comprobación de sesión en una petición cualquiera añade menos de 50 ms. |
| Usabilidad | Iniciar sesión pide únicamente usuario y contraseña; nunca el nombre de la empresa. |
| Auditoría | Todo registro creado guarda quién lo creó y cuándo. Toda deshabilitación guarda quién la hizo y cuándo. |

## 8. Decisiones cerradas

- [x] **D-1 — Ámbito del nombre de usuario. (revisada el 2026-09-18)** Único **en todo el sistema**, no por empresa. El nombre de empresa se pide solo en el registro, para identificar o crear la empresa; no es una credencial de acceso.
  *Consecuencia:* el formulario de inicio de sesión pide dos campos: usuario y contraseña. El de registro sigue pidiendo tres: empresa, usuario y contraseña. Recogido en RN-3, CA-2.1 y CA-2.2 a CA-2.4.
  *Motivo del cambio:* la primera versión ataba usuario a empresa para permitir nombres repetidos entre empresas (`admin` en dos empresas), pero complicaba el login sin necesidad real. Con usuario único global, el login es más simple y el nombre de empresa queda donde corresponde: en el registro, como dato de la empresa.

- [x] **D-2 — Registro contra empresa existente.** Se rechaza. Permitir unirse escribiendo el nombre correcto dejaría entrar a cualquiera que lo conozca. **Confirmada sin cambios** al revisar D-1: seguir eligiendo esto explícitamente, y no una consecuencia accidental de otra decisión, es lo que la mantiene sostenible.
  *Consecuencia:* hasta que exista un mecanismo de invitación, **cada empresa tiene exactamente un usuario**. Añadir usuarios a una empresa existente queda fuera de alcance (§3) y necesitará su propia spec.

- [x] **D-3 — Caducidad de sesión. (revisada el 2026-09-18)** Tope absoluto de **15 días** desde el inicio de sesión, sin importar la actividad — antes eran 30. El cierre por 8 horas de inactividad (CA-3.3) se mantiene sin cambios y sigue siendo, en la práctica, el límite que más se activa.
  *Consecuencia:* se añade CA-3.5 para dejarlo comprobable como criterio propio, separado de la inactividad.

- [x] **D-4 — Bloqueo por intentos fallidos. (retirada el 2026-09-19)** Queda **fuera de alcance**: el sistema no bloquea ni limita los intentos de inicio de sesión fallidos, ni por usuario ni por origen. Se retiran CA-2.5 y CA-2.6 (sus números no se reutilizan).
  *Consecuencia:* el inicio de sesión no depende de la IP del cliente ni guarda historial de intentos. La protección contra adivinación de contraseñas queda limitada al coste deliberado del hash (RN-4, §7) y a la política de contraseñas. Si se necesita más adelante, requiere su propia spec.
  *Antes decía:* bloqueo de 15 minutos tras 5 fallos del mismo usuario o 20 desde el mismo origen.

- [x] **D-5 — Composición de la contraseña. (2026-09-19)** Se sustituye el rechazo por lista de contraseñas comprometidas por reglas de composición: mayúscula, minúscula, número y un especial de la lista cerrada `#$%&*_@`, con un mínimo de 12 caracteres. Solo se admiten esos caracteres. Recogido en RN-4, CA-1.4 y §5.
  *Consecuencia:* ya no hace falta mantener una lista de contraseñas comprometidas. Espacios, letras acentuadas, `ñ` y cualquier otro símbolo se rechazan.

> Sin preguntas abiertas. La spec está lista para `plan.md`.

## 9. Checklist de salida

- [x] Cada criterio de aceptación es comprobable sin suponer nada
- [x] Cero menciones de tecnología
- [x] Sin preguntas abiertas
- [x] Los casos borde cubren: vacío, duplicado, límite, concurrencia y acceso ajeno
- [x] Cada regla de negocio tiene al menos un criterio de aceptación que la ejercita
