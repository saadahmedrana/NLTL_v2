"""Deterministic delivery/handoff; no model calls or evaluation imports."""
import hashlib,shutil,json
from .core import write

def finalize(output,history,terminal):
 # A provider failure during review must not erase completed technical evidence.
 history=list(history)
 known={h['version'] for h in history}
 for path in sorted(output.glob('technical_*.json')):
  technical=json.loads(path.read_text());v=technical['candidate_version']
  if v not in known:history.append(dict(version=v,sha256=technical['candidate_sha256'],technical=technical,accepted=False,review=None,findings=technical.get('findings',[])))
 integrity=terminal=='REQUEST_INTEGRITY_FAILURE'
 qualifying=[]
 for row in history:
  t=row.get('technical',{})
  if not t.get('qualifies'):continue
  p=output/f"candidate_{row['version']:02d}.ttl"
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('DELIVERY_CANDIDATE_INTEGRITY_FAILURE')
  qualifying.append(row)
 chosen=max(qualifying,key=lambda h:h['version']) if qualifying and not integrity else None
 status='NO_VERDICT' if chosen is None else 'ACCEPTED' if chosen.get('accepted') else 'UNVERIFIED'
 review=chosen.get('review') if chosen else None
 decision=(review or {}).get('decision')
 # Terminal review is preserved. This mapping is a handoff, not another review call.
 handoff='APPROVE' if status=='ACCEPTED' else 'REJECT' if status=='NO_VERDICT' or decision=='REJECT' else 'HUMAN_REVIEW_REQUIRED'
 result=dict(status=status,version=chosen['version'] if chosen else None,sha256=chosen['sha256'] if chosen else None,final_review=handoff,final_review_basis='Deterministic handoff from validated saved review and technical eligibility; no additional model review or repair',selected_review_decision=decision,terminal_review_decision=next((h['review']['decision'] for h in reversed(history) if h.get('review')),None),terminal_reason=terminal,selection_basis='Highest version passing fixed technical checks; no external scores',findings=chosen.get('findings',[]) if chosen else [],all_candidate_findings_preserved=True,correctness_certified=False)
 if chosen:shutil.copyfile(output/f"candidate_{chosen['version']:02d}.ttl",output/'delivered.ttl')
 write(output/'delivery.json',result);return result
