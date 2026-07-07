"""Pydantic request/response models for the backend API."""

from pydantic import BaseModel


class SignupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    username: str


class MessageRequest(BaseModel):
    message: str


class RenameRequest(BaseModel):
    title: str
