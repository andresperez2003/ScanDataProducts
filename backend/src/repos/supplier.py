import uuid
from datetime import datetime

from sqlmodel import col, func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.pagination import MAX_PAGE_SIZE
from src.models.domain import SupplierData
from src.models.supplier import Supplier

# Las filas de una página y el total que cumple el filtro. Alias de módulo y no
# `tuple[list[...], int]` escrito en la firma: el método se llama `list` y, con
# las anotaciones perezosas de Python 3.14 (PEP 649), sombrearía al builtin al
# evaluarse en el ámbito de la clase.
type SupplierPage = tuple[list[SupplierData], int]


def _to_domain(row: Supplier) -> SupplierData:
    return SupplierData(
        id=row.id,
        company_id=row.company_id,
        name=row.name,
        created_at=row.created_at,
        disabled_at=row.disabled_at,
    )


class SupplierRepo:
    """Acceso a `suppliers`. Hace flush, nunca commit: la transacción es del servicio.

    `company_id` es el primer parámetro de todos los métodos y entra en todas las
    consultas, sin excepción (constitución, principio 1).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        company_id: uuid.UUID,
        *,
        name: str,
        name_normalized: str,
        created_by: uuid.UUID,
    ) -> SupplierData:
        row = Supplier(
            company_id=company_id,
            name=name,
            name_normalized=name_normalized,
            created_by=created_by,
        )
        self._db.add(row)
        await self._db.flush()
        # created_at lo pone la BD (server_default).
        await self._db.refresh(row)
        return _to_domain(row)

    async def get(
        self, company_id: uuid.UUID, supplier_id: uuid.UUID
    ) -> SupplierData | None:
        """El proveedor, incluido si está deshabilitado. None si es de otra empresa."""
        consulta = select(Supplier).where(
            Supplier.company_id == company_id, Supplier.id == supplier_id
        )
        row = (await self._db.exec(consulta)).first()
        return _to_domain(row) if row is not None else None

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        include_disabled: bool = False,
        page: int = 1,
        page_size: int = MAX_PAGE_SIZE,
    ) -> SupplierPage:
        """Una página de proveedores y el total que cumple el filtro (CA-2.1).

        `search` ya viene normalizado por el servicio, igual que `name_normalized`:
        así la comparación no depende de mayúsculas ni de espacios (CA-2.2).
        Sin `include_disabled` solo devuelve los activos (CA-2.4).
        """
        filtros = [col(Supplier.company_id) == company_id]
        if not include_disabled:
            filtros.append(col(Supplier.disabled_at).is_(None))
        if search:
            # autoescape: un '%' o '_' escrito por el usuario es un carácter más.
            filtros.append(
                col(Supplier.name_normalized).icontains(search, autoescape=True)
            )

        total = (
            await self._db.exec(
                select(func.count()).select_from(Supplier).where(*filtros)
            )
        ).one()
        tamano = min(page_size, MAX_PAGE_SIZE)
        pagina = select(Supplier).where(*filtros)
        # Orden estable: sin un desempate por id, dos nombres iguales podrían
        # repetirse o perderse entre páginas.
        pagina = pagina.order_by(col(Supplier.name_normalized), col(Supplier.id))
        pagina = pagina.offset(max(page - 1, 0) * tamano).limit(tamano)
        filas = (await self._db.exec(pagina)).all()
        return [_to_domain(f) for f in filas], total

    async def update(
        self,
        company_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        name: str,
        name_normalized: str,
    ) -> bool:
        """False si el proveedor no existe en esa empresa (CA-5.4)."""
        consulta = (
            update(Supplier)
            .where(
                col(Supplier.company_id) == company_id,
                col(Supplier.id) == supplier_id,
            )
            .values(name=name, name_normalized=name_normalized)
        )
        resultado = await self._db.exec(consulta)
        # Las filas ya cargadas en la sesión deben releerse tras el UPDATE.
        self._db.expire_all()
        return resultado.rowcount == 1

    async def disable(
        self,
        company_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        disabled_by: uuid.UUID,
        at: datetime,
    ) -> bool:
        """Marca `disabled_at` (nunca borra). False si no existe o ya estaba."""
        consulta = (
            update(Supplier)
            .where(
                col(Supplier.company_id) == company_id,
                col(Supplier.id) == supplier_id,
                col(Supplier.disabled_at).is_(None),
            )
            .values(disabled_at=at, disabled_by=disabled_by)
        )
        resultado = await self._db.exec(consulta)
        self._db.expire_all()
        return resultado.rowcount == 1

    async def enable(self, company_id: uuid.UUID, supplier_id: uuid.UUID) -> bool:
        """Vuelve a dejarlo activo. False si no existe o ya estaba activo (CA-1.8)."""
        consulta = (
            update(Supplier)
            .where(
                col(Supplier.company_id) == company_id,
                col(Supplier.id) == supplier_id,
                col(Supplier.disabled_at).is_not(None),
            )
            .values(disabled_at=None, disabled_by=None)
        )
        resultado = await self._db.exec(consulta)
        self._db.expire_all()
        return resultado.rowcount == 1
