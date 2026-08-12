# Stage 1 naming audit report

Date: 2026-08-11  
Project: NLTL_v2 / MVP  
Status: Stage 1 naming audit complete; no final RDF/JSON-LD ontology or SHACL vocabulary profile has been emitted.

## Outcome

The shortlist now contains **823 distinct candidate concepts** linked to **all 313 locked requirements**. The earlier workbook display of 831 rows meant one header plus 830 candidate rows. The naming audit consolidated duplicate semantic candidates and alternate formula spellings, split collapsed references where they represented different standards, and added readable clause-defined formula inputs. The net result is 823 candidates with no loss of requirement coverage.

All 823 proposed local names:

- are unique;
- match ASCII-safe lowerCamelCase (`^[a-z][A-Za-z0-9]*$`);
- have at least one retained source alias, a verified evidence excerpt, requirement links, a naming basis, a naming authority, an applied rule, and a QA result;
- contain no unit suffix in the canonical name;
- contain no opaque generated prefixes such as `term...` or `clause...`;
- passed the naming QA recorded in `NAMING_AUDIT` and `TERMINOLOGY_SHORTLIST`.

Confidence for the naming decision is **High for 117 candidates** and **Medium for 706 candidates**. Medium means the name is a transparent regulation-anchored normalization or benchmark coinage, not that it is an unresolved blocker.

## Naming basis counts

| Naming basis | Count | Defence |
|---|---:|---|
| Locked-workbook normalized regulatory term | 362 | The descriptive locked variable is normalized to ASCII lowerCamelCase and retained as an alias. |
| Benchmark-coined descriptive engineering term | 338 | The name is constructed from the subject/component, characteristic, and qualifier/state stated or required by the verified clause. |
| Unit-stripped normalized regulatory variable | 82 | Unit text is removed from the identifier and retained in unit/quantity metadata. |
| Verified exact implementation term | 22 | The exact Haitham SSP URI/local name and semantic context were verified. |
| Explicit regulation-reference transcription | 10 | The governing instrument is named and separators are spelled as `Point` or `Dash` to avoid ambiguous digit strings. |
| Regulatory symbol expanded from a directly verified definition | 9 | The regulation's stated engineering meaning is used; the original symbol remains an alias. |

These categories describe the **name's provenance**. A QUDT or W3C URI may separately support a unit or datatype without being claimed as the source of the property name.

## Deterministic naming rules

1. **N1 – verified exact reuse:** reuse only after exact URI/local-name and semantic-context verification.
2. **N2 – regulatory symbol expansion:** use the meaning defined by the clause and retain the symbol as an alias.
3. **N3 – unit separation:** keep units and quantity kinds in metadata, not in the local name.
4. **N4 – transparent normalization:** preserve the source concept while converting its descriptive label to ASCII lowerCamelCase.
5. **N5 – clause-anchored coinage:** when no reusable verified term exists, construct subject/component + characteristic + qualifier/state.
6. **N6 – regulation-reference transcription:** name the governing instrument and spell numeric separators to prevent collisions.
7. **N7 – no lexical-only mapping:** do not populate DNV, QUDT, W3C, Haitham, Rana, or AnchorMap mappings from similar spelling alone.

## Examples of corrections made

- `PWOM_present` is now `polarWaterOperationalManualPresent`, not the information-losing `present`.
- `P_min_UIWL_kW` and `P_min_LIWL_kW` are now `minimumRequiredPowerAtUpperIceWaterline` and `minimumRequiredPowerAtLowerIceWaterline`; kW remains unit metadata.
- `sigma_fl`, `sigma_fat`, `gamma_e1`, `gamma_e2`, `gamma_v`, `gamma_m`, and `sigma_exp` use readable names based on the definitions directly verified in TRAFICOM sections 6.6.2.3–6.6.2.4; the equation symbols remain aliases.
- `gamma_stem` is now `stemAngle`, based on the definition directly verified in IACS UR I2.13.2.1.
- `SOLAS_V_22_1_9_4_compliance_status` is now `solasRegulationV22Point1Point9Point4ComplianceStatus`, rather than `term22194ComplianceStatus`.
- `STCW_II_2_status` and `STCW_A_II_2_status` are separate candidates because they refer to the STCW Convention regulation and STCW Code section, respectively.
- Duplicate candidates created by alternate spellings or formula notation were merged, including thrust variables, fatigue/yield-strength variables, and reversed `bending/shear` wording.

## DNV/Vista use

DNV terminology was not forced onto properties for which no exact public identifier was verified. DNV describes GMOD as a hierarchical ship data structure, and the official Vista SDK separates GMOD paths from metadata codebooks and data-channel naming. This supports using GMOD for reproducible component/system paths and codebooks where exact codes are available, not treating a similar English phrase as an exact property mapping. See the [DNV Vista tools documentation](https://docs.vista.dnv.com/docs/tools/) and the [official DNV Vista SDK](https://github.com/dnv-opensource/vista-sdk).

The official SDK resource directory exposed versioned GMOD/codebook files through VIS 3.11a when checked on 2026-08-11. Because no exact versioned code/path was reproducibly established for the shortlisted regulatory properties, the workbook records **zero claimed exact DNV GMOD mappings** rather than speculative ones. This is intentional and defensible.

## Treatment of the former unresolved items

The three previous rows were not all vocabulary blockers:

- **w3id registration** is now `ACT-01`, a publication action. It must be completed or replaced by a final institutional URI before public ontology release, but it does not affect Stage 1 names.
- **ISO 19848 unavailability** is now `LIM-01`, a documented source limitation. No normative ISO definition or identifier is claimed. Public DNV material is contextual only.
- **short formula-symbol review** is now `QA-01`, resolved by the symbol-expansion/alias policy and direct PDF checks.

The required `UNRESOLVED` sheet is retained as a register and now states that no blocking Stage 1 naming issue remains. Non-blocking items are kept in `PUBLICATION_LIMITATIONS` so they are not forgotten or misrepresented.

## Coverage and activation status

- Locked requirements: **313**
- Covered by candidate concepts: **313**
- Direct/deterministic Stage 2 candidates: **240**
- Complex/evidence workflow deferred: **40**
- Dynamic/history/simulation deferred: **17**
- Physical-test evidence only: **16**

The 16 physical-test requirements remain recorded for vocabulary and evidence modelling but are not active SHACL-inferred physical results.

## Compatibility controls retained

- Exact Haitham SSP mappings: **22** shortlisted names after consolidation.
- Exact DNV GMOD mappings claimed: **0**; no lexical-only mappings.
- Verified QUDT unit URIs are retained only in unit metadata.
- Exact W3C datatype URIs are emitted only for a single determined XSD datatype; review unions do not produce malformed pseudo-URIs.
- `BROKENONTOLOGYFROMGITHUB` remains excluded from naming and mapping authority.
- Haitham's final Turtle files remain valid implementation evidence; all 111 SSP local names referenced by the final rules occur in the final ship graph.

## Review decision required before Stage 2

No additional technical source is required to review Stage 1. The remaining decision is whether to approve:

1. the 823-name shortlist and the seven-rule naming policy as the controlled Stage 1 evidence base; and
2. progression to Stage 2 using the already accepted 240 direct/deterministic activation boundary.

Namespace registration and licensed ISO 19848 access can be handled later as publication governance or optional alignment work; neither should block approval of this naming audit.
