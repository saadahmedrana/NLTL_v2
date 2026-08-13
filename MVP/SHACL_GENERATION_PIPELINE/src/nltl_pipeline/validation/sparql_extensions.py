from __future__ import annotations

import math

from rdflib import Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql.operators import register_custom_function


MATH_NAMESPACE = "http://www.w3.org/2005/xpath-functions/math#"


def _unary(function):
    def evaluate(value: Literal) -> Literal:
        return Literal(function(float(value)), datatype=XSD.double)
    return evaluate


def register_math_functions() -> None:
    """Register the XPath math functions needed by verified formula rules."""
    for local_name, function in {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "atan": math.atan,
    }.items():
        register_custom_function(
            URIRef(MATH_NAMESPACE + local_name),
            _unary(function),
            override=True,
        )
