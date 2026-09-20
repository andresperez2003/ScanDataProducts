# Spec 002: Catálogo — productos y proveedores

**Estado:** Aprobado
**Fecha:** 2026-09-19
**Depende de:** `001-cimientos-y-auth` (autenticación y aislamiento por empresa)

> Aquí no se menciona ningún lenguaje, librería, tabla ni endpoint. Solo comportamiento
> observable. Las decisiones técnicas (esquema de tablas, formato de paginación, endpoints)
> van en `plan.md`.

## 1. Problema

Un seguimiento de lote necesita indicar de qué producto se trata y de qué proveedor
proviene. Sin un catálogo propio de cada empresa, esos datos habría que escribirlos a
mano en cada seguimiento, lo que impide agruparlos, buscarlos, o siquiera saber si
"Tornillo 5mm" y "tornillo 5 mm" son el mismo producto.

## 2. Objetivo

Una persona de una empresa puede mantener su propio catálogo de proveedores y su propio
catálogo de productos —cada producto asociado, opcionalmente, a uno de sus proveedores—
para usarlos después como origen de los desplegables de un seguimiento.

## 3. Fuera de alcance

- Importación masiva de productos o proveedores.
- Categorías o jerarquías de productos.
- Datos de contacto del proveedor (teléfono, email, dirección).
- Precio, stock o cualquier dato de inventario o facturación (fuera del alcance del
  proyecto completo, ver constitución).
- Asociar un producto a más de un proveedor.
- El propio seguimiento de lote: esta spec entrega los catálogos que una spec posterior
  consumirá como desplegables.

## 4. Historias de usuario

### HU-1: Mantener el catálogo de proveedores

Como usuario de una empresa, quiero dar de alta, editar, deshabilitar y rehabilitar
proveedores, para tener una lista confiable de quién me provee productos.

**Criterios de aceptación**

- **CA-1.1** Dado un nombre que ningún proveedor activo de mi empresa usa, cuando doy de
  alta un proveedor con ese nombre, entonces se crea activo.
- **CA-1.2** Dado un nombre que ya usa un proveedor activo de mi empresa, cuando intento
  darlo de alta, entonces se rechaza indicando que el nombre ya está en uso.
- **CA-1.3** Dado un nombre vacío, cuando envío el alta, entonces se rechaza indicando
  el campo faltante, sin crear nada.
- **CA-1.4** Dado uno de mis proveedores, cuando edito su nombre a uno que ningún otro
  proveedor activo mío usa, entonces se actualiza.
- **CA-1.5** Dado uno de mis proveedores, cuando edito su nombre al de otro proveedor
  activo mío, entonces se rechaza como duplicado y el original no cambia.
- **CA-1.6** Dado un proveedor activo mío con productos asociados, cuando lo deshabilito,
  entonces deja de estar disponible para asignarlo a un producto, pero los productos que
  ya lo tenían asociado lo conservan y lo siguen mostrando.
- **CA-1.7** Dado un proveedor deshabilitado cuyo nombre ya usa un proveedor activo mío,
  cuando intento rehabilitarlo, entonces se rechaza.
- **CA-1.8** Dado un proveedor deshabilitado sin ese conflicto, cuando lo rehabilito,
  entonces vuelve a estar activo y disponible para asignar a productos.

### HU-2: Listar y buscar proveedores

Como usuario, quiero listar y buscar entre mis proveedores para encontrar uno rápido
aunque tenga muchos.

**Criterios de aceptación**

- **CA-2.1** Dado que tengo más proveedores activos que el tamaño de una página, cuando
  listo sin buscar, entonces recibo una página con el total de proveedores indicado.
- **CA-2.2** Dado un texto que coincide parcialmente, sin distinguir mayúsculas, con el
  nombre de uno o más de mis proveedores, cuando busco con ese texto, entonces recibo
  únicamente esos.
- **CA-2.3** Dado un texto que no coincide con ningún nombre, cuando busco, entonces
  recibo una lista vacía, no un error.
- **CA-2.4** Dado que tengo proveedores activos y deshabilitados, cuando listo sin pedir
  explícitamente el histórico, entonces solo aparecen los activos.

### HU-3: Mantener el catálogo de productos

Como usuario de una empresa, quiero dar de alta, editar, deshabilitar y rehabilitar
productos, cada uno con un nombre, opcionalmente un proveedor mío y opcionalmente un
código (SKU).

**Criterios de aceptación**

- **CA-3.1** Dado un nombre que ningún producto activo del mismo proveedor indicado (o,
  si no indico proveedor, ningún producto activo sin proveedor) usa en mi empresa, cuando
  doy de alta el producto, entonces se crea activo.
- **CA-3.2** Dado un nombre que ya usa un producto activo del mismo proveedor indicado
  (o sin proveedor, si es ese el caso), cuando intento darlo de alta, entonces se rechaza
  indicando que el nombre ya está en uso para ese proveedor.
- **CA-3.3** Dado un nombre ya usado por un producto activo de **otro** proveedor (o del
  mismo nombre entre "sin proveedor" y "con proveedor"), cuando doy de alta un producto
  con ese nombre bajo el proveedor distinto, entonces se crea sin conflicto: la
  unicidad del nombre es por proveedor, no por toda la empresa.
- **CA-3.4** Dado un nombre vacío, cuando envío el alta, entonces se rechaza indicando
  el campo faltante.
- **CA-3.5** Dado que no indico proveedor, cuando doy de alta el producto, entonces se
  crea sin proveedor asociado, agrupado a efectos de unicidad con los demás productos
  sin proveedor de mi empresa.
- **CA-3.6** Dado un proveedor mío que está deshabilitado, cuando intento darlo de alta
  o asignarlo como proveedor de un producto (nuevo o existente), entonces se rechaza: un
  proveedor deshabilitado no es una opción válida.
- **CA-3.7** Dado uno de mis productos, cuando le cambio el proveedor asociado (incluido
  quitárselo), entonces se actualiza, sujeto a la misma regla de unicidad de nombre y de
  SKU en el proveedor de destino (CA-3.2, CA-3.9).
- **CA-3.8** Dado un SKU no vacío que ya usa un producto activo del mismo proveedor (o
  sin proveedor, según corresponda), cuando doy de alta o edito un producto con ese SKU,
  entonces se rechaza indicando que el código ya está en uso para ese proveedor.
- **CA-3.9** Dado un SKU ya usado por un producto activo de otro proveedor, cuando doy
  de alta un producto con ese mismo SKU bajo el proveedor distinto, entonces se crea sin
  conflicto.
- **CA-3.10** Dado un producto activo, cuando lo deshabilito, entonces deja de estar
  disponible en el desplegable de un seguimiento nuevo.
- **CA-3.11** Dado un producto deshabilitado cuyo nombre o SKU ya usa un producto activo
  del mismo proveedor, cuando intento rehabilitarlo, entonces se rechaza.
- **CA-3.12** Dado un producto deshabilitado sin ese conflicto, cuando lo rehabilito,
  entonces vuelve a estar activo.

### HU-4: Listar y buscar productos

Como usuario, quiero listar y buscar entre mis productos, por nombre o por código, para
encontrar uno rápido aunque tenga muchos.

**Criterios de aceptación**

- **CA-4.1** Dado que tengo más productos activos que el tamaño de una página, cuando
  listo sin buscar, entonces recibo una página con el total de productos indicado, y
  cada producto muestra su proveedor asociado o la indicación de que no tiene uno.
- **CA-4.2** Dado un texto que coincide parcialmente, sin distinguir mayúsculas, con el
  nombre **o** el SKU de uno o más de mis productos, cuando busco con ese texto,
  entonces recibo únicamente esos.
- **CA-4.3** Dado un texto que no coincide con ningún producto, cuando busco, entonces
  recibo una lista vacía, no un error.
- **CA-4.4** Dado que tengo productos activos y deshabilitados, cuando listo sin pedir
  explícitamente el histórico, entonces solo aparecen los activos.
- **CA-4.5** Dado que quiero ver solo los productos de un proveedor puntual, cuando
  filtro por ese proveedor, entonces recibo únicamente los productos asociados a él.

### HU-5: Aislamiento entre empresas

Como usuario de una empresa, necesito que ningún usuario de otra empresa pueda ver ni
modificar mis proveedores o productos, y no poder ver los suyos.

**Criterios de aceptación**

- **CA-5.1** Dado un usuario de la empresa A y un proveedor o producto de la empresa B,
  cuando el usuario A lo solicita por su identificador, entonces recibe "no encontrado",
  indistinguible de si no existiera.
- **CA-5.2** Dado un usuario de la empresa A, cuando lista o busca proveedores o
  productos, entonces el resultado contiene únicamente los de la empresa A.
- **CA-5.3** Dado un usuario de la empresa A, cuando intenta indicar explícitamente otra
  empresa en cualquier parte de una petición, entonces el sistema ignora ese dato y
  opera sobre la empresa A.
- **CA-5.4** Dado un usuario de la empresa A, cuando edita, deshabilita o rehabilita un
  recurso indicando el identificador de uno de la empresa B, entonces la operación falla
  como "no encontrado" y el recurso de B no cambia.

## 5. Casos borde

| Caso | Comportamiento esperado |
| --- | --- |
| Nombre de proveedor o producto que solo difiere en mayúsculas o espacios sobrantes (`Tornillo 5mm` vs `  tornillo   5mm `) | Se considera el mismo nombre a efectos de unicidad. El nombre se almacena tal como lo escribió el usuario. |
| SKU que solo difiere en mayúsculas o espacios sobrantes | Se considera el mismo código a efectos de unicidad, igual que el nombre. |
| Dos altas simultáneas con el mismo nombre (mismo proveedor, o ambas sin proveedor) | Solo una tiene éxito; la otra recibe el error de duplicado, nunca un error interno. |
| Un producto sin proveedor y otro con proveedor, mismo nombre | Coexisten sin conflicto: "sin proveedor" es su propio grupo a efectos de unicidad. |
| Reasignar el proveedor de un producto a uno que ya tiene un producto activo con ese nombre o SKU | Se rechaza, igual que un alta duplicada. |
| Un proveedor se deshabilita mientras se está creando un producto con ese proveedor ya seleccionado en el formulario | El alta se rechaza al enviarse (CA-3.6): la validez del proveedor se comprueba en el servidor al guardar, no solo al abrir el formulario. |
| Buscar con el campo de búsqueda vacío | Equivale a listar sin buscar: primera página de resultados activos. |
| SKU vacío en dos productos del mismo proveedor | No es un conflicto: la unicidad de SKU solo aplica cuando el campo no está vacío. |

## 6. Reglas de negocio

- **RN-1** El nombre de un proveedor es único entre los proveedores activos de la misma
  empresa, comparado sin distinguir mayúsculas ni espacios sobrantes.
- **RN-2** El nombre de un producto es único entre los productos activos **del mismo
  proveedor** de la misma empresa; los productos sin proveedor forman su propio grupo a
  este efecto. Comparado sin distinguir mayúsculas ni espacios sobrantes.
- **RN-3** El SKU de un producto, cuando no está vacío, sigue la misma regla de unicidad
  y agrupamiento que RN-2.
- **RN-4** Un producto tiene como máximo un proveedor asociado, y ese proveedor debe
  estar activo en el momento de asignarlo (alta o edición). Un producto puede no tener
  ningún proveedor asociado.
- **RN-5** Deshabilitar un proveedor no afecta el estado de los productos ya asociados a
  él: siguen activos y utilizables. Solo impide que ese proveedor se asigne —de nuevo o
  por primera vez— a cualquier producto mientras siga deshabilitado.
- **RN-6** Ni proveedores ni productos se borran: se deshabilitan. Un registro
  deshabilitado no se puede usar en un seguimiento nuevo ni asignarse como proveedor de
  un producto, pero los registros que ya lo referencian lo conservan.
- **RN-7** Toda operación sobre proveedores y productos ocurre en el ámbito de la
  empresa del usuario autenticado. La empresa nunca se determina a partir de datos
  enviados por el cliente.
- **RN-8** Un proveedor o producto de otra empresa es indistinguible de uno inexistente,
  en el mensaje y en el código de respuesta.

## 7. Requisitos no funcionales

| Aspecto | Requisito medible |
| --- | --- |
| Usabilidad | Listar y buscar responden en menos de 1 segundo en el percentil 95, con hasta 10 000 registros activos por empresa. |
| Usabilidad | El listado paginado devuelve como máximo 20 registros por página por defecto. |
| Auditoría | Todo proveedor y producto creado guarda quién lo creó y cuándo. Toda deshabilitación y rehabilitación guarda quién la hizo y cuándo. |
| Consistencia | Un producto listado siempre muestra el nombre actual de su proveedor (o su ausencia), nunca un dato copiado que pueda desactualizarse. |

## 8. Decisiones cerradas

- [x] **D-1 — ¿El proveedor es obligatorio en un producto?** No. Un producto puede
  crearse y existir sin proveedor asociado.
  *Consecuencia:* la unicidad de nombre y de SKU (RN-2, RN-3) necesita un grupo propio
  para "sin proveedor", en vez de simplemente no aplicar unicidad a esos productos.

- [x] **D-2 — Alcance de la unicidad de nombre y SKU de producto.** Por proveedor, no
  por toda la empresa. Dos proveedores distintos de la misma empresa pueden tener cada
  uno un producto con el mismo nombre o el mismo SKU.
  *Motivo:* productos de proveedores distintos son entidades distintas aunque compartan
  nombre comercial o código; exigir unicidad global obligaría a inventar sufijos
  artificiales sin necesidad real.

- [x] **D-3 — Efecto de deshabilitar un proveedor sobre sus productos.** Ninguno sobre
  los productos existentes: siguen activos. Solo se bloquea asignar ese proveedor
  (nuevo o de nuevo) a cualquier producto mientras esté deshabilitado.
  *Motivo:* ni cascada ni bloqueo total encajan con "nada se borra, deshabilitar no se
  propaga por sí solo" (constitución, principio 4); el usuario deshabilita cada entidad
  explícitamente si quiere retirarla.

- [x] **D-4 — Rehabilitar con conflicto de nombre o SKU.** Se rechaza, igual que un alta
  duplicada, tanto para proveedores como para productos.
  *Motivo:* consistente con cómo 001 trata la reutilización de un nombre (RN-2 de esa
  spec); rehabilitar no debería crear una unicidad rota que un alta nunca permitiría.

- [x] **D-5 — Campos del proveedor.** Solo nombre. Sin datos de contacto en esta spec.
  *Motivo:* no hay ninguna historia de usuario que los necesite todavía; agregarlos sin
  uso violaría el principio de alcance de la constitución.

- [x] **D-6 — Tamaño de página por defecto: 20.** Es una cifra de UX razonable para un
  desplegable/listado, no derivada de ningún criterio de negocio.
  *Nota:* a diferencia de D-1 a D-5, esta no se negoció explícitamente — es la propuesta
  del autor de la spec. Fácil de cambiar en revisión si 20 no es el número deseado.

> Sin preguntas abiertas. La spec está lista para `plan.md`.

## 9. Checklist de salida

- [x] Cada criterio de aceptación es comprobable sin suponer nada
- [x] Cero menciones de tecnología
- [x] Sin preguntas abiertas
- [x] Los casos borde cubren: vacío, duplicado, límite, concurrencia y acceso ajeno
- [x] Cada regla de negocio tiene al menos un criterio de aceptación que la ejercita