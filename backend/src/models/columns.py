from datetime import datetime

from sqlalchemy import Column, DateTime, text


def timestamptz(
    *, nullable: bool = False, index: bool = False, server_now: bool = False
) -> Column[datetime]:
    """Columna de instante en UTC con zona horaria explícita (constitución, Fechas).

    Cada llamada crea una columna nueva: SQLAlchemy no permite compartirlas entre
    tablas.
    """
    return Column(
        DateTime(timezone=True),
        nullable=nullable,
        index=index,
        server_default=text("now()") if server_now else None,
    )
