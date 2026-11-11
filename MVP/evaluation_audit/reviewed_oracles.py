"""Source/contract fixture checks for the first extension batch.

This module never reads generated SHACL or a validation report. Each check returns
named fixture defects; dependent calculations stop when an operand is unavailable
so one missing datum is not counted as several unrelated defects. Scope is the
represented requirement, not complete regulatory compliance of a real vessel.
"""
from datetime import date
from decimal import Decimal
from rdflib import Namespace, RDF, XSD, Literal
N=Namespace('https://w3id.org/nltl/vocab#')
Q=Namespace('http://qudt.org/schema/qudt/')
U=Namespace('http://qudt.org/vocab/unit/')
SUPPORTED={'I2-004','I2-005','I2-006','I2-013','I2-019','TRF-003','TRF-010','TRF-013','TRF-017','TRF-018','IMO-006','IMO-008','IMO-010','IMO26-009','IMO26-014'}

def inspect_fixture(g,requirement):
    if requirement not in SUPPORTED:raise ValueError('No reviewed extension oracle: '+requirement)
    defects=[];checked=[]
    def fail(code):defects.append(code)
    def mark(code):checked.append(code)
    def objects(s,p,required=True):
        mark('presence:'+str(p));vs=list(g.objects(s,p))
        if not vs and required:fail('presence:'+str(p))
        return vs
    def one(s,p,required=True):
        vs=objects(s,p,required)
        if len(vs)>1:fail('cardinality:'+str(p))
        return vs[0] if len(vs)==1 else None
    def scalar(s,p,datatype=None,required=True):
        v=one(s,p,required)
        if v is not None and datatype:
            mark('datatype:'+str(p))
            if not isinstance(v,Literal) or v.datatype!=datatype:fail('datatype:'+str(p));return None
        return v
    def quantity(s,p,unit,required=True):
        q=one(s,p,required)
        if q is None:return None
        mark('quantity_structure:'+str(p))
        if (q,RDF.type,Q.QuantityValue) not in g:fail('quantity_type:'+str(p))
        nums=list(g.objects(q,Q.numericValue));units=list(g.objects(q,Q.unit))
        if len(nums)!=1 or not isinstance(nums[0],Literal) or nums[0].datatype!=XSD.decimal:
            fail('numeric:'+str(p));return None
        if units!=[unit]:fail('unit:'+str(p));return None
        try:return Decimal(str(nums[0]))
        except Exception:fail('numeric:'+str(p));return None
    def links(s,p,cls):
        vs=objects(s,p)
        for v in vs:
            mark('owner_type:'+str(p))
            if (v,RDF.type,cls) not in g:fail('owner_type:'+str(p))
        return vs
    def compare(code,condition):
        mark(code)
        if not condition:fail(code)
    ships=list(g.subjects(RDF.type,N.ship))
    if len(ships)!=1:return dict(defects=['ship_target'],checked=['ship_target'])
    ship=ships[0]
    if requirement=='I2-004':
        values=[quantity(c,N.waterlineCaseDisplacement,U.KiloTON_Metric) for c in links(ship,N.hasUpperIceWaterlineCase,N.upperIceWaterlineCase)]
        selected=quantity(ship,N.upperIceWaterlineDisplacement,U.KiloTON_Metric)
        if values and all(v is not None for v in values) and selected is not None:compare('maximum_displacement',selected==max(values))
    elif requirement=='I2-005':
        for point in links(ship,N.hasBottomRegionLowerRegionBoundaryPoint,N.hullBoundaryPoint):
            angle=quantity(point,N.shellInclinationAngle,U.DEG)
            if angle is not None:compare('boundary_angle',angle==Decimal('7'))
    elif requirement=='I2-006':
        intent=scalar(ship,N.asternIceOperationIntent,XSD.boolean)
        if intent is not None and intent.toPython() is True:
            for p,value in [(N.aftSectionDesignBasis,'Bow and Bow Intermediate'),(N.hullAreaRequirementSet,'Bow and Bow Intermediate hull area requirements')]:
                v=scalar(ship,p,XSD.string)
                if v is not None:compare('value:'+str(p),str(v)==value)
    elif requirement=='I2-013':
        for p in [N.classificationSocietyAccelerationEvidence,N.inertialLoadDesignConsiderationEvidence]:links(ship,p,N.evidenceArtifact)
    elif requirement=='I2-019':
        for member in links(ship,N.hasStructuralMember,N.structuralMember):
            areas=links(member,N.hasSpannedHullArea,N.hullAreaValue)
            factors=[quantity(a,N.hullAreaFactor,U.UNITLESS) for a in areas]
            selected=quantity(member,N.selectedHullAreaFactor,U.UNITLESS)
            if factors and all(f is not None for f in factors) and selected is not None:compare('maximum_area_factor',selected==max(factors))
    elif requirement=='TRF-003':
        d=scalar(ship,N.constructionContractDate,XSD.date);edition=scalar(ship,N.applicableIceClassRegulationEdition)
        if d is not None and edition is not None:
            # Reviewed 2015 fixture predates the optional 2017-12-01 exception.
            value=date.fromisoformat(str(d))
            compare('edition_2010',date(2012,1,1)<=value<date(2017,12,1) and edition==N.iceClassRegulationEdition2010)
    elif requirement=='TRF-010':
        ice=scalar(ship,N.iceClass)
        if ice is not None:compare('ice_class_enumeration',ice in [N.iceClassIaSuper,N.iceClassIa,N.iceClassIb,N.iceClassIc,N.iceClassIi,N.iceClassIii])
    elif requirement=='TRF-013':
        strengthened=scalar(ship,N.shipIceStrengthened,XSD.boolean)
        ice=scalar(ship,N.iceClass)
        if strengthened is not None and strengthened.toPython() is True:
            links(ship,N.hasUpperIceWaterline,N.iceWaterline);links(ship,N.hasLowerIceWaterline,N.iceWaterline)
            for end in ['Fore','Aft']:
                low=quantity(ship,N['minimumIceClassDraught'+end],U.M)
                high=quantity(ship,N['maximumIceClassDraught'+end],U.M)
                actual=quantity(ship,N['operating'+end+'Draught'],U.M)
                if low is not None and high is not None:compare('ordered_limits:'+end,low<=high)
                if all(v is not None for v in [low,high,actual]):compare('draught_range:'+end,low<=actual<=high)
    elif requirement=='TRF-017':
        restricted=scalar(ship,N.propulsionOutputRestrictionApplies,XSD.boolean)
        continuous=quantity(ship,N.propulsionMachineryContinuousOutput,U.KiloW)
        total=quantity(ship,N.maximumContinuousRatingPower,U.KiloW)
        additional=quantity(ship,N.additionalPropulsionPower,U.KiloW,required=False)
        if additional is None and not list(g.objects(ship,N.additionalPropulsionPower)):additional=Decimal('0')
        if restricted is not None:
            base=quantity(ship,N.restrictedPropulsionOutput,U.KiloW) if restricted.toPython() is True else continuous
            if all(v is not None for v in [base,total,additional]):compare('total_propulsion_power',total==base+additional)
    elif requirement=='TRF-018':
        ice=scalar(ship,N.iceClass)
        if ice in [N.iceClassIaSuper,N.iceClassIa,N.iceClassIb,N.iceClassIc]:
            required=quantity(ship,N.calculatedRequiredPower,U.KiloW)
            actual=quantity(ship,N.maximumContinuousRatingPower,U.KiloW)
            if required is not None and actual is not None:compare('required_power_floor',actual>=max(required,Decimal('2800') if ice==N.iceClassIaSuper else Decimal('1000')))
        elif ice is not None:fail('unsupported_batch_applicability')
    elif requirement in ['IMO-006','IMO-008']:
        ice=scalar(ship,N.iceTypeClassification)
        kind=N.mediumFirstYearIce if requirement=='IMO-006' else N.thinFirstYearIce
        if ice!=kind:fail('unsupported_batch_applicability')
        thickness=quantity(ship,N.iceThickness,U.M)
        low,high=(Decimal('.7'),Decimal('1.2')) if requirement=='IMO-006' else (Decimal('.3'),Decimal('.7'))
        if thickness is not None:compare('ice_thickness_range',low<=thickness<=high)
    elif requirement=='IMO-010':
        days=quantity(ship,N.maximumExpectedRescueTime,U.DAY)
        if days is not None:compare('rescue_time_minimum',days>=Decimal('5'))
    elif requirement=='IMO26-009':
        likely=scalar(ship,N.iceAccretionLikely,XSD.boolean)
        antennas=links(ship,N.hasRequiredNavigationOrCommunicationAntenna,N.navigationOrCommunicationAntenna)
        if likely is not None and likely.toPython() is True:
            for antenna in antennas:
                protection=scalar(antenna,N.antennaIceAccumulationPreventionPresent,XSD.boolean)
                if protection is not None:compare('antenna_protection',protection.toPython() is True)
        elif likely is None:
            # Inspect supplied dependent evidence as well; the missing selector
            # does not excuse malformed values already present in the graph.
            for antenna in antennas:scalar(antenna,N.antennaIceAccumulationPreventionPresent,XSD.boolean,required=False)
    elif requirement=='IMO26-014':
        daylight=scalar(ship,N.operatesOnlyInContinuousDaylight,XSD.boolean)
        count=scalar(ship,N.visualIceDetectionIlluminationMeansCount,XSD.integer,required=daylight is not None and daylight.toPython() is False)
        if daylight is not None and daylight.toPython() is False and count is not None:compare('illumination_minimum',int(count)>=2)
    return dict(defects=sorted(set(defects)),checked=sorted(set(checked)))
