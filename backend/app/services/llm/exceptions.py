class LLMConfigurationError(RuntimeError):
    """Raised when no usable provider config is available."""


class LLMInvocationError(RuntimeError):
    """Raised when the model call fails."""


class LLMOutputParseError(RuntimeError):
    """Raised when the model output cannot be parsed into the target schema."""

