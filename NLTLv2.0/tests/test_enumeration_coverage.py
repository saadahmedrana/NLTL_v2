"""Source/schema-only synthetic tests and labelled pilot-copy diagnostics; no model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import SH
from pyshacl import validate

from nltlv2.core import Project, Candidate, load, write, digest
from nltlv2.schema import Schema, N
from nltlv2.enumerations import coverage_findings
from nltlv2.checks import check, regression
from nltlv2.requests import repair_request, assert_integrity, initial_request
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport

PREFIX = '@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix n: <https://w3id.org/nltl/vocab#> .\n'
LOCALS = ['iceClassIaSuper', 'iceClassIa', 'iceClassIb', 'iceClassIc', 'iceClassIi', 'iceClassIii']
MEMBERS = ' '.join('n:'+x for x in LOCALS)
GOOD = PREFIX+'<urn:dev:shape> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:iceClass ; sh:minCount 1 ; sh:in ('+MEMBERS+') ] .\n'
MISSING = PREFIX+'<urn:dev:shape> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:iceClass ; sh:minCount 1 ; sh:nodeKind sh:IRI ] .\n'
ACCEPT = json.dumps(dict(decision='ACCEPT', issues=[]))
def wrap(code):
    return '<BEGIN_SHACL>\n'+code+'<END_SHACL>\n'


class EnumerationCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Project(os.environ['NLTL_TEST_PROJECT'])
        cls.s = Schema(cls.p)
        cls.out = Path(os.environ['NLTL_TEST_OUTPUT'])

    def proof(self, code):
        candidate = Candidate(1, code, wrap(code))
        fs, reports = coverage_findings(candidate, self.s, 'TRF-010')
        return fs, reports[0]

    def equivalent_or(self, singleton='in'):
        branches = ' '.join('[ sh:in (n:'+x+') ]' if singleton=='in' else '[ sh:hasValue n:'+x+' ]' for x in LOCALS)
        return PREFIX+'<urn:dev:shape> a sh:NodeShape ; sh:targetClass n:ship ; sh:property [ sh:path n:iceClass ; sh:minCount 1 ; sh:node [ sh:or ('+branches+') ] ] .\n'

    def test_complete_source_and_registry_verification(self):
        ctx = self.s.context('TRF-010')
        self.assertIn('6. ice class III;', ctx['requirement']['text'])
        self.assertIn('normally capable of navigating in difficult ice conditions', ctx['requirement']['text'])
        self.assertEqual(len(ctx['contract']['controlledValueMappings']), 6)
        self.assertEqual(set(ctx['contract']['controlledValueTerms']), set(LOCALS))
        base = load(self.p.path('schema/term_registry.json'))
        self.assertFalse(any(r['localName'] in LOCALS for r in base))
        for name in LOCALS:
            row = self.s.controlled_registry['terms'][name]
            self.assertEqual(row['locked_registry_verification']['status'], 'ABSENT')
            self.assertEqual(row['iri'], str(N[name]))
            self.assertIn(row, ctx['schema_terms'])
        self.assertEqual(self.s.validate_enumeration_contracts()['status'], 'VERIFIED')

    def test_initial_context_identical_both_methods(self):
        requests = []
        for f in ['single_shot', 'nltl']:
            config = self.p.config('configs/'+f+'.json')
            requests.append(initial_request(self.p, self.s.context('TRF-010'), {k:config[k] for k in ['model','generation_max_tokens','review_max_tokens']}))
        self.assertEqual(requests[0], requests[1])
        for name in LOCALS:
            self.assertIn(str(N[name]), requests[0]['user'])

    def test_missing_enumeration_confirmed(self):
        fs, proof = self.proof(MISSING)
        self.assertEqual(proof['status'], 'MISSING_ENUMERATION')
        self.assertTrue(fs[0].confirmed)
        self.assertEqual(fs[0].category, 'SOURCE_BACKED_LOGIC_ERROR')

    def test_correct_sh_in(self):
        fs, proof = self.proof(GOOD)
        self.assertEqual(proof['status'], 'COVERED')
        self.assertEqual(fs, [])

    def test_omitted_member(self):
        fs, proof = self.proof(GOOD.replace('n:iceClassIii', ''))
        self.assertEqual(proof['status'], 'INCORRECT_ENUMERATION_SET')
        self.assertEqual(proof['missing_IRIs'], [str(N.iceClassIii)])
        self.assertTrue(fs[0].confirmed)

    def test_extra_member(self):
        _, proof = self.proof(GOOD.replace('n:iceClassIii)', 'n:iceClassIii <urn:dev:unlistedIceCategory>)'))
        self.assertEqual(proof['extra_terms'], ['<urn:dev:unlistedIceCategory>'])
        self.assertEqual(proof['status'], 'INCORRECT_ENUMERATION_SET')

    def test_literal_members_are_not_canonical_IRIs(self):
        _, proof = self.proof(GOOD.replace('n:iceClassIii', '"III"'))
        self.assertEqual(proof['status'], 'INCORRECT_ENUMERATION_SET')
        self.assertIn('"III"', proof['extra_terms'])

    def test_duplicate_members_have_set_semantics(self):
        self.assertEqual(self.proof(GOOD.replace('n:iceClassIii)', 'n:iceClassIii n:iceClassIii)'))[1]['status'], 'COVERED')

    def test_class_only_is_not_enum(self):
        code = MISSING.replace('sh:nodeKind sh:IRI', 'sh:class n:iceClassValue')
        self.assertEqual(self.proof(code)[1]['status'], 'MISSING_ENUMERATION')

    def test_iri_only_is_not_enum(self):
        self.assertEqual(self.proof(MISSING)[1]['status'], 'MISSING_ENUMERATION')

    def test_cardinality_only_is_not_enum(self):
        self.assertEqual(self.proof(MISSING.replace('sh:nodeKind sh:IRI', 'sh:maxCount 1'))[1]['status'], 'MISSING_ENUMERATION')

    def test_wrong_path(self):
        fs, proof = self.proof(GOOD.replace('sh:path n:iceClass', 'sh:path <urn:dev:otherProperty>'))
        self.assertEqual(proof['status'], 'WRONG_PATH_OR_APPLICABILITY')
        self.assertEqual(fs[0].category, 'PATH_CONTRACT_ERROR')

    def test_wrong_target_scope(self):
        _, proof = self.proof(GOOD.replace('sh:targetClass n:ship', 'sh:targetClass n:hullBoundaryPoint'))
        self.assertEqual(proof['status'], 'WRONG_PATH_OR_APPLICABILITY')

    def test_superclass_target_covers_ship(self):
        self.assertEqual(self.proof(GOOD.replace('sh:targetClass n:ship', 'sh:targetClass n:benchmarkEntity'))[1]['status'], 'COVERED')

    def test_inactive_property_not_coverage(self):
        _, proof = self.proof(GOOD.replace('sh:path n:iceClass', 'sh:deactivated true ; sh:path n:iceClass'))
        self.assertEqual(proof['status'], 'MISSING_ENUMERATION')

    def test_inactive_target_not_coverage(self):
        _, proof = self.proof(GOOD.replace('sh:targetClass n:ship', 'sh:deactivated true ; sh:targetClass n:ship'))
        self.assertNotEqual(proof['status'], 'COVERED')

    def test_unreferenced_enum_not_coverage(self):
        code = MISSING+'<urn:dev:unused> a sh:NodeShape ; sh:in ('+MEMBERS+') .\n'
        self.assertEqual(self.proof(code)[1]['status'], 'MISSING_ENUMERATION')

    def test_enum_in_message_does_not_count(self):
        code = MISSING.replace('sh:nodeKind sh:IRI', 'sh:message "sh:in of six values" ; sh:nodeKind sh:IRI')
        self.assertEqual(self.proof(code)[1]['status'], 'MISSING_ENUMERATION')

    def test_logical_bypass_does_not_cover_all_applicability(self):
        code = PREFIX+'<urn:dev:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:or ( [ sh:property [ sh:path n:iceClass ; sh:in ('+MEMBERS+') ] ] [ sh:class n:ship ] ) .\n'
        _, proof = self.proof(code)
        self.assertEqual(proof['status'], 'MISSING_ENUMERATION')
        self.assertTrue(any('alternative' in n for n in proof['notes']))

    def test_or_branch_class_range_bypasses_membership(self):
        code = GOOD.replace('sh:in ('+MEMBERS+')', 'sh:or ([ sh:in ('+MEMBERS+') ] [ sh:class n:iceClassValue ])')
        self.assertEqual(self.proof(code)[1]['status'], 'MISSING_ENUMERATION')

    def test_unknown_conditional_scope_is_unresolved(self):
        code = PREFIX+'<urn:dev:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:or ( [ sh:property [ sh:path n:iceClass ; sh:in ('+MEMBERS+') ] ] [ sh:class n:hullBoundaryPoint ] ) .\n'
        fs, proof = self.proof(code)
        self.assertEqual(proof['status'], 'UNRESOLVED_EQUIVALENCE')
        self.assertFalse(fs[0].confirmed)

    def test_node_indirection_equivalent(self):
        code = GOOD.replace('sh:in ('+MEMBERS+')', 'sh:node [ sh:in ('+MEMBERS+') ]')
        self.assertEqual(self.proof(code)[1]['status'], 'COVERED')

    def test_or_of_singleton_sets_equivalent(self):
        self.assertEqual(self.proof(self.equivalent_or())[1]['status'], 'COVERED')

    def test_or_of_value_focus_hasValue_equivalent(self):
        self.assertEqual(self.proof(self.equivalent_or('hasValue'))[1]['status'], 'COVERED')

    def test_and_intersection_equivalent(self):
        lists = '[ sh:in ('+MEMBERS+' <urn:dev:extra>) ] [ sh:in ('+MEMBERS+') ]'
        code = GOOD.replace('sh:in ('+MEMBERS+')', 'sh:and ('+lists+')')
        self.assertEqual(self.proof(code)[1]['status'], 'COVERED')

    def test_or_partial_sets_union_equivalent(self):
        lists = '[ sh:in ('+' '.join('n:'+x for x in LOCALS[:3])+') ] [ sh:in ('+' '.join('n:'+x for x in LOCALS[3:])+') ]'
        code = GOOD.replace('sh:in ('+MEMBERS+')', 'sh:or ('+lists+')')
        self.assertEqual(self.proof(code)[1]['status'], 'COVERED')

    def test_other_target_strategy_unresolved(self):
        code = GOOD.replace('sh:targetClass n:ship', 'sh:targetSubjectsOf n:iceClass')
        self.assertEqual(self.proof(code)[1]['status'], 'UNRESOLVED_EQUIVALENCE')

    def test_sparql_equivalence_not_guessed(self):
        code = PREFIX+'<urn:dev:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:sparql [ sh:select "SELECT $this WHERE { $this <https://w3id.org/nltl/vocab#iceClass> ?v . FILTER(?v NOT IN (<urn:dev:v>)) }" ] .\n'
        fs, proof = self.proof(code)
        self.assertEqual(proof['status'], 'UNRESOLVED_EQUIVALENCE')
        self.assertFalse(fs[0].confirmed)

    def test_qualified_membership_not_guessed(self):
        code = GOOD.replace('sh:in ('+MEMBERS+')', 'sh:qualifiedValueShape [ sh:in ('+MEMBERS+') ] ; sh:qualifiedMinCount 1')
        self.assertEqual(self.proof(code)[1]['status'], 'UNRESOLVED_EQUIVALENCE')

    def test_hasValue_at_property_focus_is_not_universal_set(self):
        code = MISSING.replace('sh:nodeKind sh:IRI', 'sh:hasValue n:iceClassIa')
        self.assertEqual(self.proof(code)[1]['status'], 'UNRESOLVED_EQUIVALENCE')

    def test_repair_packet_precise_and_latest(self):
        candidate = Candidate(4, MISSING, wrap(MISSING))
        fs, proof = coverage_findings(candidate, self.s, 'TRF-010')
        packet = repair_request(self.p, self.s.context('TRF-010'), candidate, fs)
        assert_integrity(packet, candidate, fs)
        data = packet['payload']
        self.assertEqual(data['previous_candidate'], MISSING)
        self.assertEqual(data['candidate_version'], 4)
        self.assertEqual(data['candidate_sha256'], digest(MISSING))
        self.assertIn('6. ice class III;', data['exact_regulatory_text'])
        item = data['current_findings'][0]
        self.assertIn('offsets', item['location'])
        self.assertEqual(json.loads(item['diagnostic']), proof[0])
        self.assertIn('source', json.loads(item['evidence']))
        for name in LOCALS:
            self.assertIn(str(N[name]), item['expected'])
        self.assertIn('sh:in', item['suggestion'])
        self.assertIn('Preserve unrelated', item['suggestion'])
        self.assertIn('permit unlisted', item['message'])

    def test_source_only_synthetic_execution_equivalents(self):
        # This is the only execution witness used here: explicitly synthetic, source/schema derived.
        # No external fixtures, labels or counterparts are accessed.
        for code in [GOOD, self.equivalent_or(), self.equivalent_or('hasValue')]:
            shape = Graph().parse(data=code, format='turtle')
            for value in [N[x] for x in LOCALS] + [URIRef('urn:dev:unlistedIceCategory')]:
                data = Graph();data.add((URIRef('urn:dev:ship'), RDF.type, N.ship));data.add((URIRef('urn:dev:ship'), N.iceClass, value))
                data.add((value,RDF.type,N.iceClassValue)) # Type-consistent outsider still must reject.
                conforms, _, _ = validate(data, shacl_graph=shape, ont_graph=self.s.graph, inference='rdfs', advanced=True)
                self.assertEqual(conforms, value in {N[x] for x in LOCALS})

    def test_maxCount_separate_not_required_or_invented(self):
        policy = self.s.context('TRF-010')['contract']['cardinalityReview']
        self.assertIsNone(policy['maximum_count'])
        self.assertFalse(policy['functional_property_declared'])
        self.assertIn('UNRESOLVED', policy['status'])
        self.assertEqual(self.proof(GOOD)[1]['status'], 'COVERED') # no maxCount
        self.assertEqual(self.proof(GOOD.replace('sh:minCount 1', 'sh:maxCount 1 ; sh:minCount 1'))[1]['status'], 'COVERED')
        self.assertIn('do not require maxCount 1', self.p.path('prompts/reviewer.txt').read_text())

    def test_missing_enum_gates_before_semantic_accept(self):
        dest = self.out/self._testMethodName;dest.mkdir()
        config = self.p.config('configs/nltl.json');config['maximum_candidate_attempts']=1
        transport = ScriptedTransport([wrap(MISSING), ACCEPT])
        result = Runner(self.p, config, transport, dest).run('TRF-010')
        self.assertIsNone(result['accepted_version'])
        self.assertEqual(result['status'], 'ATTEMPT_LIMIT_EXHAUSTED')
        self.assertEqual(len(transport.calls), 1) # ACCEPT canary was never requested.

    def test_scripted_enum_correction_then_internal_accept(self):
        dest = self.out/self._testMethodName;dest.mkdir()
        corrected = GOOD.replace('sh:minCount 1', 'sh:nodeKind sh:IRI ; sh:minCount 1')
        transport = ScriptedTransport([wrap(MISSING),wrap(corrected),ACCEPT])
        result = Runner(self.p,self.p.config('configs/nltl.json'),transport,dest).run('TRF-010')
        self.assertEqual(result['accepted_version'],2)
        self.assertEqual([r['route'] for r in transport.calls],['generation','targeted_repair','review'])
        self.assertEqual(transport.calls[1]['payload']['previous_candidate'],MISSING)

    def test_incomplete_set_correction_does_not_lose_other_obligations(self):
        bad = GOOD.replace('n:iceClassIii', '')
        old = Candidate(1,bad,wrap(bad));new=Candidate(2,GOOD,wrap(GOOD))
        fs,_=coverage_findings(old,self.s,'TRF-010')
        self.assertEqual(regression(old,new,fs),[])
        removed = GOOD.replace('sh:minCount 1 ; ','')
        self.assertTrue(regression(old,Candidate(2,removed,wrap(removed)),fs))

    def test_deleted_enumeration_does_not_count_as_repair(self):
        old=Candidate(1,GOOD,wrap(GOOD));new=Candidate(2,MISSING,wrap(MISSING))
        self.assertTrue(regression(old,new))
        self.assertTrue(self.proof(MISSING)[0])

    def test_named_shape_identifier_is_not_a_regulatory_operand(self):
        code=GOOD.replace('<urn:dev:shape>', 'n:TRF010DevelopmentShape')
        self.assertNotIn('CANONICAL_IDENTIFIER_ERROR',{f.category for f in check(Candidate(1,code,wrap(code)),self.s,'TRF-010')})

    def test_pilot_shapes_diagnostic_copies_only(self):
        manifest=load(self.p.path('smoke_tests/diagnostic_inputs/manifest.json'))
        for item in manifest:
            code=self.p.path(item['file']).read_text();self.assertEqual(digest(code),item['sha256'])
            candidate=Candidate(1,code,wrap(code));fs,proof=coverage_findings(candidate,self.s,'TRF-010')
            self.assertEqual(proof[0]['status'],'MISSING_ENUMERATION')
            dest=self.out/(self._testMethodName+'_'+Path(item['file']).stem);dest.mkdir()
            (dest/'diagnostic_candidate.ttl').write_text(code)
            packet=repair_request(self.p,self.s.context('TRF-010'),candidate,fs)
            write(dest/'repair_request.json',packet)
            (dest/'repair_request.rendered.txt').write_text(packet['system']+'\n\n--- USER ---\n'+packet['user'])
            write(dest/'integrity.json',assert_integrity(packet,candidate,fs));write(dest/'coverage.json',proof)
            config=self.p.config('configs/nltl.json');config['maximum_candidate_attempts']=1
            transport=ScriptedTransport([wrap(code),ACCEPT])
            run=dest/'diagnostic_replay';run.mkdir();result=Runner(self.p,config,transport,run).run('TRF-010')
            self.assertIsNone(result['accepted_version']);self.assertEqual(len(transport.calls),1)
            self.assertEqual(digest((dest/'diagnostic_candidate.ttl').read_text()),item['sha256'])
            write(dest/'scope.json',dict(role='Diagnostic copy replay only, no repairs applied or baseline scores changed',source=item['source'],source_sha256=item['sha256'],missing_obligation_prevents_acceptance=True))

    def test_generation_loop_does_not_read_evaluation_files(self):
        class GenerationOnlyProject(Project):
            def path(self, relative):
                if str(relative).startswith('evaluation/'):
                    raise AssertionError('External evaluation inputs entered generation')
                return super().path(relative)
        project=GenerationOnlyProject(self.p.root)
        dest=self.out/self._testMethodName;dest.mkdir()
        transport=ScriptedTransport([wrap(GOOD),ACCEPT])
        self.assertEqual(Runner(project,project.config('configs/nltl.json'),transport,dest).run('TRF-010')['status'],'ACCEPTED')

    def test_owner_or_split_sets_does_not_assume_maxCount_one(self):
        branches = '[ sh:property [ sh:path n:iceClass ; sh:in ('+' '.join('n:'+x for x in LOCALS[:3])+') ] ] [ sh:property [ sh:path n:iceClass ; sh:in ('+' '.join('n:'+x for x in LOCALS[3:])+') ] ]'
        code = PREFIX+'<urn:dev:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:or ('+branches+') .\n'
        fs, proof = self.proof(code)
        self.assertEqual(proof['status'],'UNRESOLVED_EQUIVALENCE')
        self.assertFalse(fs[0].confirmed)
        self.assertTrue(any('cardinality' in x for x in proof['notes']))

    def test_owner_or_dominating_set_equivalent(self):
        branches = '[ sh:property [ sh:path n:iceClass ; sh:in ('+MEMBERS+') ] ] [ sh:property [ sh:path n:iceClass ; sh:in (n:iceClassIa) ] ]'
        code = PREFIX+'<urn:dev:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:or ('+branches+') .\n'
        self.assertEqual(self.proof(code)[1]['status'],'COVERED')

    def test_owner_selector_guards_are_not_assumed_applicable(self):
        branch = '[ sh:property [ sh:path n:iceClass ; sh:in ('+MEMBERS+') ] ; sh:property [ sh:path <urn:dev:selector> ; sh:hasValue true ] ]'
        code = PREFIX+'<urn:dev:s> a sh:NodeShape ; sh:targetClass n:ship ; sh:or ('+branch+') .\n'
        self.assertEqual(self.proof(code)[1]['status'],'UNRESOLVED_EQUIVALENCE')

    def test_incompatible_value_class_does_not_get_equivalence_credit(self):
        code=GOOD.replace('sh:minCount 1', 'sh:class n:ship ; sh:minCount 1')
        self.assertEqual(self.proof(code)[1]['status'],'UNRESOLVED_EQUIVALENCE')

    def test_single_step_sequence_path_equivalent(self):
        self.assertEqual(self.proof(GOOD.replace('sh:path n:iceClass','sh:path (n:iceClass)'))[1]['status'],'COVERED')

    def test_complete_wrong_sequence_path_detected(self):
        self.assertEqual(self.proof(GOOD.replace('sh:path n:iceClass','sh:path (n:hasStructuralMember n:iceClass)'))[1]['status'],'WRONG_PATH_OR_APPLICABILITY')

    def test_xone_not_guessed(self):
        self.assertEqual(self.proof(self.equivalent_or().replace('sh:or','sh:xone'))[1]['status'],'UNRESOLVED_EQUIVALENCE')

    def test_source_binding_tampering_rejected(self):
        for kind in ['iri','source','duplicate','label','path']:
            modified=copy.copy(self.s)
            modified.enumeration_obligations=copy.deepcopy(self.s.enumeration_obligations)
            modified.controlled_registry=copy.deepcopy(self.s.controlled_registry)
            obligation=modified.enumeration_obligations['TRF-010'][0]
            if kind=='iri':modified.controlled_registry['terms']['iceClassIa']['iri']='urn:dev:invented'
            if kind=='source':obligation['source']['sha256']='0'*64
            if kind=='duplicate':obligation['members'][0]['iri']=obligation['members'][1]['iri']
            if kind=='label':obligation['members'][0]['source_label']='Invented label'
            if kind=='path':obligation['path']=[str(N.hasStructuralMember),str(N.iceClass)]
            with self.assertRaises(ValueError,msg=kind):modified.validate_enumeration_contracts()

    def test_unknown_equivalence_blocks_without_repair_or_reviewer(self):
        code=GOOD.replace('sh:in ('+MEMBERS+')','sh:qualifiedValueShape [ sh:in ('+MEMBERS+') ] ; sh:qualifiedMinCount 1')
        dest=self.out/self._testMethodName;dest.mkdir()
        transport=ScriptedTransport([wrap(code),ACCEPT])
        result=Runner(self.p,self.p.config('configs/nltl.json'),transport,dest).run('TRF-010')
        self.assertEqual(result['status'],'UNRESOLVED_CONTEXT')
        self.assertIsNone(result['accepted_version'])
        self.assertEqual(len(transport.calls),1)

    def test_custom_constraint_equivalence_unresolved(self):
        code=GOOD+'<urn:dev:component> a sh:ConstraintComponent ; sh:parameter [ sh:path <urn:dev:finite> ] .\n'
        code=code.replace('sh:minCount 1', '<urn:dev:finite> true ; sh:minCount 1')
        self.assertEqual(self.proof(code)[1]['status'],'UNRESOLVED_EQUIVALENCE')

    def test_direct_value_or_equivalent(self):
        branches=' '.join('[ sh:hasValue n:'+name+' ]' for name in LOCALS)
        code=GOOD.replace('sh:in ('+MEMBERS+')','sh:or ('+branches+')')
        self.assertEqual(self.proof(code)[1]['status'],'COVERED')

    def test_synthetic_multivalue_membership_preserves_quantifier_scope(self):
        # Logical encoding witness only, not certification of regulatory maximum cardinality.
        for code in [GOOD,self.equivalent_or(),self.equivalent_or('hasValue')]:
            data=Graph();ship=URIRef('urn:dev:multivalueWitness');data.add((ship,RDF.type,N.ship))
            for value in [N.iceClassIa,N.iceClassIii]:data.add((ship,N.iceClass,value))
            conforms,_,_=validate(data,shacl_graph=Graph().parse(data=code,format='turtle'),ont_graph=self.s.graph,inference='rdfs',advanced=True)
            self.assertTrue(conforms)

    def test_shape_identifier_used_as_operand_still_checked(self):
        code=GOOD.replace('<urn:dev:shape>','n:DevShape').replace('sh:path n:iceClass','sh:path n:DevShape')
        findings=check(Candidate(1,code,wrap(code)),self.s,'TRF-010')
        self.assertIn('CANONICAL_IDENTIFIER_ERROR',{f.category for f in findings})
