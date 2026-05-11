import json
import re
from typing import Any


def extract_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if not content:
        raise ValueError("empty response")
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
