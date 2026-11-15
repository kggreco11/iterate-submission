"""Run-scoped past.dev adapter. Never sends credentials to logs."""
import json
import hashlib
import os
import time
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from copy import deepcopy

from sepdesign.swarm_context import MAX_RECORD_BYTES, encoded


class NoMemory:
    """Independent search control: no publications or peer findings."""
    sharing = False

    def start(self, run_id, agents):
        self.run_id = run_id
        self.clean_slate = {'verified': True, 'readers': len(agents), 'remote': False}

    def publish(self, record): return None
    def barrier(self): pass
    def recall(self, agent, query=None): return []


class LocalMemory:
    """Deterministic test double; create a new instance for every run."""
    sharing = True

    def start(self, run_id, agents):
        self.run_id, self.records = run_id, {}
        self.clean_slate = {'verified': True, 'readers': len(agents), 'remote': False}

    def publish(self, record):
        self.records[record['id']] = deepcopy(record)
        return record['id']

    def barrier(self):
        pass

    def recall(self, agent, query=None):
        return [{'id': k, 'sources': [{'sourceId': k}], 'content': json.dumps(v)} for k, v in self.records.items()]


class ExactMemory(LocalMemory):
    """Control with the runner's exact incumbent/recent packet, no retrieval."""
    def recall(self, agent, query=None):
        return []


class PastMemory:
    sharing = True

    def __init__(self, timeout=300, request_timeout=30, blocking=False):
        self.timeout, self.request_timeout = timeout, request_timeout
        self.blocking = blocking
        self.events = []
        self.key = os.environ['PAST_API_KEY']
        if sys.platform == 'win32':
            import truststore
            self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            self.ssl_context = ssl.create_default_context()

    def _request(self, method, path, body=None):
        start = time.monotonic()
        req = urllib.request.Request('https://api.past.dev/api/v1/' + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'}, method=method)
        event = {'method': method, 'path': path, 'usd': None, 'usd_label': 'unknown'}
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout, context=self.ssl_context) as response:
                event.update(request_id=response.headers.get('X-Request-Id'), ok=True)
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                error_code = json.loads(exc.read()).get('code', 'unknown')
            except (ValueError, AttributeError):
                error_code = 'unknown'
            event.update(ok=False, status=exc.code, code=error_code)
            raise RuntimeError(f'past.dev HTTP {exc.code} ({error_code}) on {path}') from None
        except Exception as exc:
            event.update(ok=False, error_type=type(exc).__name__)
            raise
        finally:
            event['seconds'] = time.monotonic() - start
            self.events.append(event)

    def start(self, run_id, agents):
        if getattr(self, 'run_id', None) is not None:
            raise ValueError('Use a new PastMemory instance and audience for every run')
        self.run_id, self.pending, self.sources = run_id, [], set()
        self.pending_since = {}
        self.clean_slate = {'verified': False, 'audience': run_id, 'readers': len(agents),
                            'remote': True, 'raw_findings': 0}
        self.identities = {a: f'{run_id}-{a}' for a in agents}
        self._request('PUT', 'audiences/' + run_id,
                      {'kind': 'fixed', 'name': run_id, 'identities': list(self.identities.values())})
        # Filtered-empty is insufficient: project-visible memories can be read by
        # every identity. Detect that setup error before any model/solver work.
        for agent in agents:
            response = self._request('POST', 'recall', {
                'identity': self.identities[agent], 'query': 'Prior simulator experiments, findings and plant design results',
                'maxTokens': 8000, 'limit': 100})
            self.clean_slate['raw_findings'] += len(response['results'])
        if self.clean_slate['raw_findings']:
            raise RuntimeError('Clean-slate check failed: fresh readers can recall existing memory; use a dedicated experiment project without project-visible data')
        self.clean_slate['verified'] = True

    def publish(self, record):
        return self.publish_batch([record])[0]

    def barrier(self):
        deadline = time.monotonic() + self.timeout
        for ingestion in list(self.pending):
            while True:
                result = self._request('GET', 'ingest/' + ingestion)
                if getattr(self, 'events', None):
                    self.events[-1]['ingestion_status'] = result['status']
                if result['status'] == 'completed':
                    self.pending.remove(ingestion)
                    getattr(self, 'pending_since', {}).pop(ingestion, None)
                    break
                if result['status'] == 'failed':
                    raise RuntimeError('past.dev ingestion failed: ' + ingestion)
                since = getattr(self, 'pending_since', {}).get(ingestion, time.monotonic())
                age = time.monotonic() - since
                overdue = age >= self.timeout
                if getattr(self, 'events', None):
                    self.events[-1].update(pending_age_s=age, visibility_overdue=overdue)
                # Async visibility is allowed to lag; retain the job and report
                # its age rather than terminating unrelated simulator work.
                if not getattr(self, 'blocking', True):
                    break
                if time.monotonic() >= deadline or overdue:
                    raise TimeoutError('past.dev visibility deadline exceeded')
                time.sleep(2)

    def publish_batch(self, records):
        """One ingestion job per proposal round, with one scoped point per result."""
        if not records:
            return []
        items = []
        timestamp = datetime.now(timezone.utc).isoformat()
        for record in records:
            content = encoded(record)
            if len(content.encode()) > MAX_RECORD_BYTES:
                raise ValueError('Memory publication exceeds compact evidence budget')
            items.append(dict(id=record['id'], audience=self.run_id, timestamp=timestamp,
                label=f"{record['agent']} round {record['round']}; valid={record['measured'].get('valid')}; reward={record['measured'].get('reward')}",
                content=content))
        response = self._request('POST', 'ingest/batch', dict(items=items,
            idempotencyKey=hashlib.sha256(encoded([r['id'] for r in records]).encode()).hexdigest()))
        sources = {item['sourceId'] for item in response['items']}
        if sources != {record['id'] for record in records}:
            raise RuntimeError('past.dev batch source IDs differ from submitted versions')
        self.sources.update(sources)
        self.pending.append(response['ingestionId'])
        self.pending_since[response['ingestionId']] = time.monotonic()
        return [response['ingestionId']] * len(records)

    def recall(self, agent, query=None):
        response = self._request('POST', 'recall', {
            'identity': self.identities[agent], 'query': query or f'Simulator findings, measured results and design settings from run {self.run_id}',
            'maxTokens': 8000, 'limit': 100})
        self.last_source_ids = [s['sourceId'] for r in response['results'] for s in r.get('sources', [])]
        # Project-visible or mixed-source memories must never enter the agent context.
        accepted = [r for r in response['results'] if r.get('sources') and
                all(s['sourceId'] in self.sources for s in r['sources'])]
        self.last_recall = dict(agent=agent, query=query, raw_findings=len(response['results']),
            accepted_findings=len(accepted), filtered_findings=len(response['results'])-len(accepted),
            used_evidence_tokens=response.get('usedEvidenceTokens'),
            pending=response.get('pending'), source_ids=self.last_source_ids)
        if getattr(self, 'events', None):
            self.events[-1]['recall'] = self.last_recall
        return accepted
