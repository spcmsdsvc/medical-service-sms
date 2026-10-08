"""Forget the app's once-per-process "table is ready" flags.

`app.py` remembers in `_*_ready` globals that a table was created or seeded, and skips the
work afterwards. A test that drops every table, or swaps in its own database file for a while,
leaves those flags describing a database that no longer exists, so a later module in the same
process finds an empty Product name catalog or a missing table. Call this after `drop_all()` or
after putting the shared engine back; every `ensure_*` helper is safe to run again.
"""


def reset_schema_flags(app_module):
    for name, value in list(vars(app_module).items()):
        if name.startswith('_') and name.endswith('_ready') and value is True:
            setattr(app_module, name, False)
