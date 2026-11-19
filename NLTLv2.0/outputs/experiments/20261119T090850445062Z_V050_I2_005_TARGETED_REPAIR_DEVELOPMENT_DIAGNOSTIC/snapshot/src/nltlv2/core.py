from __future__ import annotations
import contextlib,dataclasses,datetime,hashlib,json,pathlib,re,socket
from typing import Any

def digest(text:str)->str:return hashlib.sha256(text.encode('utf-8')).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def write(p,x):pathlib.Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def stamp():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
class Project:
 def __init__(self,root):
  self.root=pathlib.Path(root).resolve()
  if not (self.root/'pyproject.toml').is_file():raise ValueError('Not an NLTLv2.0 project root')
 def path(self,relative):
  p=pathlib.Path(relative)
  if p.is_absolute() or '..' in p.parts:raise ValueError('Only project-relative resource paths allowed')
  out=(self.root/p).resolve()
  if not out.is_relative_to(self.root):raise ValueError('Resource escapes project root')
  return out
 def output(self,kind,identifier):
  if kind not in ['experiments','smoke_tests','audits'] or not re.fullmatch(r'[A-Za-z0-9_-]+',identifier):raise ValueError('Invalid output destination')
  p=self.path(f'outputs/{kind}/{identifier}');p.mkdir(parents=True,exist_ok=False);return p
 def config(self,relative):
  c=load(self.path(relative))
  if c['method'] not in ['NLTL','Single-shot','offline','evaluation','study','paired-development-pilot']:raise ValueError('Unknown method')
  if not 1<=c.get('maximum_candidate_attempts',1)<=6:raise ValueError('Attempt limit must be 1..6')
  if c.get('fresh_regeneration',False):raise ValueError('Fresh regeneration disabled for prefix study')
  policy=c.get('stagnation',{})
  if not isinstance(policy.get('enabled',False),bool):raise ValueError('Stagnation enabled must be boolean')
  for name in ['repeated_failure_set_limit','unchanged_candidate_limit','oscillation_limit']:
   limit=policy.get(name)
   if limit is not None and (isinstance(limit,bool) or not isinstance(limit,int) or limit<1):raise ValueError('Invalid explicit stagnation limit')
  if c.get('seed_candidate'):
   if c['method']!='NLTL' or c.get('run_label')!='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC':raise ValueError('Seed mode requires explicit NLTL diagnostic label')
   for key in ['path','raw_response']:
    seedpath=c['seed_candidate'][key]
    if not seedpath.startswith('smoke_tests/regression_inputs/') or not self.path(seedpath).is_file():raise ValueError('Seed must be approved development input, not evaluation data')
  for v in c.get('resources',{}).values():
   if not self.path(v).is_file():raise ValueError('Missing configured resource: '+v)
  if c['method']=='paired-development-pilot':
   from .preflight import validate_manifest
   validate_manifest(self,c)
  return c
@dataclasses.dataclass(frozen=True)
class Candidate:
 version:int
 code:str
 raw:str
 @property
 def sha256(self):return digest(self.code)
@dataclasses.dataclass(frozen=True)
class Finding:
 category:str
 message:str
 location:str
 excerpt:str
 expected:str
 evidence:str
 suggestion:str
 version:int
 candidate_sha256:str
 diagnostic:str
 confirmed:bool=True
 contract_id:str=''
 obligation_id:str=''
 witness_id:str=''
 check_id:str=''
 query_sha256:str=''
 assessment:str='CONFIRMED_FINDING'
 blocking:bool=True
 @property
 def key(self):return digest(json.dumps([self.contract_id,self.obligation_id,self.witness_id,self.check_id]))
 def asdict(self):return dataclasses.asdict(self)
def finding(c,category,message,excerpt='',expected='',evidence='',suggestion='',location='candidate',confirmed=True,diagnostic=None,contract_id='candidate-structural',obligation_id='',witness_id='',check_id='',query_sha256='',assessment='',blocking=True):
 base_location=location
 token=excerpt if excerpt and excerpt in c.code else None
 if not token and excerpt.startswith(('http://','https://')):
  for prefix,namespace in re.findall(r'(?i)(?:@prefix|PREFIX)\s+([\w-]+):\s*<([^>]+)>',c.code):
   if excerpt.startswith(namespace) and prefix+':'+excerpt[len(namespace):] in c.code:token=prefix+':'+excerpt[len(namespace):];break
 if token:
  pos=c.code.index(token);line=c.code.count('\n',0,pos)+1;column=pos-c.code.rfind('\n',0,pos)
  location+=f' [line {line}, column {column}]'
 return Finding(category,message,location,excerpt,expected,evidence,suggestion,c.version,c.sha256,diagnostic if diagnostic is not None else message,confirmed,contract_id,obligation_id or category,witness_id,check_id or digest(json.dumps([category,message,base_location,expected])),query_sha256,assessment or ('CONFIRMED_FINDING' if confirmed else 'UNRESOLVED'),blocking)
class WrapperError(ValueError):pass
def normalize(raw):
 # Port of R13 standalone wrapper slicing, tightened to reject multiple blocks.
 regex=re.compile(r'^[ \t]*(<BEGIN_SHACL>|<END_SHACL>|</END_SHACL>)[ \t]*(?:\r?\n|$)',re.M)
 hits=list(regex.finditer(raw));markers=[dict(marker=m.group(1),offset=m.start(),line=raw.count('\n',0,m.start())+1) for m in hits]
 if len(hits)!=2 or hits[0].group(1)!='<BEGIN_SHACL>' or hits[1].group(1) not in ['<END_SHACL>','</END_SHACL>']:
  raise WrapperError(json.dumps(dict(expected=['<BEGIN_SHACL>','<END_SHACL>'],observed=markers,error='Exactly one unambiguous standalone block required')))
 body=raw[hits[0].end():hits[1].start()]
 if not body.strip() or '```' in body:raise WrapperError('Empty SHACL body or Markdown fences inside block; observed='+json.dumps(markers))
 return body,dict(alternate_closing_marker=hits[1].group(1)=='</END_SHACL>',markers=markers,text_outside=bool((raw[:hits[0].start()]+raw[hits[1].end():]).strip()),body_sha256=digest(body))
@contextlib.contextmanager
def offline_network_guard():
 def denied(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
 orig=(socket.socket,socket.create_connection,socket.getaddrinfo)
 socket.socket=socket.create_connection=socket.getaddrinfo=denied
 try:yield
 finally:socket.socket,socket.create_connection,socket.getaddrinfo=orig

class GenerationProject(Project):
 """Resource firewall for source/context/check/repair. Evaluation is a separate consumer."""
 def path(self,relative):
  value=pathlib.Path(relative)
  if value.parts and value.parts[0] in ['evaluation','outputs','results']:
   raise ValueError('EVALUATION_RESOURCE_FORBIDDEN_IN_GENERATION_OR_REPAIR: '+str(relative))
  return super().path(relative)
