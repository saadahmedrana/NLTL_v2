import pyshacl
from rdflib import Graph

# ship data
data_graph = Graph()
data_graph.parse("ship.ttl", format="turtle")

# SHACL rules
shapes_graph = Graph()
shapes_graph.parse("rulesV2.ttl", format="turtle")

# validation
result = pyshacl.validate(
    data_graph,
    shacl_graph=shapes_graph,
    inference='rdfs',
    meta_shacl=False
)

conforms, results_graph, results_text = result

if conforms:
    print("Validation successful! The ship meets all requirements.")
    print(results_text)
else:
    print("Validation failed. Issues found:")
    print(results_text)
    