import json,pathlib,collections
from rdflib import Graph,Variable,Namespace
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue
D=pathlib.Path(__file__).resolve().parent;S=Namespace('http://www.w3.org/ns/shacl#')
def vars_expr(x):
 if isinstance(x,Variable):return {str(x)}
 if isinstance(x,dict):return set().union(*(vars_expr(v) for k,v in x.items() if k not in ['_vars','graph']))
 if isinstance(x,(list,tuple,set)):return set().union(*(vars_expr(v) for v in x))
 return set()
def bound(x):
 if not isinstance(x,CompValue):return set()
 if x.name=='BGP':return vars_expr(x.get('triples',[]))
 if x.name=='Extend':return bound(x['p'])|{str(x['var'])}
 if x.name=='Union':return bound(x['p1'])|bound(x['p2']) # possible, not definite: conservative
 if x.name in ['Join','LeftJoin']:return bound(x['p1'])|bound(x['p2'])
 if 'p' in x:return bound(x['p'])
 return set()
def walk(x,path=()):
 if isinstance(x,dict):
  yield x,path
  for k,v in x.items():
   if k!='_vars':yield from walk(v,path+(str(getattr(x,'name','dict'))+'/'+k,))
 elif isinstance(x,(list,tuple)):
  for i,v in enumerate(x):yield from walk(v,path+(str(i),))
fs=[]
for shape in json.loads((D/'shape_inventory.json').read_text()):
 g=Graph().parse(shape['path'])
 for q in g.objects(None,S.select):
  try:a=prepareQuery(str(q)).algebra
  except Exception:continue
  for node,path in walk(a):
   if not isinstance(node,CompValue) or node.name!='Filter':continue
   expr=node['expr']
   if not isinstance(expr,CompValue) or expr.name not in ['RelationalExpression','ConditionalAndExpression']:continue
   # Only required conjunction operands; an OR can succeed with another arm.
   required=[expr] if expr.name=='RelationalExpression' else [z for z in [expr['expr']]+list(expr.get('other',[])) if isinstance(z,CompValue) and z.name=='RelationalExpression']
   required_vars=set().union(*(vars_expr(z) for z in required))
   # EXISTS receives outer bindings by definition. Never flag its inner graph
   # as an independent UNION branch merely because an outer name is referenced.
   if any('/graph' in seg for seg in path):continue
   free={v for v in required_vars-bound(node['p'])-{'this','PATH','value','currentShape'} if not v.startswith('__agg_')}
   if free:fs.append(dict(**shape,family='SPARQL_BINDING_SCOPE',mechanism='UNBOUND_COMPARISON_IN_LOCAL_ALGEBRA_SCOPE',variables=sorted(free),algebra_path=path,expression=str(expr),query=str(q),certainty='PROVISIONAL_REQUIRES_QUERY_REVIEW',effect='A comparison with an unbound operand errors rather than producing a violation row.'))
(D/'scope_flags.json').write_text(json.dumps(fs,indent=2)+'\n')
print('sites',len(fs))
for w in ['NO_SEMANTIC','SINGLESHOT']:
 ff=[f for f in fs if f['condition']==w];print(w,'shapes',len({f['requirement_id'] for f in ff}),'reviewed exposures',len({c for f in ff for c in f['reviewed_cases']}))
 for r in sorted({f['requirement_id'] for f in ff}):print(r,sorted({v for f in ff if f['requirement_id']==r for v in f['variables']}))
