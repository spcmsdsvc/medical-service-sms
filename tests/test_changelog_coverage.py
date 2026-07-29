"""Safety net: a user-facing change must ship with a What's New entry.

This exists because the discipline already failed. The manifest's newest entry was
2026-07-23 while b791a3c shipped 2026-07-24 ("Sort TSR archive by recently added"),
so users were never told about a change they could see.

The check is deliberately narrow: it only looks at the most recent commit, and only
fails when that commit touched something a user could notice.
"""

import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Paths that never need a changelog entry on their own.
EXEMPT_PREFIXES = (
    'tests/',
    'docs/',
    '.claude/',
    'changes.md',
    'README.md',
    'requirements.txt',
    'runtime.txt',
    'Procfile',
    'static/changelog/',
)

# Nothing here is visible to a user, so a commit touching only these is exempt too.
EXEMPT_SUFFIXES = ('.md',)


def git(*args):
    try:
        result = subprocess.run(
            ['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=20
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def user_facing_paths(paths):
    facing = []
    for path in paths:
        normalized = path.replace('\\', '/')
        if normalized.startswith(EXEMPT_PREFIXES):
            continue
        if normalized.endswith(EXEMPT_SUFFIXES):
            continue
        facing.append(normalized)
    return facing


class ChangelogCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = ROOT / 'static' / 'changelog' / 'releases.json'
        cls.manifest_dates = set()
        if manifest.exists():
            try:
                payload = json.loads(manifest.read_text(encoding='utf-8'))
                cls.manifest_dates = {
                    (release.get('release_date') or '').strip()
                    for release in payload.get('releases', [])
                }
            except Exception:
                cls.manifest_dates = set()

    def test_manifest_is_valid_json_with_unique_item_keys(self):
        manifest = ROOT / 'static' / 'changelog' / 'releases.json'
        self.assertTrue(manifest.exists(), 'release manifest is missing')
        payload = json.loads(manifest.read_text(encoding='utf-8'))
        releases = payload.get('releases')
        self.assertIsInstance(releases, list)

        item_keys, release_keys = [], []
        for release in releases:
            release_keys.append(release.get('release_key'))
            for item in release.get('items', []):
                item_keys.append(item.get('item_key'))
                self.assertTrue(item.get('description'), 'every item needs a description')

        self.assertEqual(len(item_keys), len(set(item_keys)), 'item_key values must be unique')
        self.assertEqual(len(release_keys), len(set(release_keys)), 'release_key values must be unique')

    def test_manifest_does_not_use_the_reserved_inapp_namespace(self):
        # Keys starting with app- belong to the in-app composer; the sync skips them, so
        # a manifest entry using that prefix would silently never appear.
        manifest = ROOT / 'static' / 'changelog' / 'releases.json'
        payload = json.loads(manifest.read_text(encoding='utf-8'))
        for release in payload.get('releases', []):
            self.assertFalse((release.get('release_key') or '').startswith('app-'),
                             f"reserved prefix in release_key: {release.get('release_key')}")
            for item in release.get('items', []):
                self.assertFalse((item.get('item_key') or '').startswith('app-'),
                                 f"reserved prefix in item_key: {item.get('item_key')}")

    def test_latest_user_facing_commit_has_a_changelog_entry(self):
        commit_date = git('log', '-1', '--format=%ad', '--date=short')
        commit_hash = git('log', '-1', '--format=%h')
        subject = git('log', '-1', '--format=%s')
        changed = git('show', '--name-only', '--format=', 'HEAD')

        if not commit_date or changed is None:
            self.skipTest('git history unavailable')

        paths = [line for line in changed.split('\n') if line.strip()]
        facing = user_facing_paths(paths)
        if not facing:
            self.skipTest(f'{commit_hash} touches no user-facing paths')

        self.assertIn(
            commit_date, self.manifest_dates,
            "\n"
            f"Commit {commit_hash} ({commit_date}) changed user-facing files but\n"
            f"static/changelog/releases.json has no release dated {commit_date}.\n"
            f"  Subject: {subject}\n"
            f"  Files:   {', '.join(facing[:6])}{' ...' if len(facing) > 6 else ''}\n\n"
            f"Add a release with release_key and release_date of {commit_date}, or append an\n"
            "item to that day's existing release. If this commit genuinely changes nothing a\n"
            "user would notice, add its paths to EXEMPT_PREFIXES in this test."
        )


if __name__ == '__main__':
    unittest.main()
