"""Pydantic request/response models for the backend API."""

from pydantic import BaseModel


class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    full_name: str | None = None


class MessageRequest(BaseModel):
    message: str


class RenameRequest(BaseModel):
    title: str
