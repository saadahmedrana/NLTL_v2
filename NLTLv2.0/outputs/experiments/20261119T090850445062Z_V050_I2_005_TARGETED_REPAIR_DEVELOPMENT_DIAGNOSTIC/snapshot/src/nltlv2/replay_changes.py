"""Offline unchanged historical-candidate replay. No provider/evaluation access."""
import json
from .core import Candidate,digest,write,stamp
from .checks import check,regression
from .constraint_changes import grants
from .development_checks import assess
from .schema import Schema
from .requests import repair_request,assert_integrity

def replay_changes(project,manifest_path,run_id=None):
    from .core import GenerationProject
    p=GenerationProject(project.root);schema=Schema(p);manifest=json.loads(p.path(manifest_path).read_text())
    out=project.output('audits',run_id or stamp());rows=[];previous={}
    for item in manifest['candidates']:
        rid=item['requirement_id'];code=p.path(item['path']).read_text()
        if digest(code)!=item['sha256']:raise ValueError('REPLAY_SEED_INTEGRITY_FAILURE')
        raw=p.path(item['raw_response']).read_text()
        if digest(raw)!=item['raw_sha256']:raise ValueError('REPLAY_RAW_INTEGRITY_FAILURE')
        c=Candidate(item['version'],code,raw);dest=out/(rid+'_v'+str(c.version));dest.mkdir();(dest/'candidate.ttl').write_text(code)
        fs=check(c,schema,rid);bf,cov=assess(c,schema,rid);fs+=bf;prior=previous.get(rid)
        guard=regression(prior[0],c,prior[1],schema=schema,rid=rid) if prior else []
        write(dest/'findings.json',[f.asdict() for f in fs]);write(dest/'development_coverage.json',cov);write(dest/'pairwise_preservation.json',[f.asdict() for f in guard])
        if fs or guard:
            request=repair_request(p,schema.context(rid),c,fs+guard);write(dest/'repair_request.json',request);write(dest/'request_integrity.json',assert_integrity(request,c,fs+guard));(dest/'repair_request.rendered.txt').write_text(request['system']+'\n\n--- USER ---\n'+request['user'])
        rows.append(dict(requirement=rid,version=c.version,sha256=c.sha256,historical_candidate_unchanged=True,findings=[dict(category=f.category,assessment=f.assessment,message=f.message) for f in fs],counterexamples=[r['witness_id'] for r in cov['witnesses'] if r['status']=='CONFIRMED_COUNTEREXAMPLE'],witnesses=len(cov['witnesses']),validated_authorizations=len(grants(fs)),pairwise_preservation_findings=len(guard)))
        previous[rid]=(c,fs)
    result=dict(label='OFFLINE_HISTORICAL_DIAGNOSTIC_REPLAY',version='0.5.0',model_calls=0,evaluation_inputs_used=False,historical_scores_modified=False,pairwise_policy='Each adjacent historical pair checked independently; not workflow acceptance or permission for compound edits.',candidates=rows,output=str(out.relative_to(project.root)))
    write(out/'summary.json',result);write(out/'input_manifest.json',manifest);return result
