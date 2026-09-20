"""Utilidades compartidas por los tests de API del catálogo (T009, T010, T011).

Cada empresa se crea con un registro real, así que su `company_id` sale de la
sesión igual que en producción: ningún test puede colarlo por la petición.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from httpx import AsyncClient

from tests.integration.conftest import ClientFactory

# Cumple la política de 001: 12+ caracteres, mayúscula, minúscula, número y símbolo.
CONTRASENA = "Trazabilidad#2026"


@dataclass
class Empresa:
    """Una empresa registrada, con su cliente HTTP y sus cookies propias."""

    cliente: AsyncClient
    company_id: uuid.UUID
    user_id: uuid.UUID

    @property
    def csrf(self) -> dict[str, str]:
        """Cabecera CSRF copiada de la cookie (double-submit, 001 plan §2)."""
        return {"X-CSRF-Token": self.cliente.cookies["csrf_token"]}

    async def post(self, ruta: str, **cuerpo: Any) -> httpx.Response:
        return await self.cliente.post(ruta, json=cuerpo, headers=self.csrf)

    async def patch(self, ruta: str, **cuerpo: Any) -> httpx.Response:
        return await self.cliente.patch(ruta, json=cuerpo, headers=self.csrf)

    async def accion(self, ruta: str) -> httpx.Response:
        """POST sin cuerpo: los endpoints /disable y /enable de plan §5."""
        return await self.cliente.post(ruta, headers=self.csrf)

    async def get(self, ruta: str, **params: Any) -> httpx.Response:
        return await self.cliente.get(ruta, params=params)


async def registrar(make_client: ClientFactory, nombre: str) -> Empresa:
    cliente = make_client()
    cuerpo = (
        await cliente.post(
            "/api/v1/auth/register",
            json={"company_name": nombre, "username": nombre, "password": CONTRASENA},
        )
    ).json()
    return Empresa(
        cliente, uuid.UUID(cuerpo["company"]["id"]), uuid.UUID(cuerpo["user"]["id"])
    )


def error_de(respuesta: httpx.Response) -> str:
    """El código de error del formato único de 001 (plan §5)."""
    codigo: str = respuesta.json()["error"]["code"]
    return codigo
