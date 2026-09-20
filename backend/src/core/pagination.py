"""Tamaño de página del catálogo (spec §7, D-6).

En `core/` y no en un repositorio porque lo comparten las tres capas: los repos
lo aplican al `LIMIT`, los servicios lo propagan y los schemas validan con él el
query param. Importarlo desde `repos/supplier.py` obligaría al repo de productos
y a los schemas a depender del de proveedores para una constante que no es suya.
"""

# Por defecto y máximo a la vez: la spec fija 20 y no lo hace configurable.
MAX_PAGE_SIZE = 20
