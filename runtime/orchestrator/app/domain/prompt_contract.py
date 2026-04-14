"""Day06 Step1 prompt and token contract skeletons."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel


class PromptRenderMode(StrEnum):
    """Stable render modes reserved for future provider consumption."""

    EXECUTION = "execution"
    VERIFICATION = "verification"


class TokenAccountingMode(StrEnum):
    """How the token usage snapshot was produced."""

    HEURISTIC = "heuristic"
    PROVIDER_REPORTED = "provider_reported"
    PROVIDER_MOCK = "provider_mock"


class ProviderReceiptSource(StrEnum):
    """Source category for one provider-like usage receipt."""

    REAL_PROVIDER = "real_provider"
    PROVIDER_MOCK = "provider_mock"


class PromptTemplateRef(DomainModel):
    """Registry identifier for one prompt contract."""

    prompt_key: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("prompt_key", "version")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim text identifiers and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Prompt template fields cannot be blank.")
        return normalized_value


class PromptRegistryEntry(DomainModel):
    """One prompt entry exposed by the minimal runtime registry."""

    template_ref: PromptTemplateRef
    render_mode: PromptRenderMode = PromptRenderMode.EXECUTION
    system_instruction: str = Field(min_length=1, max_length=2_000)
    include_acceptance_criteria: bool = True
    include_context_summary: bool = True
    include_routing_summary: bool = True

    @field_validator("system_instruction")
    @classmethod
    def normalize_system_instruction(cls, value: str) -> str:
        """Normalize the registry-level system instruction."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("system_instruction cannot be blank.")
        return normalized_value


class PromptSection(DomainModel):
    """One rendered prompt section."""

    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=4_000)

    @field_validator("key", "title", "content")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim section values and reject blank text."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Prompt section fields cannot be blank.")
        return normalized_value


class BuiltPromptEnvelope(DomainModel):
    """Rendered prompt payload reserved for future provider adapters."""

    template_ref: PromptTemplateRef
    render_mode: PromptRenderMode = PromptRenderMode.EXECUTION
    provider_key: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=100)
    sections: list[PromptSection] = Field(default_factory=list, max_length=20)
    prompt_text: str = Field(min_length=1, max_length=20_000)
    prompt_char_count: int = Field(ge=0)

    @field_validator("prompt_text")
    @classmethod
    def normalize_prompt_text(cls, value: str) -> str:
        """Normalize rendered prompt text."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("prompt_text cannot be blank.")
        return normalized_value


class ProviderUsageReceipt(DomainModel):
    """Provider usage/receipt payload later mapped into token accounting."""

    provider_key: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    receipt_id: str = Field(min_length=1, max_length=100)
    receipt_source: ProviderReceiptSource = ProviderReceiptSource.REAL_PROVIDER
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    pricing_source: str = Field(min_length=1, max_length=100)

    @field_validator("provider_key", "model_name", "receipt_id", "pricing_source")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim receipt text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Provider usage receipt fields cannot be blank.")
        return normalized_value

    @model_validator(mode="after")
    def normalize_total_tokens(self) -> "ProviderUsageReceipt":
        """Keep total tokens aligned with prompt/completion token counts."""

        minimum_total_tokens = self.prompt_tokens + self.completion_tokens
        if self.total_tokens < minimum_total_tokens:
            self.total_tokens = minimum_total_tokens
        return self


class TokenAccountingSnapshot(DomainModel):
    """Minimal Day06 token accounting contract attached to one run."""

    accounting_mode: TokenAccountingMode = TokenAccountingMode.HEURISTIC
    template_ref: PromptTemplateRef
    provider_key: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=100)
    provider_receipt_id: str | None = Field(default=None, max_length=100)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    pricing_source: str = Field(min_length=1, max_length=100)

    @field_validator("provider_receipt_id", "pricing_source")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim text fields and reject blank non-null values."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Token accounting text fields cannot be blank.")
        return normalized_value

    @model_validator(mode="after")
    def normalize_total_tokens(self) -> "TokenAccountingSnapshot":
        """Keep snapshot total tokens aligned with prompt/completion tokens."""

        minimum_total_tokens = self.prompt_tokens + self.completion_tokens
        if self.total_tokens < minimum_total_tokens:
            self.total_tokens = minimum_total_tokens
        return self
