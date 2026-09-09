from edgeops.tools.contracts import Actor, PolicyDecision, RiskLevel, Target, ToolDefinition


class PolicyEngine:
    def evaluate(self, definition: ToolDefinition, actor: Actor, target: Target) -> PolicyDecision:
        if definition.required_permission not in actor.permissions or target not in actor.allowed_targets:
            return PolicyDecision.DENY
        if definition.risk_level == RiskLevel.FORBIDDEN:
            return PolicyDecision.DENY
        if definition.risk_level == RiskLevel.READ_ONLY:
            return PolicyDecision.ALLOW_AUTOMATICALLY
        return PolicyDecision.REQUIRE_APPROVAL
