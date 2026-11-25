from pathlib import Path
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');p=R/'evaluation/evaluate_hosted_shared_start.py';s=p.read_text()
pos=s.index('def main():')
s=s[:pos]+'''def execute_unchanged(data,shape,schema,evaluator,scope_findings=(),parse_error=None):
 """Same execution for both arms. Scope violations block admitted credit, not diagnostics."""
 if shape is None:behavior=dict(conforms=None,status='CANDIDATE_PARSE_ERROR',error=parse_error);report=None
 else:behavior,report=evaluator.validate_pair_graph(data,shape,schema)
 findings=[f.asdict() if hasattr(f,'asdict') else f for f in scope_findings]
 admitted=dict(conforms=None,status='UNRESOLVED_SHAPE_SCOPE',findings=findings) if findings else dict(behavior)
 return dict(behavior=behavior,admitted=admitted,scope_findings=findings,scope_qualified=not findings),report

'''+s[pos:]
s=s.replace("    verdicts={};meanings=[]", "    verdicts={};admitted_verdicts={};meanings=[]")
s=s.replace("     verdict=dict(conforms=None,error=parse_error or 'UNRESOLVED_SHAPE_SCOPE') if shape is None or boundary else ev.validate_pair_graph(inputs[(c['case_id'],kind)][0],shape,s)[0]\n     verdicts[kind]=verdict", """     execution,report=execute_unchanged(inputs[(c['case_id'],kind)][0],shape,s,ev,boundary,parse_error)
     verdict=execution['behavior'];verdicts[kind]=verdict;admitted_verdicts[kind]=execution['admitted']
     if report is not None:
      d=E/item['workflow']/item['requirement_id']/('candidate_'+str(item['version']).zfill(2))/c['case_id'];d.mkdir(parents=True,exist_ok=True);report.serialize(d/(kind+'_report.ttl'),format='turtle')""")
s=s.replace("row.update(verdicts=verdicts,conforms=neg,ordinary_agreement=", "row.update(scope_findings=[f.asdict() for f in boundary],scope_qualified=not boundary,verdicts=verdicts,admitted_verdicts=admitted_verdicts,admitted_conforms=admitted_verdicts['fixture']['conforms'],conforms=neg,ordinary_agreement=")
s=s.replace("    rows.append(row)", "    if c.get('counterfactual'):row['admitted_strict_status']='INADMISSIBLE_SCOPE' if boundary else row['strict_status']\n    rows.append(row)")
s=s.replace("row['delivery_status']=entry['status'];row['final_review']=entry.get('final_review');selected_rows.append(row)", """row['delivery_status']=entry['status'];row['final_review']=entry.get('final_review');row['execution_status']='NOT_RUN' if entry['terminal_reason']=='NOT_RUN' else 'NO_VERDICT' if row['conforms'] is None else 'EVALUATED_UNCHANGED';selected_rows.append(row)""")
s=s.replace("no_verdict=sum(r['conforms'] is None for r in rs)", "no_verdict=sum(r['conforms'] is None and r['execution_status']!='NOT_RUN' for r in rs),not_run=sum(r['execution_status']=='NOT_RUN' for r in rs),scope_violation_cases=sum(bool(r.get('scope_findings')) for r in rs),admitted_correct=sum(r.get('admitted_conforms') is not None and r['ordinary_agreement'] is True for r in rs),admitted_no_verdict=sum(r.get('admitted_conforms') is None and r['execution_status']!='NOT_RUN' for r in rs),admitted_strict_statuses=dict(collections.Counter(r.get('admitted_strict_status') for r in rs if r['expected']=='FAIL'))")
s=s.replace("before=prev['conforms'],after=r['conforms'],change=", "before=prev['conforms'],after=r['conforms'],scope_before=prev['scope_qualified'],scope_after=r['scope_qualified'],admitted_before=prev['admitted_conforms'],admitted_after=r['admitted_conforms'],change=")
s=s.replace("held_out=False,dispatch_closed_sha256=", "held_out=False,evaluation_policy='Identical unchanged-shape execution for both arms; raw behavior and scope-qualified credit reported separately; NOT_RUN is not a model failure',dispatch_closed_sha256=")
p.write_text(s)
p=R/'src/nltlv2/token_budget.py';s=p.read_text().replace("if path.parent!=cache or hashlib", "if not path.is_file() or path.parent!=cache or hashlib");p.write_text(s)
p=R/'tests/test_hosted_shared_start.py';s=p.read_text().replace('max_request_bytes=110000,','')
a=s.index(' def test_context_limit_no_silent_truncation');b=s.index(' @patch.dict',a)
s=s[:a]+''' def test_large_complete_packet_is_not_blocked_by_bytes(self):
  with tempfile.TemporaryDirectory() as td:
   t=self.transport(pathlib.Path(td));q=self.request();q['user']='x '*110001
   with patch.object(t.session,'post',return_value=Mock(status_code=200,content=json.dumps(self.response()).encode())) as post:
    t.dispatch(q);self.assertEqual(json.loads(post.call_args.kwargs['data'])['input'][1]['content'][0]['text'],q['user']);self.assertEqual(t.calls,1)
'''+s[b:]
p.write_text(s)
print('Symmetric unchanged-shape behavioral/scope evaluation and byte-guard regression control added.')
