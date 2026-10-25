"""Generate docs/architecture-diagram.png: the EDGEOPS tool-execution enforcement
pipeline as described in docs/architecture.md. Run from the project root:

    python scripts/generate_architecture_diagram.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BG = "#0d1117"
BOX = "#161b22"
TEXT = "#e6edf3"
MUTED = "#9aa4b2"
FLOW = "#58a6ff"
ALLOW = "#3fb950"
APPROVE = "#f0883e"
DENY = "#f85149"
AUDIT = "#a371f7"

R1_Y, R1_H = 470, 84          # main pipeline row
CH_Y, CH_H = 308, 68          # policy outcome chips band
R2_Y, R2_H = 150, 84          # result snake row
AU_Y, AU_H = 30, 84           # audit row

# (x, y, w, h, label, sublabel, edge)  — main pipeline, left to right
BOXES = [
    (25,   R1_Y, 190, R1_H, "Actor + ToolRequest", "trusted caller supplies identity", FLOW),
    (235,  R1_Y, 165, R1_H, "Validate envelope",   "strict, no field echo", FLOW),
    (420,  R1_Y, 155, R1_H, "Registry lookup",     "unknown -> UNKNOWN_TOOL", FLOW),
    (595,  R1_Y, 165, R1_H, "Validate arguments",  "strict input schema", FLOW),
    (780,  R1_Y, 150, R1_H, "Policy engine",       "perm / scope / risk", FLOW),
    (950,  R1_Y, 160, R1_H, "Target validator",    "must return True", FLOW),
    (1130, R1_Y, 180, R1_H, "Adapter",             "bounded timeout", FLOW),
    # result snake, right to left
    (1140, R2_Y, 160, R2_H, "Revalidate output", "", FLOW),
    (930,  R2_Y, 170, R2_H, "Redact secrets", "", FLOW),
    (690,  R2_Y, 190, R2_H, "Result envelope", "", FLOW),
]

# (x, y, w, h, label, sublabel, edge) — outcome chips directly under the policy engine
CHIPS = [
    (320, CH_Y, 190, CH_H, "DENY", "POLICY_DENIED, no execution", DENY),
    (530, CH_Y, 230, CH_H, "REQUIRE_APPROVAL", "APPROVAL_REQUIRED, no execution", APPROVE),
    (780, CH_Y, 200, CH_H, "ALLOW_AUTOMATICALLY", "permitted: continue", ALLOW),
    (520, AU_Y, 320, AU_H, "Audit log", "one immutable event per attempt", AUDIT),
]

EDGES = [
    # row 1 flow (y = vertical center of row 1)
    (215, 512, 233, 512), (400, 512, 418, 512), (575, 512, 593, 512),
    (760, 512, 778, 512), (930, 512, 948, 512), (1110, 512, 1128, 512),
    # adapter down into the result snake, then right to left
    (1220, R1_Y, 1220, CH_H + R2_Y + 6),          # down past the chips corridor
    (1140, 192, 1104, 192),
    (930, 192, 884, 192),
    # result envelope down to the audit log
    (785, 146, 785, AU_Y + AU_H + 4),
]

BRANCHES = [
    (855, 462, 410, CH_Y + CH_H + 4, DENY),
    (855, 462, 640, CH_Y + CH_H + 4, APPROVE),
    (855, 462, 880, CH_Y + CH_H + 4, ALLOW),
    (984, CH_Y + 34, 1004, 462, ALLOW),   # allowed -> resume at the target validator
]

NOTES = [
    ("EDGEOPS AI — tool-execution enforcement pipeline", (25, 668), TEXT, 15, "bold"),
    ("Every attempt follows the same path; policy outcomes are deterministic and always audited.", (25, 645), MUTED, 9.5, "normal"),
    ("read-only -> run      mutations -> REQUIRE_APPROVAL      forbidden -> DENY", (820, 590), MUTED, 8.5, "normal"),
    ("Adapters: Stage 1 = synthetic fixtures      later stages = host / Docker / HTTP / Git / DB", (865, 78), MUTED, 8.5, "normal"),
    ("continue:  validator -> adapter -> result", (1046, 420), ALLOW, 7.4, "normal"),
]


def draw() -> None:
    fig, ax = plt.subplots(figsize=(13.3, 7.0), dpi=100)
    ax.set_facecolor(BG)
    fig.set_facecolor(BG)
    ax.set_xlim(0, 1330)
    ax.set_ylim(10, 685)
    ax.axis("off")

    for text, (x, y), color, size, weight in NOTES:
        ax.text(x, y, text, color=color, fontsize=size, fontweight=weight, va="top")

    for x, y, w, h, label, sublabel, edge in BOXES:
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=4,rounding_size=8",
                                    facecolor=BOX, edgecolor=edge, linewidth=1.2))
        ax.text(x + w / 2, y + h / 2 + (11 if sublabel else 0), label,
                color=TEXT, fontsize=8.6, fontweight="bold", ha="center", va="center")
        if sublabel:
            ax.text(x + w / 2, y + 14, sublabel, color=MUTED, fontsize=6.8,
                    ha="center", va="bottom")

    for x, y, w, h, label, sublabel, edge in CHIPS:
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=4,rounding_size=8",
                                    facecolor=BOX, edgecolor=edge, linewidth=1.4))
        ax.text(x + w / 2, y + h / 2 + 11, label, color=edge, fontsize=8.0,
                fontweight="bold", ha="center", va="center")
        ax.text(x + w / 2, y + 13, sublabel, color=MUTED, fontsize=6.6,
                ha="center", va="bottom")

    for x0, y0, x1, y1 in EDGES:
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                     mutation_scale=13, color=FLOW, linewidth=1.4,
                                     shrinkA=0, shrinkB=0))

    for x0, y0, x1, y1, color in BRANCHES:
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                     mutation_scale=13, color=color, linewidth=1.4,
                                     shrinkA=0, shrinkB=0))

    out = Path(__file__).resolve().parent.parent / "docs" / "architecture-diagram.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=BG)
    print(f"wrote {out}")


if __name__ == "__main__":
    draw()
