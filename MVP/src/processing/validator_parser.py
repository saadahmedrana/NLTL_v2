import json
import re
from typing import Any


def parse_validator_json(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise ValueError("Could not extract valid JSON object from validator output.")
        parsed = json.loads(match.group(0))

    defaults = {
        "decision": "retry",
        "confidence": 0.0,
        "semantic_match": False,
        "syntax_valid": False,
        "expected_outcome": "unknown",
        "actual_outcome": "unknown",
        "ship_behavior_correct": False,
        "reason_alignment": False,
        "applicability_handled_correctly": False,
        "facts_used": [],
        "regulation_interpretation": "",
        "applicability_explanation": "",
        "justification": "",
        "issues": [],
        "suggested_fix": "",
    }

    for key, value in defaults.items():
        parsed.setdefault(key, value)

    return parsed