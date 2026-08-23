# R8 verification policy

This policy is source/formalism-driven and was not derived from model success or failure.

Static uses direct SHACL verification. Static Calculation uses direct numerical verification only for the supported basic arithmetic subset: +, -, *, /, comparisons, min/max, simple piecewise branches, integer powers, fixed constants, and ordinary table selection. A fixed constant such as sqrt(3) alone does not make a requirement Complex.

Complex uses COMPLEX_READINESS when direct source compliance requires roots on variable expressions, fractional or negative powers, trigonometry, interpolation, nonlinear/direct structural analysis, externally delegated procedures, or another method outside the basic subset. Formulae remain semantic metadata. SHACL verifies applicability, inputs, owners/paths, datatypes/units, calculation/evidence structures, outputs, and explicit DIRECT_CHECK residuals; it is not required to reconstruct the full engineering calculation.
