from pathlib import Path
import json,hashlib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_IDENTIFIER_ROUTING_AND_20_10_READINESS';A.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['src/nltlv2/requests.py','src/nltlv2/runner.py']:
 p=A/'before'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/n,p)
(A/'protected_before.json').write_text(json.dumps({str(p.relative_to(R)):sha(p) for folder in ['outputs/experiments','results','schema','data','evaluation','prompts','configs','docs'] for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}))
p=R/'src/nltlv2/requests.py';s=p.read_text();s=s.replace('def review_proposal_routing(obj,schema,rid,context):','def review_proposal_routing(obj,schema,rid,context,*,candidate=None):').replace(' """Route failures without changing properties, paths, roles, evidence or issues.',' """Compare supplied identifier spellings without mutating model proposals.')
needle=" evidenced=(supplied.get('kind')=='REPRESENTATION_ONLY' and supplied.get('owners')==bindings.get('owners',{}) and supplied.get('modelPaths')==bindings.get('model_paths',[]) and supplied.get('target_owner')==bindings.get('target_owner') and context.get('quantityEncoding')==schema.quantity_profile)"
assert needle in s
s=s.replace(needle,needle+'''
 # Identity resolution only: current-candidate namespace declarations and supplied mappings.
 # Never infer a new property/path or rewrite a model claim or role.
 namespaces={};resolutions=[]
 if candidate is not None:
  try:
   from rdflib import Graph
   namespaces={prefix:str(iri) for prefix,iri in Graph().parse(data=candidate.code,format='turtle').namespaces()}
  except Exception:pass  # Unparseable code grants no extra identifier aliases.
 path_terms={step for paths in allowed.values() for route in paths for step in route}|{schema.quantity_profile['numeric_predicate']}
 def identity(value,permitted):
  if not evidenced or not isinstance(value,str) or value in permitted:return value
  if ':' in value:
   prefix,local=value.split(':',1);expanded=namespaces.get(prefix,'')+local if prefix in namespaces else None
   return expanded if expanded in permitted else value
  matches=[iri for iri in permitted if schema.terms.get(iri,{}).get('localName')==value]
  return matches[0] if len(matches)==1 else value
''')
needle="   prop=proposal.get('property');proposed=proposal.get('proposed_path');role=proposal.get('proposed_path_role') or 'PROPERTY'\n   conflicts=review_conflicts({'issues':[proposal]},schema,rid)"
assert needle in s
s=s.replace(needle,"""   raw_proposal=proposal;prop=identity(proposal.get('property'),set(allowed));raw_path=proposal.get('proposed_path');proposed=[identity(step,path_terms) for step in raw_path] if isinstance(raw_path,list) else raw_path;role=proposal.get('proposed_path_role') or 'PROPERTY'
   proposal=dict(proposal,property=prop,proposed_path=proposed)
   if prop!=raw_proposal.get('property') or proposed!=raw_path:resolutions.append(dict(path=path,original_property=raw_proposal.get('property'),resolved_property=prop,original_path=raw_path,resolved_path=proposed,basis='Exact current-candidate namespace/unique supplied localName identity within evidenced mappings; no model claim changed'))
   conflicts=review_conflicts({'issues':[proposal]},schema,rid)""")
s=s.replace("return dict(correctable=correctable,blocking=blocking,route='CONFLICT' if blocking else 'CORRECT_RESPONSE' if correctable else 'VALID')","return dict(correctable=correctable,blocking=blocking,identifier_resolutions=resolutions,route='CONFLICT' if blocking else 'CORRECT_RESPONSE' if correctable else 'VALID')")
p.write_text(s)
p=R/'src/nltlv2/runner.py';s=p.read_text().replace("review_proposal_routing(obj,self.schema,context['requirement']['id'],context)","review_proposal_routing(obj,self.schema,context['requirement']['id'],context,candidate=c)");p.write_text(s)
print(str(A))
