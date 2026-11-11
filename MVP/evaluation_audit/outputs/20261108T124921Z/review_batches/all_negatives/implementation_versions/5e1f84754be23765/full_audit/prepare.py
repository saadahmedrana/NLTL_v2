"""All-case source/schema/independent-oracle gates. No shape inspection."""
import inspect
from decimal import Decimal
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from rdflib import Graph, Literal, URIRef, RDF, RDFS, XSD
from common import audit, BASE, OUT, OLD, SCRIPTS, SOURCE_FILES, atomic
from evidence import load_script, oracle_for, trace_for, default_proposals

N,Q=audit.N,audit.Q
U=audit.Namespace('http://qudt.org/vocab/unit/')
INDEX=audit.read(audit.R13/'requirement_term_index.json')
REG={r['localName']:r for r in audit.read(audit.R13/'registry/term_registry.json')}
ONTO=Graph().parse(audit.ONTOLOGY)
MANIFEST={}
for p in sorted((audit.BENCH/'manifests').glob('*_batch_*_manifest.jsonl')):
    for line in p.read_text().splitlines():
        r=json.loads(line);MANIFEST[r['case_id']]=dict(r,manifest_path=str(p))
SOURCES={family:(audit.HERE/'source_review'/name).read_text() for family,name in SOURCE_FILES.items()}
PRIOR_SPECS=audit.expected_specs(audit.HERE/'reviewed_failure_specs_batch50.json')
KNOWN_BLOCKERS={r['case_id']:r for r in audit.read(audit.HERE/'review_blockers_batch50.json')}

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC',re.sub(r'-\s*\n\s*','',s)).lower().replace('°','deg') if c.isalnum())
NORMAL={k:norm(v) for k,v in SOURCES.items()}

def source_evidence(row):
    req=row['requirement_id'];family=req.split('-')[0];text=row['frozen_requirement_text'];needle=norm(text);hay=NORMAL[family]
    proof=dict(source_path=str(audit.HERE/'source_review'/SOURCE_FILES[family]),source_sha256=audit.sha(audit.HERE/'source_review'/SOURCE_FILES[family]),source_clause=row['source_clause'],frozen_requirement_text=text,requirement_context_path=row['requirement_context_path'],contract=INDEX['dependencyContracts'].get(req,{}),term_owners=INDEX['termOwners'].get(req,{}))
    if needle and needle in hay:
        proof['verification']='EXACT_NORMALIZED_SOURCE_QUOTATION'
        return proof,None
    if req=='I2-048':
        proof.update(verification='PREVIOUSLY_VERIFIED_SOURCE_TABLE8_AND_OWNER_MODEL',evidence=str(BASE/'table8_source_cell_checks.csv'))
        return proof,None
    reviewed_path=audit.HERE/'full_audit/source_reviews.json'
    reviewed=audit.read(reviewed_path) if reviewed_path.exists() else {}
    if req in reviewed:
        proof.update(verification='REVIEWED_EQUIVALENT_SOURCE_CLAUSE',evidence=reviewed[req])
        return proof,None
    # Prior source reviews are reused only for their exact requirement/contract,
    # not to invent new mutations. A case still needs a separately valid repair.
    earlier=[s for s in PRIOR_SPECS.values() if s['requirement']==req and isinstance(s.get('source_evidence'),dict)]
    if earlier:
        proof.update(verification='EXISTING_REVIEWED_SOURCE_EXCERPT',evidence=earlier[0]['source_evidence'])
        return proof,None
    return proof,'SOURCE_EXPECTATION_RECONCILIATION_REQUIRED'


def types_of(g,node):
    values=set(g.objects(node,RDF.type))|set(ONTO.objects(node,RDF.type));pending=list(values)
    while pending:
        t=pending.pop()
        for parent in ONTO.objects(t,RDFS.subClassOf):
            if isinstance(parent,URIRef) and parent not in values:values.add(parent);pending.append(parent)
    return values

def schema_issues(g):
    issues=[]
    for s,p,o in g:
        if not str(p).startswith(str(N)):continue
        name=str(p).split('#')[-1];term=REG.get(name)
        if term is None:
            if (p,None,None) not in ONTO:issues.append(dict(kind='UNKNOWN_PROPERTY',property=str(p),subject=str(s)))
            continue
        domains=[d for d in ONTO.objects(p,RDFS.domain) if isinstance(d,URIRef) and d!=N.benchmarkEntity]
        if domains and any(d not in types_of(g,s) for d in domains):issues.append(dict(kind='OWNER_DOMAIN',property=str(p),subject=str(s),expected=[str(d) for d in domains],asserted_types=[str(x) for x in types_of(g,s)]))
        if term['kind']=='QuantityProperty':
            expected=term.get('unitIri');unit=list(g.objects(o,Q.unit));num=list(g.objects(o,Q.numericValue))
            if (o,RDF.type,Q.QuantityValue) not in g:issues.append(dict(kind='QUANTITY_TYPE',property=str(p),subject=str(s),value=str(o)))
            if len(num)!=1 or not isinstance(num[0],Literal) or num[0].datatype!=XSD.decimal:issues.append(dict(kind='QUANTITY_NUMBER',property=str(p),subject=str(s),value=str(o)))
            if expected and unit!=[URIRef(expected)]:issues.append(dict(kind='QUANTITY_UNIT',property=str(p),subject=str(s),value=str(o),expected=expected,actual=[str(v) for v in unit]))
        if term['kind']=='DatatypeProperty':
            datatype=term.get('datatype','');expected={'xsd:boolean':XSD.boolean,'xsd:string':XSD.string,'xsd:integer':XSD.integer,'xsd:decimal':XSD.decimal,'xsd:date':XSD.date}.get(datatype)
            if expected and (not isinstance(o,Literal) or (o.datatype or (XSD.string if isinstance(o,Literal) and not o.language else None))!=expected):issues.append(dict(kind='DATATYPE',property=str(p),subject=str(s),expected=str(expected),actual=str(getattr(o,'datatype',None))))
        if term['kind']=='ObjectProperty':
            ranges=[t for t in ONTO.objects(p,RDFS.range) if isinstance(t,URIRef) and t!=N.benchmarkEntity]
            if any(t not in types_of(g,o) for t in ranges):issues.append(dict(kind='OBJECT_RANGE',property=str(p),subject=str(s),value=str(o),expected=[str(t) for t in ranges],asserted_types=[str(t) for t in types_of(g,o)]))
    return sorted(issues,key=lambda x:json.dumps(x,sort_keys=True))


def correction_normalize(g,req,cid):
    """Only the already-confirmed, versioned I2-048 preparation correction."""
    h=audit.clone(g)
    if req=='I2-048':
        for c in h.subjects(RDF.type,N.steelGradeRequirementCase):
            plates=list(h.objects(c,N.steelGradeRequirementCasePlating))
            if not plates and cid=='I2-048-H-F002':plates=[URIRef(str(c).rsplit('/',1)[0]+'/plating')]
            for p in plates:
                for value in list(h.objects(p,N.asBuiltPlateThickness)):h.remove((p,N.asBuiltPlateThickness,value));h.add((c,N.asBuiltPlateThickness,value))
    return h


def align_numeric_lexicals(graph,retained):
    # Replaying source constructors can produce decimal "12" where the retained
    # Turtle export spells the same value "12.0". Preserve retained RDF terms
    # whenever values and datatypes agree; never rename nodes or change values.
    h=audit.clone(graph)
    for subject,predicate,value in list(h):
        if not isinstance(value,Literal) or value.datatype not in [XSD.decimal,XSD.integer,XSD.double,XSD.float]:continue
        old=list(retained.objects(subject,predicate))
        if len(old)==1 and isinstance(old[0],Literal) and old[0].datatype==value.datatype:
            try:same=Decimal(str(old[0]))==Decimal(str(value))
            except Exception:same=False
            if same and old[0]!=value:h.remove((subject,predicate,value));h.add((subject,predicate,old[0]))
    return h

def semantic_roots(bad,good):
    removed=set(bad)-set(good);added=set(good)-set(bad);old_nodes=set(bad.all_nodes());roots=[]
    for s,p,o in removed|added:
        if s not in old_nodes:continue
        if p in [Q.numericValue,Q.unit]:
            incoming={(owner,prop) for graph in [bad,good] for owner,prop in graph.subject_predicates(s) if str(prop).startswith(str(N))}
            roots.extend(incoming)
        elif str(p).startswith(str(N)):roots.append((s,p))
        elif p==RDF.type:
            incoming={(owner,prop) for graph in [bad,good] for owner,prop in graph.subject_predicates(s) if str(prop).startswith(str(N))}
            roots.extend(incoming or [(s,p)])
        else:roots.append((s,p))
    return sorted(set(roots),key=lambda t:tuple(map(str,t)))

def coupled_quantity_changes(bad,good):
    """An existing number and its unit are separate defects even on one field."""
    changed=set(bad)^set(good)
    return [str(node) for node in set(bad.all_nodes())
            if list(bad.objects(node,Q.numericValue)) and list(good.objects(node,Q.numericValue))
            and any(s==node and p==Q.numericValue for s,p,o in changed)
            and any(s==node and p==Q.unit for s,p,o in changed)]


def rationale_matches(row,roots,proposal):
    rationale=row['source_oracle_rationale'].lower();props={str(p).split('#')[-1] for _,p in roots}
    if not props:return False
    if re.match(r'^(bad|wrong|missing|omit|orphan|duplicate|invalid)',proposal.get('parameter','')):return True
    if proposal.get('parameter') in ['missing','omit','wrong_unit','wrong_owner','missing_term','omit_term'] and any(name.lower() in proposal.get('before','').lower() for name in props):return True
    if 'unit' in rationale and proposal.get('method')=='CANONICAL_UNIT_RESTORATION':return True
    for name in props:
        if name.lower() in rationale:return True
        tokens=set(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|$)',name))
        tokens={x.lower() for x in tokens}-{'has','is','of','the','required','present','status','value','result','ship','ice','class','calculated','quantity'}
        overlap=tokens & set(re.findall(r'[a-z]+',rationale))
        if len(overlap)>=2 or any(len(t)>=7 for t in overlap):return True
    return False


def manual_table_repairs(bad,cid):
    """Source Table 8 and explicit original builder base constants, no shape read."""
    h=audit.clone(bad);ship=next(h.subjects(RDF.type,N.ship));case=next(h.objects(ship,N.hasSteelGradeRequirementCase));suffix=cid.rsplit('-',1)[-1]
    def put(s,p,o):h.remove((s,p,None));h.add((s,p,o))
    if suffix=='F001':put(ship,N.polarClass,N.polarClassPc3)
    elif suffix=='F002':put(case,N.steelGradeRequirementCasePlating,URIRef(str(case).rsplit('/',1)[0]+'/plating'))
    elif suffix=='F003':
        q=URIRef(str(case).rsplit('/',1)[0]+'/auditThickness');h.add((case,N.asBuiltPlateThickness,q));h.add((q,RDF.type,Q.QuantityValue));h.add((q,Q.numericValue,Literal('17.5',datatype=XSD.decimal)));h.add((q,Q.unit,U.MilliM))
    elif suffix=='F004':put(h.value(case,N.asBuiltPlateThickness),Q.unit,U.MilliM)
    elif suffix in ['F005','F006']:put(case,N.steelMaterialClass,N.steelMaterialClassOne)
    elif suffix=='F007':put(case,N.steelStrengthCategory,N.normalStrengthSteelCategory)
    elif suffix in ['F008','F015']:put(case,N.tableReference,N.iacsUrI2Table8)
    elif suffix in ['F009','F012','F013']:put(case,N.actualHullStructuralSteelGrade,N.steelGradeD)
    elif suffix in ['F010','F011']:put(case,N.requiredHullStructuralSteelGrade,N.steelGradeD)
    elif suffix=='F014':h.remove((case,N.requiredHullStructuralSteelGrade,None))
    else:return []
    return [dict(method='SOURCE_TABLE8_REPAIR',parameter=suffix,before='Frozen Table-8 negative',after='Exact source selector/result/cardinality restoration',graph=h)]


def prepare_case(row):
    cid=row['case_id'];req=row['requirement_id'];manifest=MANIFEST[cid]
    record=dict(case_id=cid,requirement_id=req,expected=row['expected'],source_clause=row['source_clause'],intended_rationale=row['source_oracle_rationale'],original_fixture=str(audit.BENCH/row['rdf_path']),corrected_fixture=str(BASE/'corrected_benchmark'/row['rdf_path']),manifest_path=manifest['manifest_path'],manifest_sha256=audit.sha(manifest['manifest_path']),stage='SOURCE_AND_REPAIR_REVIEW',blockers=[],candidate_attempts=[])
    proof,source_error=source_evidence(row);record['source_evidence']=proof
    if source_error:record['blockers'].append(dict(code=source_error,detail=f"Frozen source text for {req} ({row['source_clause']}) is not established as an exact complete source quotation. Formula/table/parent-clause or extraction differences must be reconciled; the benchmark's own oracle alone is insufficient.",rationale=row['source_oracle_rationale']))
    if req=='I2-043':record['blockers'].append(dict(code='PARENT_PROFILE_SCOPE_UNESTABLISHED',detail='I2.9.4 is scoped to welded profiles; frozen outstand rule generalises it to structuralMember. The fixtures do not establish welded-profile applicability, so no weld-status assertion is invented.'))
    if req=='I2-065':record['blockers'].append(dict(code='OMITTED_SOURCE_ACCEPTANCE_CRITERIA',detail='Full I2.17.6 also requires detailed acceptance criteria decided by the Classification Society (item 4), absent from the frozen three-item requirement. The generic acceptance artifact does not establish those criteria or their authority.'))
    if req in ['IMO26-010','IMO26-011']:
        record['blockers'].append(dict(code='PARENT_APPLICABILITY_UNESTABLISHED',detail='Full source 9-1.3.2.1.4 additionally requires ice-strengthening; fixture/frozen single-clause text omits that selector. No applicability assertion is invented.'))
    if cid in KNOWN_BLOCKERS:record['blockers'].append(dict(code='PREVIOUS_CASE_SPECIFIC_BLOCKER',detail=KNOWN_BLOCKERS[cid]['reason']))
    script_name=Path(manifest['manifest_path']).name.replace('_manifest.jsonl','.py');script=SCRIPTS/('validate_'+script_name)
    record.update(preparation_script=str(script),preparation_script_sha256=audit.sha(script) if script.exists() else None)
    if not script.exists():record['blockers'].append(dict(code='PREPARATION_SCRIPT_MISSING',detail=str(script)));return record
    loaded=load_script(script);oracle=oracle_for(loaded,req)
    if req=='I2-048':oracle=lambda g:audit.table_oracle(g,INDEX['dependencyContracts'][req])
    if oracle is None:record['blockers'].append(dict(code='INDEPENDENT_ORACLE_UNAVAILABLE',detail=f'No independent source/contract oracle found for {req} in retained preparation script'));return record
    record['oracle_function']=getattr(oracle,'__name__',str(oracle));record['loader_errors']=loaded['errors']
    bad=Graph().parse(record['corrected_fixture']);record['negative_schema_issues']=schema_issues(bad)
    try:record['negative_original_oracle']=bool(oracle(bad))
    except Exception as exc:record['blockers'].append(dict(code='ORACLE_EXECUTION_ERROR',detail=f'{type(exc).__name__}: {exc}'));return record
    if record['blockers']:return record
    proposals=[]
    if req=='I2-048':proposals=manual_table_repairs(bad,cid)
    else:
        trace=trace_for(loaded,cid)
        if trace is None and req in ['I2-022','I2-023','I2-024','I2-040','I2-043']:
            authoring=audit.ROOT.parent/'create_i2_batch_b.py'
            if authoring.exists():
                authoring_loaded=load_script(authoring);trace=trace_for(authoring_loaded,cid);record['additional_builder_evidence']=dict(path=str(authoring),sha256=audit.sha(authoring),execution='Declarations and pure fixture construction only; repository root resolved to source-file parent; file-writing code never executed')
        if trace:
            bound=inspect.BoundArguments(trace['signature'],trace['arguments'])
            try:
                reconstructed=trace['function'](*bound.args,**bound.kwargs)
                if isinstance(reconstructed,tuple):reconstructed=reconstructed[0]
                reconstructed=align_numeric_lexicals(correction_normalize(reconstructed,req,cid),bad)
                if set(reconstructed)==set(bad):
                    proposals=default_proposals(trace);record['builder_function']=trace['function'].__name__;record['builder_arguments']={k:repr(v) for k,v in trace['arguments'].items()}
                else:record['candidate_attempts'].append(dict(method='BUILDER_REPLAY',rejected='Retained RDF terms do not exactly reproduce; URI allocation or post-builder mutation differs. No pairing is inferred.'))
            except Exception as exc:record['candidate_attempts'].append(dict(method='BUILDER_REPLAY',rejected=f'{type(exc).__name__}: {exc}'))
        # A wrong unit has a source/schema-defined repair, without inventing a
        # value or searching positive fixtures. Other schema issues are not fixed.
        if 'unit' in row['source_oracle_rationale'].lower():
            unit_issues=[x for x in record['negative_schema_issues'] if x['kind']=='QUANTITY_UNIT']
            if len(unit_issues)==1:
                issue=unit_issues[0];h=audit.clone(bad);node=URIRef(issue['value']);h.remove((node,Q.unit,None));h.add((node,Q.unit,URIRef(issue['expected'])))
                proposals.insert(0,dict(method='CANONICAL_UNIT_RESTORATION',parameter=issue['property'],before=repr(issue['actual']),after=issue['expected'],graph=h))
    accepted=[]
    for proposal in proposals:
        attempt={k:v for k,v in proposal.items() if k!='graph'};good=proposal.get('graph')
        if good is None:record['candidate_attempts'].append(attempt);continue
        good=align_numeric_lexicals(correction_normalize(good,req,cid),bad);removed=set(bad)-set(good);added=set(good)-set(bad);roots=semantic_roots(bad,good)
        attempt.update(removed_triples=audit.triples(removed),added_triples=audit.triples(added),semantic_roots=[[str(s),str(p)] for s,p in roots])
        if not removed and not added:attempt['rejected']='NO_CHANGE'
        elif coupled_quantity_changes(bad,good):attempt['rejected']='COUPLED_EXISTING_NUMBER_AND_UNIT_CHANGES'
        elif len({p for s,p in roots})!=1:attempt['rejected']='MULTIPLE_SEMANTIC_FIELDS_CHANGE'
        elif req!='I2-048' and not rationale_matches(row,roots,proposal):attempt['rejected']='REPAIR_TARGET_NOT_ESTABLISHED_FROM_INTENDED_RATIONALE'
        else:
            selectors=set(INDEX['dependencyContracts'].get(req,{}).get('applicabilityTerms',[]))
            selectors.update({'shipCategory','iceClass','polarClass','designIceCondition','iceTypeClassification','constructionDate','constructionContractDate','shipIceStrengthened','iceAccretionLikely','operatesOnlyInContinuousDaylight','shipOperatesInLowAirTemperature'})
            selectors.update(str(p).split('#')[-1] for s,p in roots if any(token in str(p).split('#')[-1].lower() for token in ['applicab','applies','intent','likely','constructiondate','contractdate']))
            for policy in INDEX['dependencyContracts'].get(req,{}).get('selectorPolicies',[]):selectors.update(policy.get('selectorTerms',[]))
            changed_present_selectors=[str(p).split('#')[-1] for s,p in roots if str(p).split('#')[-1] in selectors and list(bad.objects(s,p)) and set(bad.objects(s,p))!=set(good.objects(s,p))]
            if changed_present_selectors:attempt['rejected']='PRESENT_APPLICABILITY_SELECTOR_WOULD_CHANGE: '+repr(changed_present_selectors)
            else:
                issues=schema_issues(good);attempt['repaired_schema_issues']=issues
                try:attempt['repaired_original_oracle']=bool(oracle(good))
                except Exception as exc:attempt['oracle_error']=f'{type(exc).__name__}: {exc}'
                if issues:attempt['rejected']='REPAIRED_FIXTURE_HAS_UNRELATED_OR_UNRECONCILED_SCHEMA_ISSUES'
                elif not attempt.get('repaired_original_oracle'):attempt['rejected']='INDEPENDENT_ORACLE_STILL_FAILS'
                elif record['negative_original_oracle'] and not record['negative_schema_issues']:attempt['rejected']='ORIGINAL_NEGATIVE_NOT_REJECTED_BY_INDEPENDENT_ORACLE'
                else:accepted.append((proposal,good,roots,attempt))
        record['candidate_attempts'].append(attempt)
    if not accepted:
        codes=sorted({a.get('rejected','NO_GRAPH') for a in record['candidate_attempts']})
        record['blockers'].append(dict(code='INTENDED_ONLY_REPAIR_NOT_ESTABLISHED',detail=f"For {cid}: {row['source_oracle_rationale']} No source-authoring default or canonical-unit repair passed the single-field, unchanged-applicability, schema and independent-oracle gates.",failed_gates=codes or ['No source-builder default restoration contract available']))
        return record
    # Equivalent proposals are fine; different independently valid counterfactuals
    # are not chosen according to generated-shape behavior. Use smallest RDF delta.
    accepted.sort(key=lambda x:(len(x[3]['removed_triples'])+len(x[3]['added_triples']),x[0].get('parameter','')))
    proposal,good,roots,attempt=accepted[0];folder=OUT/'cases'/cid;folder.mkdir(parents=True,exist_ok=True)
    bad.serialize(folder/'negative_fixture.ttl',format='nt',encoding='utf-8');good.serialize(folder/'repaired_fixture.ttl',format='nt',encoding='utf-8')
    record.update(stage='PAIR_VERIFIED',selected_repair=attempt,negative_fixture=str(folder/'negative_fixture.ttl'),repaired_fixture=str(folder/'repaired_fixture.ttl'),negative_fixture_sha256=audit.sha(folder/'negative_fixture.ttl'),repaired_fixture_sha256=audit.sha(folder/'repaired_fixture.ttl'),independent_negative_valid=False,independent_repaired_valid=True,oracle_scope='Retained source-backed representation contract plus canonical schema; not full-vessel regulatory compliance')
    return record
