"""Offline readiness evidence, distinct from generation/repair and evaluation scores.
Probes are incomplete synthetic structural examples, never regulatory answers.
"""
from __future__ import annotations
import collections
import hashlib
import json
from pathlib import Path
from rdflib import Graph, URIRef, RDF
from .core import Candidate,load,write,digest,stamp
from .schema import Schema,N,Q,U
from .checks import check
from .requests import initial_request

REQUIREMENTS=('I2-004','I2-005','I2-042','IMO-001','TRF-010','TRF-035')
PREFIX='@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix n: <https://w3id.org/nltl/vocab#> . @prefix q: <http://qudt.org/schema/qudt/> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def settings(config):return {k:config[k] for k in ['model','generation_max_tokens','review_max_tokens']}
def generated_request(project,rid,config):return initial_request(project,Schema(project).context(rid),settings(config))

def structural_probe(schema,rid):
    """Demonstrate narrow checker capabilities and absence of logic proof, without fixtures."""
    contract=schema.effective_contract(rid);owners=schema.effective_owners(rid)
    terms=[schema.terms[str(N[t])] for t in schema.development_profiles[rid]['active_terms'] if str(N[t]) in schema.terms]
    quantities=[row for row in terms if row['kind']=='QuantityProperty']
    if quantities:
        term=quantities[0];path=schema.allowed_paths(rid)[1][term['iri']][0]
        path_text='<'+path[0]+'>' if len(path)==1 else '('+' '.join('<'+p+'>' for p in path)+')'
        body='sh:property [ sh:path '+path_text+' ; sh:node [ sh:property [ sh:path q:numericValue ; sh:datatype xsd:decimal ] ; sh:property [ sh:path q:unit ; sh:hasValue <'+term['unitIri']+'> ] ] ]'
        code=PREFIX+'<urn:development:structuralProbe> a sh:NodeShape ; sh:targetClass n:ship ; '+body+' .\n'
        wrong_unit=str(U.MilliM) if term['unitIri']==str(U.M) else str(U.M)
        mutations={
          'wrong_unit':(code.replace('<'+term['unitIri']+'>','<'+wrong_unit+'>'),'UNIT_CONSISTENCY_ERROR'),
          'literal_numeric_operand':(code.replace('xsd:decimal','xsd:string'),'TERM_KIND_ERROR'),
          'exclusive_double_rejects_canonical_decimal':(code.replace('xsd:decimal','xsd:double'),'TERM_KIND_ERROR'),
          'wrong_owner_path':(code.replace(path_text,'<'+term['iri']+'>' if len(path)>1 else '(n:hasStructuralMember <'+term['iri']+'>)'),'PATH_CONTRACT_ERROR'),
          'wrong_predicate':(code.replace('<'+term['iri']+'>','<'+term['iri']+'Typo>'),'CANONICAL_IDENTIFIER_ERROR')}
    else:
        # Property/value representation only: intentionally no regulatory implication or presence logic.
        props=[str(N[t]) for t in owners]
        code=PREFIX+'<urn:development:structuralProbe> a sh:NodeShape ; sh:targetClass n:ship ; '+' ; '.join('sh:property [ sh:path <'+p+'> ; sh:nodeKind sh:IRI ]' for p in props)+' .\n'
        mutations={'literal_on_object_property':(code.replace('sh:nodeKind sh:IRI','sh:datatype xsd:string'),'TERM_KIND_ERROR'),
                   'wrong_predicate':(code.replace('<'+props[0]+'>','<'+props[0]+'Typo>'),'CANONICAL_IDENTIFIER_ERROR')}
    def findings(text):return check(Candidate(1,text,text),schema,rid)
    baseline=findings(code);probes=[]
    for name,(bad,expected) in mutations.items():
        fs=findings(bad);detected=any(f.category==expected and f.confirmed for f in fs)
        probes.append(dict(name=name,expected_category=expected,detected=detected,candidate=bad,findings=[f.asdict() for f in fs]))
    return dict(requirement_id=rid,source='Source/schema-only synthetic structural examples; no complete regulatory SHACL solution.',baseline_candidate=code,baseline_findings=[f.asdict() for f in baseline],probes=probes,all_supported_mutations_detected=all(p['detected'] for p in probes),regulatory_logic_missing_from_scaffold=True,confirmed_logic_omission_detected=any(f.category=='SOURCE_BACKED_LOGIC_ERROR' and f.confirmed for f in baseline),conclusion='Structural/unit/type checks do not prove source arithmetic, existence, implication or branch coverage. Those obligations remain explicitly unchecked by the deterministic gate.')

def validate_manifest(project,manifest,require_ready=False):
    if manifest.get('method')!='paired-development-pilot' or manifest.get('dispatch') is not False:raise ValueError('Manifest must be prepared/non-dispatching')
    selected=manifest.get('requirements',[])
    if not selected or len(selected)!=len(set(selected)) or any(rid not in REQUIREMENTS for rid in selected):raise ValueError('Pilot must contain a unique explicit subset of the reviewed development requirements')
    one=project.config(manifest['workflows']['Single-shot']['config']);nltl=project.config(manifest['workflows']['NLTL']['config'])
    if one['method']!='Single-shot' or one['maximum_candidate_attempts']!=1 or one['semantic_review']:raise ValueError('Single-shot must be one call without review/repair')
    if nltl['method']!='NLTL' or nltl['maximum_candidate_attempts']!=6 or nltl['fresh_regeneration']:raise ValueError('NLTL must stop on internal acceptance within six candidates, no regeneration')
    if settings(one)!=settings(nltl):raise ValueError('Generation settings differ across workflows')
    if any(manifest['workflows']['Single-shot'].get(key) for key in ['checker_feedback','revision','semantic_review']) or manifest['workflows']['NLTL'].get('fresh_regeneration') is not False:raise ValueError('Workflow feedback/regeneration policy inconsistent')
    if manifest['workflows']['Single-shot'].get('maximum_generation_calls')!=1 or manifest['workflows']['NLTL'].get('maximum_candidate_attempts')!=6 or not manifest['workflows']['NLTL'].get('early_acceptance'):raise ValueError('Manifest limits inconsistent')
    if manifest['evaluation'].get('execution')!='AFTER_WORKFLOW_COMPLETION_ONLY' or manifest['evaluation'].get('feedback_to_repair') is not False:raise ValueError('Evaluation firewall absent')
    for key,path in manifest['generation']['resources'].items():
        project.path(path)
        if path.startswith(('evaluation/','outputs/')) or not project.path(path).is_file():raise ValueError('Evaluation/output path or broken resource in generation input')
    stale=[path for path,expected in manifest['source_hashes'].items() if sha(project.path(path))!=expected]
    selection=load(project.path(manifest['evaluation']['selection']))
    selected_cases=[c for c in selection['cases'] if c['requirement_id'] in selected]
    if len(selected_cases)!=len(selection['cases']) or set(selection['requirements'])!=set(selected):raise ValueError('Evaluation selection differs from declared pilot requirements')
    for field,actual in [('cases',len(selected_cases)),('positive',sum(c['expected']=='PASS' for c in selected_cases)),('negative',sum(c['expected']=='FAIL' for c in selected_cases))]:
        if manifest['evaluation'][field]!=actual:raise ValueError('Evaluation case count mismatch: '+field)
    by_requirement={rid:[c['case_id'] for c in selected_cases if c['requirement_id']==rid] for rid in selected}
    if by_requirement!=manifest['evaluation']['case_ids_by_requirement']:raise ValueError('Evaluation case ID mismatch')
    for path,expected in manifest.get('evaluation_hashes',{}).items():
        if not path.startswith('evaluation/') or sha(project.path(path))!=expected:raise ValueError('Evaluation artifact mismatch: '+path)
    schema=Schema(project);blockers=[]
    for rid in selected:
        context=schema.context(rid);a=initial_request(project,context,settings(one));b=initial_request(project,context,settings(nltl))
        if a!=b:raise ValueError('Different paired initial request: '+rid)
        if digest(json.dumps(a,ensure_ascii=False))!=manifest['initial_request_hashes'][rid]:stale.append('initial_request:'+rid)
        for item in context.get('unresolvedSourceContext',[]):
            if item.get('blocking_before_generation'):blockers.append(dict(requirement=rid,code=item['code'],detail=item['disposition']))
    if require_ready and (blockers or stale):raise ValueError('PILOT_NOT_READY: '+json.dumps(dict(blockers=blockers,stale_artifacts=stale)))
    return dict(structurally_valid=True,ready_for_dispatch=not blockers and not stale,dispatch_performed=False,blockers=blockers,stale_artifacts=stale,requirements=selected,logical_coverage='Structural and finite-set checks plus source-authored finite arithmetic/branch witnesses; no complete correctness proof. Reviewer ACCEPT cannot erase unchecked coverage.')


def run_preflight(project,manifest_path='configs/paired_development_pilot.json',require_ready=False):
    """Read evaluation inputs only in this external offline audit, not in Schema.context or Runner."""
    schema=Schema(project);out=project.output('audits',stamp()+'_DEVELOPMENT_PREFLIGHT')
    manifest=load(project.path(manifest_path));valid=validate_manifest(project,manifest)
    configs=[project.config('configs/single_shot.json'),project.config('configs/nltl.json')]
    selection=load(project.path('evaluation/selections/regression_core.json'));branches=load(project.path('evaluation/specifications/core_branches.json'))
    from .evaluation import oracle
    rows=[];ledger=[]
    for rid in manifest['requirements']:
        context=schema.context(rid);folder=out/rid;folder.mkdir();write(folder/'initial_context.json',context)
        requests=[initial_request(project,context,settings(c)) for c in configs];assert requests[0]==requests[1]
        write(folder/'shared_initial_request.json',requests[0])
        cases=[c for c in selection['cases'] if c['requirement_id']==rid]
        for c in cases:
            data=Graph().parse(project.path(c['fixture']));original_oracle=oracle(data,rid)
            if sha(project.path(c['fixture']))!=c['fixture_sha256'] or original_oracle['conforms']!=(c['expected']=='PASS'):raise ValueError('Case/hash disagreement '+c['case_id'])
            repaired_oracle=None;certificate=None
            if c.get('counterfactual'):
                certificate=c['source_review']['independent_repair_review']
                if not certificate.get('one_intended_property_changed') or not certificate.get('intended_defect_corresponds_to_operation'):raise ValueError('Uncertified intended-only operation')
                if sha(project.path(c['counterfactual']))!=c['counterfactual_sha256']:raise ValueError('Counterfactual hash mismatch')
                repaired_oracle=oracle(Graph().parse(project.path(c['counterfactual'])),rid)
                if repaired_oracle['conforms'] is not True:raise ValueError('Supplied repair not valid under represented oracle')
            ledger.append(dict(requirement_id=rid,case_id=c['case_id'],expected=c['expected'],fixture=c['fixture'],fixture_sha256=c['fixture_sha256'],counterfactual=c.get('counterfactual'),counterfactual_sha256=c.get('counterfactual_sha256'),historical_certification=c['certification'],retained_intended_only_certificate=certificate,represented_scope_oracle=original_oracle,repaired_scope_oracle=repaired_oracle,current_applicability_status='UNRESOLVED_WELDED_PROFILE_BINDING' if rid in [b['requirement'] for b in valid['blockers']] else 'SCOPED_REPRESENTATION_ONLY; source-population preconditions are not independently derived',source_labels_or_scores_changed=False))
        actual_examples=[x['exampleId'] for x in context['examples']]
        corpus=[json.loads(line) for line in project.path('data/examples/few_shot_pairs.jsonl').read_text().splitlines() if line.strip()]
        active={URIRef(x['iri']) for x in context['schema_terms'] if x['kind']!='Class'}
        related=[]
        for example in corpus:
            graph=Graph().parse(data=example['expectedShapeTurtle'],format='turtle')
            terms={v for triple in graph for v in triple if isinstance(v,URIRef)}
            shared=sorted(map(str,active & terms))
            if shared:related.append(dict(example_id=example['exampleId'],selected=example['exampleId'] in actual_examples,shared_schema_terms=shared,interpretation='Generic synthetic pattern overlap, not an exact source requirement or evaluation case.'))
        overlap=any(rid in json.dumps(e) or e['inputRequirement'] in [context['requirement']['text'],context['requirement']['normalized']] for e in context['examples'])
        if overlap:raise ValueError('Target requirement included in selected examples')
        profile=schema.development_profiles.get(rid)
        proof=structural_probe(schema,rid) if profile else dict(scope='TRF-010 existing source-backed finite-set gate verified by its retained tests and completed live pilot')
        if profile and not proof['all_supported_mutations_detected']:raise ValueError('Advertised checker capability failed '+rid)
        write(folder/'checker_probes.json',proof)
        rows.append(dict(requirement_id=rid,status='BLOCKED_APPLICABILITY' if rid in [b['requirement'] for b in valid['blockers']] else 'SCOPED_DEVELOPMENT_READY_WITH_FINITE_WITNESSES' if profile else 'SCOPED_DEVELOPMENT_READY_FINITE_SET_GATE',source_clause=context['requirement']['clause'],source_evidence=(profile or {}).get('source',context['contract'].get('enumerationObligations',[{}])[0].get('source')),scope=context['contract'].get('verificationScope'),positive_cases=sum(c['expected']=='PASS' for c in cases),negative_cases=sum(c['expected']=='FAIL' for c in cases),repaired_counterparts=sum(bool(c.get('counterfactual')) for c in cases),paired_initial_context_identical=True,selected_examples=actual_examples,selected_example_overlap=False,related_corpus_examples=related,all_corpus_example_overlap_note='Selected examples are the same two synthetic boolean examples; the corpus contains generic examples of quantities/conditions, not these source requirements.',remaining_test_gaps=branches[rid]['gaps'],active_terms=(profile or {}).get('active_terms'),inactive_legacy_terms=(profile or {}).get('inactive_terms',{}),explicit_owner_paths=schema.allowed_paths(rid)[1],datatype_profile=context.get('quantityEncoding'),logical_obligations=(profile or {}).get('obligations'),finite_behavioral_checks=context['contract'].get('developmentVerification'),complete_verification=False,blockers=[b for b in valid['blockers'] if b['requirement']==rid],generation_evaluation_firewall=True))
    write(out/'case_readiness_ledger.json',ledger);write(out/'requirement_readiness.json',rows);write(out/'manifest_validation.json',valid)
    report=['# Six-requirement development readiness preflight','','No model calls or dispatch. Source/schema metadata and synthetic structural probes are separate from external case review. Historical labels and scores are unchanged.','','| Requirement | Status | P / N / repaired | Evidence / exact correction | Remaining blocker or unchecked obligation |','|---|---|---:|---|---|']
    corrections={
      'I2-004':('I2.1.2.2; add the source/schema-confirmed ship → hasUpperIceWaterlineCase → case path; quarantine unbound upperIceWaterline string; expose canonical kt/decimal profile.','Finite witnesses cover maximum/equality, single/multiple/tied cases and missing inputs; not a proof for all graphs.'),
      'I2-005':('I2.2.5; retain complete 7° quotation, sampled-point scope and explicit point path; expose DEG/decimal profile.','Finite witnesses cover exact 7°, boundaries and sampled-point existence; whole-hull geometry/population eligibility remain outside scope.'),
      'I2-042':('I2.9.4(i); restore welded-profile header; quarantine generic metre thickness; retain ≥ 5× net-web thickness in mm.','BLOCKED: no explicit welded-profile applicability binding. Do not infer one from section type or fixtures.'),
      'IMO-001':('Introduction 2.1; supplement canonical Category A binding and correct the medium-condition source reference; preserve mandatory-selector policy.','Finite witnesses cover applicable/nonapplicable branches and selector readiness; unknown/multiple selectors and engineering capability remain unchecked.'),
      'TRF-035':('4.1.1 L definition; expose equality operand/result roles, metres and decimal profile; quarantine adjacent hull-region/name fields.','Finite witnesses cover numeric equality and operand readiness; society-rule derivation and universal graph equivalence remain outside scope.'),
      'TRF-010':('Existing six-value source/contract gate retained; initial context and shared prompts unchanged from completed v0.2.0 pilot.','Max cardinality remains unresolved; no general correctness or performance claim.')}
    for row in rows:
        a,b=corrections[row['requirement_id']];report.append(f"| {row['requirement_id']} | {row['status']} | {row['positive_cases']} / {row['negative_cases']} / {row['repaired_counterparts']} | {a} | {b} |")
    report+=['','All 37 retained core cases (17 positive, 20 negative) and 20 intended-only counterparts remain present. I2-042 historical certifications remain recorded, but current welded applicability is unresolved; no fixture was relabelled, excluded or silently certified for an unqualified source-domain claim.','', 'UR I2 Polar Class population and relevant design-record eligibility are declared scope preconditions, not inferred from missing RDF assertions. The represented checks do not certify the whole ship or source applicability outside that scope.','', ('Selected manifest inputs are current and unblocked; no dispatch is authorized or performed.' if valid['ready_for_dispatch'] else 'Selected manifest is NOT DISPATCHABLE: inspect blockers and stale artifacts. Frozen v0.3.0 manifest is preserved, not refreshed.')+' The other 44 study requirements remain pending review.','', 'Canonical decimal encoding is verified from the locked JSON-LD context. That coercion is not a new global RDFS range. Direct exclusive sh:datatype restrictions that reject this canonical encoding are detected; other SPARQL/literal equivalence remains limited.','', 'v0.3.1 adds finite behavioral witnesses and preserves unchecked scope after ACCEPT. The TRF-010 initial context and shared prompts remain byte-equivalent to the completed v0.2.0 paired pilot; nevertheless results from different implementation versions must be tagged rather than silently pooled.']
    (out/'REPORT.md').write_text('\n'.join(report)+'\n')
    result=dict(output=str(out.relative_to(project.root)),requirements=rows,manifest=valid,model_calls=0,dispatch_performed=False,core_cases=len(ledger),repaired_counterparts=sum(bool(c.get('counterfactual')) for c in ledger),historical_core_cases=37,deferred_requirements=manifest.get('deferred_requirements',[]),study_gap=44)
    write(out/'summary.json',result)
    if require_ready and not valid['ready_for_dispatch']:raise ValueError('PILOT_NOT_READY: '+json.dumps(valid['blockers']))
    return result
