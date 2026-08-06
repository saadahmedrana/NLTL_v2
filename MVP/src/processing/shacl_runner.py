from pathlib import Path
from typing import Any, Dict

import pyshacl
from rdflib import Graph


def run_shacl_validation(
    shacl_text: str,
    data_graph_path: str | Path,
) -> Dict[str, Any]:
    data_graph_path = Path(data_graph_path)

    data_graph = Graph()
    shapes_graph = Graph()

    try:
        data_graph.parse(data_graph_path, format="turtle")
    except Exception as exc:
        return {
            "execution_ok": False,
            "conforms": None,
            "results_text": "",
            "error": f"Failed to parse data graph '{data_graph_path}': {exc}",
        }

    try:
        shapes_graph.parse(data=shacl_text, format="turtle")
    except Exception as exc:
        return {
            "execution_ok": False,
            "conforms": None,
            "results_text": "",
            "error": f"Failed to parse SHACL graph: {exc}",
        }

    try:
        conforms, results_graph, results_text = pyshacl.validate(
            data_graph,
            shacl_graph=shapes_graph,
            inference="rdfs",
            meta_shacl=False,
        )
        return {
            "execution_ok": True,
            "conforms": bool(conforms),
            "results_text": str(results_text),
            "error": "",
        }
    except Exception as exc:
        return {
            "execution_ok": False,
            "conforms": None,
            "results_text": "",
            "error": f"pySHACL execution failed: {exc}",
        }