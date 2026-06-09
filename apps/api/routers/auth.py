"""
CargoIQ — Auth Router
Handles sign-up, sign-in, and session management via Supabase Auth.
"""
import re
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from ..models.schemas import SignUpRequest, SignInRequest, AuthResponse
from ..core.supabase_client import get_supabase_admin
from ..core.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert org name to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug[:50]


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(payload: SignUpRequest):
    """
    Register a new user and create their organisation.
    Creates: Supabase Auth user → Organisation → User profile.
    """
    admin = get_supabase_admin()

    # Generate slug
    org_slug = payload.org_slug or slugify(payload.org_name)

    # Check slug uniqueness
    existing = admin.table("organisations").select("id").eq("slug", org_slug).execute()
    if existing.data:
        org_slug = f"{org_slug}-{re.sub(r'[^a-z0-9]', '', payload.email.split('@')[0])}"

    try:
        # 1. Create Supabase Auth user
        auth_response = admin.auth.admin.create_user({
            "email": payload.email,
            "password": payload.password,
            "email_confirm": True,  # Auto-confirm for now (add email verification later)
        })
        auth_user = auth_response.user
        if not auth_user:
            raise HTTPException(status_code=400, detail="Failed to create authentication account")

        # 2. Create organisation
        org = admin.table("organisations").insert({
            "name": payload.org_name,
            "slug": org_slug,
            "plan": "pilot",
            "monthly_limit": 200,
        }).execute()
        org_data = org.data[0]

        # 3. Create user profile linked to org
        user_profile = admin.table("users").insert({
            "id": auth_user.id,
            "org_id": org_data["id"],
            "email": payload.email,
            "full_name": payload.full_name,
            "role": "admin",  # First user in org is admin
        }).execute()

        # 4. Sign in to get JWT
        sign_in = admin.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        return AuthResponse(
            access_token=sign_in.session.access_token,
            user={
                "id": auth_user.id,
                "email": payload.email,
                "full_name": payload.full_name,
                "role": "admin",
            },
            organisation={
                "id": org_data["id"],
                "name": org_data["name"],
                "slug": org_data["slug"],
                "plan": org_data["plan"],
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sign-up failed: {e}")
        # Try to clean up if org was created but user profile failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)[:100]}"
        )


@router.post("/signin", response_model=AuthResponse)
async def sign_in(payload: SignInRequest):
    """Authenticate user and return JWT access token."""
    admin = get_supabase_admin()

    try:
        auth_response = admin.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        if not auth_response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Get user profile with org
        user_data = admin.table("users") \
            .select("*, organisations(*)") \
            .eq("id", auth_response.user.id) \
            .single() \
            .execute()

        if not user_data.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = user_data.data
        org = profile.get("organisations", {})

        # Update last login
        admin.table("users").update(
            {"last_login_at": "now()"}
        ).eq("id", profile["id"]).execute()

        return AuthResponse(
            access_token=auth_response.session.access_token,
            user={
                "id": profile["id"],
                "email": profile["email"],
                "full_name": profile.get("full_name"),
                "role": profile["role"],
            },
            organisation={
                "id": org.get("id"),
                "name": org.get("name"),
                "slug": org.get("slug"),
                "plan": org.get("plan"),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sign-in failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user profile."""
    admin = get_supabase_admin()
    user_data = admin.table("users") \
        .select("*, organisations(*)") \
        .eq("id", current_user["user_id"]) \
        .single() \
        .execute()

    if not user_data.data:
        raise HTTPException(status_code=404, detail="User not found")

    return user_data.data


@router.post("/signout")
async def sign_out(current_user: dict = Depends(get_current_user)):
    """Sign out current user (invalidate token client-side)."""
    # Supabase JWT invalidation happens client-side
    # Server-side: just confirm the request was received
    return {"message": "Signed out successfully"}
