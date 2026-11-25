import importlib.util,json,copy,pathlib,socket,sys
spec=importlib.util.spec_from_file_location('frozen_comp',str(pathlib.Path(__file__).with_name('run_frozen_comparison.py')));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def deny(*a,**k):raise RuntimeError('NO_NETWORK_SOFTWARE_CONTROL')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
ready=m.preflight_check();manifest,g,lock,state,c,payloads,limits=m.frozen_inputs();wire=json.loads(payloads['A_current']['input'][1]['content'][0]['text']);schema=m.Schema(m.Project(m.R))
# Synthetic software outputs, NEVER sent and no workflow credit.
response=dict(assessment='APPROVE',issues=[],questions=[],gap_review=[dict(id=x['id'],material=False,why='Scripted interface control only, no source correctness assertion.') for x in wire['retrieval_gaps']])
valid=m.inspect_response(dict(text=json.dumps(response)),wire,state,c,schema,False);assert valid['valid'],valid['errors']
missing=m.inspect_response(dict(text=json.dumps(response)),wire,state,c,schema,True);assert not missing['valid'] and missing['errors'][0]['code']=='MISSING_COMPARISON_COVERAGE'
source=next(e for e in wire['evidence_catalog']['entries'] if e['kind']=='SOURCE');entry=dict(criterion='Generic software instrumentation control only',kind='INPUT_READINESS',status='IMPLEMENTED',evidence=[source['evidence_id']],locations=[dict(start=1,end=1,unit='lines')],explanation='Synthetic format control, not substantive verification.')
withcoverage=copy.deepcopy(response);withcoverage['coverage']=[entry];tested=m.inspect_response(dict(text=json.dumps(withcoverage)),wire,state,c,schema,True);assert tested['valid'],tested['errors'];assert 'coverage' not in tested['projection'];assert withcoverage['coverage']==[entry]
for field,value,expected in [('evidence',['UNKNOWN'],'MISSING_OR_UNSUPPLIED_EVIDENCE_ID'),('locations',[dict(start=999999,end=999999,unit='lines')],'INVALID_CODE_RANGE'),('evidence',[dict(id=source['evidence_id'],start=0,end=0,quote='Invented quote software control')],'INVALID_EVIDENCE_SPAN')]:
 bad=copy.deepcopy(withcoverage);bad['coverage'][0][field]=value;result=m.inspect_response(dict(text=json.dumps(bad)),wire,state,c,schema,True);assert not result['valid'] and expected in [e['code'] for e in result['errors']],result['errors']
bad=copy.deepcopy(withcoverage);bad['coverage'][0]['status']='MISSING';assert 'COVERAGE_DECISION_CONTRADICTION' in [e['code'] for e in m.inspect_response(dict(text=json.dumps(bad)),wire,state,c,schema,True)['errors']]
trunc=m.inspect_response(dict(text='',status='incomplete',finish_reason='max_output_tokens'),wire,state,c,schema,False);assert trunc['errors'][0]['code']=='TRUNCATED_REVIEW'
assert m.classify(ValueError('SOURCE_FREEZE_INTEGRITY_FAILURE'))=='PIPELINE_INTEGRITY_ROUTING_OR_MISSING_IO';assert m.classify(RuntimeError('HOSTED_FINAL_OUTPUT_MISSING'))=='PIPELINE_INTEGRITY_ROUTING_OR_MISSING_IO';assert m.classify(RuntimeError('HOSTED_TRANSPORT_FAILURE_Timeout'))=='TRANSPORT_INFRASTRUCTURE'
assert manifest['max_HTTP_calls_total']==2*(1+manifest['shared_corrections_per_arm'])==4
print(json.dumps(dict(status='PASS',label='OFFLINE_SCRIPTED_INTERFACE_CONTROLS_NO_WORKFLOW_CREDIT',preflight=ready,controls=['A no-coverage permitted','B coverage required','valid coverage separate projection','unknown evidence rejected','bad code range rejected','invalid span/quote rejected','MISSING needs issue','truncation is protocol failure','distinct failure classes','4-call bound'],model_calls=0),indent=2))
