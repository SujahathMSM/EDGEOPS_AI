from dataclasses import replace
import unittest

from edgeops.core.errors import RegistryError, UnknownToolError
from edgeops.tools.contracts import Idempotency, StrictModel
from edgeops.tools.definitions.demo import build_demo_registry
from edgeops.tools.registry import ToolRegistry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_demo_registry()
        self.definition = self.registry.resolve("get_demo_host_health")

    def test_register_resolve_and_list(self):
        self.assertEqual(self.definition.name, "get_demo_host_health")
        self.assertEqual(len(self.registry.names()), 2)

    def test_unknown(self):
        with self.assertRaises(UnknownToolError):
            self.registry.resolve("arbitrary_shell")

    def test_duplicate_does_not_replace_original(self):
        with self.assertRaises(RegistryError):
            self.registry.register(self.definition)
        self.assertIs(self.registry.resolve(self.definition.name), self.definition)

    def test_invalid_metadata(self):
        for changes in (
            {"name": "shell;echo"}, {"required_permission": ""},
            {"timeout_seconds": 0}, {"timeout_seconds": float("nan")},
            {"timeout_seconds": 121}, {"input_schema": dict},
            {"adapter": lambda *_: {}}, {"target_validator": None},
            {"idempotency": Idempotency.KEY_REQUIRED}, {"risk_level": "mystery"},
        ):
            with self.subTest(changes=changes), self.assertRaises(RegistryError):
                ToolRegistry().register(replace(self.definition, **changes))

    def test_permissive_schema_rejected(self):
        class Loose(StrictModel):
            model_config = {"extra": "allow"}
        with self.assertRaises(RegistryError):
            ToolRegistry().register(replace(self.definition, input_schema=Loose))
