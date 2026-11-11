"""Read-only extraction of retained fixture authoring evidence.

Original generation/evaluation entrypoints and file-writing statements are never
executed. Only local builder/oracle declarations and pure fixture construction
statements are evaluated. No generated SHACL is read by this module.
"""
import ast
import functools
import inspect
import json
import re
from pathlib import Path
from rdflib import Graph

DANGEROUS={'write_text','write_bytes','mkdir','serialize','copy','copy2','copyfile','move','unlink','rmtree','open','exit','print','generate','generate_batch','validate_batch','main','run','SystemExit'}
CACHE={}

def unsafe(node):
    for n in ast.walk(node):
        if isinstance(n,ast.Call):
            name=n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else ''
            if name in DANGEROUS:return True
    return False

def load_script(path):
    path=Path(path).resolve()
    if str(path) in CACHE:return CACHE[str(path)]
    tree=ast.parse(path.read_text());ns={'__file__':str(path),'__name__':'retained_fixture_evidence_only'};traces=[];errors=[]
    def wrap(fn):
        @functools.wraps(fn)
        def traced(*args,**kwargs):
            result=fn(*args,**kwargs)
            graph=result if isinstance(result,Graph) else result[0] if isinstance(result,tuple) and result and isinstance(result[0],Graph) else None
            if graph is not None:
                bound=inspect.signature(fn).bind(*args,**kwargs)
                traces.append(dict(function=fn,arguments=dict(bound.arguments),signature=inspect.signature(fn),graph=graph))
            return result
        return traced
    for node in tree.body:
        if isinstance(node,ast.If) and '__name__' in ast.unparse(node.test):continue
        declaration=isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef))
        if not declaration and unsafe(node):continue
        try:
            if path.name.startswith('create_') and isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REPO' for t in node.targets):
                ns['REPO']=path.parent;continue
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
            if isinstance(node,ast.FunctionDef) and (node.name.startswith('build') or re.fullmatch(r'b\d+',node.name) or node.name in ['bg']):ns[node.name]=wrap(ns[node.name])
        except Exception as exc:errors.append(dict(line=node.lineno,error=f'{type(exc).__name__}: {exc}'))
    result=dict(namespace=ns,traces=traces,errors=errors,script=str(path));CACHE[str(path)]=result;return result

def oracle_for(loaded,requirement):
    ns=loaded['namespace'];oracle=ns.get('ORACLES',{}).get(requirement)
    if oracle is not None:return oracle
    if callable(ns.get('oracle')):
        fn=ns['oracle'];sig=inspect.signature(fn)
        if len(sig.parameters)==2:return functools.partial(fn,requirement)
    suffix=requirement.rsplit('-',1)[-1]
    for name in ['oracle_'+suffix,'oracle'+suffix,'o'+suffix]:
        if callable(ns.get(name)):return ns[name]
    return None

def case_graphs(loaded):
    out={}
    for key in ['CASES','CASE_DEFS']:
        for item in loaded['namespace'].get(key,[]):
            if isinstance(item,dict):
                cid=item.get('case_id');graph=item.get('graph') or item.get('g')
                if cid and isinstance(graph,Graph):out[cid]=graph
    return out

def trace_for(loaded,case_id):
    graph=case_graphs(loaded).get(case_id)
    matching=[]
    for t in loaded['traces']:
        if graph is not None and t['graph'] is graph:matching.append(t)
        elif any(v==case_id for v in t['arguments'].values() if isinstance(v,str)):matching.append(t)
    return matching[-1] if matching else None

def default_proposals(trace):
    """Explicit source-builder default restorations, not guessed positive pairs."""
    proposals=[]
    for name,value in trace['arguments'].items():
        param=trace['signature'].parameters[name]
        if param.default is inspect.Parameter.empty or name.lower() in {'cid','case_id','caseid','id','name'}:continue
        default=param.default
        if value==default:continue
        arguments=dict(trace['arguments']);arguments[name]=default
        try:
            bound=inspect.BoundArguments(trace['signature'],arguments)
            result=trace['function'](*bound.args,**bound.kwargs)
            graph=result if isinstance(result,Graph) else result[0] if isinstance(result,tuple) and result and isinstance(result[0],Graph) else None
            if graph is not None:proposals.append(dict(parameter=name,before=repr(value),after=repr(default),graph=graph))
        except Exception as exc:proposals.append(dict(parameter=name,before=repr(value),after=repr(default),error=f'{type(exc).__name__}: {exc}'))
    return proposals
