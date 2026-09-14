"""Version-controlled Gunicorn settings for the single-worker backup service.

Railway may invoke ``gunicorn app:app`` directly instead of using the repository's
Procfile.  Gunicorn automatically discovers this file from the application working
directory, so the backup-safe settings live here as the common source of truth.
"""


def required_settings():
    """Return settings that must remain stable while a backup is being built."""
    return {
        'worker_class': 'gthread',
        'workers': 1,
        'threads': 8,
        'timeout': 180,
        'graceful_timeout': 30,
        'max_requests': 0,
        'max_requests_jitter': 0,
        'reload': False,
        'preload_app': False,
    }


def validate_effective_settings(server):
    """Reject effective Gunicorn settings that can interrupt a backup build.

    The check runs after Gunicorn has combined this file with command-line and
    ``GUNICORN_CMD_ARGS`` values.  Only conflicting setting names are included in
    the error so an environment value or other secret can never be echoed to logs.
    """
    expected = required_settings()
    config = getattr(server, 'cfg', None)

    # Gunicorn exposes the configured worker in two different forms.  The
    # ``worker_class`` property resolves the configured URI to a Python class,
    # while ``worker_class_str`` is the supported string form used in Gunicorn's
    # own startup log.  Compare the latter so the required ``gthread`` setting
    # is validated against the same effective value Gunicorn reports, rather
    # than comparing a class object with a string.
    effective_names = {
        'worker_class': 'worker_class_str',
    }
    conflicts = [
        name for name, expected_value in expected.items()
        if getattr(config, effective_names.get(name, name), None) != expected_value
    ]
    if conflicts:
        raise RuntimeError(
            'Gunicorn backup configuration conflict: ' + ', '.join(conflicts) + '.'
        )

    logger = getattr(server, 'log', None)
    log_info = getattr(logger, 'info', None)
    if callable(log_info):
        log_info(
            'Gunicorn backup-safe settings validated: gthread worker, one process, '
            'eight threads, 180-second timeout.'
        )
    return True


# The required values are deliberately configuration variables rather than command
# arguments duplicated in each deployment file.  Ordinary bind/logging options remain
# free for the platform to provide.
worker_class = 'gthread'
workers = 1
threads = 8
timeout = 180
graceful_timeout = 30
max_requests = 0
max_requests_jitter = 0
reload = False
preload_app = False

# One function is used for initial startup and a future HUP/reload, so a later
# configuration change cannot quietly replace the worker while a build owns it.
on_starting = validate_effective_settings
on_reload = validate_effective_settings
