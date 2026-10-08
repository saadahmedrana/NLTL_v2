# Ocean Engineering results

Complete saved evaluation coverage

Equal-weight requirement accuracy averages correct/included-case fractions across requirements with at least one included case. Missing verdicts earn zero. Pooled case accuracy is supplementary. PASS is the positive class.

Original frozen labels are used throughout. RDF_EDIT sensitivity excludes proposed edits, not confirmed invalid cases. Explicit exclusions are a separate scenario and are not automatically unioned with proposed edits.

Official FULL_REPAIR_V2 RUN_01 is separate from the retrospective substitution of 25 rejected fourth-attempt candidates. Historical FULL is excluded. Single selected runs do not support significance claims or general scaling laws.

Workflow manual review covers 70 selected requirements per condition; model review covers ten per model/stage. All manual subset figures are exploratory. The V2 manual review describes the retrospective selection. Semantic and implementation scores are distinct; a major defect remains a major defect regardless of mean score.

N/A is excluded from rubric denominators; blank/UNCLEAR prevents a final numeric score. Unassessable slots remain in verdict counts and are outside numeric means.

NOT_PARSED alone is not evidence of invalid Turtle. Failure comparisons use recorded stage/exception labels; behavioural mismatch causes remain undetermined unless the diagnostics establish them.

## Behavioural results

```csv
policy,condition,stage,requirements,cases,requirement_level_accuracy,supplementary_pooled_case_accuracy,correct,false_accept,false_reject,no_verdict,requirements_with_all_verdicts,exact_requirements,recorded_output_requirements,recorded_no_output_requirements,evaluation_complete,requirements_without_cases
ORIGINAL,FULL_REPAIR_V2,RUN_01,268,2186,0.7369226197419787,0.6733760292772186,1472,95,213,406,236,115,237,31,True,
ORIGINAL,NO_SEMANTIC,RUN_01,268,2186,0.7577577494186881,0.692131747483989,1513,81,386,206,246,115,263,5,True,
ORIGINAL,SINGLESHOT,RUN_01,268,2186,0.6813994343354123,0.6171088746569076,1349,78,352,407,221,98,254,14,True,
ORIGINAL,RETROSPECTIVE_V2_PLUS_REJECTED25,RUN_01,268,2186,0.8021100753212252,0.737419945105215,1612,108,259,207,261,118,262,6,True,
ORIGINAL,luna,FIRST_GENERATION,50,381,0.7160310245310245,0.7217847769028871,275,14,35,57,42,20,50,0,True,
ORIGINAL,sol,FIRST_GENERATION,50,381,0.8793802308802308,0.8818897637795275,336,6,39,0,50,27,50,0,True,
ORIGINAL,gemini,FIRST_GENERATION,50,381,0.7045129870129869,0.7296587926509186,278,39,34,30,45,13,47,3,True,
ORIGINAL,gpt_oss,FIRST_GENERATION,50,381,0.5197193362193362,0.5065616797900262,193,18,46,124,34,8,47,3,True,
ORIGINAL,luna,SELF_REPAIR_FINAL,50,381,0.7149913419913418,0.7086614173228346,270,21,31,59,43,19,43,7,True,
ORIGINAL,sol,SELF_REPAIR_FINAL,50,381,0.813743867243867,0.8241469816272966,314,13,32,22,47,23,47,3,True,
ORIGINAL,gemini,SELF_REPAIR_FINAL,50,381,0.7271796536796536,0.7427821522309711,283,39,34,25,46,14,46,4,True,
ORIGINAL,gpt_oss,SELF_REPAIR_FINAL,50,381,0.46891919191919196,0.4671916010498688,178,8,26,169,28,11,28,22,True,
PROPOSED_RDF_EDIT_SENSITIVITY,FULL_REPAIR_V2,RUN_01,268,2160,0.7396470926157054,0.6763888888888889,1461,95,204,400,236,117,237,31,True,
PROPOSED_RDF_EDIT_SENSITIVITY,NO_SEMANTIC,RUN_01,268,2160,0.761091014412401,0.6949074074074074,1501,80,377,202,246,117,263,5,True,
PROPOSED_RDF_EDIT_SENSITIVITY,SINGLESHOT,RUN_01,268,2160,0.6846867978839699,0.6194444444444445,1338,77,344,401,221,101,254,14,True,
PROPOSED_RDF_EDIT_SENSITIVITY,RETROSPECTIVE_V2_PLUS_REJECTED25,RUN_01,268,2160,0.8065109190877409,0.7398148148148148,1598,108,247,207,261,122,262,6,True,
PROPOSED_RDF_EDIT_SENSITIVITY,luna,FIRST_GENERATION,50,373,0.7242215007215006,0.7238605898123325,270,14,32,57,42,22,50,0,True,
PROPOSED_RDF_EDIT_SENSITIVITY,sol,FIRST_GENERATION,50,373,0.8875707070707071,0.8873994638069705,331,6,36,0,50,29,50,0,True,
PROPOSED_RDF_EDIT_SENSITIVITY,gemini,FIRST_GENERATION,50,373,0.7113701298701298,0.7345844504021448,274,39,32,28,45,15,47,3,True,
PROPOSED_RDF_EDIT_SENSITIVITY,gpt_oss,FIRST_GENERATION,50,373,0.5205764790764791,0.5093833780160858,190,18,45,120,34,9,47,3,True,
PROPOSED_RDF_EDIT_SENSITIVITY,luna,SELF_REPAIR_FINAL,50,373,0.7203246753246754,0.7131367292225201,266,21,29,57,43,20,43,7,True,
PROPOSED_RDF_EDIT_SENSITIVITY,sol,SELF_REPAIR_FINAL,50,373,0.8219343434343435,0.8284182305630027,309,13,29,22,47,25,47,3,True,
PROPOSED_RDF_EDIT_SENSITIVITY,gemini,SELF_REPAIR_FINAL,50,373,0.7353701298701298,0.7453083109919572,278,39,31,25,46,16,46,4,True,
PROPOSED_RDF_EDIT_SENSITIVITY,gpt_oss,SELF_REPAIR_FINAL,50,373,0.4704191919191919,0.4745308310991957,177,8,25,163,28,11,28,22,True,

```

## Exclusion policy and sample sizes

policy,experiment,excluded_cases,included_cases,included_requirements,requirements_without_cases,excluded_case_ids
ORIGINAL,workflow,0,2186,268,,
ORIGINAL,model,0,381,50,,
PROPOSED_RDF_EDIT_SENSITIVITY,workflow,26,2160,268,,I2-008-F02|I2-008-P01|I2-035-F01|I2-035-P01|I2-064-F06|I2-064-P01|IMO-058-F02|IMO-058-P02|TRF-009-F02|TRF-009-P02|TRF-030-F12|TRF-030-P01|TRF-034-F03|TRF-034-P01|TRF-040-F03|TRF-040-P02|TRF-060-F04|TRF-060-P01|TRF-101-F02|TRF-101-P01|TRF-114-F03|TRF-114-P02|TRF-120-F02|TRF-120-P01|TRF-123-F04|TRF-123-P01
PROPOSED_RDF_EDIT_SENSITIVITY,model,8,373,50,,I2-008-F02|I2-008-P01|TRF-060-F04|TRF-060-P01|TRF-101-F02|TRF-101-P01|TRF-123-F04|TRF-123-P01


## Manual review

condition,stage,selected_outputs,CORRECT,MINOR_DEFECT,MAJOR_DEFECT,NOT_ASSESSABLE,UNCLEAR,semantic_mean,semantic_mean_n,implementation_mean,implementation_mean_n,semantic_incomplete_n,implementation_incomplete_n
GPT-5.6 Luna,FIRST_GENERATION,10,3,1,6,0,0,0.8,10,0.7333333333333333,10,0,0
GPT-5.6 Luna,SELF_REPAIR_FINAL,10,5,0,3,2,0,0.8392857142857144,8,0.9166666666666667,8,0,0
GPT-5.6 SOL,FIRST_GENERATION,10,6,3,1,0,0,0.8642857142857142,10,0.9666666666666666,10,0,0
GPT-5.6 SOL,SELF_REPAIR_FINAL,10,6,2,1,1,0,0.8888888888888888,9,1.0,9,0,0
Gemini 3.5 Flash,FIRST_GENERATION,10,3,1,4,2,0,0.8035714285714286,8,1.0,8,0,0
Gemini 3.5 Flash,SELF_REPAIR_FINAL,10,2,1,4,3,0,0.7959183673469389,7,1.0,7,0,0
NO_SEMANTIC,MANUAL_70,70,30,8,29,3,0,0.8646055437100214,67,0.8532338308457712,67,0,0
RETROSPECTIVE_V2_PLUS_REJECTED25,MANUAL_70,70,38,5,27,0,0,0.8734693877551022,70,0.8619047619047618,70,0,0
SINGLESHOT,MANUAL_70,70,22,5,33,10,0,0.819047619047619,60,0.8527777777777777,60,0,0
gpt-oss-120b,FIRST_GENERATION,10,3,0,5,2,0,0.6428571428571429,8,0.625,8,0,0
gpt-oss-120b,SELF_REPAIR_FINAL,10,2,0,2,6,0,0.75,4,0.7916666666666666,4,0,0


## Retrospective contribution

policy,candidate_requirements,candidate_cases,candidate_correct,net_correct_gain,official_accuracy,retrospective_accuracy
ORIGINAL,25,199,140,140,0.7369226197419787,0.8021100753212252
PROPOSED_RDF_EDIT_SENSITIVITY,25,193,137,137,0.7396470926157054,0.8065109190877409


## Cached workbook checks

44 cached score discrepancies. See manual_cache_discrepancies and behavioural_cache_discrepancies. Original formulas and caches are exported; no formula recalculation or workbook modification is performed.

Paper-summary outcome counts, accuracy, and manual categorical counts/means are checked in summary_cache_checks.csv. The manual comparison uses all selected slots, so reviewed-only workbook summaries may omit unassessable slots. These denominator differences are reported explicitly. All original formulas/caches are preserved.

## Verification and figures

Outcome totals and independent macro means were reconciled during this run. Frozen IDs, stage generation-run alignment and exclusion policies were checked. Full details: verification.csv.

Figure exports use constrained layout and tight bounds. figure_verification.csv records text outside the initial canvas. Review the HTML gallery visually before manuscript submission; automated bounds checks cannot prove absence of all overlapping text.

See sources_used.csv for hashed inputs and referenced_files.csv for evidence availability. See MISSING_DATA.md for missing records.

![original_workflow_accuracy](figures/original_workflow_accuracy.png)

![original_workflow_outcomes](figures/original_workflow_outcomes.png)

![original_model_progression](figures/original_model_progression.png)

![original_model_dumbbell](figures/original_model_dumbbell.png)

![original_model_by_mode](figures/original_model_by_mode.png)

![original_model_requirements](figures/original_model_requirements.png)

![proposed_rdf_edit_sensitivity_workflow_accuracy](figures/proposed_rdf_edit_sensitivity_workflow_accuracy.png)

![proposed_rdf_edit_sensitivity_workflow_outcomes](figures/proposed_rdf_edit_sensitivity_workflow_outcomes.png)

![proposed_rdf_edit_sensitivity_model_progression](figures/proposed_rdf_edit_sensitivity_model_progression.png)

![proposed_rdf_edit_sensitivity_model_dumbbell](figures/proposed_rdf_edit_sensitivity_model_dumbbell.png)

![proposed_rdf_edit_sensitivity_model_by_mode](figures/proposed_rdf_edit_sensitivity_model_by_mode.png)

![proposed_rdf_edit_sensitivity_model_requirements](figures/proposed_rdf_edit_sensitivity_model_requirements.png)

![manual_verdict_distributions](figures/manual_verdict_distributions.png)

![manual_semantic_scores](figures/manual_semantic_scores.png)

![manual_implementation_scores](figures/manual_implementation_scores.png)

![manual_rubric_NoSemantic](figures/manual_rubric_NoSemantic.png)

![manual_rubric_Scaling_audit_B01](figures/manual_rubric_Scaling_audit_B01.png)

![manual_rubric_SingleShot](figures/manual_rubric_SingleShot.png)

![manual_rubric_V2](figures/manual_rubric_V2.png)

![original_failure_labels](figures/original_failure_labels.png)

![proposed_rdf_edit_sensitivity_failure_labels](figures/proposed_rdf_edit_sensitivity_failure_labels.png)
