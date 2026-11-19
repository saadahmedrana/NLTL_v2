"""Reusable source-authored finite witnesses. No external evaluation access or ID logic.
A mismatch is a concrete counterexample; a pass is never an equivalence proof.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import hashlib,json,copy
from collections import OrderedDict
_CACHE=OrderedDict()
from rdflib import Graph,URIRef,RDF,Literal,XSD
from rdflib.namespace import SH
from .core import load,finding,digest
from .execution_policy import classify,diagnostic
from .schema import Q,N

CORRECTIONS={
 'max_equal':'Require complete linked operands and a selected quantity; compare its numeric value with the maximum of all linked numeric values, supporting one or many cases and ties. Reject both below-maximum and above-maximum results; do not impose maxCount 1 on cases.',
 'constant_equal':'Require the represented sampled-point relationship and its complete quantity; enforce numeric equality to the source constant on each represented point (both inclusive bounds or equivalent). Do not replace equality with a one-sided bound.',
 'quantity_equal':'Require both complete quantity operands and compare their numeric values for equality at the evidenced paths, not quantity-node identity. Do not reverse the rejection predicate or invent a tolerance.',
 'conditional_value':'Require selector readiness under the locked policy. Enforce the required value in the applicable branch only; allow the known nonapplicable branch without this result. Absence of selector is not false applicability.'
}
RESOURCE='data/contracts/development_witness_contracts.json'
OPERATIONS={'max_equal','constant_equal','quantity_equal','conditional_value'}

def contracts(schema):
    rows=load(schema.project.path(RESOURCE))['requirements']
    for rid,c in rows.items():
        if c['operation'] not in OPERATIONS:raise ValueError('Unsupported development witness operation')
        profile=schema.development_profiles[rid]
        if c['source']!=profile['source']:raise ValueError('Witness source does not match approved source profile')
        for evidence in [c['source'],c['representation_evidence']]+([c['branch_control_evidence']] if 'branch_control_evidence' in c else []):
            file=schema.project.path(evidence['file'])
            if hashlib.sha256(file.read_bytes()).hexdigest()!=evidence['sha256']:raise ValueError('Stale witness evidence')
            if 'exact_excerpt' in evidence and evidence['exact_excerpt'] not in file.read_text():raise ValueError('Absent witness source excerpt')
        evidence=c['representation_evidence']
        if evidence['exact_contract']!=schema.index['dependencyContracts'][rid]:raise ValueError('Witness representation contract differs')
        allowed=schema.allowed_paths(rid)[1]
        if c['target_class']!=str(N[schema.allowed_paths(rid)[0]]):raise ValueError('Unverified witness target')
        for field in c['fields'].values():
            path=field['path']
            if tuple(path) not in allowed.get(path[-1],[]):raise ValueError('Witness path not established by explicit owner contract')
            if field['kind']=='quantity' and schema.terms[path[-1]].get('unitIri')!=field['unit']:raise ValueError('Witness unit differs from locked property representation')
        op=c['operation'];o=profile['obligations'][0]
        if op=='constant_equal' and Decimal(c['constant'])!=Decimal(str(o['source_constant'])):raise ValueError('Witness constant differs from source obligation')
        if op=='max_equal' and (o['kind']!='MAX_SELECTION' or c['fields']['result']['path'][-1]!=str(N[o['result']]) or c['fields']['items']['path'][-1]!=str(N[o['operands'][0]])):raise ValueError('Witness maximum operands differ')
        if op=='quantity_equal' and (o['kind']!='VALUE_EQUALITY' or c['fields']['operand']['path'][-1]!=str(N[o['operand']]) or c['fields']['result']['path'][-1]!=str(N[o['result']])):raise ValueError('Witness equality operands differ')
        if op=='conditional_value':
            if c['applicable_value']!=str(N[o['required_selector_value']]) or c['required_value']!=str(N[o['required_value']]):raise ValueError('Witness conditional values differ')
            if c['fields']['selector']['path']!=[str(N[o['selector']])] or c['fields']['value']['path']!=[str(N[o['result']])]:raise ValueError('Witness conditional paths differ')
            policy=schema.effective_contract(rid)['selectorPolicies'][0]
            if policy['absenceMeansFalse'] or policy['missingEvidence']!='VIOLATION':raise ValueError('Missing-selector witness not backed by readiness policy')
        if len({v['id'] for v in c['vectors']})!=len(c['vectors']):raise ValueError('Duplicate witness IDs')
        for v in c['vectors']:
            for name,f in c['fields'].items():
                if f['kind']=='iri' and name in v['values'] and v['values'][name] not in schema.canonical:raise ValueError('Unknown witness controlled value')
    return rows

def expected(c,values):
    """Independent arithmetic/branch oracle, defined only on synthetic input records."""
    def number(value,field):
        if value is None:return None
        d=value if isinstance(value,dict) else {'number':value,'unit':field['unit']}
        if d.get('unit')!=field['unit'] or 'number' not in d:return None
        try:
            n=Decimal(str(d['number']))
            return n if n.is_finite() else None
        except InvalidOperation:return None
    f=c['fields'];op=c['operation']
    if op=='conditional_value':
        if not values.get('selector'):return False
        return values['selector']!=c['applicable_value'] or values.get('value')==c['required_value']
    if op=='quantity_equal':
        a=number(values.get('result'),f['result']);b=number(values.get('operand'),f['operand'])
        return a is not None and b is not None and a==b
    items=[number(v,f['items']) for v in values.get('items',[])]
    if not items or any(v is None for v in items):return False
    if op=='constant_equal':return all(v==Decimal(c['constant']) for v in items)
    result=number(values.get('result'),f['result'])
    return result is not None and result==max(items)

def graph_for(c,vector,schema):
    """Generate new synthetic graphs from contract paths, not retained fixtures."""
    g=Graph();root=URIRef('urn:nltlv2:development:subject');g.add((root,RDF.type,URIRef(c['target_class'])))
    for name,field in c['fields'].items():
        if name not in vector['values']:continue
        seq=vector['values'][name] if name=='items' else [vector['values'][name]]
        for i,value in enumerate(seq):
            owner=root;path=field['path']
            for j,p in enumerate(path[:-1]):
                child=URIRef(f'urn:nltlv2:development:{name}:{i}:owner:{j}');g.add((owner,URIRef(p),child))
                for cls in schema.graph.objects(URIRef(p),__import__('rdflib').RDFS.range):g.add((child,RDF.type,cls))
                owner=child
            if value is None:continue
            predicate=URIRef(path[-1])
            if field['kind']=='iri':g.add((owner,predicate,URIRef(value)));continue
            q=URIRef(f'urn:nltlv2:development:{name}:{i}:quantity');g.add((owner,predicate,q));g.add((q,RDF.type,Q.QuantityValue))
            d=value if isinstance(value,dict) else dict(number=value,unit=field['unit'])
            if 'number' in d:g.add((q,Q.numericValue,Literal(d['number'],datatype=XSD.decimal)))
            if 'unit' in d:g.add((q,Q.unit,URIRef(d['unit'])))
    return g

def missing_requirements(contract,values):
    missing=[]
    for name,field in contract['fields'].items():
        if contract['operation']=='conditional_value' and name=='value' and values.get('selector')!=contract['applicable_value']:continue
        path=field['path']
        if name not in values or (name=='items' and not values[name]):
            missing.append(dict(path=path[:1] if name=='items' else path,requirement='Required represented input presence'));continue
        for value in values[name] if name=='items' else [values[name]]:
            if value is None:missing.append(dict(path=path,requirement='Required operand presence'))
            elif field['kind']=='quantity' and isinstance(value,dict):
                for key,predicate in [('number',str(Q.numericValue)),('unit',str(Q.unit))]:
                    if key not in value:missing.append(dict(path=path+[predicate],requirement='Complete canonical quantity input'))
    return missing

def assess(c,schema,rid,*,use_cache=True):
    contract=contracts(schema).get(rid)
    if not contract:return [],dict(status='NOT_CONFIGURED',complete_verification=False,unchecked=['No source-authored behavioral witness contract for this requirement.'])
    # Cache only exact candidate/version, evidence and current graph content; never cache execution failures.
    key=(c.version,c.sha256,rid,json.dumps(contract,sort_keys=True),tuple(sorted(schema.graph)))
    if use_cache and key in _CACHE:
        _CACHE.move_to_end(key);return copy.deepcopy(_CACHE[key])
    try:shape_graph=Graph().parse(data=c.code,format='turtle')
    except Exception as e:return [],dict(status='UNASSESSED_PARSE_ERROR',complete_verification=False,unchecked=[str(e)])
    from pyshacl import validate
    from .sparql_extensions import register_math_functions
    register_math_functions();rows=[];out=[]
    # Source-backed missing constraints have no offending constraint: locate target/full candidate explicitly.
    queries=[str(q) for q in shape_graph.objects(None,SH.select)]
    excerpt=queries[0] if len(queries)==1 else c.code
    for vector in contract['vectors']:
        data=graph_for(contract,vector,schema);want=expected(contract,vector['values'])
        record=dict(contract_scope_id='development:'+rid,obligation_id=contract['id'],witness_id=vector['id'],operation=contract['operation'],expected_conforms=want,input=vector['values'],synthetic_graph=data.serialize(format='turtle'),candidate_version=c.version,candidate_sha256=c.sha256)
        try:
            result,report,log=validate(data,shacl_graph=shape_graph,ont_graph=schema.graph,inference='rdfs',advanced=True,abort_on_first=False,meta_shacl=False,inplace=False)
            if not isinstance(result,bool) or not isinstance(report,Graph):raise RuntimeError(str(report))
            record.update(observed_conforms=result,original_validation_log=log,validation_report=report.serialize(format='turtle'),status='OBSERVED_MATCH' if want==result else 'CONFIRMED_COUNTEREXAMPLE')
            if want!=result:
                detail=dict(record,candidate_queries=[dict(excerpt=q,line=c.code.count('\n',0,c.code.find(q))+1 if q in c.code else None) for q in queries],source=contract['source'],representation_evidence=contract['representation_evidence'],scope=contract['scope'],readiness_policy=contract['readiness_policy'],attribution='Full-shape behavioral counterexample; report/query evidence does not prove unique root cause.',complete_verification=False)
                absent=missing_requirements(contract,vector['values']);detail['missing_requirements']=absent;detail['binding_evidence']=[]
                from .sparql_analysis import analyze
                for qi,q in enumerate(queries):detail['binding_evidence'].append(analyze(c,q,scope='SHACL-SPARQL:'+rid,slot='select['+str(qi)+']')[1])
                detail['minimal_relevant_input']=vector['values'];detail['offending_token']=None if absent else excerpt;detail['insertion_context']=dict(target_class=contract['target_class'],required_paths=absent) if absent else None
                out.append(finding(c,'SOURCE_BACKED_LOGIC_ERROR','Source-authored development counterexample: '+vector['id'],'' if absent else excerpt,expected='conforms='+str(want)+'; observed='+str(result),evidence=json.dumps(dict(source=contract['source'],representation=contract['representation_evidence'],scope=contract['scope'])),suggestion=CORRECTIONS[contract['operation']]+' Implement '+schema.development_profiles[rid]['obligations'][0]['description']+' Follow the evidenced paths and canonical units; enforce readiness for required operands. Use the observed witness/report to locate the missing or excessive constraint; preserve unrelated obligations. Passing finite witnesses is not proof.',location=('insertion context: '+contract['target_class']+'; missing obligation at '+json.dumps(absent)) if absent else ('sh:select' if len(queries)==1 else 'full candidate/target scope; constraint attribution not unique'),diagnostic=json.dumps(detail,ensure_ascii=False),contract_id='development:'+rid,obligation_id=contract['id'],witness_id=vector['id'],check_id='behavior:'+contract['operation'],query_sha256=digest(queries[0]) if len(queries)==1 else '',assessment='DEMONSTRATED_BEHAVIORAL_FAILURE'))
        except Exception as e:
            kind=classify(e);candidate=kind=='CANDIDATE_ERROR'
            record.update(status='UNASSESSABLE_CANDIDATE_ERROR' if candidate else 'UNRESOLVED_EXECUTION',failure_kind=kind,original_validation_log=diagnostic(e))
            out.append(finding(c,'SPARQL_ERROR' if candidate else 'RESOURCE_UNCERTAIN' if kind=='RESOURCE_UNCERTAIN' else 'INFRASTRUCTURE_ERROR','Generated query cannot execute' if candidate else 'Development witness execution unavailable',excerpt,expected='Executable witness result; no behavioral verdict exists for this candidate',evidence=json.dumps(contract['source']),suggestion='Correct the exact SHACL engine restriction in the existing query; preserve source obligations and established bindings.' if candidate else 'Stop dispatch and investigate infrastructure/resources; attribution to generated code is not established.',location='development witness runtime',confirmed=candidate,diagnostic=json.dumps(record),contract_id='SHACL-SPARQL:'+rid,obligation_id='sparql-execution',check_id='engine.execution',query_sha256=digest(queries[0]) if len(queries)==1 else '',assessment='CONFIRMED_CANDIDATE_QUERY_ERROR' if candidate else kind))

        rows.append(record)
    status='UNASSESSABLE_CANDIDATE_ERROR' if any(r['status']=='UNASSESSABLE_CANDIDATE_ERROR' for r in rows) else 'UNRESOLVED_EXECUTION' if any(r['status']=='UNRESOLVED_EXECUTION' for r in rows) else 'COUNTEREXAMPLES_FOUND' if out else 'FINITE_WITNESSES_PASSED'
    out=list({f.key:f for f in out}.values())
    result=(out,dict(contract_scope_id='development:'+rid,obligation_id=contract['id'],status=status,contract_id=contract['id'],source=contract['source'],scope=contract['scope'],witnesses=rows,complete_verification=False,unchecked=contract['limits']+['Only the listed synthetic graphs were tested; arbitrary multiplicities, datatypes and other unlisted branches are not certified.'],provenance=contract['provenance']))
    if use_cache and status not in ['UNRESOLVED_EXECUTION','UNASSESSABLE_CANDIDATE_ERROR']:
        _CACHE[key]=copy.deepcopy(result)
        while len(_CACHE)>64:_CACHE.popitem(last=False)
    return result
