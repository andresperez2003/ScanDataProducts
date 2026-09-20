import uuid
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlmodel import and_, col, func, or_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.pagination import MAX_PAGE_SIZE
from src.models.domain import ProductData, SupplierData
from src.models.product import Product
from src.models.supplier import Supplier

# Mismo motivo que en `repos/supplier.py`: el método se llama `list` y, con las
# anotaciones perezosas de Python 3.14 (PEP 649), `list[...]` escrito en la firma
# se evaluaría en el ámbito de la clase, donde el nombre ya está tomado.
type ProductPage = tuple[list[ProductData], int]


def _to_domain(row: Product, supplier: Supplier | None) -> ProductData:
    return ProductData(
        id=row.id,
        company_id=row.company_id,
        name=row.name,
        sku=row.sku,
        supplier=(
            None
            if supplier is None
            else SupplierData(
                id=supplier.id,
                company_id=supplier.company_id,
                name=supplier.name,
                created_at=supplier.created_at,
                disabled_at=supplier.disabled_at,
            )
        ),
        created_at=row.created_at,
        disabled_at=row.disabled_at,
    )


class ProductRepo:
    """Acceso a `products`. Hace flush, nunca commit: la transacción es del servicio.

    `company_id` es el primer parámetro de todos los métodos y entra en todas las
    consultas, sin excepción (constitución, principio 1). El proveedor se lee con
    un LEFT JOIN en la misma consulta: su nombre nunca se copia en `products`
    (§7, "consistencia").
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        company_id: uuid.UUID,
        *,
        name: str,
        name_normalized: str,
        sku: str | None,
        sku_normalized: str | None,
        supplier_id: uuid.UUID | None,
        created_by: uuid.UUID,
    ) -> ProductData:
        row = Product(
            company_id=company_id,
            supplier_id=supplier_id,
            name=name,
            name_normalized=name_normalized,
            sku=sku,
            sku_normalized=sku_normalized,
            created_by=created_by,
        )
        self._db.add(row)
        await self._db.flush()
        # Releerlo por `get` trae el proveedor con el mismo JOIN que el listado, y
        # con el company_id en la consulta: ninguna lectura lo omite (principio 1).
        creado = await self.get(company_id, row.id)
        assert creado is not None, "el producto recién creado debe poder leerse"
        return creado

    async def get(
        self, company_id: uuid.UUID, product_id: uuid.UUID
    ) -> ProductData | None:
        """El producto, incluido si está deshabilitado. None si es de otra empresa."""
        consulta = (
            select(Product, Supplier)
            .join(
                Supplier,
                and_(
                    col(Product.supplier_id) == col(Supplier.id),
                    # Principio 1: también la tabla del JOIN se filtra por empresa.
                    # El servicio ya impide asignar un proveedor ajeno (RN-4), pero
                    # la BD no lo garantiza: si una fila cruzara la frontera, aquí
                    # el nombre ajeno quedaría fuera en vez de mostrarse.
                    col(Supplier.company_id) == company_id,
                ),
                isouter=True,
            )
            .where(col(Product.company_id) == company_id, col(Product.id) == product_id)
        )
        fila = (await self._db.exec(consulta)).first()
        return None if fila is None else _to_domain(fila[0], fila[1])

    def _filtros(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None,
        supplier_id: uuid.UUID | None,
        include_disabled: bool,
    ) -> list[ColumnElement[bool]]:
        filtros: list[ColumnElement[bool]] = [col(Product.company_id) == company_id]
        if not include_disabled:
            filtros.append(col(Product.disabled_at).is_(None))
        if supplier_id is not None:
            # CA-4.5: solo los productos de ese proveedor.
            filtros.append(col(Product.supplier_id) == supplier_id)
        if search:
            # CA-4.2: el mismo término busca en el nombre y en el código.
            # autoescape: un '%' o '_' escrito por el usuario es un carácter más.
            filtros.append(
                or_(
                    col(Product.name_normalized).icontains(search, autoescape=True),
                    col(Product.sku_normalized).icontains(search, autoescape=True),
                )
            )
        return filtros

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        supplier_id: uuid.UUID | None = None,
        include_disabled: bool = False,
        page: int = 1,
        page_size: int = MAX_PAGE_SIZE,
    ) -> ProductPage:
        """Una página de productos y el total que cumple el filtro (CA-4.1).

        `search` ya viene normalizado por el servicio, igual que `name_normalized`
        y `sku_normalized` (CA-4.2). Sin `include_disabled` solo devuelve los
        activos (CA-4.4).
        """
        filtros = self._filtros(
            company_id,
            search=search,
            supplier_id=supplier_id,
            include_disabled=include_disabled,
        )
        total = (
            await self._db.exec(
                select(func.count()).select_from(Product).where(*filtros)
            )
        ).one()
        tamano = min(page_size, MAX_PAGE_SIZE)
        pagina = (
            select(Product, Supplier)
            .join(
                Supplier,
                and_(
                    col(Product.supplier_id) == col(Supplier.id),
                    # Principio 1: también la tabla del JOIN se filtra por empresa.
                    # El servicio ya impide asignar un proveedor ajeno (RN-4), pero
                    # la BD no lo garantiza: si una fila cruzara la frontera, aquí
                    # el nombre ajeno quedaría fuera en vez de mostrarse.
                    col(Supplier.company_id) == company_id,
                ),
                isouter=True,
            )
            .where(*filtros)
            # Orden estable: sin un desempate por id, dos nombres iguales podrían
            # repetirse o perderse entre páginas.
            .order_by(col(Product.name_normalized), col(Product.id))
            .offset(max(page - 1, 0) * tamano)
            .limit(tamano)
        )
        filas = (await self._db.exec(pagina)).all()
        return [_to_domain(p, s) for p, s in filas], total

    async def update(
        self,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        *,
        name: str,
        name_normalized: str,
        sku: str | None,
        sku_normalized: str | None,
        supplier_id: uuid.UUID | None,
    ) -> bool:
        """False si el producto no existe en esa empresa (CA-5.4).

        `supplier_id` se escribe siempre, también cuando es `None`: quitarle el
        proveedor a un producto es un cambio válido (CA-3.7).
        """
        consulta = (
            update(Product)
            .where(
                col(Product.company_id) == company_id,
                col(Product.id) == product_id,
            )
            .values(
                name=name,
                name_normalized=name_normalized,
                sku=sku,
                sku_normalized=sku_normalized,
                supplier_id=supplier_id,
            )
        )
        resultado = await self._db.exec(consulta)
        # Las filas ya cargadas en la sesión deben releerse tras el UPDATE.
        self._db.expire_all()
        return resultado.rowcount == 1

    async def disable(
        self,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        *,
        disabled_by: uuid.UUID,
        at: datetime,
    ) -> bool:
        """Marca `disabled_at` (nunca borra). False si no existe o ya estaba."""
        consulta = (
            update(Product)
            .where(
                col(Product.company_id) == company_id,
                col(Product.id) == product_id,
                col(Product.disabled_at).is_(None),
            )
            .values(disabled_at=at, disabled_by=disabled_by)
        )
        resultado = await self._db.exec(consulta)
        self._db.expire_all()
        return resultado.rowcount == 1

    async def enable(self, company_id: uuid.UUID, product_id: uuid.UUID) -> bool:
        """Vuelve a dejarlo activo. False si no existe o ya estaba activo (CA-3.12)."""
        consulta = (
            update(Product)
            .where(
                col(Product.company_id) == company_id,
                col(Product.id) == product_id,
                col(Product.disabled_at).is_not(None),
            )
            .values(disabled_at=None, disabled_by=None)
        )
        resultado = await self._db.exec(consulta)
        self._db.expire_all()
        return resultado.rowcount == 1
