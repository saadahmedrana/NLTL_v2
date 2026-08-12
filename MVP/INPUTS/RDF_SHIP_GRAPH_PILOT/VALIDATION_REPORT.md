# RDF ship graph pilot validation

- Pilot: `NLTL-RDF-SHIP-GRAPH-PILOT-2026-08-12-R1`
- Cases: 4
- RDF variants: 8
- Requirement links: 7
- Expected-pass graphs conforming: 4/4
- Expected-fail graphs non-conforming: 4/4
- pySHACL: `0.31.0`
- RDFLib: `7.6.0`
- Overall result: PASS

| Variant | Level | Expected | Actual | Deliberate changed property | QA |
|---|---|---|---|---|---|
| RQ-IMO-075-PASS | requirement | conforms | conforms | availableSurvivalEquipmentCapacity | PASS |
| RQ-IMO-075-FAIL | requirement | does not conform | does not conform | availableSurvivalEquipmentCapacity | PASS |
| RQ-IMO26-014-PASS | requirement | conforms | conforms | visualIceDetectionIlluminationMeansCount | PASS |
| RQ-IMO26-014-FAIL | requirement | does not conform | does not conform | visualIceDetectionIlluminationMeansCount | PASS |
| INT-001-PASS | integrated | conforms | conforms | bridgeWingsEnclosed | PASS |
| INT-001-FAIL | integrated | does not conform | does not conform | bridgeWingsEnclosed | PASS |
| INT-002-PASS | integrated | conforms | conforms | independentTransducerCount | PASS |
| INT-002-FAIL | integrated | does not conform | does not conform | independentTransducerCount | PASS |
