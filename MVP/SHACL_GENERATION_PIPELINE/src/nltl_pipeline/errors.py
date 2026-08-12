class PipelineError(RuntimeError):
    """Base class for controlled pipeline failures."""


class ConfigurationError(PipelineError):
    """Configuration or locked-input contract is invalid."""


class ApiError(PipelineError):
    """Non-retryable API failure."""


class ResponseContractError(PipelineError):
    """An LLM response does not satisfy the local response contract."""


class VocabularyGapError(PipelineError):
    """No verified canonical vocabulary term can satisfy a needed concept."""

