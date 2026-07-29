import json
import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_changelog_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class ChangelogSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_migrations_are_additive(self):
        for ddl in (
            'ALTER TABLE changelog_release ADD COLUMN publish_at DATETIME',
            'ALTER TABLE changelog_item ADD COLUMN branches_json TEXT',
            'ALTER TABLE changelog_item ADD COLUMN is_minor BOOLEAN DEFAULT 0 NOT NULL',
            'ALTER TABLE changelog_item ADD COLUMN manifest_snapshot_json TEXT',
        ):
            self.assertIn(ddl, self.app_source)
        self.assertNotIn('DROP COLUMN publish_at', self.app_source)

    def test_authoring_verbs_exist_and_are_admin_guarded(self):
        for route in (
            "@app.route('/api/changelog/admin/releases', methods=['POST'])",
            "@app.route('/api/changelog/admin/releases/<int:release_id>', methods=['DELETE'])",
            "@app.route('/api/changelog/admin/releases/<int:release_id>/items', methods=['POST'])",
            "@app.route('/api/changelog/admin/items/<int:item_id>', methods=['DELETE'])",
            "@app.route('/api/changelog/admin/items/<int:item_id>/revert', methods=['POST'])",
        ):
            self.assertIn(route, self.app_source)

    def test_digest_send_is_guarded_by_its_own_flag(self):
        # EMAIL_NOTIFICATIONS_ENABLED defaults to true, so the digest must not rely on it.
        self.assertIn("os.environ.get('CHANGELOG_DIGEST_ENABLED', 'false')", self.app_source)
        send_fn = self.app_source.split('def send_changelog_digest(')[1].split('\n@app.route')[0]
        self.assertIn('if not changelog_digest_sending_enabled():', send_fn)
        # The refusal must come before anything that could reach a mail provider.
        guard_at = send_fn.index('changelog_digest_sending_enabled()')
        send_at = send_fn.index('send_email_notification(')
        self.assertLess(guard_at, send_at, 'the flag check must precede any send')

    def test_send_logs_the_real_outcome_not_an_assumed_one(self):
        """The activity log previously recorded a successful send unconditionally.

        A provider rejection still left "Sent What's New digest" in the audit trail,
        which is worse than no record at all.
        """
        send_fn = self.app_source.split('def send_changelog_digest(')[1].split('\n@app.route')[0]
        send_at = send_fn.index('sent, message = send_email_notification(')
        log_at = send_fn.index('add_activity_log_entry(')
        self.assertLess(send_at, log_at, 'the outcome must be known before it is logged')
        self.assertIn('if sent:', send_fn)
        self.assertIn('FAILED', send_fn)

    def test_send_honours_branch_targeting(self):
        # Preview accepted a branch and send ignored it, so a branch-targeted
        # preview would have gone to every branch.
        send_fn = self.app_source.split('def send_changelog_digest(')[1].split('\n@app.route')[0]
        self.assertIn('branch_code', send_fn)
        self.assertIn('audience=audience, branch_code=branch_code', send_fn)
        self.assertIn('STOCK_INVENTORY_BRANCHES', send_fn)

    def test_naming_a_group_without_a_mode_still_means_the_group(self):
        """Audience is the default mode, but it must not widen an explicit group send.

        A caller that passes recipient_group and no recipient_mode meant the group;
        silently promoting that to the whole audience would turn a short curated list
        into every matching account.
        """
        send_fn = self.app_source.split('def send_changelog_digest(')[1].split('\n@app.route')[0]
        self.assertIn(
            "recipient_mode = 'group' if clean_str(payload.get('recipient_group')) else 'audience'",
            send_fn
        )


class ChangelogDigestRecipientGroupTests(unittest.TestCase):
    """The digest needs an announcement list of its own.

    Every other group is a workflow handoff (accounting, HR, procurement), so
    without this a product announcement would have to borrow one of them.
    """

    def test_announcement_group_is_registered_and_ordered(self):
        key = app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY
        self.assertEqual(key, 'changelog_announcements')
        self.assertIn(key, app_module.EMAIL_RECIPIENT_GROUPS)
        self.assertIn(key, app_module.EMAIL_RECIPIENT_GROUP_ORDER)
        self.assertEqual(
            app_module.EMAIL_RECIPIENT_GROUPS[key]['label'],
            "What's New Announcements"
        )

    def test_group_is_offered_by_settings_and_accepted_by_the_normalizer(self):
        keys = [group['key'] for group in app_module.get_email_recipient_groups_payload()]
        self.assertIn(app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY, keys)
        self.assertEqual(
            app_module.normalize_email_recipient_group('changelog_announcements'),
            'changelog_announcements'
        )

    def test_unknown_group_is_still_rejected(self):
        self.assertEqual(app_module.normalize_email_recipient_group('not_a_group'), '')
        self.assertEqual(app_module.get_active_email_recipients_by_group('not_a_group'), [])


class ChangelogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_changelog_tables()

    def _client(self, username, role='engineer'):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=username).first()
            if not user:
                user = app_module.User(
                    username=username, role=role, is_active=True,
                    password=app_module.generate_password_hash('ClogTest123')
                )
                app_module.db.session.add(user)
                app_module.db.session.commit()
            user_id = user.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _admin_client(self):
        # is_superadmin_user() requires membership in SUPERADMIN_USERNAMES.
        name = sorted(app_module.SUPERADMIN_USERNAMES)[0]
        return self._client(name, role='superadmin')

    def _create_release(self, client, **overrides):
        payload = {'title': 'Test announcement', 'summary': 'A summary'}
        payload.update(overrides)
        return client.post('/api/changelog/admin/releases', json=payload)

    # --- authorization ---

    def test_non_admin_cannot_author(self):
        client = self._client('clog_plain_user')
        self.assertEqual(self._create_release(client).status_code, 403)
        self.assertEqual(client.delete('/api/changelog/admin/releases/1').status_code, 403)
        self.assertEqual(client.post('/api/changelog/admin/items/1/revert').status_code, 403)
        self.assertEqual(client.get('/api/changelog/admin/digest/preview').status_code, 403)

    # --- authoring ---

    def test_create_release_and_item_uses_reserved_namespace(self):
        client = self._admin_client()
        response = self._create_release(client, title='Submit July liquidations by Friday')
        self.assertEqual(response.status_code, 201)
        release = response.get_json()['release']
        self.assertTrue(release['release_key'].startswith('app-'))
        self.assertTrue(release['is_inapp'])

        item_response = client.post(
            f"/api/changelog/admin/releases/{release['id']}/items",
            json={'description': 'Please file your claims before Friday.',
                  'category': 'Reminder', 'audiences': ['engineers']}
        )
        self.assertEqual(item_response.status_code, 201)
        items = item_response.get_json()['release']['items']
        self.assertTrue(items[-1]['item_key'].startswith('app-'))

    def test_manifest_sync_leaves_inapp_entries_alone(self):
        client = self._admin_client()
        release = self._create_release(client, title='Survives sync').get_json()['release']
        client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                    json={'description': 'Should not be touched by the manifest.'})

        with self.app.app_context():
            app_module.sync_changelog_release_manifest()
            stored = app_module.ChangelogRelease.query.filter_by(
                release_key=release['release_key']).first()
            self.assertIsNotNone(stored)
            self.assertEqual(stored.title, 'Survives sync')
            self.assertEqual(len(stored.items), 1)

    def test_manifest_entries_cannot_be_deleted(self):
        client = self._admin_client()
        with self.app.app_context():
            manifest_item = app_module.ChangelogItem.query.filter(
                ~app_module.ChangelogItem.item_key.startswith('app-')).first()
            self.assertIsNotNone(manifest_item, 'manifest should have synced items')
            item_id = manifest_item.id
            release_id = manifest_item.release_id

        self.assertEqual(client.delete(f'/api/changelog/admin/items/{item_id}').status_code, 400)
        self.assertEqual(client.delete(f'/api/changelog/admin/releases/{release_id}').status_code, 400)

    def test_delete_inapp_release_removes_it(self):
        client = self._admin_client()
        release = self._create_release(client, title='Delete me').get_json()['release']
        self.assertEqual(client.delete(f"/api/changelog/admin/releases/{release['id']}").status_code, 200)
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.ChangelogRelease, release['id']))

    # --- scheduling ---

    def test_future_publish_at_hides_release_until_due(self):
        client = self._admin_client()
        future = (app_module.get_manila_time() + timedelta(days=2)).isoformat()
        release = self._create_release(client, title='Scheduled note', publish_at=future).get_json()['release']
        client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                    json={'description': 'Only visible later.'})

        with self.app.app_context():
            stored = app_module.db.session.get(app_module.ChangelogRelease, release['id'])
            self.assertFalse(app_module.changelog_release_is_live(stored))
            stored.publish_at = app_module.get_manila_time() - timedelta(minutes=5)
            app_module.db.session.commit()
            self.assertTrue(app_module.changelog_release_is_live(stored))

    # --- branch targeting ---

    def test_branch_targeting_filters_and_empty_means_all(self):
        client = self._admin_client()
        release = self._create_release(client, title='Branch targeted').get_json()['release']
        client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                    json={'description': 'Cebu only note.', 'branches': ['BC02']})
        client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                    json={'description': 'Everyone note.'})

        with self.app.app_context():
            stored = app_module.db.session.get(app_module.ChangelogRelease, release['id'])
            all_branches = app_module.changelog_visible_items(
                stored, audiences={'everyone'}, branch_code='')
            cebu = app_module.changelog_visible_items(
                stored, audiences={'everyone'}, branch_code='BC02')
            manila = app_module.changelog_visible_items(
                stored, audiences={'everyone'}, branch_code='BC01')

        self.assertEqual(len(all_branches), 2, 'no branch context sees everything')
        self.assertEqual(len(cebu), 2)
        self.assertEqual(len(manila), 1, 'Manila must not see the Cebu-only note')

    # --- revert ---

    def test_revert_restores_the_manifest_version(self):
        client = self._admin_client()
        with self.app.app_context():
            item = app_module.ChangelogItem.query.filter(
                ~app_module.ChangelogItem.item_key.startswith('app-'),
                app_module.ChangelogItem.manifest_snapshot_json.isnot(None)
            ).first()
            self.assertIsNotNone(item, 'sync should have recorded manifest snapshots')
            item_id = item.id
            original = item.description

        edited = client.put(f'/api/changelog/admin/items/{item_id}',
                            json={'description': 'Locally reworded text.'})
        self.assertEqual(edited.status_code, 200)
        with self.app.app_context():
            self.assertTrue(app_module.db.session.get(app_module.ChangelogItem, item_id).admin_edited)

        reverted = client.post(f'/api/changelog/admin/items/{item_id}/revert')
        self.assertEqual(reverted.status_code, 200)
        with self.app.app_context():
            restored = app_module.db.session.get(app_module.ChangelogItem, item_id)
            self.assertFalse(restored.admin_edited)
            self.assertEqual(restored.description, original)

    def test_revert_refuses_for_inapp_items(self):
        client = self._admin_client()
        release = self._create_release(client, title='No manifest version').get_json()['release']
        created = client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                              json={'description': 'Written in the app.'}).get_json()
        item_id = created['release']['items'][-1]['id']
        self.assertEqual(client.post(f'/api/changelog/admin/items/{item_id}/revert').status_code, 400)

    # --- reading experience ---

    def test_pagination_caps_releases_per_page(self):
        client = self._admin_client()
        payload = client.get('/api/changelog/releases').get_json()
        self.assertEqual(payload['per_page'], 10)
        self.assertLessEqual(len(payload['releases']), 10)
        self.assertGreaterEqual(payload['total_pages'], 1)
        self.assertIn('categories', payload)

    def test_search_matches_description_and_category(self):
        client = self._admin_client()
        hit = client.get('/api/changelog/releases?search=signature').get_json()
        for release in hit['releases']:
            joined = ' '.join(
                (i['description'] + ' ' + i['category']).lower() for i in release['items']
            )
            self.assertTrue('signature' in joined
                            or 'signature' in (release['title'] + release['summary']).lower())

        miss = client.get('/api/changelog/releases?search=zzzznotpresent').get_json()
        self.assertEqual(miss['count'], 0)

    # --- acknowledgement granularity ---

    def test_minor_items_do_not_change_the_acknowledgement_hash(self):
        client = self._admin_client()
        release = self._create_release(client, title='Hash stability').get_json()['release']
        client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                    json={'description': 'Headline change.'})

        with self.app.app_context():
            stored = app_module.db.session.get(app_module.ChangelogRelease, release['id'])
            items = app_module.changelog_visible_items(stored, audiences={'everyone'}, branch_code='')
            before = app_module.changelog_visible_content_hash(stored, items)

        client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                    json={'description': 'Tiny typo fix.', 'is_minor': True})

        with self.app.app_context():
            stored = app_module.db.session.get(app_module.ChangelogRelease, release['id'])
            items = app_module.changelog_visible_items(stored, audiences={'everyone'}, branch_code='')
            after = app_module.changelog_visible_content_hash(stored, items)

        self.assertEqual(before, after, 'a minor item must not re-flag the release as unread')

    # --- digest ---

    def test_digest_preview_renders_without_sending(self):
        client = self._admin_client()
        response = client.get('/api/changelog/admin/digest/preview?audience=engineers')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload['sending_enabled'])
        self.assertIn('digest', payload)

    def test_digest_send_is_refused_while_disabled(self):
        self.assertFalse(self.app.config.get('CHANGELOG_DIGEST_ENABLED'),
                         'sending must default to off')
        client = self._admin_client()
        response = client.post('/api/changelog/admin/digest/send',
                               json={'audience': 'engineers', 'recipient_group': 'anything'})
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertFalse(payload['success'])
        self.assertFalse(payload['sending_enabled'])

    def test_digest_send_never_reaches_a_provider_while_disabled(self):
        """Even with a recipient group present, no mail call may happen."""
        client = self._admin_client()
        calls = []
        original = app_module.send_email_notification
        app_module.send_email_notification = lambda *a, **k: calls.append(a) or (True, 'sent')
        try:
            client.post('/api/changelog/admin/digest/send',
                        json={'audience': 'everyone', 'recipient_group': 'tsr_client_cc'})
        finally:
            app_module.send_email_notification = original
        self.assertEqual(calls, [], 'no email may be attempted while the digest is disabled')

    def test_test_mode_is_refused_while_disabled_too(self):
        """Test mode bypasses the recipient group, so it must not bypass the flag."""
        client = self._admin_client()
        calls = []
        original = app_module.send_email_notification
        app_module.send_email_notification = lambda *a, **k: calls.append(a) or (True, 'sent')
        try:
            response = client.post('/api/changelog/admin/digest/send',
                                   json={'audience': 'everyone', 'test_only': True})
        finally:
            app_module.send_email_notification = original
        self.assertEqual(response.status_code, 409)
        self.assertEqual(calls, [], 'test mode must not reach a provider while disabled')

    def test_preview_reports_recipient_counts_without_exposing_addresses(self):
        client = self._admin_client()
        payload = client.get('/api/changelog/admin/digest/preview').get_json()
        self.assertEqual(payload['default_group'], app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY)

        groups = {group['key']: group for group in payload['recipient_groups']}
        self.assertIn(app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY, groups)
        for group in payload['recipient_groups']:
            self.assertIn('active_count', group)
            self.assertIsInstance(group['active_count'], int)
            # Counts inform the decision; the addresses stay in Settings.
            self.assertNotIn('emails', group)
            self.assertNotIn('recipients', group)

    def test_preview_still_sends_nothing(self):
        client = self._admin_client()
        calls = []
        original = app_module.send_email_notification
        app_module.send_email_notification = lambda *a, **k: calls.append(a) or (True, 'sent')
        try:
            response = client.get('/api/changelog/admin/digest/preview?audience=engineers&branch=MANILA')
        finally:
            app_module.send_email_notification = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [], 'preview must never reach a mail provider')


class ChangelogDigestEnabledPathTests(unittest.TestCase):
    """Exercise the send path with the flag ON but the provider replaced.

    The disabled-path tests prove nothing can escape while the flag is off. These
    prove the path actually works once it is on, without ever contacting Brevo.
    Every test restores both the flag and the real sender.

    Deliberately not a subclass of ChangelogApiTests: inheriting would re-run that
    class's disabled-path assertions with the flag turned on.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_changelog_tables()

    def _admin_client(self):
        name = sorted(app_module.SUPERADMIN_USERNAMES)[0]
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=name).first()
            if not user:
                user = app_module.User(
                    username=name, role='superadmin', is_active=True,
                    password=app_module.generate_password_hash('ClogTest123')
                )
                app_module.db.session.add(user)
                app_module.db.session.commit()
            user_id = user.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def setUp(self):
        self._original_sender = app_module.send_email_notification
        self._original_flag = self.app.config.get('CHANGELOG_DIGEST_ENABLED')
        self.app.config['CHANGELOG_DIGEST_ENABLED'] = True
        self.sent = []

    def tearDown(self):
        app_module.send_email_notification = self._original_sender
        self.app.config['CHANGELOG_DIGEST_ENABLED'] = self._original_flag

    def _capture(self, ok=True, message='sent'):
        def fake(to_emails, subject, text_body, html_body=None):
            self.sent.append({'to': list(to_emails), 'subject': subject, 'html': html_body})
            return ok, message
        app_module.send_email_notification = fake

    def _seed_group(self, *emails):
        with self.app.app_context():
            app_module.ensure_email_recipient_setting_table()
            key = app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY
            for existing in app_module.EmailRecipientSetting.query.filter_by(group_key=key).all():
                app_module.db.session.delete(existing)
            # Flush the deletes before re-inserting, or SQLAlchemy orders the
            # inserts first and trips the (group_key, email) unique constraint.
            app_module.db.session.flush()
            for index, email in enumerate(emails):
                app_module.db.session.add(app_module.EmailRecipientSetting(
                    group_key=key, email=email, display_name=email,
                    is_active=True, sort_order=index
                ))
            app_module.db.session.commit()

    def test_group_send_reaches_exactly_the_active_recipients(self):
        self._seed_group('one@example.invalid', 'two@example.invalid')
        self._capture()
        client = self._admin_client()

        response = client.post('/api/changelog/admin/digest/send', json={
            'audience': 'everyone',
            'recipient_group': app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(sorted(self.sent[0]['to']),
                         ['one@example.invalid', 'two@example.invalid'])

    def test_empty_group_is_refused_before_any_send(self):
        self._seed_group()
        self._capture()
        client = self._admin_client()

        response = client.post('/api/changelog/admin/digest/send', json={
            'recipient_group': app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sent, [], 'an empty group must not produce a send')

    def test_test_mode_goes_only_to_the_requesting_admin(self):
        self._seed_group('everyone@example.invalid')
        self._capture()
        client = self._admin_client()

        with self.app.app_context():
            name = sorted(app_module.SUPERADMIN_USERNAMES)[0]
            user = app_module.User.query.filter_by(username=name).first()
            own = app_module.normalize_single_email_address(
                app_module.get_user_email_for_notification(user))

        response = client.post('/api/changelog/admin/digest/send',
                               json={'test_only': True})

        if not own:
            # No address on file: must refuse rather than fall back to the group.
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.sent, [])
            return

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['test_only'])
        self.assertEqual(self.sent[0]['to'], [own])
        self.assertNotIn('everyone@example.invalid', self.sent[0]['to'])

    def _activity_since(self, marker_id):
        with self.app.app_context():
            entries = (app_module.ActivityLog.query
                       .filter(app_module.ActivityLog.id > marker_id)
                       .order_by(app_module.ActivityLog.id.asc()).all())
            return ' | '.join(entry.action or '' for entry in entries)

    def _latest_activity_id(self):
        with self.app.app_context():
            newest = (app_module.ActivityLog.query
                      .order_by(app_module.ActivityLog.id.desc()).first())
            return newest.id if newest else 0

    def test_a_failed_send_is_logged_as_a_failure(self):
        """The audit trail previously said "Sent" even when the provider refused."""
        self._seed_group('one@example.invalid')
        self._capture(ok=False, message='provider rejected')
        client = self._admin_client()
        marker = self._latest_activity_id()

        response = client.post('/api/changelog/admin/digest/send', json={
            'recipient_group': app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY
        })
        self.assertFalse(response.get_json()['success'])

        logged = self._activity_since(marker)
        self.assertIn('FAILED', logged)
        self.assertIn('provider rejected', logged)
        self.assertNotIn("Sent What's New digest", logged)

    def test_a_successful_send_is_logged_as_a_send(self):
        self._seed_group('one@example.invalid')
        self._capture(ok=True)
        client = self._admin_client()
        marker = self._latest_activity_id()

        client.post('/api/changelog/admin/digest/send', json={
            'recipient_group': app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY
        })

        logged = self._activity_since(marker)
        self.assertIn("Sent What's New digest", logged)
        self.assertNotIn('FAILED', logged)

    # --- audience-driven recipients ---

    def _make_account(self, username, role='engineer', is_active=True, email=None):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=username).first()
            if not user:
                user = app_module.User(
                    username=username, role=role,
                    password=app_module.generate_password_hash('AudTest123')
                )
                app_module.db.session.add(user)
            user.role = role
            user.is_active = is_active
            if email is not None and hasattr(user, 'email'):
                user.email = email
            app_module.db.session.commit()
            return user.id

    def test_audience_resolution_skips_inactive_accounts(self):
        self._make_account('aud_active_eng', 'engineer', is_active=True)
        self._make_account('aud_inactive_eng', 'engineer', is_active=False)

        with self.app.app_context():
            emails, missing = app_module.resolve_changelog_audience_recipients('engineers')

        everyone = set(emails) | set(missing)
        self.assertIn('aud_active_eng', everyone | {m for m in missing})
        self.assertNotIn('aud_inactive_eng', missing)
        self.assertNotIn('aud_inactive_eng@', ' '.join(emails))

    def test_accounts_without_an_email_are_reported_not_dropped(self):
        """A shrinking send must be visible, not silent."""
        self._make_account('aud_no_email_user', 'engineer', is_active=True)

        with self.app.app_context():
            emails, missing = app_module.resolve_changelog_audience_recipients('engineers')

        self.assertIn('aud_no_email_user', missing,
                      'an account with no resolvable address must be named')
        for address in emails:
            self.assertIn('@', address)

    def test_audience_send_reaches_the_resolved_accounts(self):
        self._make_account('aud_send_eng', 'engineer', is_active=True)
        self._capture()
        client = self._admin_client()

        with self.app.app_context():
            expected, _ = app_module.resolve_changelog_audience_recipients('engineers')

        response = client.post('/api/changelog/admin/digest/send',
                               json={'audience': 'engineers', 'recipient_mode': 'audience'})

        if not expected:
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.sent, [])
            return

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['recipient_mode'], 'audience')
        self.assertEqual(sorted(self.sent[0]['to']), sorted(expected))

    def test_audience_with_no_addresses_is_refused_before_any_send(self):
        self._capture()
        client = self._admin_client()

        with self.app.app_context():
            emails, _ = app_module.resolve_changelog_audience_recipients('approvers')
        if emails:
            self.skipTest('approvers resolve to real addresses in this fixture')

        response = client.post('/api/changelog/admin/digest/send',
                               json={'audience': 'approvers', 'recipient_mode': 'audience'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sent, [], 'an unresolvable audience must not send')

    # --- per-send update selection ---

    def _item_visible_to(self, audience, audiences_json):
        """Create a release with one item tagged for the given audiences."""
        client = self._admin_client()
        release = client.post('/api/changelog/admin/releases',
                              json={'title': f'Selection fixture {audiences_json}',
                                    'summary': 'fixture'}).get_json()['release']
        item = client.post(f"/api/changelog/admin/releases/{release['id']}/items",
                           json={'description': f'Fixture item for {audiences_json}',
                                 'category': 'Fixture',
                                 'audiences': audiences_json}).get_json()['release']['items'][-1]
        return release, item

    def test_selection_narrows_the_body(self):
        release, item = self._item_visible_to('everyone', ['everyone'])
        client = self._admin_client()

        full = client.get('/api/changelog/admin/digest/preview').get_json()['digest']
        narrowed = client.get(
            f"/api/changelog/admin/digest/preview?item_ids={item['id']}"
        ).get_json()['digest']

        self.assertEqual(narrowed['item_count'], 1)
        self.assertLess(narrowed['item_count'], full['item_count'])
        self.assertIn('Fixture item for', narrowed['text'])

    def test_selection_cannot_widen_past_the_audience_filter(self):
        """The case that would leak an admins-only note to engineers.

        Selection is applied after audience filtering, so passing the id of an item
        this audience cannot see must not smuggle it into their email.
        """
        release, admin_item = self._item_visible_to('admins', ['admins'])
        client = self._admin_client()

        payload = client.get(
            f"/api/changelog/admin/digest/preview?audience=engineers&item_ids={admin_item['id']}"
        ).get_json()

        self.assertEqual(payload['digest']['item_count'], 0,
                         'an admins-only item must not appear in an engineers digest')
        offered = [entry['id'] for entry in payload['selectable_items']]
        self.assertNotIn(admin_item['id'], offered,
                         'the picker must not even offer it')

    def test_choosing_nothing_sends_nothing(self):
        """An empty selection must not fall back to sending everything."""
        self._capture()
        client = self._admin_client()

        payload = client.get('/api/changelog/admin/digest/preview?item_ids=').get_json()
        self.assertEqual(payload['digest']['item_count'], 0)

        response = client.post('/api/changelog/admin/digest/send',
                               json={'audience': 'everyone', 'item_ids': []})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sent, [], 'an empty selection must not send')

    def test_preview_reports_audience_recipients(self):
        self._make_account('aud_preview_eng', 'engineer', is_active=True)
        client = self._admin_client()
        payload = client.get('/api/changelog/admin/digest/preview?audience=engineers').get_json()

        self.assertIn('audience_recipient_count', payload)
        self.assertIsInstance(payload['audience_recipient_count'], int)
        self.assertIn('aud_preview_eng', payload['audience_missing_email'])
        self.assertIn('selectable_items', payload)

    def test_branch_targeting_changes_what_is_sent(self):
        self._seed_group('one@example.invalid')
        self._capture()
        client = self._admin_client()

        client.post('/api/changelog/admin/digest/send', json={
            'recipient_group': app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY,
            'branch': 'MANILA'
        })
        client.post('/api/changelog/admin/digest/send', json={
            'recipient_group': app_module.CHANGELOG_ANNOUNCEMENT_GROUP_KEY,
            'branch': 'not-a-real-branch'
        })

        # Both are accepted; the invalid one falls back to all branches rather
        # than erroring, matching how preview validates the same parameter.
        self.assertEqual(len(self.sent), 2)


if __name__ == '__main__':
    unittest.main()
