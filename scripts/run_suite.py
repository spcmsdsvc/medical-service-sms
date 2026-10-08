"""Run the full test suite in parallel and compare it with the known failures.

Usage (from the project root):
    venv/Scripts/python.exe scripts/run_suite.py                 # run and compare
    venv/Scripts/python.exe scripts/run_suite.py --update-known  # rewrite the known list

Test modules are split across one process per CPU core. Each process imports `tests` on its
own, so `tests/__init__.py` gives it its own fresh database. The file of every failing test
is then rerun on its own; a test counts as failing only if it fails there too (some tests leak
state, e.g. the shared login rate limit, and fail only next to certain other files). The
result is compared by test id with `tests/known_failures.txt`.
Exit code 0 when there are no new failures.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
KNOWN = ROOT / 'tests' / 'known_failures.txt'


def run_worker(modules, out_path):
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    with open(os.devnull, 'w') as sink:
        result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    failed = [test.id() if hasattr(test, 'id') else str(test) for test, _ in result.failures + result.errors]
    print('Modules in order:', ' '.join(modules))
    for test, trace in result.failures + result.errors:
        print(f'\n=== {test.id() if hasattr(test, "id") else test}\n{trace}')
    pathlib.Path(out_path).write_text(json.dumps({
        'run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'skipped': len(result.skipped),
        'failed': failed,
    }))


def start_worker(modules, workdir, index):
    env = {k: v for k, v in os.environ.items() if k != 'MEDICAL_SERVICE_TEST_DB'}
    out = workdir / f'worker{index}.json'
    log = open(workdir / f'worker{index}.log', 'w')
    proc = subprocess.Popen(
        [sys.executable, __file__, '--worker', str(out), *modules],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    return proc, out, log


def collect(jobs):
    totals = {'run': 0, 'failures': 0, 'errors': 0, 'skipped': 0, 'failed': []}
    for proc, out, log in jobs:
        proc.wait()
        log.close()
        if not out.exists():
            sys.exit(f'A test process crashed; see {log.name}')
        data = json.loads(out.read_text())
        for key in ('run', 'failures', 'errors', 'skipped'):
            totals[key] += data[key]
        totals['failed'] += data['failed']
    return totals


def module_of(test_id):
    """`tests.mod.Class.test` or `setUpClass (tests.mod.Class)` -> `tests.mod`."""
    name = test_id.split(' (')[-1].rstrip(')') if ' (' in test_id else test_id
    return '.'.join(name.split('.')[:2])


def split(modules, workers):
    """Biggest files first into the lightest group, so the groups finish close together."""
    groups = [[] for _ in range(workers)]
    loads = [0] * workers
    for module in sorted(modules, key=lambda m: -(ROOT / 'tests' / f'{m.split(".")[1]}.py').stat().st_size):
        i = loads.index(min(loads))
        groups[i].append(module)
        loads[i] += (ROOT / 'tests' / f'{module.split(".")[1]}.py').stat().st_size
    return [g for g in groups if g]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update-known', action='store_true', help='save this run\'s failures as the known list')
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()

    started = time.perf_counter()
    modules = sorted(f'tests.{p.stem}' for p in (ROOT / 'tests').glob('test_*.py'))
    workdir = pathlib.Path(tempfile.mkdtemp(prefix='run_suite_'))
    jobs = [start_worker(group, workdir, i) for i, group in enumerate(split(modules, args.workers))]
    totals = collect(jobs)
    grouped = set(totals['failed'])

    # Rerun the file of every failure on its own; only a test that also fails alone counts.
    retry = sorted({module_of(t) for t in grouped})
    alone = set(collect([start_worker([m], workdir, f'_alone{i}') for i, m in enumerate(retry)])['failed'])
    failed = sorted(grouped & alone)
    order_dependent = sorted(grouped - alone)

    print(f"{totals['run']} tests, {totals['failures']} failures, {totals['errors']} errors, "
          f"{totals['skipped']} skips in {time.perf_counter() - started:.0f}s ({len(jobs)} processes)")
    print(f'{len(failed)} fail alone too; {len(order_dependent)} fail only next to other test files')

    if args.update_known:
        KNOWN.write_text('# Known failing tests on main; rewrite with: scripts/run_suite.py --update-known\n'
                         + ''.join(f'{t}\n' for t in failed))
        print(f'Saved {len(failed)} known failures to {KNOWN.relative_to(ROOT)}')
        return 0

    known = {line.strip() for line in KNOWN.read_text().splitlines() if line.strip() and not line.startswith('#')}
    new = [t for t in failed if t not in known]
    fixed = sorted(known - set(failed))

    for test in new:
        print(f'NEW FAILURE: {test}')
    for test in fixed:
        print(f'NOW PASSING (remove from known list): {test}')
    if not new:
        print('No new failures.')
        shutil.rmtree(workdir, ignore_errors=True)
        return 0
    print(f'Worker logs (tracebacks): {workdir}')
    return 1


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--worker':
        sys.path.insert(0, str(ROOT))
        run_worker(sys.argv[3:], sys.argv[2])
    else:
        sys.exit(main())
