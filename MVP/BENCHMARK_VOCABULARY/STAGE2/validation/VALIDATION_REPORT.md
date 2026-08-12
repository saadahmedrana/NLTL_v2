# Stage 2 validation report

Status: **PASS**

Checks passed: **42**

- canonical term count: PASS — 821
- Stage 1 candidate lineage: PASS — 823
- one documented semantic merge: PASS — 1
- one incoherent generic candidate retired: PASS — ['VOC-0747']
- documented naming refinements: PASS — 12
- unique local names: PASS — 821
- ASCII lowerCamelCase: PASS — 821/821
- all names have traceability: PASS — 821/821
- superseded names excluded from canonical set: PASS — []
- canonical local names contain no unit tokens: PASS — {}
- generic multi-dimension fallback term excluded: PASS — excluded and redirected
- term-kind total: PASS — {'Class': 76, 'DatatypeProperty': 463, 'ObjectProperty': 24, 'QuantityProperty': 258}
- no answer logic flag: PASS — False
- deadweight is a unit-separated mass quantity: PASS — QuantityProperty
- continuous-daylight applicability is Boolean: PASS — xsd:boolean
- S-N notation has readable canonical name: PASS — xsd:string
- no substring-induced operation/administration quantities: PASS — []
- ontology declarations match registry: PASS — 821
- Turtle/RDFXML graph equivalence: PASS — {'ttl': 16104, 'rdfxml': 16104}
- one schema property shape per property: PASS — 745
- candidate shapes contain no cardinality answers: PASS — 0 candidate cardinalities
- no thresholds/formulas/answer constraints: PASS — 0
- protected JSON-LD context: PASS — True
- context covers every approved name: PASS — 821
- JSON-LD context expands illustrative graph: PASS — {'jsonld': 12, 'turtle': 12}
- master profile exact term set: PASS — 821
- master profile requirement count: PASS — 313
- direct profile requirement count: PASS — 240
- all profiles are whitelists only: PASS — ['traficom', 'imo_polar_code', 'direct_deterministic', 'iacs_ur_i2', 'evidence_and_deferred', 'master', 'imo_amend_2026']
- all profile terms use master URIs: PASS — 7
- source profiles cover all requirements: PASS — 313
- verified Haitham exact mapping count: PASS — 22
- no unsafe OWL equivalence to legacy model: PASS — 0
- no claimed DNV exact URI: PASS — 0
- positive example conforms: PASS — deterministic schema-only fallback: conforms
- negative missing-unit example rejected: PASS — deterministic schema-only fallback: https://example.org/nltl-stage2-invalid/q: expected exactly one IRI-valued qudt:unit
- unit IRIs are absolute and syntactically clean: PASS — 255
- all asserted units are in external URI evidence: PASS — 28
- every quantity has an explicit unit decision: PASS — 258
- only source-ambiguous viscosity lacks a global recommended unit: PASS — ['manufacturerMaxViscosity', 'manufacturerMinViscosity', 'observedViscosity']
- quantity terms use QuantityValue: PASS — 258
- core regulated enumerations use IRIs: PASS — {'iceClass': 'https://w3id.org/nltl-benchmark/vocab#iceClassValue', 'polarClass': 'https://w3id.org/nltl-benchmark/vocab#polarClassValue', 'shipCategory': 'https://w3id.org/nltl-benchmark/vocab#polarShipCategoryValue'}
