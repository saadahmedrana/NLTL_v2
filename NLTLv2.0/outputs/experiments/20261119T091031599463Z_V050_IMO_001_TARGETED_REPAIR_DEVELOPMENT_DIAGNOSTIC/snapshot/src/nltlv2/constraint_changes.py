"""Source-backed, exact-clause change permissions. No model-issued permissions.
Only unconditional sh:property/sh:node trees are attributed here. Finite tests are
counterexamples, not a general proof. Complete RDF graphs protect neighboring rules.
"""
import json,re,hashlib
from decimal import Decimal,InvalidOperation
from rdflib import Graph,URIRef,Literal,BNode,RDF,RDFS,XSD
from rdflib.namespace import SH
from rdflib.collection import Collection
from rdflib.compare import isomorphic
from .core import finding,digest
from .schema import Q
from .development_checks import assess,contracts

COSMETIC={SH.message,SH.name,SH.description,RDFS.label,RDFS.comment}

def nodes(g):
    def walk(node,steps,path,seen):
        if node in seen or g.value(node,SH.deactivated)==Literal(True):return
        yield node,steps,path
        for child in g.objects(node,SH.property):
            p=g.value(child,SH.path)
            if isinstance(p,URIRef):yield from walk(child,steps+[['property',str(p)]],path+[str(p)],seen|{node})
        for child in g.objects(node,SH.node):yield from walk(child,steps+[['node']],path,seen|{node})
    for root,target in g.subject_objects(SH.targetClass):
        if isinstance(root,URIRef):
            for node,steps,path in walk(root,[],[],set()):yield node,dict(root=str(root),target=str(target),steps=steps),path

def locate(g,locator):
    current=[URIRef(locator['root'])]
    if (current[0],SH.targetClass,URIRef(locator['target'])) not in g:return None
    for step in locator['steps']:
        current=[child for parent in current for child in g.objects(parent,SH.property if step[0]=='property' else SH.node) if step[0]!='property' or g.value(child,SH.path)==URIRef(step[1])]
    return current[0] if len(current)==1 else None

def term_data(g,pred,obj):
    if pred==SH['in']:return dict(members=[x.n3() for x in Collection(g,obj)])
    return dict(term=obj.n3())

def local_shape(g,node):
    out=Graph();seen=set();root=URIRef('urn:nltlv2:constraint-root')
    def visit(s):
        if s in seen:return
        seen.add(s)
        for p,o in g.predicate_objects(s):
            out.add((root if s==node else s,p,root if o==node else o))
            if isinstance(o,BNode):visit(o)
    visit(node)
    # Turtle may serialize a decimal as a bare numeric token. Normalize both
    # descriptions identically for attribution only; never alter input SHACL/data.
    return Graph().parse(data=out.serialize(format='turtle'),format='turtle')

def leaf_matches(report,g,node,path,row,component):
    data=Graph().parse(data=row['synthetic_graph'],format='turtle')
    owners={URIRef('urn:nltlv2:development:subject')}
    for p in path[:-1]:owners={v for owner in owners for v in data.objects(owner,URIRef(p))}
    for result in report.subjects(RDF.type,SH.ValidationResult):
        if report.value(result,SH.sourceConstraintComponent)!=component or report.value(result,SH.resultPath)!=g.value(node,SH.path) or report.value(result,SH.focusNode) not in owners:continue
        source=report.value(result,SH.sourceShape)
        if isinstance(node,URIRef) and source==node:return True
        if source is not None and isomorphic(local_shape(g,node),local_shape(report,source)):return True
    return False

def permission(c,contract,locator,predicate,value,kind,schema):
    files=['schema/Schema_for_NLTL.ttl','schema/locked_representation_context.jsonld','data/contracts/constraint_change_policy.json']
    evidence={name:hashlib.sha256(schema.project.path(name).read_bytes()).hexdigest() for name in files}
    body=dict(policy_version='0.5.0',schema_policy_sha256=evidence,candidate_version=c.version,candidate_sha256=c.sha256,contract_id=contract['id'],source=contract['source'],representation_evidence=contract['representation_evidence'],locator=locator,predicate=str(predicate),value=value,kind=kind)
    return dict(body,authorization_id=digest(json.dumps(body,sort_keys=True)))

def review(c,schema,rid):
    """Independently validates source, path, and a report's actual leaf constraint.
    A whole-shape failure or a reviewer suggestion alone cannot authorize a deletion.
    """
    contract=contracts(schema).get(rid)
    if not contract or contract['operation'] not in ['constant_equal','conditional_value']:return []
    try:g=Graph().parse(data=c.code,format='turtle')
    except Exception:return []
    _,coverage=assess(c,schema,rid);rows=coverage.get('witnesses',[]);out=[]
    for node,locator,path in nodes(g):
        if locator['target']!=contract['target_class'] or locate(g,locator)!=node:continue
        numeric=contract['operation']=='constant_equal' and path==contract['fields']['items']['path']+[str(Q.numericValue)]
        selector=contract['operation']=='conditional_value' and path==contract['fields']['selector']['path']
        if not numeric and not selector:continue
        pred=SH.hasValue if numeric else SH['in']
        for obj in g.objects(node,pred):
            if numeric:
                if not isinstance(obj,Literal) or obj.datatype!=XSD.decimal:continue
                try:
                    if Decimal(str(obj))!=Decimal(contract['constant']):continue
                except InvalidOperation:continue
                relevant=[r for r in rows if r['witness_id'].startswith('numeric-lexical-equivalent-')]
            else:
                try:members=list(Collection(g,obj))
                except Exception:continue
                relevant=[r for r in rows if r['expected_conforms'] and r['input'].get('selector') and URIRef(r['input']['selector']) not in members]
            evidence=[]
            for row in relevant:
                if row['status']!='CONFIRMED_COUNTEREXAMPLE' or not row['expected_conforms']:continue
                report=Graph().parse(data=row['validation_report'],format='turtle')
                component=SH.HasValueConstraintComponent if numeric else SH.InConstraintComponent
                # Blank-node IDs from data and shape graphs are deliberately not compared.
                if leaf_matches(report,g,node,path,row,component):
                    evidence.append(row)
            if not evidence:continue
            kind='NUMERIC_VALUE_EQUALITY_EXACT_TERM' if numeric else 'UNSUPPORTED_SELECTOR_CLOSURE'
            grant=permission(c,contract,locator,pred,term_data(g,pred,obj),kind,schema)
            # Precise RDF locator is stable across parsing; source text is included verbatim.
            excerpt=obj.n3() if numeric and obj.n3() in c.code else ''
            pattern=(r'sh:hasValue\s+"'+re.escape(str(obj))+r'"\^\^[^\s;]+') if numeric else r'sh:in\s*\([^)]*\)'
            excerpts=re.findall(pattern,c.code)
            if len(excerpts)==1:excerpt=excerpts[0]
            expected=('Numeric equality to '+contract['constant']+' with xsd:decimal, including equivalent decimal spellings; no tolerance.' if numeric else 'Selector readiness plus conditional result, without excluding the source-backed nonapplicable selector.')
            suggestion=('Replace only this numeric sh:hasValue with equal sh:minInclusive/sh:maxInclusive bounds using the source constant, or retain an already equivalent numeric comparison after removing this redundant exact-term test. Preserve sh:datatype xsd:decimal, presence, unit and all other constraints.' if numeric else 'Remove only the identified selector sh:in clause and its private RDF list. Preserve selector sh:minCount, term kind/class, conditional query and all unrelated constraints; no other deletion is authorized.')
            detail=dict(status=kind,validated_change_authorization=grant,source=contract['source'],representation_evidence=contract['representation_evidence'],branch_control_evidence=contract.get('branch_control_evidence'),exact_constraint=dict(locator=locator,predicate=str(pred),value=term_data(g,pred,obj),complete_data_path=path),original_validation_log=evidence[0]['original_validation_log'],witness_evidence=evidence,expected=expected,observed='Source-valid synthetic input rejected by the identified leaf component',scope_limits='Unconditional explicit property/node trees only; this is exact-clause authorization, not arbitrary query equivalence.')
            out.append(finding(c,'SOURCE_BACKED_LOGIC_ERROR',kind,excerpt,expected=expected,evidence=json.dumps(dict(source=contract['source'],representation=contract['representation_evidence'],branch=contract.get('branch_control_evidence'))),suggestion=suggestion,location='RDF constraint '+json.dumps(locator,sort_keys=True)+' predicate '+str(pred),diagnostic=json.dumps(detail,ensure_ascii=False),contract_id=contract['id'],obligation_id=kind,check_id=digest(json.dumps(locator,sort_keys=True)),assessment='INDEPENDENTLY_VALIDATED_CONSTRAINT_CHANGE'))
    return out

def grants(findings):
    result=[]
    for f in findings or []:
        if f.assessment=='INDEPENDENTLY_VALIDATED_CONSTRAINT_CHANGE':
            result.append(json.loads(f.diagnostic)['validated_change_authorization'])
    return result

def erase(g,grant):
    node=locate(g,grant['locator'])
    if node is None:return False
    pred=URIRef(grant['predicate']);matches=[o for o in g.objects(node,pred) if term_data(g,pred,o)==grant['value']]
    if len(matches)!=1:return False
    obj=matches[0];g.remove((node,pred,obj))
    if pred==SH['in']:
        # Delete only now-private RDF list cells; shared lists remain protected.
        while obj!=RDF.nil and isinstance(obj,BNode) and not list(g.subject_predicates(obj)):
            nxt=g.value(obj,RDF.rest);g.remove((obj,RDF.first,None));g.remove((obj,RDF.rest,None));obj=nxt
    return True

def clean(g):
    for pred in COSMETIC:g.remove((None,pred,None))
    return g

def protected_matches(code,diagnostic):
    """Used by the persistent guard too. Permissions never transfer to a new clause."""
    g=clean(Graph().parse(data=code,format='turtle'))
    protected=Graph().parse(data=diagnostic['protected_graph'],format=diagnostic.get('protected_graph_format','turtle'))
    for grant in diagnostic['authorizations']:
        if grant['kind']=='NUMERIC_VALUE_EQUALITY_EXACT_TERM':
            node=locate(g,grant['locator'])
            if node is not None:
                n=Decimal(diagnostic['numeric_constant'])
                # Only the supported exact numeric-bound replacement is permitted.
                for p in [SH.minInclusive,SH.maxInclusive]:
                    for value in list(g.objects(node,p)):
                        try:valid=isinstance(value,Literal) and value.datatype in [XSD.decimal,XSD.integer] and Decimal(str(value))==n
                        except InvalidOperation:valid=False
                        if valid:
                            original=locate(protected,grant['locator'])
                            if original is None or (original,p,value) not in protected:g.remove((node,p,value))
    return isomorphic(g,protected)

def authorized_regression(previous,current,findings,schema,rid):
    requested=grants(findings)
    if not requested:return None
    verified=review(previous,schema,rid);valid=grants(verified)
    if any(x not in valid for x in requested):raise ValueError('AUTHORIZATION_INTEGRITY_FAILURE: absent, stale or unvalidated exact constraint permission')
    g=clean(Graph().parse(data=previous.code,format='turtle'))
    for grant in requested:
        if not erase(g,grant):raise ValueError('AUTHORIZATION_INTEGRITY_FAILURE: ambiguous exact clause')
    contract=contracts(schema)[rid]
    detail=dict(authorizations=requested,protected_graph=g.serialize(format='nt'),protected_graph_format='nt',numeric_constant=contract.get('constant'),previous_candidate_version=previous.version,previous_candidate_sha256=previous.sha256)
    if protected_matches(current.code,detail):return []
    return [finding(current,'SOURCE_BACKED_LOGIC_ERROR','Repair changed protected constraints beyond the exact authorized correction','',expected='Preserve the protected RDF graph; only listed exact clauses may change.',evidence=json.dumps(requested),suggestion='Keep the supported correction; restore other changed readiness, conditional, target, datatype or unrelated constraints. The authorized defective restriction must not be restored.',location='RDF preservation graph comparison',diagnostic=json.dumps(detail),contract_id='candidate-obligation-preservation',obligation_id='exact-authorized-change',check_id=digest(previous.sha256),assessment='EXACT_CHANGE_PRESERVATION_GUARD')]

def preservation_conflicts(c,findings,previous_findings):
    """Never resolve a contradiction by silently restoring a validated bad clause."""
    authorized=grants(previous_findings);out=[]
    for f in findings:
        if f.assessment!='REGRESSION_GUARD':continue
        required=json.loads(f.diagnostic.split('REMOVED_OR_CHANGED ',1)[1])
        for grant in authorized:
            value=grant['value'].get('term') or json.dumps(sorted(grant['value'].get('members',[])))
            path=next((step[1] for step in reversed(grant['locator']['steps']) if step[0]=='property'),'node')
            if [grant['predicate'],path,value] in required:
                out.append(finding(c,'PRESERVATION_CONFLICT','Validated exact correction contradicts a preservation instruction','',expected='Stop dispatch and retain both pieces of evidence for adjudication',evidence=json.dumps(grant),suggestion='Resolve the contradictory preservation instruction; do not restore the independently demonstrated defective restriction or broaden deletion permission.',location=f.location,diagnostic=json.dumps(dict(validated_authorization=grant,conflicting_guard=f.asdict())),contract_id='candidate-obligation-preservation',obligation_id='preservation-conflict',check_id=grant['authorization_id'],assessment='PRESERVATION_CONFLICT'))
    return out
