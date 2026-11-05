"""A repicked TSR draft must not be saved over by another client's schedule (2026-11-05)."""

import json
import pathlib
import subprocess
import unittest

from tests.sw_cache_version import assert_cache_version_at_least

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')


class TsrDraftOtherClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tsr = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.apply_fn = cls.tsr.split('function applyScheduleToStandaloneTSR(')[1].split('\nfunction ')[0]

    def test_repick_keeps_the_draft_only_for_the_same_client(self):
        self.assertIn('const keepsRepickedDraft = awaitingScheduleRepick && isRepickForSameClient(schedule);', self.apply_fn)
        guard = self.apply_fn.split('if(!isSameSchedule && !keepsRepickedDraft){')[1].split('}')[0]
        self.assertIn('clearStandaloneTSRWorkFieldsForScheduleChange();', guard)
        self.assertIn("standaloneCurrentDraftId = '';", guard)
        self.assertIn("standaloneTSRReservationToken = '';", guard)

    def test_same_client_helper(self):
        if not NODE.exists():
            self.skipTest('node runtime not available')
        helper = 'function isRepickForSameClient(' + self.tsr.split('function isRepickForSameClient(')[1].split('\nfunction ')[0]
        script = helper + r"""
let selectedStandaloneScheduleSnapshot = null;
let customer = '';
const document = { getElementById: () => ({ value: customer }) };
function run(snapshot, field, schedule){ selectedStandaloneScheduleSnapshot = snapshot; customer = field; return isRepickForSameClient(schedule); }
console.log(JSON.stringify([
  run({client_id: 7, client_name: 'A Hospital'}, '', {client_id: 7, client_name: 'A Hospital (renamed)'}),
  run({client_id: 7, client_name: 'A Hospital'}, '', {client_id: 9, client_name: 'A Hospital'}),
  run({client_name: 'St.  Luke  Medical'}, '', {client_name: 'st. luke medical'}),
  run({client_name: 'A Hospital'}, '', {client_name: 'B Clinic'}),
  run(null, 'A Hospital', {client_name: 'A Hospital'}),
  run(null, 'A Hospital', {client_name: 'B Clinic'}),
  run(null, '', {client_name: 'B Clinic'}),
]));
"""
        result = subprocess.run([str(NODE), '-e', script], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [True, False, True, False, True, False, False])

    def test_schedule_filter_says_other_drafts_are_hidden(self):
        render = self.tsr.split('async function renderStandaloneTSRDraftPanel(')[1].split('\nasync function ')[0]
        self.assertIn('hasStandaloneScheduleSelection() && !standaloneTSRDraftsIgnoreScheduleFilter', render)
        self.assertIn('const otherScheduleCount = allGroupCount - groups.length;', render)
        self.assertIn('showAllStandaloneTSRDraftSchedules()', render)
        self.assertIn('${otherScheduleNote}<div class="standalone-tsr-draft-empty">No saved TSR drafts for the selected schedule.', render)
        self.assertIn('historyWarning + otherScheduleNote + groups.map(', render)
        self.assertIn('function showAllStandaloneTSRDraftSchedules(){', self.tsr)

    def test_service_worker_bumped(self):
        assert_cache_version_at_least(self, 361)


if __name__ == '__main__':
    unittest.main()
