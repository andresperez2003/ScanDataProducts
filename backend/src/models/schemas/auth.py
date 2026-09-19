"""Contratos de /api/v1/auth (plan §5).

Ningún schema de entrada acepta company_id: los campos extra se ignoran
(RN-8, CA-4.3). El de login no tiene company_name (RN-3).
"""

import uuid

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    company_name: str
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    username: str


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str


class AuthResponse(BaseModel):
    user: UserOut
    company: CompanyOut
