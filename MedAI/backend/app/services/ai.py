"""Bridge between the API and the separate AI package in MedAI/ai."""
import sys
from functools import lru_cache

from app.core.config import PROJECT_DIR, get_settings

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ai.inference.service import SCORE_DESCRIPTIONS, ModelUnavailable, XrayModelService  # noqa: E402
from ai.preprocessing.xray import ImageNotSuitable, open_image  # noqa: E402

__all__ = ["get_model_service", "ModelUnavailable", "ImageNotSuitable", "open_image", "describe_score"]


@lru_cache
def get_model_service() -> XrayModelService:
    return XrayModelService(get_settings().model_config_path)


def describe_score(score_type: str) -> str | None:
    return SCORE_DESCRIPTIONS.get(score_type)
