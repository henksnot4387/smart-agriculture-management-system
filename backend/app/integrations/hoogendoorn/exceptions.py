class HoogendoornError(Exception):
    """Base Hoogendoorn integration error."""


class TemporaryHoogendoornError(HoogendoornError):
    """Retryable integration error."""


class ConfigurationHoogendoornError(HoogendoornError):
    """Raised when required provider configuration is missing."""
