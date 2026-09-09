from dataclasses import replace
import unittest

from edgeops.tools.contracts import Actor, PolicyDecision, RiskLevel, Target
from edgeops.tools.definitions.demo import build_demo_registry
from edgeops.tools.policy import PolicyEngine


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.target = Target(host_id="demo-host")
        self.actor = Actor("user", frozenset({"tools.host.read"}), frozenset({self.target}))
        self.definition = build_demo_registry().resolve("get_demo_host_health")
        self.policy = PolicyEngine()

    def test_read_only_allowed(self):
        self.assertEqual(self.policy.evaluate(self.definition, self.actor, self.target),
                         PolicyDecision.ALLOW_AUTOMATICALLY)

    def test_all_mutations_require_approval(self):
        for risk in (RiskLevel.LOW_RISK, RiskLevel.MEDIUM_RISK, RiskLevel.HIGH_RISK):
            with self.subTest(risk=risk):
                self.assertEqual(self.policy.evaluate(replace(self.definition, risk_level=risk),
                                 self.actor, self.target), PolicyDecision.REQUIRE_APPROVAL)

    def test_forbidden_denied(self):
        self.assertEqual(self.policy.evaluate(replace(self.definition, risk_level=RiskLevel.FORBIDDEN),
                         self.actor, self.target), PolicyDecision.DENY)

    def test_missing_permission_denied(self):
        self.assertEqual(self.policy.evaluate(self.definition, replace(self.actor, permissions=frozenset()),
                         self.target), PolicyDecision.DENY)

    def test_target_scope_includes_environment_and_resource(self):
        for target in (Target(host_id="other"), Target(host_id="demo-host", environment="production"),
                       Target(host_id="demo-host", resource_id="database")):
            with self.subTest(target=target):
                self.assertEqual(self.policy.evaluate(self.definition, self.actor, target), PolicyDecision.DENY)
