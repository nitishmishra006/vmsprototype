"""Pydantic schemas for API request / response bodies."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthModelStatus(BaseModel):
    name: str
    loaded: bool
    device: str | None = None
    group: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    load_time_s: float | None = None
    loaded_at: float | None = None
    last_used: float | None = None
    load_error: str | None = None


class FeatureStatus(BaseModel):
    """A capability the UI can enable/disable. ``available=False`` means the model
    is missing — the UI shows it as unavailable rather than faking results."""

    name: str
    available: bool
    detail: str = ""
    fix_command: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    phase: int
    device: str
    device_reason: str
    database: bool
    storage: bool
    models: list[HealthModelStatus] = Field(default_factory=list)
    features: list[FeatureStatus] = Field(default_factory=list)


class MetricsResponse(BaseModel):
    process_rss_mb: float
    process_cpu_percent: float
    system_ram_total_mb: float
    system_ram_available_mb: float
    system_ram_percent: float
    gpu: dict[str, Any] | None = None


class SetupItem(BaseModel):
    key: str
    label: str
    ok: bool
    detail: str = ""
    fix_command: str | None = None


class SetupStatusResponse(BaseModel):
    ok: bool
    items: list[SetupItem]


class SettingValue(BaseModel):
    key: str
    value: Any
    source: Literal["env", "override"]
    type: str


class SettingsResponse(BaseModel):
    settings: list[SettingValue]


class SettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any] = Field(default_factory=dict)
    #: keys to reset back to the .env / default value
    reset: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
