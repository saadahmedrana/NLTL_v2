from __future__ import annotations

import unittest

import context_pack


class ContextPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = context_pack.load_sources()
        context_pack.verify_locked_sources(cls.sources)
        cls.index = context_pack.requirement_term_index(cls.sources)

    def test_complete_requirement_index(self) -> None:
        self.assertEqual(len(self.index), 313)
        self.assertTrue(all(self.index.values()))

    def test_single_requirement_pack_is_scoped(self) -> None:
        pack = context_pack.build_context_pack(self.sources, ["TRF-016"])
        names = {term["localName"] for term in pack["terms"]}
        self.assertEqual(names, set(self.index["TRF-016"]))
        self.assertFalse(pack["selection"]["all821TermsIncluded"])
        self.assertEqual(pack["selection"]["mode"], "requirement")

    def test_integrated_pack_is_exact_union(self) -> None:
        requirement_ids = ["TRF-016", "IMO26-007", "IMO-093"]
        pack = context_pack.build_context_pack(self.sources, requirement_ids)
        names = {term["localName"] for term in pack["terms"]}
        expected = set().union(*(set(self.index[item]) for item in requirement_ids))
        self.assertEqual(names, expected)
        self.assertEqual(pack["selection"]["mode"], "integrated-case")

    def test_scoped_context_has_selected_terms_only(self) -> None:
        pack = context_pack.build_context_pack(self.sources, ["IMO26-007"])
        context = pack["scopedJsonLdContext"]["@context"]
        selected = {term["localName"] for term in pack["terms"]}
        registry_names = {term["localName"] for term in self.sources["terms"]}
        self.assertTrue(selected <= set(context))
        self.assertFalse((registry_names - selected) <= set(context))

    def test_unknown_requirement_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            context_pack.build_context_pack(self.sources, ["NOT-A-REQUIREMENT"])

    def test_generation_is_deterministic(self) -> None:
        first = context_pack.build_context_pack(self.sources, ["TRF-016"])
        second = context_pack.build_context_pack(self.sources, ["TRF-016"])
        self.assertEqual(first, second)

    def test_pack_contract_validation(self) -> None:
        pack = context_pack.build_context_pack(self.sources, ["IMO-093"])
        context_pack.validate_context_pack(pack, self.sources)


if __name__ == "__main__":
    unittest.main()
