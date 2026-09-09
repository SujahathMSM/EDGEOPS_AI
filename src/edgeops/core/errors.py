"""Internal errors never expose adapter exception messages to callers."""


class RegistryError(ValueError):
    """Invalid or duplicate tool registration."""


class UnknownToolError(LookupError):
    """The requested capability is not registered."""
