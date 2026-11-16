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
  if c['method'] not in ['NLTL','Single-shot','offline','evaluation','study']:raise ValueError('Unknown method')
  if not 1<=c.get('maximum_candidate_attempts',1)<=6:raise ValueError('Attempt limit must be 1..6')
  if c.get('fresh_regeneration',False):raise ValueError('Fresh regeneration disabled for prefix study')
  for v in c.get('resources',{}).values():
   if not self.path(v).is_file():raise ValueError('Missing configured resource: '+v)
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
 @property
 def key(self):return digest(json.dumps([self.category,self.location,self.expected,self.excerpt]))
 def asdict(self):return dataclasses.asdict(self)
def finding(c,category,message,excerpt='',expected='',evidence='',suggestion='',location='candidate',confirmed=True,diagnostic=None):
 token=excerpt if excerpt and excerpt in c.code else None
 if not token and excerpt.startswith(('http://','https://')):
  for prefix,namespace in re.findall(r'(?i)(?:@prefix|PREFIX)\s+([\w-]+):\s*<([^>]+)>',c.code):
   if excerpt.startswith(namespace) and prefix+':'+excerpt[len(namespace):] in c.code:token=prefix+':'+excerpt[len(namespace):];break
 if token:
  pos=c.code.index(token);line=c.code.count('\n',0,pos)+1;column=pos-c.code.rfind('\n',0,pos)
  location+=f' [line {line}, column {column}; token {token}]'
 return Finding(category,message,location,excerpt,expected,evidence,suggestion,c.version,c.sha256,diagnostic if diagnostic is not None else message,confirmed)
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
