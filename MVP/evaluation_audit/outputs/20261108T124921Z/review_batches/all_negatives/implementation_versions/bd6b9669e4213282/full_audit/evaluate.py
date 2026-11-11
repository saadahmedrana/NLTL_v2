"""Paired offline evaluation with conservative, auditable reason matching."""
import hashlib
import json
import re
import shutil
from decimal import Decimal
from pathlib import Path
from rdflib import Graph, RDF, URIRef, Literal, XSD
from rdflib.collection import Collection
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue
from common import audit, BASE, OUT, OLD, atomic
from prepare import INDEX, REG, ONTO, schema_issues
from evidence import load_script, oracle_for
N,Q,S=audit.N,audit.Q,audit.S
BASELINE={(r['condition'],r['case_id']):r for r in audit.read(BASE/'baseline_results.json')}
PRIOR=audit.expected_specs(audit.HERE/'reviewed_failure_specs_batch50.json')


def path_value(g,node):
    if isinstance(node,URIRef):return str(node)
    if node is None:return None
    try:return [str(x) for x in Collection(g,node)]
    except Exception:return 'UNRESOLVED_COMPLEX_PATH'

def violations(report,shape):
    details=[]
    for node in report.subjects(RDF.type,S.ValidationResult):
        source=report.value(node,S.sourceShape);constraint=report.value(node,S.sourceConstraint);component=report.value(node,S.sourceConstraintComponent)
        values=lambda p:list(report.objects(source,p)) or (list(shape.objects(source,p)) if isinstance(source,URIRef) else [])
        params={str(p):[x.n3() for x in values(p)] for p in [S.hasValue,S['class'],S.datatype,S.minCount,S.maxCount,S.minInclusive,S.maxInclusive,S.minExclusive,S.maxExclusive] if values(p)}
        query=report.value(constraint,S.select) if constraint is not None else None
        if query is None and constraint is not None:query=shape.value(constraint,S.select)
        enumeration=[]
        heads=values(S['in'])
        if len(heads)==1:
            try:enumeration=[x.n3() for x in Collection(report,heads[0])]
            except Exception:pass
        details.append(dict(component=str(component).removeprefix(str(S)),path=path_value(report,report.value(node,S.resultPath)),focus=str(report.value(node,S.focusNode)),source_shape=str(source),messages=[str(x) for x in report.objects(node,S.resultMessage)],parameters=params,enumeration=enumeration,nested_details=len(list(report.objects(node,S.detail))),query=str(query) if query is not None else None,query_sha256=hashlib.sha256(str(query).encode()).hexdigest() if query is not None else None,logic_fingerprint=audit.logic_fingerprint(shape,source,'OrConstraintComponent') if str(component)==str(S.OrConstraintComponent) and isinstance(source,URIRef) else None))
    return details

def parameter(v,p):
    values=v['parameters'].get(str(p),[])
    if len(values)!=1:return None
    try:return next(iter(audit.load_triples([f'<urn:parameter> <urn:value> {values[0]} .'])))[2]
    except Exception:return None

def not_exists_patterns(query):
    """Inspect parsed algebra; never execute a query to invent a repair."""
    found=[]
    try:root=prepareQuery(query).algebra
    except Exception:return found
    def triples(node):
        out=[]
        if isinstance(node,CompValue):
            if node.name=='BGP':out.extend(node.get('triples',[]))
            for value in node.values():out.extend(triples(value))
        elif isinstance(node,(list,tuple)):
            for value in node:out.extend(triples(value))
        return out
    def walk(node):
        if isinstance(node,CompValue):
            if node.name=='Builtin_NOTEXISTS':found.extend(triples(node.get('graph')))
            for value in node.values():walk(value)
        elif isinstance(node,(list,tuple)):
            for value in node:walk(value)
    walk(root);return found

def oracle_callable(record):
    if record['requirement_id']=='I2-048':return lambda g:audit.table_oracle(g,INDEX['dependencyContracts']['I2-048'])
    return oracle_for(load_script(record['preparation_script']),record['requirement_id'])

def numeric_boundary_matches(record,good,q,component,bound):
    """Verify the reported boundary against the independent source oracle.

    This verifies violation semantics after the repair was frozen. It does not
    search for or choose repair values using a generated constraint.
    """
    if bound is None:return False,{}
    try:value=Decimal(str(bound));step=max(abs(value),Decimal('1'))*Decimal('0.00001')
    except Exception:return False,{}
    source_oracle=oracle_callable(record)
    probes={}
    for label,numeric in [('at',value),('below',value-step),('above',value+step)]:
        graph=audit.clone(good);graph.set((q,Q.numericValue,Literal(str(numeric),datatype=XSD.decimal)))
        try:probes[label]=bool(source_oracle(graph)) and not schema_issues(graph)
        except Exception:probes[label]=None
    needed={'MinInclusiveConstraintComponent':(True,False,None),'MinExclusiveConstraintComponent':(False,False,True),'MaxInclusiveConstraintComponent':(True,None,False),'MaxExclusiveConstraintComponent':(False,True,False)}
    expected=needed.get(component)
    return bool(expected and all(want is None or probes[k] is want for k,want in zip(['at','below','above'],expected))),dict(bound=str(value),step=str(step),outcomes=probes)

def match_reason(record,bad,good,shape,details):
    roots=[(URIRef(s),URIRef(p)) for s,p in record['selected_repair']['semantic_roots']]
    props={p for s,p in roots};good_owners={(s,p) for s,p in roots if list(good.objects(s,p))}
    quantity_nodes={q for s,p in good_owners for q in good.objects(s,p) if (q,RDF.type,Q.QuantityValue) in good}
    missing={(s,p) for s,p in good_owners if not list(bad.objects(s,p))}
    unit_nodes={q for q in quantity_nodes if set(bad.objects(q,Q.unit))!=set(good.objects(q,Q.unit))}
    matched=[];unrelated=[];unresolved=[];wrappers=[];proofs=[]
    for v in details:
        c=v['component'];path=v['path'];focus=URIRef(v['focus']);ok=False;known=False
        if c=='NodeConstraintComponent' and v['nested_details']:
            wrappers.append(v);continue # all nested ValidationResults are inspected below
        if c in ['MinCountConstraintComponent','HasValueConstraintComponent'] and isinstance(path,str) and (focus,URIRef(path)) in missing:
            if c=='MinCountConstraintComponent':ok=parameter(v,S.minCount)==Literal(1)
            else:
                required=parameter(v,S.hasValue);ok=required is not None and required in set(good.objects(focus,URIRef(path)))
            known=True
        elif c=='MaxCountConstraintComponent' and isinstance(path,str) and URIRef(path) in props:
            maximum=parameter(v,S.maxCount)
            contract_max=record['source_evidence']['contract'].get('cardinalityPolicies',{}).get(path.split('#')[-1],{}).get('maxCount')
            if (focus,URIRef(path)) in good_owners and maximum is not None and contract_max is not None and int(maximum)==contract_max:
                ok=len(list(bad.objects(focus,URIRef(path))))>int(maximum) and len(list(good.objects(focus,URIRef(path))))<=int(maximum);known=True
        elif path==str(Q.unit) and focus in unit_nodes and c=='HasValueConstraintComponent':
            required=parameter(v,S.hasValue);ok=required is not None and set(good.objects(focus,Q.unit))=={required};known=True
        elif c=='HasValueConstraintComponent' and isinstance(path,str) and (focus,URIRef(path)) in good_owners:
            required=parameter(v,S.hasValue);ok=required is not None and required in set(good.objects(focus,URIRef(path))) and required not in set(bad.objects(focus,URIRef(path)));known=True
        elif c=='ClassConstraintComponent' and isinstance(path,str) and (focus,URIRef(path)) in good_owners:
            required=parameter(v,S['class']);ranges=set(ONTO.objects(URIRef(path),audit.RDFS.range))
            ok=required is not None and required in ranges;known=True
        elif c=='InConstraintComponent' and isinstance(path,str) and (focus,URIRef(path)) in good_owners:
            # A changed field alone does not establish the meaning of sh:in.
            # Exhaust the independently finite boolean domain; other domains
            # need a separately reviewed enumeration contract.
            current=list(good.objects(focus,URIRef(path)))
            if current and all(isinstance(x,Literal) and x.datatype==XSD.boolean for x in current) and v.get('enumeration'):
                expected=set();source_oracle=oracle_callable(record)
                for value in [Literal(True),Literal(False)]:
                    probe=audit.clone(good);probe.set((focus,URIRef(path),value))
                    if source_oracle(probe) and not schema_issues(probe):expected.add(value.n3())
                ok=set(v['enumeration'])==expected and set(bad.objects(focus,URIRef(path)))!=set(current);known=True
        elif c=='DatatypeConstraintComponent' and ((path==str(Q.numericValue) and focus in quantity_nodes) or (isinstance(path,str) and (focus,URIRef(path)) in good_owners)):
            expected=parameter(v,S.datatype)
            values=list(good.objects(focus,URIRef(path))) if isinstance(path,str) else []
            ok=bool(expected and values and all(isinstance(x,Literal) and (x.datatype or XSD.string)==expected for x in values));known=True
        elif path==str(Q.numericValue) and focus in quantity_nodes and c in ['MinInclusiveConstraintComponent','MinExclusiveConstraintComponent','MaxInclusiveConstraintComponent','MaxExclusiveConstraintComponent']:
            p={'MinInclusiveConstraintComponent':S.minInclusive,'MinExclusiveConstraintComponent':S.minExclusive,'MaxInclusiveConstraintComponent':S.maxInclusive,'MaxExclusiveConstraintComponent':S.maxExclusive}[c]
            ok,proof=numeric_boundary_matches(record,good,focus,c,parameter(v,p));known=True;proofs.append(dict(component=c,focus=str(focus),independent_boundary_check=proof,matched=ok))
        elif c=='SPARQLConstraintComponent':
            query=v.get('query');patterns=not_exists_patterns(query) if query else []
            pset={p for s,p in roots}
            # Source-backed missing-link/value and canonical-unit semantics can
            # be exposed by a NOT EXISTS pattern, without message-text matching.
            for s,p in good_owners:
                if (s,p) in missing and any(pred==p for sub,pred,obj in patterns):ok=True;known=True
                for q in good.objects(s,p):
                    if q in unit_nodes:
                        units=set(good.objects(q,Q.unit))
                        if any(pred==p for sub,pred,obj in patterns) and any(pred==Q.unit and obj in units for sub,pred,obj in patterns):ok=True;known=True
                    elif isinstance(q,Literal) and q not in set(bad.objects(s,p)) and any(pred==p and obj==q for sub,pred,obj in patterns):ok=True;known=True
            for prior in PRIOR.values():
                if prior['requirement']!=record['requirement_id'] or URIRef(prior['expected_predicate']) not in pset:continue
                for rule in prior['admissible_semantics'].get(record['_workflow'],[]):
                    if rule.get('query_sha256')==v.get('query_sha256') and rule.get('query_sha256'):ok=True;known=True
                    if rule.get('logic_fingerprint') and audit.logic_fingerprint(shape,URIRef(v['source_shape']),'SPARQLConstraintComponent')==rule['logic_fingerprint']:ok=True;known=True
        elif c=='OrConstraintComponent':
            for prior in PRIOR.values():
                if prior['requirement']!=record['requirement_id'] or URIRef(prior['expected_predicate']) not in props:continue
                if any(rule.get('logic_fingerprint')==v.get('logic_fingerprint') and rule.get('logic_fingerprint') for rule in prior['admissible_semantics'].get(record['_workflow'],[])):ok=True;known=True
            source=URIRef(v['source_shape']);head=shape.value(source,S['or'])
            if head is not None:
                try:branches=list(Collection(shape,head))
                except Exception:branches=[]
                for owner,p in missing:
                    if focus!=owner:continue
                    def requires(branch):
                        properties=list(shape.objects(branch,S.property))
                        if shape.value(branch,S.path)==p:properties.append(branch)
                        return any(shape.value(n,S.path)==p and (shape.value(n,S.minCount) is not None and int(shape.value(n,S.minCount))>=1 or shape.value(n,S.hasValue) is not None) for n in properties)
                    if branches and all(requires(b) for b in branches):ok=True;known=True
        if ok:matched.append(v)
        elif known:unrelated.append(v)
        else:unresolved.append(v)
    return dict(intended=matched,unrelated=unrelated,unresolved=unresolved,wrappers=wrappers,semantic_checks=proofs)


def fault_cause(status,record,row,bad,good,repaired_details):
    if status=='STRICT_INTENDED_MATCH':return dict(primary='NONE_IDENTIFIED',detail='Reviewed fixture pair and violation semantics meet all strict conditions.')
    if status=='NO_VERDICT':return dict(primary='UNRESOLVED',detail='Original generation/eligibility produced no verdict; no offline credit is assigned.',generation_status=row['generation_status'],pipeline_status=row['generation_pipeline_status'])
    if status=='MISSED_INTENDED_DEFECT':return dict(primary='GENERATED_SHAPE_DEFECT',detail='The unchanged eligible shape accepts an independently source-invalid fixture. The specific originating prompt/context defect is not inferred.')
    for v in repaired_details:
        if v['path']==str(Q.unit):
            expected=parameter(v,S.hasValue);actual=set(good.objects(URIRef(v['focus']),Q.unit))
            if expected is not None and actual and expected not in actual:return dict(primary='RUNTIME_LITERAL_UNIT_PROBLEM',detail='The valid counterfactual uses the source/schema unit, but the shape requires a different unit IRI.',expected_by_shape=str(expected),source_fixture_units=[str(x) for x in actual])
        if v['component']=='MinCountConstraintComponent' and isinstance(v['path'],str) and v['path'].startswith(str(N)):
            prop=URIRef(v['path']);focus=URIRef(v['focus']);owners=list(good.subjects(prop,None));domains=set(ONTO.objects(prop,audit.RDFS.domain))
            if owners and domains and not any(d in set(good.objects(focus,RDF.type)) for d in domains):return dict(primary='CONTEXT_SCHEMA_MISMATCH',detail='The shape requires an absent property on a different focus/owner while source-valid owners already carry it.',property=str(prop),shape_focus=str(focus),source_owners=[str(x) for x in owners])
    return dict(primary='UNRESOLVED',detail='The independently valid intended-only counterfactual still rejects or violation meaning is not established. Reports are saved; no context-vs-generator cause is invented.')


def workflow_pair(record,row):
    w=row['condition'];folder=OUT/'cases'/record['case_id']/w;folder.mkdir(parents=True,exist_ok=True)
    bad=Graph().parse(record['negative_fixture']);good=Graph().parse(record['repaired_fixture'])
    assert set(bad)==set(Graph().parse(BASE/'corrected_benchmark'/row['rdf_path'])),'Saved negative report requires identical corrected RDF terms'
    result=dict(condition=w,workflow=row['workflow'],case_id=record['case_id'],requirement_id=record['requirement_id'],original_eligible=row['original_eligible'],negative_fixture=record['negative_fixture'],repaired_fixture=record['repaired_fixture'],arm='UNCHANGED_GENERATED_SHAPE')
    if not row['original_eligible']:
        result.update(status='NO_VERDICT',original_generation_status=row['generation_status'],original_pipeline_status=row['generation_pipeline_status'],negative=None,repaired=None)
        result['likely_cause']=fault_cause(result['status'],record,row,bad,good,[]);atomic(folder/'record.json',result);return result
    assert audit.sha(row['shape_path'])==row['generated_shape_sha256']
    shape=Graph().parse(row['shape_path']);shutil.copyfile(row['shape_path'],folder/'evaluated_shape.ttl')
    previous=BASELINE[w,record['case_id']];negative_report=Path(previous['corrected_report'])
    shutil.copyfile(negative_report,folder/'negative_report.ttl')
    text=negative_report.with_suffix('.txt')
    if text.exists():shutil.copyfile(text,folder/'negative_report.txt')
    negative_rg=Graph().parse(folder/'negative_report.ttl');negative=dict(conforms=previous['corrected_conforms'],report_path=str(folder/'negative_report.ttl'),report_sha256=audit.sha(folder/'negative_report.ttl'),reused_from=str(negative_report),violations=violations(negative_rg,shape))
    result['negative']=negative
    execution_path=folder/'repaired_execution.json';fingerprint=dict(negative_sha256=record['negative_fixture_sha256'],repaired_sha256=record['repaired_fixture_sha256'],shape_sha256=row['generated_shape_sha256'],environment=audit.read(BASE/'environment.json'))
    cached=audit.read(execution_path) if execution_path.exists() else None
    if cached and cached.get('input_fingerprint')==fingerprint:
        repaired=cached['result']
    else:
        try:repaired=audit.validate(good,shape,folder,'repaired')
        except Exception as exc:repaired=dict(conforms=None,error=f'{type(exc).__name__}: {exc}')
        atomic(execution_path,dict(input_fingerprint=fingerprint,result=repaired))
    result['repaired']=repaired
    repaired_details=[]
    if repaired.get('report_path'):
        repaired_details=violations(Graph().parse(repaired['report_path']),shape);repaired['violations']=repaired_details
    if repaired.get('conforms') is None:
        result.update(status='UNRESOLVED_REASON',blocker=dict(code='REPAIRED_VALIDATION_ERROR',detail=repaired.get('error','No repaired verdict')))
    elif negative['conforms'] is True:result['status']='MISSED_INTENDED_DEFECT'
    elif repaired['conforms'] is False:result['status']='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE'
    else:
        scoped=dict(record,_workflow=w);meaning=match_reason(scoped,bad,good,shape,negative['violations']);result['violation_reason_review']=meaning
        if meaning['unrelated']:result['status']='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE'
        elif meaning['unresolved'] or not meaning['intended']:
            result.update(status='UNRESOLVED_REASON',blocker=dict(code='VIOLATION_SEMANTICS_UNESTABLISHED',detail='The negative rejects and the intended-only repair passes, but one or more reported logical/SPARQL/complex-path failures lack a reviewed semantic correspondence. No strict credit is inferred from verdicts alone.',unresolved_components=[v['component'] for v in meaning['unresolved']]))
        else:result['status']='STRICT_INTENDED_MATCH'
    result['likely_cause']=fault_cause(result['status'],record,row,bad,good,repaired_details)
    result['shape_sha256']=row['generated_shape_sha256'];result['input_fingerprint']=fingerprint
    atomic(folder/'record.json',result);return result


def evaluate_case(record,rows):
    try:
        result=dict(record);result['workflows']={}
        for row in rows:
            try:result['workflows'][row['condition']]=workflow_pair(record,row)
            except Exception as exc:
                result['workflows'][row['condition']]=dict(condition=row['condition'],workflow=row['workflow'],status='UNRESOLVED_REASON',blocker=dict(code='EVALUATION_ERROR',detail=f'{type(exc).__name__}: {exc}'),original_eligible=row['original_eligible'])
        errors=[dict(workflow=w,**r['blocker']) for w,r in result['workflows'].items() if r.get('blocker')]
        result['blockers']=list(result.get('blockers',[]))+errors
        result['state']='BLOCKED' if errors else 'COMPLETED'
        result['stage']='PAIRED_EVALUATION_AND_REASON_REVIEW'
        return result
    except Exception as exc:return dict(record,state='BLOCKED',blockers=[dict(code='EVALUATION_FATAL',detail=f'{type(exc).__name__}: {exc}')])
