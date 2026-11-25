# v0.9.1 I2-004 bounded operational check

**Workflow outcome: NO_VERDICT.** One fresh candidate, no internal acceptance. The frozen controller stopped at REVIEWER_FORMAT_FAILURE after one review and its single format retry. No second candidate, SHACL repair, seed, regeneration, rerun, Single-shot or extra requirement was dispatched.

## Approval, freeze and isolation

The user's current-conversation approval is recorded verbatim in approval_reference.txt and the new approved scope. The draft is preserved. The approved common scope retains definition hash66e222d93338d440d53a5b380a93fd10716f061ea215a06edd6646e7656a3561 and the selected I2 Rev4/I1 Rev2 experimental editions; no real-vessel/date/legal eligibility certification is claimed. Installed/source v0.9.1 matched before dispatch; Git revision/working changes, exact source/schema/prompts/configs and hashes are frozen. Base configuration and production code are unchanged. Runtime file-access tests denied original evaluation, witness, solution and historical-shape resources. Actual outbound payloads contain common scope only; no evaluation node/case IDs or counterparts. Evaluation started only after dispatch_closed.json.

## Exercised versus unexercised

| Step | Observed evidence |
|---|---|
| Real provider requests/response handling | Three completed responses from configured model/endpoint; no truncation or network failure |
| Root activation | Active nltl:ship root; reachable constraints; no deactivation |
| Local query execution | Actual pySHACL probe completed, conformance deliberately ignored |
| Context retrieval | One of two permitted rounds; UR I1 Rev2 and bounded I2 source passages retrieved, 12,577 new characters; schema evidence retrieved; partial/missing dependencies retained |
| Review | One primary review and one format retry; valid JSON but neither validated as grounded review |
| SHACL repair/diffs/regression checking | **Unexercised**: terminal review failure before repair; no candidate edits |
| Independent execution | All six original inputs and three counterparts executed after dispatch closed |

## Why review stopped

Both attempts fail exactly at `$.issues[0].evidence_excerpt`, code UNSUPPORTED_SCHEMA_EVIDENCE/category UNSUPPORTED_SCHEMA_ASSERTION. First quote is the property's recommendedUnit triple; retry quote is its rdfs:range QuantityValue triple. Both triples actually exist in the locked ontology, and the source/candidate quotations are exact. They are rendered by the model as N-Triples while context evidence is JSON arrays/metadata; neither is a literal substring accepted by the frozen checker. This is a demonstrated evidence-serialization/interface failure, **not proof that those ontology facts were invented**. Retry did not fix it. The retry also adds two reconciliations despite an empty original prior_issues list; that latent protocol error was not reached because evidence validation failed first. Raw responses, normalized JSON, exact errors and retry request are preserved. No checks were weakened.

The review's source/code reasoning identifies a real one-sided comparison: `FILTER (?caseValue > ?upperValue)` detects a selected value below a case but permits it above every case. The source requires the greatest displacement. This is a static source/code finding, not a new compliance witness or a validated pipeline finding. The completeness-of-waterline-collection concern remains an interpretive/data-adequacy question, not a confirmed schema defect. Retry also calls prefix execution materially unverified, while the actual probe succeeded; positive probe evidence is saved but not explicitly supplied in the review body. No unsupported new completeness/cardinality contract was added.

## Results — do not pool diagnostic and workflow credit

| Metric | Workflow selection | Unaccepted candidate1 diagnostic |
|---|---:|---:|
| Positive acceptance | 0/3;3 NO_VERDICT | 3/3 |
| Strict intended detection | 0/3;3 NO_VERDICT | 3/3 |
| Unrelated/additional rejection | 0 | 0 |
| Missed intended defect | 0;none executable as selected | 0 on reviewed cases |
| Unresolved attribution | 0;all selected results NO_VERDICT | 0 on reviewed pairs |
| Ordinary agreement | 0/6;6 NO_VERDICT | 6/6 |
| Intended-only counterparts | 0/3;3 NO_VERDICT | 3/3 pass |

F01 reports the exact lower-than-case SPARQL constraint; F02 reports selected-displacement minCount; F03's outer node report links to the intended unit hasValue detail. There are no unrelated failures, and every intended-only counterpart passes the full unchanged shape. Blank-node IDs/message text were not used as semantic proof. The three negative pairs do not exercise the above-maximum gap, so diagnostic success is not full regulatory correctness or workflow accuracy. Other cardinality/data-completeness scope remains unverified.

## Resources and next step

3 actual provider calls:1 generation,1 review,1 reviewer-format retry,0 repairs. Input tokens157,885;output tokens9,486;total167,371. Reasoning tokens3,886 are included in output;cached input1,429 is included in input. Provider time58.96s;pipeline elapsed59.93s. Independent evaluation time is separate.

Recommendation: repair the reviewer evidence-format/retry interface offline before another live check. Preserve evidence verification; make supplied fact representations/expected quotation format unambiguous and keep format retries from manufacturing prior-issue reconciliation. No implementation change or further model call was made. Historical results, labels, fixtures, exclusions and tracker remain unchanged.
