from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

load_dotenv(REPO_ROOT / ".env", override=False)
# backend/.env is backend-local and should override same keys from repo-root .env.
load_dotenv(BACKEND_DIR / ".env", override=True)


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _build_database_url() -> str:
    direct_url = _clean_env(os.getenv("DATABASE_URL"))
    if direct_url and "${" not in direct_url:
        return direct_url

    user = _clean_env(os.getenv("POSTGRES_USER")) or "admin"
    password = _clean_env(os.getenv("POSTGRES_PASSWORD")) or "change-me-local-db-password"
    database = _clean_env(os.getenv("POSTGRES_DB")) or "hoogen_agridb"
    host = _clean_env(os.getenv("POSTGRES_HOST")) or "localhost"
    port = _clean_env(os.getenv("PG_PORT")) or _clean_env(os.getenv("POSTGRES_PORT")) or "5432"
    return f"postgresql://{user}:{password}@{host}:{port}/{database}?schema=public"


def _build_redis_url() -> str:
    direct_url = _clean_env(os.getenv("REDIS_URL"))
    if direct_url:
        return direct_url
    port = _clean_env(os.getenv("REDIS_PORT")) or "6379"
    host = _clean_env(os.getenv("REDIS_HOST")) or "localhost"
    return f"redis://{host}:{port}/0"


def _sanitize_psycopg_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    query_pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "schema"]
    return urlunparse(parsed._replace(query=urlencode(query_pairs)))


def _bool_env(name: str, default: bool) -> bool:
    value = _clean_env(os.getenv(name))
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Smart Agriculture Management Backend")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    slow_request_threshold_ms: int = int(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "1000"))
    backend_admin_token: str = os.getenv("BACKEND_ADMIN_TOKEN", "")
    backend_api_token: str = os.getenv("BACKEND_API_TOKEN", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_timeout_seconds: float = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "20"))
    local_llm_enabled: bool = field(default_factory=lambda: _bool_env("LOCAL_LLM_ENABLED", False))
    local_llm_base_url: str = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:14b")
    local_llm_timeout_seconds: float = float(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "25"))
    copilot_recommendation_max_items: int = int(os.getenv("COPILOT_RECOMMENDATION_MAX_ITEMS", "5"))
    database_url: str = field(default_factory=_build_database_url)
    psycopg_database_url: str = field(default_factory=lambda: _sanitize_psycopg_url(_build_database_url()))
    redis_url: str = field(default_factory=_build_redis_url)
    hoogendoorn_provider: str = os.getenv("HOOGENDOORN_PROVIDER", "mock")
    hoogendoorn_system_id: str = os.getenv("HOOGENDOORN_SYSTEM_ID", "")
    hoogendoorn_token_url: str = os.getenv(
        "HOOGENDOORN_TOKEN_URL",
        "https://centralauthentication.hoogendoorn-iivo.cn/connect/token",
    )
    hoogendoorn_api_base_url: str = os.getenv(
        "HOOGENDOORN_API_BASE_URL",
        "https://partnerapi.hoogendoorn-iivo.cn",
    )
    hoogendoorn_client_id: str = os.getenv("HOOGENDOORN_CLIENT_ID", "")
    hoogendoorn_client_secret: str = os.getenv("HOOGENDOORN_CLIENT_SECRET", "")
    hoogendoorn_scope: str = os.getenv("HOOGENDOORN_SCOPE", "external.partner.api")
    hoogendoorn_api_token: str = os.getenv("HOOGENDOORN_API_TOKEN", "")
    hoogendoorn_timeout_seconds: float = float(os.getenv("HOOGENDOORN_TIMEOUT_SECONDS", "15"))
    hoogendoorn_retry_attempts: int = int(os.getenv("HOOGENDOORN_RETRY_ATTEMPTS", "4"))
    hoogendoorn_retry_min_seconds: float = float(os.getenv("HOOGENDOORN_RETRY_MIN_SECONDS", "1"))
    hoogendoorn_retry_max_seconds: float = float(os.getenv("HOOGENDOORN_RETRY_MAX_SECONDS", "8"))
    hoogendoorn_sync_window_minutes: int = int(os.getenv("HOOGENDOORN_SYNC_WINDOW_MINUTES", "15"))
    hoogendoorn_sync_overlap_minutes: int = int(os.getenv("HOOGENDOORN_SYNC_OVERLAP_MINUTES", "5"))
    hoogendoorn_mock_interval_minutes: int = int(os.getenv("HOOGENDOORN_MOCK_INTERVAL_MINUTES", "5"))
    hoogendoorn_mock_zone_count: int = int(os.getenv("HOOGENDOORN_MOCK_ZONE_COUNT", "4"))
    hoogendoorn_mock_failures_before_success: int = int(
        os.getenv("HOOGENDOORN_MOCK_FAILURES_BEFORE_SUCCESS", "0")
    )
    hoogendoorn_mock_enabled: bool = field(
        default_factory=lambda: _bool_env("HOOGENDOORN_MOCK_ENABLED", True)
    )
    hoogendoorn_temperature_control_type_id: str = os.getenv(
        "HOOGENDOORN_TEMPERATURE_CONTROL_TYPE_ID",
        "",
    )
    hoogendoorn_temperature_parameter_id: str = os.getenv(
        "HOOGENDOORN_TEMPERATURE_PARAMETER_ID",
        "",
    )
    hoogendoorn_humidity_control_type_id: str = os.getenv(
        "HOOGENDOORN_HUMIDITY_CONTROL_TYPE_ID",
        "",
    )
    hoogendoorn_humidity_parameter_id: str = os.getenv(
        "HOOGENDOORN_HUMIDITY_PARAMETER_ID",
        "",
    )
    hoogendoorn_ec_control_type_id: str = os.getenv(
        "HOOGENDOORN_EC_CONTROL_TYPE_ID",
        "",
    )
    hoogendoorn_ec_parameter_id: str = os.getenv(
        "HOOGENDOORN_EC_PARAMETER_ID",
        "",
    )
    hoogendoorn_ph_control_type_id: str = os.getenv(
        "HOOGENDOORN_PH_CONTROL_TYPE_ID",
        "",
    )
    hoogendoorn_ph_parameter_id: str = os.getenv(
        "HOOGENDOORN_PH_PARAMETER_ID",
        "",
    )
    vision_inference_mode: str = os.getenv("VISION_INFERENCE_MODE", "auto")
    vision_model_path: str = os.getenv("VISION_MODEL_PATH", "yolov8n.pt")
    vision_queue_key: str = os.getenv("VISION_QUEUE_KEY", "vision:tasks")
    vision_max_upload_mb: int = int(os.getenv("VISION_MAX_UPLOAD_MB", "10"))
    vision_processing_timeout_minutes: int = int(os.getenv("VISION_PROCESSING_TIMEOUT_MINUTES", "30"))
    vision_confidence_threshold: float = float(os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.25"))
    vision_nms_iou_threshold: float = float(os.getenv("VISION_NMS_IOU_THRESHOLD", "0.45"))
    vision_class_names: str = os.getenv("VISION_CLASS_NAMES", "")
    file_storage_backend: str = os.getenv("FILE_STORAGE_BACKEND", "")
    local_storage_root: str = os.getenv("LOCAL_STORAGE_ROOT", "backend/storage")
    object_storage_provider: str = os.getenv("OBJECT_STORAGE_PROVIDER", "s3")
    object_storage_endpoint: str = os.getenv("OBJECT_STORAGE_ENDPOINT", "")
    object_storage_region: str = os.getenv("OBJECT_STORAGE_REGION", "")
    object_storage_bucket: str = os.getenv("OBJECT_STORAGE_BUCKET", "")
    object_storage_access_key_id: str = os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID", "")
    object_storage_secret_access_key: str = os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "")
    object_storage_public_base_url: str = os.getenv("OBJECT_STORAGE_PUBLIC_BASE_URL", "")
    object_storage_prefix: str = os.getenv("OBJECT_STORAGE_PREFIX", "vision/")
    object_storage_force_path_style: bool = field(
        default_factory=lambda: _bool_env("OBJECT_STORAGE_FORCE_PATH_STYLE", True)
    )
    kb_harvest_enabled: bool = field(default_factory=lambda: _bool_env("KB_HARVEST_ENABLED", True))
    kb_harvest_timeout_seconds: float = float(os.getenv("KB_HARVEST_TIMEOUT_SECONDS", "20"))


settings = Settings()
