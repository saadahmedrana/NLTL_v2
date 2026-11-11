"""Explicit source-reviewed batch construction. No generated shape is read here."""
from pathlib import Path
import json
from rdflib import Graph, RDF, Literal, XSD, URIRef
import audit
from reviewed_oracles import inspect_fixture
N,Q=audit.N,audit.Q
U=audit.Namespace('http://qudt.org/vocab/unit/')
BASE=audit.HERE/'outputs/20261108T124921Z'
OUTPUT=audit.HERE/'reviewed_failure_specs_batch50.json'
# Each entry is a reviewed operation, not a name-derived positive/negative pairing.
# kind, owner path, property, repair value, intended independent-oracle defect.
OPS={
 'I2-004-G-F02':('quantity',[],N.upperIceWaterlineDisplacement,('12',U.KiloTON_Metric),'presence:'+str(N.upperIceWaterlineDisplacement)),
 'I2-004-G-F03':('unit',[],N.upperIceWaterlineDisplacement,U.KiloTON_Metric,'unit:'+str(N.upperIceWaterlineDisplacement)),
 'I2-005-G-F01':('number',[N.hasBottomRegionLowerRegionBoundaryPoint],N.shellInclinationAngle,'7','boundary_angle'),
 'I2-006-F01':('scalar',[],N.aftSectionDesignBasis,Literal('Bow and Bow Intermediate',datatype=XSD.string),'value:'+str(N.aftSectionDesignBasis)),
 'I2-006-F02':('scalar',[],N.hullAreaRequirementSet,Literal('Bow and Bow Intermediate hull area requirements',datatype=XSD.string),'presence:'+str(N.hullAreaRequirementSet)),
 'I2-006-F03':('scalar',[],N.aftSectionDesignBasis,Literal('Bow and Bow Intermediate',datatype=XSD.string),'presence:'+str(N.aftSectionDesignBasis)),
 'I2-013-F01':('evidence',[],N.classificationSocietyAccelerationEvidence,N.evidenceArtifact,'presence:'+str(N.classificationSocietyAccelerationEvidence)),
 'I2-013-F02':('evidence',[],N.inertialLoadDesignConsiderationEvidence,N.evidenceArtifact,'presence:'+str(N.inertialLoadDesignConsiderationEvidence)),
 'I2-019-F01':('number',[N.hasStructuralMember],N.selectedHullAreaFactor,'1.4','maximum_area_factor'),
 'I2-019-F03':('quantity',[N.hasStructuralMember],N.selectedHullAreaFactor,('1.4',U.UNITLESS),'presence:'+str(N.selectedHullAreaFactor)),
 'TRF-003-F01':('scalar',[],N.applicableIceClassRegulationEdition,N.iceClassRegulationEdition2010,'edition_2010'),
 'TRF-010-F01':('scalar',[],N.iceClass,N.iceClassIa,'ice_class_enumeration'),
 'TRF-010-F02':('scalar',[],N.iceClass,N.iceClassIa,'presence:'+str(N.iceClass)),
 'TRF-013-F01':('number',[],N.operatingForeDraught,'4','draught_range:Fore'),
 'TRF-013-F03':('quantity',[],N.maximumIceClassDraughtFore,('6',U.M),'presence:'+str(N.maximumIceClassDraughtFore)),
 'TRF-013-F05':('unit',[],N.operatingForeDraught,U.M,'unit:'+str(N.operatingForeDraught)),
 'TRF-017-F01':('number',[],N.maximumContinuousRatingPower,'5800','total_propulsion_power'),
 'TRF-017-F02':('number',[],N.maximumContinuousRatingPower,'4200','total_propulsion_power'),
 'TRF-018-F01':('number',[],N.maximumContinuousRatingPower,'1000','required_power_floor'),
 'TRF-018-F02':('number',[],N.maximumContinuousRatingPower,'2800','required_power_floor'),
 'TRF-018-F03':('number',[],N.maximumContinuousRatingPower,'3478','required_power_floor'),
 'TRF-018-F05':('unit',[],N.maximumContinuousRatingPower,U.KiloW,'unit:'+str(N.maximumContinuousRatingPower)),
 'IMO-006-F01':('number',[],N.iceThickness,'.7','ice_thickness_range'),
 'IMO-006-F02':('number',[],N.iceThickness,'1.2','ice_thickness_range'),
 'IMO-006-F03':('quantity',[],N.iceThickness,('.7',U.M),'presence:'+str(N.iceThickness)),
 'IMO-008-F01':('number',[],N.iceThickness,'.3','ice_thickness_range'),
 'IMO-008-F02':('number',[],N.iceThickness,'.7','ice_thickness_range'),
 'IMO-008-F03':('quantity',[],N.iceThickness,('.3',U.M),'presence:'+str(N.iceThickness)),
 'IMO-010-F01':('number',[],N.maximumExpectedRescueTime,'5','rescue_time_minimum'),
 'IMO-010-F02':('quantity',[],N.maximumExpectedRescueTime,('5',U.DAY),'presence:'+str(N.maximumExpectedRescueTime)),
 'IMO26-009-A-F01':('scalar',[N.hasRequiredNavigationOrCommunicationAntenna],N.antennaIceAccumulationPreventionPresent,Literal(True),'antenna_protection'),
 'IMO26-009-A-F03':('scalar',[],N.iceAccretionLikely,Literal(True),'presence:'+str(N.iceAccretionLikely)),
 'IMO26-009-A-F04':('scalar',[N.hasRequiredNavigationOrCommunicationAntenna],N.antennaIceAccumulationPreventionPresent,Literal(True),'presence:'+str(N.antennaIceAccumulationPreventionPresent)),
 'IMO26-014-A-F01':('scalar',[],N.visualIceDetectionIlluminationMeansCount,Literal(2),'illumination_minimum'),
 'IMO26-014-A-F03':('scalar',[],N.operatesOnlyInContinuousDaylight,Literal(False),'presence:'+str(N.operatesOnlyInContinuousDaylight)),
 'IMO26-014-A-F04':('scalar',[],N.visualIceDetectionIlluminationMeansCount,Literal(2),'presence:'+str(N.visualIceDetectionIlluminationMeansCount)),
}
SOURCE={
 'I2-004':('IACS_I2_full.txt',23,26,'Select the greatest represented UIWL displacement, in kt. Repair is max(10,12)=12.'),
 'I2-005':('IACS_I2_full.txt',83,84,'Boundary angle is exactly 7 degrees.'),
 'I2-006':('IACS_I2_full.txt',86,87,'Astern ice operation requires Bow and Bow Intermediate design basis and requirement set.'),
 'I2-013':('IACS_I2_full.txt',137,141,'Acceleration and inertial-load consideration evidence; represented evidence-readiness check, not engineering approval.'),
 'I2-019':('IACS_I2_full.txt',367,372,'Selected factor is the maximum of represented spanned-area factors, 1.4 in both selected fixtures.'),
 'TRF-003':('TRAFICOM_full.txt',224,233,'2015 contract requires 2010 edition and predates the optional 2017-12-01 exception.'),
 'TRF-010':('TRAFICOM_full.txt',280,300,'Exactly represented allowed ice-class assignment IA Super, IA, IB, IC, II or III; counterfactual IA is one allowed assignment, not an inference of actual class.'),
 'TRF-013':('TRAFICOM_full.txt',320,326,'For ice-strengthened operation fore/aft draughts lie within represented waterline bounds. Missing fore maximum 6 m is the explicit build_013 default at validate_traficom_batch_b.py:323-333, not inferred from another fixture.'),
 'TRF-017':('TRAFICOM_full.txt',361,368,'Total power includes available additional propulsion power; a restriction selects the restricted base. Repairs are 5000+800=5800 and 4200+0=4200 kW.'),
 'TRF-018':('TRAFICOM_full.txt',376,379,'Stored MCR >= max(stored calculated required power, class floor); this does not verify the external power calculation itself.'),
 'IMO-006':('IMO_full.txt',361,361,'Medium first-year ice is 0.7 to 1.2 m, inclusive; repair to the nearest permitted boundary.'),
 'IMO-008':('IMO_full.txt',375,384,'Thin first-year ice is 0.3 to 0.7 m, inclusive; repair to the nearest permitted boundary.'),
 'IMO-010':('IMO_full.txt',517,519,'Maximum expected rescue time never less than 5 days; repair to 5 days.'),
 'IMO26-009':('IMO26_full.txt',96,99,'When ice accretion is likely, every required navigation/communication antenna has prevention means. Chapter 9-1 scope is the preselected requirement scope.'),
 'IMO26-014':('IMO26_full.txt',137,143,'Outside continuous-daylight-only operation require two means of illumination; selector absence is readiness under frozen representation.'),
}

ANCHORS={
 'I2-004':('I2.1.2.2 The ship displacement',4),
 'I2-005':('I2.2.5 The boundary',2),
 'I2-006':('I2.2.6 If a ship',2),
 'I2-013':('(ix) Ship structures',5),
 'I2-019':('(ii) In the event that a structural member spans',2),
 'TRF-003':('As from 1 December 2017',10),
 'TRF-010':('1.8       Ice classes',26),
 'TRF-013':('The maximum and minimum ice class draughts at fore and aft',5),
 'TRF-017':('The engine output P is the total maximum output',5),
 'TRF-018':('The engine output shall not be less',2),
 'IMO-006':('2.8      Medium first-year ice',1),
 'IMO-008':('2.15     Thin first-year ice',1),
 'IMO-010':('1.2.7  Maximum expected time of rescue',3),
 'IMO26-009':('.3    for ships operating in areas',4),
 'IMO26-014':('9-1.3.3 Additional navigational equipment',5),
}

def construct():
    old=audit.read(BASE/'reviewed_failure_specs.json');assert len(old)==14
    rows=audit.read(BASE/'retained_rows.json');index={r['case_id']:r for r in rows if r['condition']=='NO_SEMANTIC'}
    contracts=audit.read(audit.R13/'requirement_term_index.json')
    registry={r['localName']:r for r in audit.read(audit.R13/'registry/term_registry.json')}
    ontology=Graph().parse(audit.ONTOLOGY)
    specs=list(old);records=[]
    for cid,(kind,path,prop,value,defect) in OPS.items():
        r=index[cid];req=r['requirement_id'];bad=Graph().parse(BASE/'corrected_benchmark'/r['rdf_path']);good=audit.clone(bad)
        owner=next(good.subjects(RDF.type,N.ship));owner_path=[];wrappers=[]
        for edge in path:
            wrappers.append(dict(paths=[str(edge)],focus=[str(owner)]))
            vs=list(good.objects(owner,edge));assert len(vs)==1;owner=vs[0];owner_path.append(str(edge))
        quantity=good.value(owner,prop)
        before=inspect_fixture(bad,req);assert before['defects']==[defect],(cid,before)
        def put(s,p,o):good.remove((s,p,None));good.add((s,p,o))
        if kind=='number':put(quantity,Q.numericValue,Literal(value,datatype=XSD.decimal))
        elif kind=='unit':put(quantity,Q.unit,value)
        elif kind=='scalar':put(owner,prop,value)
        elif kind in ['quantity','evidence']:
            assert quantity is None
            new=URIRef(str(owner).rsplit('/',1)[0]+'/auditRepair_'+str(prop).split('#')[-1])
            good.add((owner,prop,new))
            if kind=='quantity':
                numeric,unit=value;good.add((new,RDF.type,Q.QuantityValue));good.add((new,Q.numericValue,Literal(numeric,datatype=XSD.decimal)));good.add((new,Q.unit,unit))
            else:good.add((new,RDF.type,value))
        else:raise ValueError(kind)
        after=inspect_fixture(good,req);assert after['defects']==[],(cid,after)
        removed=audit.triples(set(bad)-set(good));added=audit.triples(set(good)-set(bad))
        assert removed or added
        # Violation semantics are established from the source and repair target,
        # before any generated constraint/report is inspected.
        semantics=[]
        if kind in ['quantity','evidence'] or defect.startswith('presence:'):
            semantics.append(dict(paths=[str(prop)],components=['MinCountConstraintComponent'],focus=[str(owner)]))
            semantics.append(dict(paths=[str(prop)],components=['HasValueConstraintComponent'],focus=[str(owner)]))
        elif kind=='unit':
            for c in ['HasValueConstraintComponent','InConstraintComponent']:
                semantics.append(dict(paths=[str(Q.unit)],components=[c],focus=[str(quantity)],**({'expected_constraint_parameters':{str(audit.S.hasValue):[str(value)]}} if c=='HasValueConstraintComponent' else {})))
        elif kind=='number':
            cs=['HasValueConstraintComponent','MinInclusiveConstraintComponent','MaxInclusiveConstraintComponent','EqualsConstraintComponent']
            if req=='IMO-006':cs=['MinInclusiveConstraintComponent'] if cid.endswith('F01') else ['MaxInclusiveConstraintComponent']
            if req=='IMO-008':cs=['MinInclusiveConstraintComponent'] if cid.endswith('F01') else ['MaxInclusiveConstraintComponent']
            if req=='IMO-010':cs=['MinInclusiveConstraintComponent']
            for c in cs:semantics.append(dict(paths=[str(Q.numericValue)],components=[c],focus=[str(quantity)]))
        else:
            cs=['InConstraintComponent','HasValueConstraintComponent']
            if req=='IMO26-014':cs=['MinInclusiveConstraintComponent','HasValueConstraintComponent']
            for c in cs:semantics.append(dict(paths=[str(prop)],components=[c],focus=[str(owner)]))
        if req=='TRF-010' and cid.endswith('F01'):
            semantics.append(dict(paths=[str(prop)],components=['ClassConstraintComponent'],focus=[str(owner)],expected_constraint_parameters={str(audit.S['class']):[str(N.iceClassValue)]}))
        if kind in ['number','unit']:wrappers.append(dict(paths=[str(prop)],focus=[str(owner)]))
        file,lo,hi,note=SOURCE[req];source=audit.HERE/'source_review'/file
        lines=source.read_text().split('\n');needle,count=ANCHORS[req];matches=[i for i,line in enumerate(lines) if needle in line and "...." not in line];assert len(matches)==1,(req,needle);lo=matches[0]+1;hi=lo+count-1;excerpt='\n'.join(lines[lo-1:hi]);assert excerpt
        term=registry[str(prop).split('#')[-1]]
        if kind=='unit':assert term['unitIri']==str(value)
        if kind=='quantity':assert term['unitIri']==str(value[1])
        owners=list(good.objects(owner,RDF.type));assert owners
        s=dict(requirement=req,case=cid,source_clause=r['source_clause'],source_oracle_rationale=r['source_oracle_rationale'],
            review_status='REVIEWED',batch='first_50',expected_predicate=str(prop),expected_path=owner_path+[str(prop)]+([str(Q.unit)] if kind=='unit' else [str(Q.numericValue)] if kind=='number' else []),expected_owner_class=str(owners[0]),
            applicability=note,fixture_review='Independent represented-requirement oracle finds exactly the intended defect before repair and no defects after repair. Unrelated prerequisites, all operands, units and declared owner types are checked.',
            repair_description=f'{kind}: {note} Change only the explicit triples below.',removed_triples=removed,added_triples=added,expected_repaired_outcome='PASS',
            fixture_oracle=dict(implementation='reviewed_oracles.inspect_fixture',requirement=req,expected_negative_defects=[defect],expected_repaired_defects=[],checked_conditions=after['checked']),
            source_evidence=dict(path=str(source),sha256=audit.sha(source),line_start=lo,line_end=hi,excerpt=excerpt,review_note=note),
            contract_evidence=dict(path=str(audit.R13/'requirement_term_index.json'),sha256=audit.sha(audit.R13/'requirement_term_index.json'),dependency_contract=contracts['dependencyContracts'][req],term_owners=contracts['termOwners'].get(req,{}),term_registry=term,ontology_domains=[str(x) for x in ontology.objects(prop,audit.RDFS.domain)]),
            admissible_semantics={w:[dict(x) for x in semantics] for w in audit.WORKFLOWS},
            semantic_definition='Reject only this named source-oracle defect at expected_path. Logical/SPARQL implementations require separately reviewed bindings; messages are not evidence.',
            reviewed_wrappers=wrappers,
            shape_independent_review=True)
        specs.append(s);records.append(dict(case_id=cid,requirement_id=req,negative_defects=before['defects'],repaired_defects=after['defects'],removed_triples=removed,added_triples=added,source_evidence=s['source_evidence'],checked_conditions=after['checked']))
    assert len(specs)==50 and len({s['case'] for s in specs})==50
    audit.dump(OUTPUT,specs)
    audit.dump(audit.HERE/'batch50_fixture_review.json',dict(specification_sha256=audit.sha(OUTPUT),generated_shapes_read=False,records=records))
    print('Frozen source-independent specifications:',len(specs),'across',len({s['requirement'] for s in specs}),'requirements')
if __name__=='__main__':construct()
