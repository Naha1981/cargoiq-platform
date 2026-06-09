"""CargoIQ — Auth and user models."""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    org_name: str  # Creates a new organisation


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: UUID
    org_id: UUID
    org_name: str
    role: str
    full_name: Optional[str]


class UserProfile(BaseModel):
    id: UUID
    org_id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime


class OrganisationProfile(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    shipments_this_month: int
    monthly_limit: int
    created_at: datetime
