"""Parsed conservative SPARQL analysis plus the locked engine's SHACL legality check.
Warnings are not proof. No query binding or regulatory solution is invented here.
"""
from rdflib import Variable
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from pyparsing import ParseResults
from pyshacl.helper.sparql_query_helper import SPARQLQueryHelper
from .core import finding,digest

def children(x):
 if isinstance(x,CompValue):return [(k,v) for k,v in x.items() if k!='_vars']
 if isinstance(x,(tuple,list,ParseResults)):return list(enumerate(x))
 return []
def variables(x):
 if isinstance(x,Variable):return {str(x)}
 return set().union(*(variables(v) for _,v in children(x))) if children(x) else set()
def walk(x,path='query'):
 if isinstance(x,CompValue):yield path,x
 for k,v in children(x):yield from walk(v,path+'/'+str(k))
def parsed_bindings(graph):
 """Only plain triple bindings are guaranteed inside supported EXISTS graph groups."""
 return set().union(*(variables(node.get('triples',[])) for _,node in walk(graph) if node.name=='TriplesBlock'))
def reads(expr):
 if isinstance(expr,Variable):return {str(expr)}
 if isinstance(expr,CompValue) and expr.name in ['Builtin_BOUND','Builtin_COALESCE']:return set()
 if isinstance(expr,CompValue) and expr.name in ['Builtin_EXISTS','Builtin_NOTEXISTS']:
  graph=expr.get('graph');return variables(graph)-parsed_bindings(graph)
 return set().union(*(reads(v) for _,v in children(expr))) if children(expr) else set()
def bound(node):
 if not isinstance(node,CompValue):return set()
 name=node.name
 if name=='BGP':return variables(node.get('triples',[]))
 if name=='Join':return bound(node.get('p1'))|bound(node.get('p2'))
 if name=='Union':return bound(node.get('p1'))&bound(node.get('p2'))
 if name=='LeftJoin':return bound(node.get('p1'))
 if name in ['Project','SelectQuery']:return {str(v) for v in node.get('PV',[])} & bound(node.get('p'))
 if name=='Extend':
  b=bound(node.get('p'));return b|({str(node['var'])} if reads(node.get('expr'))<=b|{'this'} else set())
 if name=='AggregateJoin':return bound(node.get('p'))|{str(a['res']) for a in node.get('A',[]) if 'res' in a}
 if 'p' in node:return bound(node['p'])
 return set()

def analyze(c,query,*,scope='SHACL-SPARQL',slot='query',value_prebound=False,extravars=()):
 out=[];query_hash=digest(query);report=dict(query_sha256=query_hash,slot=slot,nested_selects=[],binding_warnings=[],limits=['Conservative RDFLib algebra analysis; OPTIONAL/EXISTS/aggregates/correlation are not fully proven.','Engine legality check mirrors pySHACL 0.31.0; its regex coverage limits are retained alongside parsed nested-SELECT inspection.'])
 def emit(check_id,message,expected,suggestion,diagnostic,*,warning=False,path='query',excerpt=None):
  out.append(finding(c,'SPARQL_STATIC_WARNING' if warning else 'SPARQL_ERROR',message,query if excerpt is None else excerpt,expected=expected,evidence='Parsed RDFLib SPARQL structure and locked pySHACL 0.31.0 SHACL pre-binding contract',suggestion=suggestion,location='sh:select '+slot+' '+path,diagnostic=diagnostic,contract_id=scope,obligation_id='sparql-execution',check_id=check_id+':'+slot,query_sha256=query_hash,assessment='STATIC_WARNING' if warning else 'CONFIRMED_CANDIDATE_QUERY_ERROR',confirmed=not warning,blocking=not warning))
 try:tree=parseQuery(query)
 except Exception as e:
  emit('parse','Embedded query does not parse','Executable SPARQL','Correct the exact parser diagnostic only.',type(e).__name__+': '+str(e));return out,report
 try:algebra=prepareQuery(query).algebra
 except Exception as e:
  # SHACL may supply prefix context absent from the standalone query string.
  # Translation failure after successful parsing is not automatically bad code.
  report['unresolved_static_context']=type(e).__name__+': '+str(e)
  emit('translation_context','Standalone algebra translation needs unresolved query context','Resolve explicit SHACL prefix/environment evidence before judging the query','Check the supplied SHACL prefix declarations or unsupported translation context. Do not invent a namespace or binding.',report['unresolved_static_context'],warning=True)
  return out,report
 projected={str(v) for v in algebra.get('PV',[])}
 if algebra.name=='SelectQuery' and 'this' not in projected:emit('outer_projection','SHACL SELECT must project ?this','SELECT $this ...','Project the existing pre-bound focus variable; $this and ?this are equivalent.','Outer projected variables: '+str(sorted(projected)))
 # Use the actual locked engine implementation to preserve its diagnostic verbatim.
 engine_error=None
 try:SPARQLQueryHelper.__new__(SPARQLQueryHelper).check_invalid_sparql(query,valuenode=object() if value_prebound else None,extravars=set(extravars))
 except Exception as e:engine_error=str(e)
 nested=[(path,node) for path,node in walk(tree) if node.name=='SubSelect']
 for subquery_index,(path,node) in enumerate(nested):
  projection=node.get('projection',[]);names={str(x['var'] if 'var' in x else x['evar']) for x in projection if 'var' in x or 'evar' in x}
  missing=({'this'}|set(extravars))-names
  if value_prebound:missing|={'value'}-names
  report['nested_selects'].append(dict(ast_path=path,projected=sorted(names),missing_prebound=sorted(missing),explicit_projection=bool(projection)))
  if missing:
   emit('nested_prebound_projection:subquery['+str(subquery_index)+']','Nested SELECT omits potentially pre-bound variable(s): '+','.join(sorted(missing)),'Explicitly project '+', '.join('?'+v for v in sorted(missing)), 'Keep the established focus binding in scope and explicitly project it from this nested SELECT ($this and ?this are the same variable). Do not invent an alias binding or change the regulatory arithmetic. SELECT * is not a supported substitute.',engine_error or 'Parsed nested SELECT does not explicitly project potentially pre-bound variables: '+','.join(sorted(missing)),path=path)
 if engine_error and not any(f.check_id.startswith('nested_prebound_projection:') for f in out):
  emit('engine_legality','Locked SHACL engine rejects query structure','SHACL-SPARQL executable structure','Correct the exact engine legality diagnostic without adding unsupported operands or changing source logic.',engine_error)
 # RDFLib algebra translation can consume FILTER nodes inside EXISTS graphs.
 # Inspect the separate, unmodified parse tree for branch-local reads as well.
 for path,node in walk(tree):
  if node.name!='GroupOrUnionGraphPattern' or len(node.get('graph',[]))<2:continue
  for bi,branch in enumerate(node['graph']):
   local={'this'}
   for part in branch.get('part',[]):
    if part.name=='TriplesBlock':local|=variables(part.get('triples',[]))
    elif part.name=='Bind' and reads(part.get('expr'))<=local:local.add(str(part['var']))
   for fi,part in enumerate(branch.get('part',[])):
    if part.name!='Filter':continue
    needed=reads(part.get('expr'));missing=needed-local
    if not missing:continue
    ast=path+'/graph/'+str(bi)+'/part/'+str(fi)
    record=dict(ast_path=ast,node='UNION branch filter',required=sorted(needed),guaranteed_local_bindings=sorted(local),not_guaranteed=sorted(missing),certainty='STATIC_WARNING; correlation/runtime semantics not proven')
    report['binding_warnings'].append(record)
    emit('union_scope:branch['+str(bi)+']:'+','.join(sorted(missing)),'Operand binding is not guaranteed in this UNION branch: '+','.join(sorted(missing)),'Operands bound in the scope that evaluates the branch filter','Inspect the source-backed operand paths and this branch scope. Keep the filter where established operands are bound, or bind the evidenced operands within the branch. Do not introduce a guessed alias or substitute values.',__import__('json').dumps(record),warning=True,path=ast)
 for binding_index,(path,node) in enumerate(walk(algebra)):
  if node.name not in ['Filter','Extend']:continue
  available=bound(node.get('p'))|{'this'};needed=reads(node.get('expr'))
  # BOUND intentionally interrogates absent values.
  needed-=set().union(*(variables(x.get('arg')) for _,x in walk(node.get('expr')) if x.name=='Builtin_BOUND'))
  missing=needed-available
  if not missing:continue
  record=dict(ast_path=path,node=node.name,required=sorted(needed),guaranteed_local_bindings=sorted(available),not_guaranteed=sorted(missing))
  report['binding_warnings'].append(record)
  simple=not any(x.name in ['Union','ToMultiSet','LeftJoin','AggregateJoin','Builtin_EXISTS','Builtin_NOTEXISTS'] for _,x in walk(algebra))
  emit('unbound_'+node.name.lower()+':instance['+str(binding_index)+']',('Unbound '+('BIND' if node.name=='Extend' else 'FILTER')+' operand: ' if simple else 'Operand binding is not guaranteed in this branch: ')+','.join(sorted(missing)),'Bind every comparison operand in the scope that evaluates it','Inspect the parsed branch/local bindings. Bind source-backed operands inside the applicable branch or keep the filter in their established scope; do not substitute invented bindings. Validate on approved synthetic witnesses.',__import__('json').dumps(record),warning=True,path=path)
 return out,report
