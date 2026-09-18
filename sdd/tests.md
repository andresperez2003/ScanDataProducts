---
paths:
  - "backend/tests/**/*.py"
---

# Tests

## De dónde salen

Los tests se derivan de `specs/NNN-*/spec.md`, **nunca del código ya escrito**.
Si el código existe antes que el test, el test solo confirma los bugs que tenga.

## Nombres

Cada test lleva en el nombre el identificador que cubre:

```python
def test_ca_1_2_login_con_contrasena_incorrecta_devuelve_401(): ...
def test_rn_3_usuario_deshabilitado_no_puede_iniciar_sesion(): ...
def test_borde_registro_con_empresa_ya_existente_es_rechazado(): ...
```

## Obligatorios

- Un test de integración por endpoint, contra Postgres real. Nunca mocks del repositorio.
- **Un test de aislamiento por cada endpoint que lea o escriba datos de negocio:**
  un usuario de la empresa B pide un recurso de la empresa A y recibe **404**.
  Este test no es opcional en ningún endpoint.
- Un test unitario por regla de negocio, con caso positivo y caso negativo.
- Un test por cada caso borde listado en §5 de la spec.

## Infraestructura

- Cada test corre en una transacción que se revierte al terminar. Sin estado compartido.
- Las factorías de datos crean siempre dos empresas, para que el aislamiento sea testeable.
- Cobertura mínima del 80 % sobre `backend/src/`.
