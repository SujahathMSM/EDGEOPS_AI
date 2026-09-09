import inspect
import math
import re

from edgeops.core.errors import RegistryError, UnknownToolError
from edgeops.tools.contracts import Idempotency, RiskLevel, StrictModel, ToolDefinition


class ToolRegistry:
    """Only trusted application startup code registers capabilities."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if not isinstance(definition, ToolDefinition):
            raise RegistryError("Expected a ToolDefinition.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", definition.name):
            raise RegistryError("Invalid tool name.")
        if definition.name in self._tools:
            raise RegistryError("Tool already registered.")
        for schema in (definition.input_schema, definition.output_schema):
            if (not isinstance(schema, type) or not issubclass(schema, StrictModel)
                    or schema.model_config.get("extra") != "forbid"
                    or schema.model_config.get("strict") is not True):
                raise RegistryError("Tool schemas must use strict validation and forbid extras.")
        if not isinstance(definition.risk_level, RiskLevel):
            raise RegistryError("Unknown risk level.")
        if not isinstance(definition.idempotency, Idempotency):
            raise RegistryError("Unknown idempotency behavior.")
        if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", definition.required_permission):
            raise RegistryError("An explicit permission is required.")
        if not math.isfinite(definition.timeout_seconds) or not 0 < definition.timeout_seconds <= 120:
            raise RegistryError("Timeout must be positive and at most 120 seconds.")
        if not inspect.iscoroutinefunction(definition.adapter):
            raise RegistryError("Adapters must be cooperative async functions.")
        if (not callable(definition.target_validator)
                or inspect.iscoroutinefunction(definition.target_validator)):
            raise RegistryError("A synchronous target validator is required.")
        expected = (Idempotency.READ_ONLY if definition.risk_level == RiskLevel.READ_ONLY
                    else Idempotency.KEY_REQUIRED)
        if definition.idempotency != expected:
            raise RegistryError("Risk and idempotency metadata disagree.")
        self._tools[definition.name] = definition

    def resolve(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError:
            raise UnknownToolError("Tool is not registered.") from None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))
