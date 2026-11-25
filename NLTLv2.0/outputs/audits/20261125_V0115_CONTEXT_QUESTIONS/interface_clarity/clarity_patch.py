from pathlib import Path
import hashlib,json,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/interface_clarity';A.mkdir(exist_ok=False)
files=['prompts/reviewer.txt','prompts/repair.txt','src/nltlv2/review_protocol.py','src/nltlv2/review_validation.py','src/nltlv2/runner.py'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in files+['outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/REPORT.txt']:
 p=A/'before'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/n,p)
protected={str(p.relative_to(R)):sha(p) for folder in ['outputs/experiments','results','evaluation','schema','data'] for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts};protected['docs/retention_ledger.json']=sha(R/'docs/retention_ledger.json');(A/'protected_before.json').write_text(json.dumps(protected))
(R/'prompts/reviewer.txt').write_text('''Assess the full current SHACL using these distinct inputs:
- Regulation establishes the represented obligation.
- Declared schema/mappings establish RDF identifiers, ownership, paths, datatypes and units; a similar label is not an equivalent mapping.
- Approved scope establishes declared external research assumptions, not real-vessel certification. Conditions inside the represented requirement remain in scope.
- Candidate code is what you assess, not source/schema evidence.
- Execution diagnostics establish observed technical behavior, not regulatory correctness or full coverage.

Procedure:
1. Read the represented requirement and approved scope.
2. Compare its conditions and obligations with the full current code, including activation, query branches and supplied changes/removals.
3. Report supported code defects as issues with actionable corrections. Preserve unaffected obligations; do not propose deletion just to pass checks.
4. Report genuinely missing or contradictory information as context questions, without inventing a code defect.
5. Explicitly address every carried-forward question using question_review; use current supplied evidence to support resolution/withdrawal. STILL_UNRESOLVED remains blocking.
6. Return one complete JSON object matching expected_response_schema and its authoritative description. Make assessment consistent with issues, questions, carried-forward questions and change/gap assessments. Delivery is separate from approval.

Evidence references identify supplied E entries only. Generic evidence-field example: "evidence":["E7"] (valid only if E7 is supplied). Optional evidence character spans refer to that entry, not code; asserted quotations must match exactly. RDF_FACT references cite the whole atomic fact.
Code locations belong in issues[].location. Generic location-field example: "location":{"start":1,"end":1,"unit":"lines"} (valid only if current line 1 exists). Software extracts exact code and binds hashes; do not quote code or invent an evidence ID such as candidate_shape. Missing constraints use a real insertion anchor. Context questions/dispositions need no code location.

Citations support claims, not their interpretation. Regulation need not contain RDF IRIs; mappings do not establish formulas or compliance answers. Keep missing mappings unresolved. Proposed representation changes must pair each operand's declared property/path/role; unit renaming is not conversion. Review supplied prior issues and functional changes/removals, including reachable replacements, using the documented conditional fields. Software owns IDs and bookkeeping.

Failed responses authorize no repair and create no accepted issues. For a response correction, keep the same candidate, evidence and original prior state; return the complete corrected review. Never request evaluation fixtures, labels, counterparts or historical solutions.
''')
(R/'prompts/repair.txt').write_text('''Revise previous_candidate: the COMPLETE latest SHACL, bound to candidate_version and candidate_sha256. Return the COMPLETE revised SHACL in one <BEGIN_SHACL> ... <END_SHACL> block. No regeneration or partial patch.

Read current_findings for what is wrong, the exact original diagnostics, affected locations, supporting evidence and suggested correction. Use the supplied regulation for obligations, schema/mappings for RDF representation and approved scope for declared external assumptions. Model findings are interpretations, not proof; execution diagnostics establish technical behavior only.

Make the targeted supported correction. Preserve unaffected obligations, activation, branches, comparisons, paths, units and datatypes. Never delete constraints merely to pass checks or silence an identifier error. Remove or replace an excessive constraint only when supplied source/schema/scope evidence supports that change; rechecking assesses preservation. Unit renaming is not numeric conversion.

Keep carried-forward material questions visible. Missing or contradictory representation must remain unresolved; do not invent an IRI, mapping, conversion or external eligibility assumption. Conditions inside the represented requirement remain in scope. Use the complete current code and resolved evidence supplied in this packet; raw reviewer logs remain artifacts. Never request evaluation fixtures, labels, counterparts or reference solutions.
''')
p=R/'src/nltlv2/review_protocol.py';s=p.read_text();a=s.index('def compact_contract_instructions():');b=s.index('\ndef contract_shape_errors',a)
s=s[:a]+'''def compact_contract_instructions():
 return ('Return complete assessment, issues and questions. APPROVE requires no current/prior issue or material question, all changes SUPPORTED and every supplied gap explicitly nonmaterial. REJECT needs an actionable code issue. HUMAN_REVIEW_REQUIRED needs a new/carried-forward material question or unresolved change/gap. '
 'Issue fields: description, evidence, location, suggestion. Evidence uses supplied E IDs or {id,start?,end?,quote?}; paired start/end are character offsets in that evidence, not code. RDF_FACT citations use the whole fact. Optional quotes are checked exactly. '
 'location uses start/end and optional unit=lines (default) or characters, on the full current candidate; software extracts exact code. Context questions/dispositions have no location and need no invented defect. '
 'Assess each supplied C ID once. REGRESSION links an actionable zero-based issue index; UNRESOLVED blocks approval. For APPROVE assess each G ID with material=false and why; material gaps require questions. '
 'Software owns hashes, IDs and reconciliation. Review supplied prior issues without returning duplicate bookkeeping. Unsupported assertions, invented references/quotes and inconsistent decisions are invalid; citation interpretation remains model judgment.')

def response_correction_instruction(errors):
 text='Correct the reported errors using expected_response_schema; return one complete review. Keep the SAME candidate, supplied evidence and ORIGINAL prior state. Failed output creates no accepted issues or repair permission; do not rewrite candidate code.'
 if any('.evidence' in e.get('path','') for e in errors):
  text+=' Evidence fields accept only supplied E IDs or {"id":"E7"} (E7 must exist in this packet), optionally paired character start/end and an exact quote. They do not accept unit or candidate IDs. Code references belong in issues[].location, e.g. {"start":1,"end":1,"unit":"lines"} if current line 1 exists; questions/dispositions need no code location. Omit optional quotations rather than paraphrasing them.'
 elif any('.location' in e.get('path','') for e in errors):text+=' Use a valid range in the full current candidate for issues[].location; line ranges are 1-based inclusive, character ranges are 0-based half-open. Software extracts code.'
 return text
''' + s[b:]
s=s.replace("  if all(variants):error('INVALID_FIELD_TYPE','One documented reference form')\n  return errors", "  if any(not v for v in variants):return []\n  for branch,branch_errors in zip(schema['anyOf'],variants):\n   if branch.get('type')=='object' and isinstance(value,dict) or branch.get('type')=='string' and isinstance(value,str):return branch_errors\n  error('INVALID_FIELD_TYPE','One documented reference form');return errors")
p.write_text(s)
p=R/'src/nltlv2/runner.py';s=p.read_text().replace('reviewer_schema,contract_instructions','reviewer_schema,contract_instructions,response_correction_instruction');old="instruction='Correct every error or withdraw an inconsistent issue. Pair each comparison operand explicitly using supplied representation evidence. Keep the SAME candidate, evidence, request binding and ORIGINAL prior issues; rejected output creates NO accepted issues or repair authorization. Return one complete response. Do not rewrite candidate code, relabel properties or invent paths to bypass validation. Full raw responses remain artifacts.'";assert old in s;s=s.replace(old,'instruction=response_correction_instruction(errors)');p.write_text(s)
p=R/'src/nltlv2/review_validation.py';s=p.read_text();s=s.replace(" errors+=contract_shape_errors(raw,schema)\n if errors:return None,audit,errors\n catalog=", " errors+=contract_shape_errors(raw,schema)\n shape_invalid=bool(errors)\n catalog=")
s=s.replace(' def references(refs,path):\n',' def references(refs,path,index_offset=0):\n').replace("at=path+'['+str(i)+']';r={'id':r}","at=path+'['+str(i+index_offset)+']';r={'id':r}")
a=s.index("   a,b=r.get('start',0),r.get('end',len(e['text']))",s.index('def validate_compact_review'));b=s.index('   resolved.append(',a)
s=s[:a]+'''   a,b=r.get('start',0),r.get('end',len(e['text']));valid_span=('start' in r)==('end' in r) and type(a) is int and type(b) is int and 0<=a<b<=len(e['text'])
   if not valid_span:error('INVALID_EVIDENCE_SPAN',at,'Paired 0-based character offsets with start < end inside the supplied evidence entry',r)
   whole_fact=e['kind']!='RDF_FACT' or a==0 and b==len(e['text'])
   if not whole_fact:error('RDF_FACT_REFERENCE_MUST_BE_WHOLE_FACT',at,'Cite the complete explicit RDF fact, not a fragment',r)
   text=e['text'][a:b] if valid_span else '';quote_ok=True
   if isinstance(r.get('quote'),str):
    problem=citation_error(catalog,r['id'],r['quote'],source=e['kind']=='SOURCE')
    if problem:error(problem[0],at+'.quote',problem[1],r['quote']);quote_ok=False
    elif valid_span and r['quote'] not in text and e['kind']!='RDF_FACT':error('ASSERTED_QUOTE_OUTSIDE_SPAN',at+'.quote','Asserted quotation inside cited span',r['quote']);quote_ok=False
   if not valid_span or not whole_fact or not quote_ok:continue
''' +s[b:]
s=s.replace(" def location(x,path):\n", """ if shape_invalid:
  # Inspect well-typed reference fragments independently; never accept a malformed review.
  if isinstance(raw,dict):
   for field in ['issues','questions','question_review','change_review']:
    items=raw.get(field,[])
    if not isinstance(items,list):continue
    for i,item in enumerate(items):
     if not isinstance(item,dict) or not isinstance(item.get('evidence'),list):continue
     for j,ref in enumerate(item['evidence']):
      if isinstance(ref,str) or isinstance(ref,dict) and isinstance(ref.get('id'),str):references([ref],'$.'+field+'['+str(i)+'].evidence',index_offset=j)
  return None,audit,errors
 def location(x,path):
""")
p.write_text(s)
print(str(A))
