"""Focused scoring checks. Run explicitly with unittest; no repository data needed."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report import rubric_heatmap, rubric_score, score


class ScoringTests(unittest.TestCase):
    def test_repeated_blinded_slot_ids_preserve_each_assessment(self):
        criteria = pd.DataFrame([
            dict(excel_row=13, requirement_id='I2-031', artifact_id='A01', criterion='Q1', numeric_score=2),
            dict(excel_row=13, requirement_id='I2-031', artifact_id='A01', criterion='Q2', numeric_score=1),
            dict(excel_row=21, requirement_id='TRF-006', artifact_id='A01', criterion='Q1', numeric_score=0),
            dict(excel_row=21, requirement_id='TRF-006', artifact_id='A01', criterion='Q2', numeric_score=None),
        ])
        heat = rubric_heatmap(criteria)
        self.assertEqual(list(heat.index), ['I2-031 / A01', 'TRF-006 / A01'])
        self.assertEqual(heat.loc['I2-031 / A01', 'Q1'], 2)
        self.assertEqual(heat.loc['TRF-006 / A01', 'Q1'], 0)
        self.assertTrue(pd.isna(heat.loc['TRF-006 / A01', 'Q2']))

    def test_duplicate_criterion_within_assessment_is_rejected(self):
        row = dict(excel_row=13, requirement_id='I2-031', artifact_id='A01', criterion='Q1', numeric_score=2)
        with self.assertRaisesRegex(ValueError, 'Duplicate rubric criterion'):
            rubric_heatmap(pd.DataFrame([row, row]))

    def test_na_changes_denominator(self):
        self.assertEqual(rubric_score([2, 1, 'N/A'], True), (.75, 2, 'COMPLETE'))

    def test_blank_and_unclear_are_incomplete(self):
        for value in [None, '', 'UNCLEAR']:
            self.assertEqual(rubric_score([2, value], True)[0], None)

    def test_unassessable_zero_scores_do_not_enter_means(self):
        self.assertEqual(rubric_score([0, 0, 0], False), (None, 3, 'UNASSESSABLE'))

    def test_macro_and_missing_verdict(self):
        rows = []
        for rid, outcomes in [('R1', ['CORRECT']), ('R2', ['CORRECT', 'NO_VERDICT', 'FALSE_ACCEPT'])]:
            for i, outcome in enumerate(outcomes):
                rows.append(dict(condition='FULL_REPAIR_V2', stage='RUN_01', requirement_id=rid, case_id=f'{rid}-{i}',
                    verification_mode='DIRECT_STATIC', source_family='TEST', expected='FAIL',
                    observed='NO_VERDICT' if outcome == 'NO_VERDICT' else 'PASS' if outcome == 'FALSE_ACCEPT' else 'FAIL',
                    scored_outcome=outcome, correct=int(outcome == 'CORRECT'), evaluation_row_present=True,
                    artifact_availability='RECORDED_ARTIFACT'))
        frame = pd.DataFrame(rows)
        _, _, summary, matrix = score(frame, 'ORIGINAL', set(), {'R1', 'R2'})
        self.assertAlmostEqual(summary.requirement_level_accuracy.iloc[0], 2 / 3)
        self.assertAlmostEqual(summary.supplementary_pooled_case_accuracy.iloc[0], .5)
        self.assertEqual(summary.no_verdict.iloc[0], 1)
        self.assertEqual(matrix['count'].sum(), 4)
        _, _, excluded, _ = score(frame, 'EXPLICIT', {'R1-0'}, {'R1', 'R2'})
        self.assertEqual(excluded.requirements_without_cases.iloc[0], 'R1')
        self.assertAlmostEqual(excluded.requirement_level_accuracy.iloc[0], 1 / 3)


if __name__ == '__main__':
    unittest.main()
