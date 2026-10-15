"""Write every account's effective access as JSON, to diff before and after a roles change.

Usage (always on a COPY of a database, never the tracked scheduler.db):

    set MEDICAL_SERVICE_TEST_DB=<copy.db>
    venv/Scripts/python.exe scripts/role_access_snapshot.py <out.json> [--migrate]

--migrate first sends one request through the app so the per-request startup
migrations run, the way the first request after a Railway deploy does.
Running it twice on the same database gives an identical file.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if not os.environ.get('MEDICAL_SERVICE_TEST_DB'):
    sys.exit('Set MEDICAL_SERVICE_TEST_DB to a copy of the database first.')

import app as app_module  # noqa: E402
from flask_login import login_user, logout_user  # noqa: E402

USER_CHECKS = [
    'is_admin_authorized', 'is_superadmin_user', 'is_scheduler_user', 'is_regional_admin_user',
    'is_manager_dashboard_user', 'is_manager_primary_user', 'is_engineer_primary_user',
    'can_administer_personnel', 'can_view_admin_reports', 'can_manage_any_schedule',
    'can_manage_purchase_orders', 'can_manage_reimbursement_tracker', 'can_access_calibration_center',
    'can_edit_products_inventory', 'can_edit_genoray_inventory', 'can_edit_vieworks_inventory',
    'can_administer_products_inventory', 'can_administer_genoray_inventory',
    'can_administer_vieworks_inventory', 'can_quick_add_timeline_client', 'can_back_up_tsr_drafts',
    'is_approval_center_user', 'is_approver_only_user', 'can_create_tsr_without_equipment_for_user',
    'has_engineer_profile', 'can_manage_stock_inventory',
]


def _call(name, *args):
    fn = getattr(app_module, name, None)
    if fn is None:
        return 'missing'
    try:
        return fn(*args)
    except Exception as exc:  # recorded, so a crash shows up in the diff
        return f'error: {type(exc).__name__}'


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def approval_queue(approver):
    """Requester ids whose requests reach this approver, per scope (legacy bypass = every account)."""
    legacy = getattr(app_module, 'is_legacy_reimbursement_approval_user', None)
    all_ids = sorted(u.id for u in app_module.User.query.all())
    queues = {}
    for scope in sorted(app_module.APPROVAL_REQUEST_SCOPES):
        if legacy and legacy(approver):
            queues[scope] = all_ids
        else:
            queues[scope] = sorted(app_module.get_requester_user_ids_for_approver(approver, scope))
    return queues


def snapshot():
    flask_app = app_module.app
    with flask_app.app_context():
        users = app_module.User.query.order_by(app_module.User.username.asc()).all()
        result = {}
        for user in users:
            with flask_app.test_request_context('/'):
                login_user(user, force=True)
                entry = {
                    'role': user.role,
                    'is_active': bool(getattr(user, 'is_active', True)),
                    'display_role': _call('get_display_role', user),
                    'engineer_profile': getattr(getattr(user, 'engineer_profile', None), 'employee_id', None),
                }
                for name in USER_CHECKS:
                    entry[name] = _call(name, user)
                entry['dashboard'] = _call('get_dashboard_capabilities', user)
                entry['nav'] = _call('inject_navigation_access')
                entry['flags'] = {
                    key: value for key, value in (_call('inject_feature_flags') or {}).items()
                    if 'stock' in key or 'hr_schedule' in key
                }
                entry['can_reset_password'] = {
                    target.username: list(_call('can_reset_password_for_user', target, user))
                    for target in users
                }
                entry['personnel_change_denial'] = {
                    target.username: _call('personnel_account_change_denial', target) for target in users
                }
                entry['approval_queue'] = approval_queue(user) if app_module.is_approval_center_user(user) else {}
                logout_user()
            result[user.username] = _jsonable(entry)
        return result


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if '--migrate' in sys.argv:
        app_module.app.test_client().get('/login')
    data = snapshot()
    with open(sys.argv[1], 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=1, sort_keys=True)
    print(f'{len(data)} accounts written to {sys.argv[1]}')


if __name__ == '__main__':
    main()
