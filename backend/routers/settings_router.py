"""
User settings router.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.schemas import LLMSettingsResponse, LLMSettingsUpdateRequest

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return f"{stripped[:4]}...{stripped[-4:]}"


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings(current_user: User = Depends(get_current_user)):
    return LLMSettingsResponse(
        provider=(current_user.llm_provider or "qwen"),
        use_env_key=bool(current_user.llm_use_env_key),
        has_custom_api_key=bool((current_user.llm_api_key or "").strip()),
        masked_custom_api_key=_mask_api_key(current_user.llm_api_key),
    )


@router.patch("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(
    payload: LLMSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    provider = payload.provider.strip().lower()
    api_key = payload.api_key.strip() if isinstance(payload.api_key, str) else None

    current_user.llm_provider = provider
    current_user.llm_use_env_key = payload.use_env_key

    if payload.use_env_key:
        current_user.llm_api_key = None
    elif api_key:
        current_user.llm_api_key = api_key
    elif not (current_user.llm_api_key or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A custom API key is required when environment mode is off.",
        )

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return LLMSettingsResponse(
        provider=current_user.llm_provider or "qwen",
        use_env_key=bool(current_user.llm_use_env_key),
        has_custom_api_key=bool((current_user.llm_api_key or "").strip()),
        masked_custom_api_key=_mask_api_key(current_user.llm_api_key),
    )
