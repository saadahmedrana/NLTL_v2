"""Conservative deterministic document selection; no regulatory answers or case data."""
import re,hashlib

def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def normalized_positions(text):
 chars=[];offsets=[]
 for m in re.finditer(r'\S+|\s+',text):
  if m.group().isspace():chars.append(' ');offsets.append(m.start())
  else:chars.extend(m.group());offsets.extend(range(m.start(),m.end()))
 return ''.join(chars),offsets

def sections(text):
 starts=[]
 pattern=re.compile(r'^\s*(?:(I\d+(?:\.\d+)+|\d+(?:\.\d+)+(?:\.)?)\s+|((?:CHAPTER|PART|INTRODUCTION|ANNEX|APPENDIX)\b[^\n]*)|([0-9]+)\s+([A-Z][A-Za-z ,/–—-]{2,90})\s*$)',re.I)
 at=0
 for line in text.splitlines(True):
  m=pattern.match(line)
  if m:
   key=(m.group(1) or m.group(2) or m.group(3)).rstrip('.');title=line.strip()
   # Numbered list rows are conservatively selectable chunks, not asserted legal hierarchy.
   starts.append(dict(id=key,start=at,title=title))
  at+=len(line)
 if not starts or starts[0]['start']>0:starts.insert(0,dict(id='PREAMBLE',start=0,title='Document preamble'))
 for i,s in enumerate(starts):s['end']=starts[i+1]['start'] if i+1<len(starts) else len(text)
 return starts

def select_document(document,record,*,supporting=False):
 text=document['text'];parts=sections(text);norm,offsets=normalized_positions(text);needle=' '.join(record.get('text','').split());hits=[];at=0
 while needle:
  found=norm.find(needle,at)
  if found<0:break
  hits.append((offsets[found],offsets[found+len(needle)-1]+1));at=found+len(needle)
 selected=set();reasons={};unresolved=[]
 def add(i,why):selected.add(i);reasons.setdefault(i,[]).append(why)
 if supporting or len(hits)!=1:
  # Do not silently pick a repeated clause number or truncate an unlocatable source.
  for i in range(len(parts)):add(i,'FULL_DOCUMENT_SUPPORTING_OR_ANCHOR_NOT_UNIQUE')
  fallback='Supporting source retained in full' if supporting else 'Excerpt anchor absent or ambiguous; full source retained'
 else:
  fallback=None;lo,hi=hits[0]
  anchors=[i for i,s in enumerate(parts) if s['start']<hi and s['end']>lo]
  for i in anchors:add(i,'EXACT_EXCERPT_SECTION')
  add(0,'DOCUMENT_PREAMBLE')
  for i in anchors:
   key=parts[i]['id'];prefixes=['.'.join(key.split('.')[:n]) for n in range(1,len(key.split('.')))]
   for prefix in prefixes:
    candidates=[j for j,p in enumerate(parts[:i+1]) if p['id']==prefix]
    if candidates:add(candidates[-1],'NUMBERED_PARENT_CONTEXT')
   # Keep the nearest named part/chapter introduction, without pulling unrelated chapters.
   named=[j for j,p in enumerate(parts[:i+1]) if re.match(r'(?i)^(CHAPTER|PART|INTRODUCTION)',p['id'])]
   if named:add(named[-1],'NEAREST_NAMED_SCOPE')
  # Preserve scope/application/definition sections and their numbered descendants.
  for j,p in enumerate(parts):
   heading=p['title']
   if re.search(r'(?i)\b(definitions?|applicability|application|scope|general requirements|general principles)\b',heading) and len(heading)<180:
    add(j,'SOURCE_SCOPE_OR_DEFINITIONS')
    for k in range(j+1,len(parts)):
     if parts[k]['id'].startswith(p['id']+'.'):add(k,'DEFINITION_OR_SCOPE_DESCENDANT')
     else:break
  # Follow explicit local references to a fixed point; ambiguous targets retained, flagged.
  while True:
   old=set(selected)
   for i in sorted(old):
    body=text[parts[i]['start']:parts[i]['end']]
    for kind,key in re.findall(r'(?i)\b(section|paragraph|clause|chapter|table|annex|appendix)\s+((?:I\d+\.)?\d+(?:\.\d+)*|[A-Z])\b',body):
     # External legal citations are not resolved by matching this document's section number.
     external=bool(re.search(r'(?i)\b'+re.escape(kind)+r'\s+'+re.escape(key)+r'\s+of\s+(?:the\s+)?(?:Act|Convention|Code|Regulation|UR)\b',body))
     candidates=[] if external else [j for j,p in enumerate(parts) if p['id'].lower() in [key.lower(),(kind+' '+key).lower()] or re.match(r'(?i)^'+re.escape(kind)+r'\s+'+re.escape(key)+r'\b',p['title'])]
     if not candidates:
      note=dict(kind=kind,key=key,reason='External citation or local target not uniquely indexed; completeness requires review')
      if note not in unresolved:unresolved.append(note)
     else:
      if len(candidates)>1:
       note=dict(kind=kind,key=key,reason='Multiple matching references retained; scope needs review')
       if note not in unresolved:unresolved.append(note)
      for j in candidates:add(j,'EXPLICIT_REFERENCE')
   if old==selected:break
 # Merge adjacent selected ranges while retaining exact original characters and offsets.
 ranges=[]
 for i in sorted(selected):
  s=parts[i]
  if ranges and ranges[-1]['end']==s['start']:ranges[-1]['end']=s['end'];ranges[-1]['section_ids'].append(s['id'])
  else:ranges.append(dict(start=s['start'],end=s['end'],section_ids=[s['id']]))
 docs=[]
 for span in ranges:
  body=text[span['start']:span['end']];docs.append(dict(document,file=document['file'],text=body,selection=dict(**span,sha256=digest(body))))
 manifest=dict(file=document['file'],document_sha256=document['sha256'],policy='exact anchor, parent/scope/definitions, explicit references; no character/token truncation',fallback=fallback,unresolved_references=unresolved,sections=[dict(p,included=i in selected,reasons=reasons.get(i,[]),sha256=digest(text[p['start']:p['end']])) for i,p in enumerate(parts)],original_characters=len(text),included_characters=sum(len(d['text']) for d in docs))
 return docs,manifest

def retrieve(project,file,document_sha256,start,end):
 raw=project.path(file).read_bytes();text=raw.decode('utf-8');assert hashlib.sha256(raw).hexdigest()==document_sha256,'SOURCE_DOCUMENT_HASH_MISMATCH'
 if not 0<=start<end<=len(text):raise ValueError('INVALID_SOURCE_SPAN')
 return dict(file=file,document_sha256=document_sha256,start=start,end=end,text=text[start:end],sha256=digest(text[start:end]))
