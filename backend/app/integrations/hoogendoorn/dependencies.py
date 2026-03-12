from functools import lru_cache

from app.core.config import settings
from app.integrations.hoogendoorn.mock_provider import MockHoogendoornProvider
from app.integrations.hoogendoorn.partner_api_provider import PartnerApiHoogendoornProvider
from app.integrations.hoogendoorn.provider import HoogendoornProvider
from app.integrations.hoogendoorn.repository import SensorDataRepository
from app.integrations.hoogendoorn.service import HoogendoornSyncService


@lru_cache
def get_hoogendoorn_provider() -> HoogendoornProvider:
    if settings.hoogendoorn_provider == "partner_api":
        return PartnerApiHoogendoornProvider(settings)
    return MockHoogendoornProvider(settings)


@lru_cache
def get_hoogendoorn_service() -> HoogendoornSyncService:
    return HoogendoornSyncService(
        settings=settings,
        provider=get_hoogendoorn_provider(),
        repository=SensorDataRepository(settings),
    )
