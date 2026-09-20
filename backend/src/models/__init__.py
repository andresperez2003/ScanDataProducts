"""Entidades de la base de datos.

Importarlas aquí registra todas las tablas en `SQLModel.metadata`, que es lo que
lee Alembic para generar migraciones.
"""

from src.models.company import Company
from src.models.product import Product
from src.models.session import Session
from src.models.supplier import Supplier
from src.models.user import User

__all__ = ["Company", "Product", "Session", "Supplier", "User"]
