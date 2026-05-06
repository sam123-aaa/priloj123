import re
from datetime import date, datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class StrictApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _reject_script_payload(value: Any):
    dangerous_pattern = (
        r"<\s*/?\s*(script|iframe|object|embed|svg|style|link|meta)\b"
        r"|javascript\s*:"
        r"|on(error|click|load|mouseover|focus|submit)\s*="
        r"|expression\s*\("
        r"|url\s*\(\s*['\"]?\s*javascript\s*:"
    )
    if isinstance(value, str) and re.search(dangerous_pattern, value, re.IGNORECASE):
        raise ValueError("HTML/script payload is not allowed")
    return value


class LoginData(StrictApiModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("email must be valid")
        return value.lower()


class RefreshTokenData(StrictApiModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class MeasurementData(StrictApiModel):
    component_id: int = Field(gt=0)
    parameter_name: str = Field(
        min_length=1,
        max_length=120,
        validation_alias=AliasChoices("parameter_name", "metric_name"),
    )
    value: float = Field(ge=-1000000, le=1000000)
    unit: str = Field(min_length=1, max_length=30)

    @field_validator("parameter_name", "unit")
    @classmethod
    def validate_text(cls, value):
        return _reject_script_payload(value)


class FaultConfirmData(StrictApiModel):
    fault_ids: List[int] = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(confirm|reject)$")

    @field_validator("fault_ids")
    @classmethod
    def validate_fault_ids(cls, value):
        if any(item <= 0 for item in value):
            raise ValueError("fault_ids must contain positive integers")
        return value


class RecommendationData(StrictApiModel):
    fault_id: int = Field(gt=0)
    recommendation_text: str = Field(min_length=3, max_length=2000)
    priority: str = Field(min_length=1, max_length=40)

    @field_validator("recommendation_text", "priority")
    @classmethod
    def validate_text(cls, value):
        return _reject_script_payload(value)


class PlanData(StrictApiModel):
    recommendation_ids: List[int] = Field(min_length=1, max_length=100)
    planned_date: date

    @field_validator("recommendation_ids")
    @classmethod
    def validate_recommendation_ids(cls, value):
        if any(item <= 0 for item in value):
            raise ValueError("recommendation_ids must contain positive integers")
        return value

    @field_validator("planned_date", mode="before")
    @classmethod
    def parse_planned_date(cls, value):
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        raise ValueError("planned_date must be in YYYY-MM-DD or DD-MM-YYYY format")


class TaskResultData(StrictApiModel):
    result: str = Field(min_length=1, max_length=2000)

    @field_validator("result")
    @classmethod
    def validate_result(cls, value):
        return _reject_script_payload(value)


class QualityCheckData(StrictApiModel):
    status: str = Field(min_length=1, max_length=40)
    notes: str = Field(min_length=1, max_length=2000)

    @field_validator("status", "notes")
    @classmethod
    def validate_text(cls, value):
        return _reject_script_payload(value)


class ReportData(StrictApiModel):
    report_type: Optional[str] = Field(default=None, max_length=80)
    template_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", value):
            raise ValueError("report_type may contain letters, digits, dot, dash and underscore only")
        return value


class DelayedReportData(ReportData):
    delay_seconds: int = Field(default=10, ge=0, le=3600)


class BffReportCommandData(ReportData):
    delay_seconds: int = Field(default=0, ge=0, le=3600)


class AccountStatusData(StrictApiModel):
    is_active: bool
    admin_password: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value):
        return _reject_script_payload(value)


class RoleChangeData(StrictApiModel):
    role_code: str = Field(min_length=3, max_length=80)
    admin_password: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, value):
        if not re.fullmatch(r"[a-z_]+", value):
            raise ValueError("role_code may contain lowercase letters and underscores only")
        return value

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value):
        return _reject_script_payload(value)


class TaskEnqueueResponse(BaseModel):
    task_id: UUID
    status: str


class TaskStatusResponse(BaseModel):
    task_id: UUID
    status: str
    meta: dict


class WebDashboardItem(BaseModel):
    plan_id: int
    planned_date: date
    equipment_name: str
    tasks_total: int
    tasks_completed: int


class MobileTaskItem(BaseModel):
    task_id: int
    description: str
    status: str
    planned_date: date
    equipment_name: str


class DesktopMonitoringItem(BaseModel):
    fault_id: int
    equipment_name: str
    severity: str
    status: Optional[str]
    detected_at: datetime
