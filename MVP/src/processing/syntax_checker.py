from typing import Dict, List
from rdflib import Graph


def check_turtle_syntax(turtle_text: str) -> Dict[str, List[str] | bool]:
    errors: List[str] = []
    warnings: List[str] = []

    if "@prefix sh:" not in turtle_text and "PREFIX sh:" not in turtle_text:
        warnings.append("No explicit sh: prefix found.")

    if "sh:NodeShape" not in turtle_text and "sh:PropertyShape" not in turtle_text:
        warnings.append("No obvious SHACL shape type found.")

    graph = Graph()
    try:
        graph.parse(data=turtle_text, format="turtle")
        syntax_valid = True
    except Exception as exc:
        syntax_valid = False
        errors.append(str(exc))

    return {
        "syntax_valid": syntax_valid,
        "errors": errors,
        "warnings": warnings,
    }