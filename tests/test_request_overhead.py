"""Shared per-request cost: schema checks and the shell's What's New dot.

Every page load runs the before_request hooks and calls /api/changelog/unread-summary.
They used to cost about 86 and 570 queries on a copy of the live database (db.create_all()
on every request; two queries per changelog release), which queued behind the Reports
page's own requests on the single production worker.
"""

import os
import pathlib
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from sqlalchemy import event

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_request_overhead_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


@contextmanager
def count_queries():
    """Count SQL statements issued from this thread (the conversion worker runs on its own)."""
    counter = {'n': 0}
    thread_id = threading.get_ident()

    def before_cursor_execute(*_args):
        if threading.get_ident() == thread_id:
            counter['n'] += 1

    engine = app_module.db.engine
    event.listen(engine, 'before_cursor_execute', before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(engine, 'before_cursor_execute', before_cursor_execute)


class RequestOverheadTests(unittest.TestCase):
    RELEASES = 40

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_changelog_tables()
            user = app_module.User.query.filter_by(username='overhead_user').first()
            if not user:
                user = app_module.User(
                    username='overhead_user', role='engineer', is_active=True,
                    password=app_module.generate_password_hash('Overhead123')
                )
                app_module.db.session.add(user)
                app_module.db.session.commit()
            cls.user_id = user.id

            today = app_module.get_manila_time().date()
            for index in range(cls.RELEASES):
                key = f'app-overhead-{index}'
                if app_module.ChangelogRelease.query.filter_by(release_key=key).first():
                    continue
                release = app_module.ChangelogRelease(
                    release_key=key, title=f'Overhead {index}', is_published=True,
                    release_date=today - timedelta(days=index % 20)
                )
                for item_index in range(2):
                    release.items.append(app_module.ChangelogItem(
                        item_key=f'{key}-{item_index}', description=f'Change {item_index}.',
                        audiences_json='["everyone"]'
                    ))
                app_module.db.session.add(release)
            app_module.db.session.commit()

            # The viewer has read every other release.
            for release in app_module.ChangelogRelease.query.filter(
                app_module.ChangelogRelease.release_key.like('app-overhead-%')
            ).all():
                if int(release.release_key.rsplit('-', 1)[1]) % 2:
                    continue
                if app_module.changelog_acknowledgement_for(release.id, user.id):
                    continue
                items = app_module.changelog_visible_items(release, user)
                app_module.db.session.add(app_module.ChangelogAcknowledgement(
                    release_id=release.id, user_id=user.id,
                    content_hash=app_module.changelog_visible_content_hash(release, items)
                ))
            app_module.db.session.commit()

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        return client

    def test_trivial_request_runs_few_queries_after_the_first(self):
        client = self._client()
        client.get('/api/preferences/appearance')
        with self.app.app_context(), count_queries() as counter:
            response = client.get('/api/preferences/appearance')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(counter['n'], 15)

    def test_unread_summary_does_not_query_per_release(self):
        client = self._client()
        client.get('/api/preferences/appearance')
        with self.app.app_context(), count_queries() as counter:
            data = client.get('/api/changelog/unread-summary').get_json()
        self.assertLessEqual(counter['n'], 12)
        self.assertGreaterEqual(data['unread_count'], self.RELEASES // 2)

    def test_unread_summary_matches_per_release_serialization(self):
        """The batched path must give the same answer as serializing release by release."""
        client = self._client()
        data = client.get('/api/changelog/unread-summary').get_json()
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            cutoff = app_module.get_manila_time().date() - timedelta(
                days=app_module.CHANGELOG_UNREAD_DOT_DAYS
            )
            expected = []
            for release in app_module.ChangelogRelease.query.filter(
                app_module.ChangelogRelease.is_published.is_(True)
            ).order_by(
                app_module.ChangelogRelease.release_date.desc(), app_module.ChangelogRelease.id.desc()
            ).all():
                if not app_module.changelog_release_is_live(release) or release.release_date < cutoff:
                    continue
                serialized = app_module.changelog_release_to_dict(release, user)
                if serialized['items'] and serialized['is_unread']:
                    expected.append(serialized)
        self.assertEqual(data['unread_count'], len(expected))
        self.assertEqual((data['latest_unread'] or {}).get('id'), expected[0]['id'] if expected else None)

    def test_schema_checks_run_once_per_process(self):
        client = self._client()
        # Let other first-run helpers (some create tables themselves) finish before counting.
        client.get('/api/preferences/appearance')
        with mock.patch.object(app_module, '_runtime_create_all_ready', False), \
                mock.patch.object(app_module, '_runtime_schema_helpers_ready', False), \
                mock.patch.object(app_module.db, 'create_all') as create_all, \
                mock.patch.object(app_module, 'ensure_schedule_delete_indexes') as delete_indexes, \
                mock.patch.object(app_module, 'ensure_approval_routing_schema') as routing_schema:
            client.get('/api/preferences/appearance')
            client.get('/api/preferences/appearance')
        self.assertEqual(create_all.call_count, 1)
        self.assertEqual(delete_indexes.call_count, 1)
        self.assertEqual(routing_schema.call_count, 1)


if __name__ == '__main__':
    unittest.main()
