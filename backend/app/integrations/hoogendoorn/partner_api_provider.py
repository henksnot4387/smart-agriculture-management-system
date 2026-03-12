from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

import httpx

from app.core.config import Settings
from app.integrations.hoogendoorn.exceptions import (
    ConfigurationHoogendoornError,
    TemporaryHoogendoornError,
)
from app.integrations.hoogendoorn.provider import HoogendoornProvider
from app.integrations.hoogendoorn.types import ControlInstance, MeasurementDefinition, SensorPoint

logger = logging.getLogger("app.integrations.hoogendoorn.partner_api")


class PartnerApiHoogendoornProvider(HoogendoornProvider):
    provider_name = "partner_api"

    def __init__(self, settings: Settings):
        self._settings = settings
        self._cached_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def fetch_control_instances(
        self,
        system_id: str,
        control_type_id: str,
    ) -> list[ControlInstance]:
        response = await self._request(
            "GET",
            f"/api/v4/systems/{system_id}/controlinstances",
            params={"controlTypeId": control_type_id},
        )
        payload = response.json()
        return [
            ControlInstance(
                type_id=item["typeId"],
                instance_id=item["instanceId"],
                instance_name=item["instanceName"],
            )
            for item in payload
        ]

    async def fetch_series(
        self,
        system_id: str,
        measurement: MeasurementDefinition,
        instances: list[ControlInstance],
        start: datetime,
        end: datetime,
    ) -> list[SensorPoint]:
        if not instances:
            return []

        response = await self._request(
            "POST",
            f"/api/v4/systems/{system_id}/parameters/series",
            json={
                "Parameters": [
                    {
                        "ControlInstanceId": instance.instance_id,
                        "ParameterId": measurement.parameter_id,
                    }
                    for instance in instances
                ],
                # Hoogendoorn Partner API expects UTC time encoded as a naive string.
                # Example: local 2026-03-03 09:00 (+08:00) must be sent as 2026-03-03T01:00:00.
                "Start": start.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds"),
                "End": end.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds"),
            },
        )

        instance_map = {instance.instance_id: instance for instance in instances}
        points: list[SensorPoint] = []
        payload = response.json()
        parameter_sets = payload if isinstance(payload, list) else payload.get("Parameters", [])
        for parameter in parameter_sets:
            instance = instance_map.get(
                parameter.get("ControlInstanceId") or parameter.get("controlInstanceId")
            )
            if instance is None:
                continue
            for item in parameter.get("values", []):
                value = item.get("value")
                if value in ("", None):
                    continue
                normalized_value = self._normalize_value(value)
                if normalized_value is None:
                    continue
                recorded_at = datetime.fromisoformat(item["dateTime"])
                if recorded_at.tzinfo is None:
                    # Real API responses also encode UTC as a naive timestamp and provide
                    # utcOffset only as display metadata. Do not add +08:00 again here.
                    recorded_at = recorded_at.replace(tzinfo=UTC)
                points.append(
                    SensorPoint(
                        metric_key=measurement.metric_key,
                        control_type_id=measurement.control_type_id,
                        parameter_id=measurement.parameter_id,
                        control_type_name=measurement.control_type_name,
                        parameter_name=measurement.parameter_name,
                        instance_id=instance.instance_id,
                        instance_name=instance.instance_name,
                        recorded_at=recorded_at.astimezone(UTC),
                        utc_offset_minutes=int(item.get("utcOffset", 0)),
                        value=normalized_value,
                        module=measurement.module,
                        module_label=measurement.module_label,
                        area=measurement.area,
                        value_type=measurement.value_type,
                        unit=measurement.unit,
                        display_name=measurement.display_name,
                        canonical_metric=measurement.canonical_metric,
                    )
                )
        return points

    def _normalize_value(self, value: object) -> float | None:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        normalized = str(value).strip().lower()
        if normalized in {"true", "on", "active", "yes"}:
            return 1.0
        if normalized in {"false", "off", "inactive", "no"}:
            return 0.0
        try:
            return float(normalized)
        except ValueError:
            return None

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        token = await self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(
            base_url=self._settings.hoogendoorn_api_base_url,
            timeout=self._settings.hoogendoorn_timeout_seconds,
        ) as client:
            try:
                response = await client.request(method, path, headers=headers, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500 or exc.response.status_code == 429:
                    raise TemporaryHoogendoornError(str(exc)) from exc
                raise
            except httpx.HTTPError as exc:
                raise TemporaryHoogendoornError(str(exc)) from exc

    async def _get_access_token(self) -> str:
        has_client_credentials = bool(
            self._settings.hoogendoorn_client_id and self._settings.hoogendoorn_client_secret
        )

        if has_client_credentials:
            if (
                self._cached_token
                and self._token_expires_at
                and datetime.now(UTC) < self._token_expires_at
            ):
                return self._cached_token
        elif self._settings.hoogendoorn_api_token:
            return self._settings.hoogendoorn_api_token
        else:
            raise ConfigurationHoogendoornError(
                "Missing Hoogendoorn credentials. Set HOOGENDOORN_CLIENT_ID/HOOGENDOORN_CLIENT_SECRET or HOOGENDOORN_API_TOKEN."
            )

        async with httpx.AsyncClient(timeout=self._settings.hoogendoorn_timeout_seconds) as client:
            try:
                response = await client.post(
                    self._settings.hoogendoorn_token_url,
                    data={
                        "client_id": self._settings.hoogendoorn_client_id,
                        "client_secret": self._settings.hoogendoorn_client_secret,
                        "grant_type": "client_credentials",
                        "scope": self._settings.hoogendoorn_scope,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500 or exc.response.status_code == 429:
                    raise TemporaryHoogendoornError(str(exc)) from exc
                raise
            except httpx.HTTPError as exc:
                raise TemporaryHoogendoornError(str(exc)) from exc

        payload = response.json()
        self._cached_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=max(expires_in - 60, 60))
        logger.info("Fetched Hoogendoorn access token")
        return self._cached_token
