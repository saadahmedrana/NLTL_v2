# R12 verification policy provenance

R12 mechanically corrects TRF-055 and supplied DIRECT_CALCULATION metadata. Every future COMPLETE DIRECT_CALCULATION contract must contain non-empty operandTerms, resultTerms, and comparisonModel. Validation must stop rather than invent missing metadata. No API transport or retry behavior changed.
