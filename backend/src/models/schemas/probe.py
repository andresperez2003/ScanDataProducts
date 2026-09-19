"""TEMPORAL (T016): contratos del endpoint sonda. Ninguno acepta company_id."""

import uuid

from pydantic import BaseModel


class ProbeItemOut(BaseModel):
    id: uuid.UUID
    name: str


class ProbeItemList(BaseModel):
    items: list[ProbeItemOut]


class RenameProbeItem(BaseModel):
    name: str
