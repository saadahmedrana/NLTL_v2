import sys,json,pathlib,collections
from rdflib import Graph,Literal,URIRef,Namespace
p=pathlib.Path(__file__).resolve().parent;S=Namespace('http://www.w3.org/ns/shacl#');N='https://w3id.org/nltl/vocab#';fs=[]
for row in json.loads((p/'shape_inventory.json').read_text()):
 g=Graph().parse(row['path']);ctx=json.loads(pathlib.Path(row['context']).read_text());meta={t['iri']:t for t in ctx['terms']}
 for n,path in g.subject_objects(S.path):
  term=meta.get(str(path),{})
  if term.get('kind')=='ObjectProperty':
   for dt in g.objects(n,S.datatype):fs.append(dict(**row,family='WRONG_IRI_NAMESPACE',mechanism='OBJECT_PROPERTY_TREATED_AS_LITERAL_DATATYPE',property=str(path),bad=str(dt),expected='IRI/object with sh:class '+str(term.get('range')),certainty='CONFIRMED_STATIC',metadata=term,excerpt=f'sh:path <{path}>; sh:datatype <{dt}>',effect='Valid controlled-value IRIs reject as non-literals.'))
print(collections.Counter(f['condition'] for f in fs))
for f in fs:print(f['condition'],f['requirement_id'],f['property'],f['bad'])
(p/'kind_findings.json').write_text(json.dumps(fs,indent=2)+'\n')
