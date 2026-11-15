"""Runtime instrumentation; no experiment scheduling or budget policy."""
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path


class Timings:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.totals = {}
        self.counts = {}

    def record(self, phase, seconds, **fields):
        with self.lock:
            self.totals[phase] = self.totals.get(phase, 0.0) + seconds
            self.counts[phase] = self.counts.get(phase, 0) + 1
            with self.path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(dict(phase=phase, seconds=seconds, **fields)) + '\n')

    @contextmanager
    def measure(self, phase):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(phase, time.perf_counter() - start)


class SerialBackend:
    """One worker per runtime. Queue and backend time are disjoint.

    Backend time includes preparation, solver process and parsing. The backend's
    runtime_s is retained separately; it is not pure solver CPU time.
    """
    def __init__(self, backend, timings, evidence):
        self.backend, self.timings = backend, timings
        self.name = backend.name
        self.family = getattr(backend, "family", None)
        self.cost_model = getattr(backend, "cost_model", None)
        self.lock = threading.Lock()
        self.evidence = Path(evidence)

    def solve_column(self, case):
        start = time.perf_counter()
        with self.lock:
            self.timings.record('queue', time.perf_counter() - start)
            try:
                with self.timings.measure('backend'):
                    result = self.backend.solve_column(case)
            except BaseException as ex:
                with self.evidence.open('a', encoding='utf-8') as f:
                    f.write(json.dumps({'case': case, 'error_type': type(ex).__name__, 'success': False}) + '\n')
                raise
            self.timings.record('solver_reported', result['runtime_s'])
            with self.evidence.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'case': case, 'result': result}) + '\n')
            return result


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)
