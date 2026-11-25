import unittest,pathlib,os
from nltlv2.core import Candidate
from nltlv2.checks import sparql_checks
from nltlv2.sparql_analysis import analyze
class SparqlGeneralTests(unittest.TestCase):
 def checkq(self,q):return sparql_checks(Candidate(1,q,q),q,scope='generic-test',slot='select')
 def test_saved_nested_projection_failure(self):
  root=pathlib.Path(os.environ.get('NLTL_TEST_PROJECT',str(pathlib.Path(__file__).resolve().parents[1])));q=(root/'tests/data/nested_projection_error.rq').read_text();fs=self.checkq(q);self.assertTrue(any(f.blocking and f.category=='SPARQL_ERROR' for f in fs))
 def test_valid_plain_select(self):self.assertFalse(any(f.blocking for f in self.checkq('SELECT $this WHERE { $this <urn:p> ?v . FILTER(?v > 0) }')))
 def test_valid_union(self):self.assertFalse(any(f.blocking for f in self.checkq('SELECT $this WHERE { {$this <urn:a> ?v} UNION {$this <urn:b> ?v} }')))
 def test_valid_nested_projection(self):self.assertFalse(any(f.blocking for f in self.checkq('SELECT $this WHERE { { SELECT ?this ?v WHERE { ?this <urn:p> ?v } } FILTER(?v>0) }')))
 def test_dollar_question_this_equivalent(self):
  q='SELECT $this WHERE { { SELECT ?this WHERE { ?this <urn:p> ?v } } }';self.assertFalse(any(f.blocking for f in self.checkq(q)))
 def test_hidden_operand_warning_not_confirmed_defect(self):
  fs=self.checkq('SELECT $this WHERE { { SELECT ?this WHERE { ?this <urn:p> ?v } } FILTER(?v>0) }');self.assertTrue(any(not f.blocking for f in fs))
 def test_external_service_policy(self):self.assertTrue(any(f.blocking and 'External' in f.message for f in self.checkq('SELECT $this WHERE { SERVICE <https://example.invalid/sparql> { $this <urn:p> ?v } }')))
 def test_external_dataset_policy(self):self.assertTrue(any(f.blocking and 'External' in f.message for f in self.checkq('SELECT $this FROM <https://example.invalid/data> WHERE { $this <urn:p> ?v }')))
 def test_word_service_in_literal_is_not_remote_access(self):self.assertFalse(any('External' in f.message for f in self.checkq('SELECT $this WHERE { $this <urn:p> "SERVICE" }')))
 def test_parse_error_has_original_query(self):
  q='SELECT WHERE { $this ?p ?o }';fs=self.checkq(q);self.assertTrue(fs);self.assertTrue(any(f.excerpt==q for f in fs));self.assertTrue(all(f.diagnostic for f in fs))
 def test_nested_projection_star_engine_error(self):
  q='SELECT $this WHERE { { SELECT * WHERE {$this <urn:p> ?v} } }';fs=self.checkq(q);self.assertTrue(any("Using 'SELECT *'" in f.diagnostic for f in fs))
 def test_top_level_star_not_blanket_rejected(self):self.assertFalse(any(f.blocking for f in self.checkq('SELECT * WHERE {$this <urn:p> ?v}')))
 def test_same_finding_identity_across_query_edits(self):
  a=self.checkq('SELECT $this WHERE { { SELECT ?v WHERE { $this <urn:p> ?v } } }');b=self.checkq('SELECT $this WHERE { { SELECT ?v WHERE { $this <urn:q> ?v } } }');self.assertTrue(set(f.key for f in a)&set(f.key for f in b))
