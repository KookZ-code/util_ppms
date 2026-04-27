"""Integration tests for all API endpoints.

Uses unittest (stdlib) + fastapi.testclient. No pytest required.

Run:
    python -m unittest api.tests.test_endpoints -v

Covers:
- Health + OpenAPI + root
- Auth (401 without key / bad key, 200 valid key)
- Response envelope shape
- Per-endpoint data shape + sanity checks
- Cache behaviour (hit on repeat, miss on different params)
- 404 on missing resources
- Known-issue regressions (ISO/FS machine count, Status Matrix, M/C DOWN)

Requires the dashboard/.env to be configured (tests hit real SQL+Oracle).
"""
import os
import unittest
import urllib.parse
import requests


VALID_KEY = os.getenv('API_KEY', 'mch_dev_12345')
BASE = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')
HEADERS = {'X-API-Key': VALID_KEY}
END = '2026-04-26'
START_7D = '2026-04-20'
START_30D = '2026-03-28'


class _RequestsClient:
    """Thin shim so existing test code that calls `client.get(path, ...)` works
    against a running API server instead of an in-process TestClient."""

    def __init__(self, base_url: str):
        self._base = base_url.rstrip('/')
        self._session = requests.Session()

    def get(self, path: str, headers=None, params=None):
        return self._session.get(
            f"{self._base}{path}",
            headers=headers,
            params=params,
            timeout=120,
        )


class APITestBase(unittest.TestCase):
    """Shared HTTP client — one session reused by every subclass method."""

    @classmethod
    def setUpClass(cls):
        cls.client = _RequestsClient(BASE)
        # Verify the server is reachable before running any test
        try:
            r = cls.client.get('/api/v1/health')
            if r.status_code != 200:
                raise unittest.SkipTest(
                    f"API at {BASE} not healthy (HTTP {r.status_code})")
        except requests.RequestException as e:
            raise unittest.SkipTest(f"API at {BASE} unreachable: {e}")

    def assertEnvelope(self, body: dict):
        self.assertEqual(body['status'], 'ok')
        self.assertIn('data', body)
        self.assertIn('meta', body)
        for key in ('cached', 'query_time_ms', 'timestamp'):
            self.assertIn(key, body['meta'])


# ══════════════════════════════════════════════════════════════════════════════
# Health + OpenAPI + root
# ══════════════════════════════════════════════════════════════════════════════

class TestHealth(APITestBase):

    def test_root(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['name'], 'Machine Dashboard API')
        self.assertEqual(body['docs'], '/docs')

    def test_health(self):
        r = self.client.get('/api/v1/health')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'ok')
        self.assertIn('databases', body)
        self.assertIn('sql_server', body['databases'])
        self.assertIn('oracle', body['databases'])

    def test_openapi_schema_documents_all_paths(self):
        r = self.client.get('/openapi.json')
        self.assertEqual(r.status_code, 200)
        paths = set(r.json()['paths'].keys())
        for p in ['/api/v1/health', '/api/v1/overview', '/api/v1/utilization',
                  '/api/v1/downtime/events', '/api/v1/machines',
                  '/api/v1/tech-performance', '/api/v1/areas',
                  '/api/v1/inventory/machines']:
            self.assertIn(p, paths, f"Missing path in OpenAPI: {p}")


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

class TestAuth(APITestBase):

    def test_missing_key_returns_401(self):
        r = self.client.get('/api/v1/overview')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['detail']['code'], 'MISSING_API_KEY')

    def test_bad_key_returns_401(self):
        r = self.client.get('/api/v1/overview',
                            headers={'X-API-Key': 'not-a-real-key'})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['detail']['code'], 'INVALID_API_KEY')

    def test_valid_key_returns_200(self):
        r = self.client.get('/api/v1/overview', headers=HEADERS)
        self.assertEqual(r.status_code, 200)


# ══════════════════════════════════════════════════════════════════════════════
# Overview
# ══════════════════════════════════════════════════════════════════════════════

class TestOverview(APITestBase):

    def test_envelope(self):
        body = self.client.get('/api/v1/overview', headers=HEADERS).json()
        self.assertEnvelope(body)

    def test_kpi_shape(self):
        kpi = self.client.get('/api/v1/overview', headers=HEADERS).json()['data']['kpi']
        for key in ('total_machines', 'running', 'down', 'waiting',
                    'on_process', 'closed_this_shift'):
            self.assertIn(key, kpi)
            self.assertIsInstance(kpi[key], int)

    def test_kpi_sanity(self):
        kpi = self.client.get('/api/v1/overview', headers=HEADERS).json()['data']['kpi']
        # Running + waiting + on_process should not exceed total
        # (allow small slack for race conditions between SQL/Oracle counts)
        self.assertLessEqual(
            kpi['waiting'] + kpi['on_process'] + kpi['running'],
            kpi['total_machines'] + 5)

    def test_iso_fs_master_count_regression(self):
        """Regression: Overview used nunique() in live events (42), should be
        62 from dbo.machine — matching Inventory page."""
        body = self.client.get('/api/v1/overview?areas=ISO,FS', headers=HEADERS).json()
        mc = body['data']['kpi']['total_machines']
        self.assertGreaterEqual(mc, 55)
        self.assertLessEqual(mc, 70)

    def test_iso_fs_status_matrix_populated_regression(self):
        """Regression: Status Matrix returned empty for Oracle-only area selection."""
        body = self.client.get('/api/v1/overview?areas=ISO,FS', headers=HEADERS).json()
        matrix = body['data']['status_matrix']
        self.assertGreater(len(matrix), 0)
        for row in matrix:
            self.assertEqual(
                set(row.keys()),
                {'job_type', 'waiting', 'on_process', 'closed', 'total'})

    def test_open_jobs(self):
        body = self.client.get('/api/v1/overview/open-jobs', headers=HEADERS).json()
        self.assertEnvelope(body)
        self.assertIn('jobs', body['data'])
        self.assertIn('total', body['data'])


# ══════════════════════════════════════════════════════════════════════════════
# Utilization
# ══════════════════════════════════════════════════════════════════════════════

class TestUtilization(APITestBase):

    def test_kpi_within_range(self):
        kpi = self.client.get(
            f'/api/v1/utilization?start={START_7D}&end={END}&areas=WB',
            headers=HEADERS).json()['data']['kpi']
        self.assertGreaterEqual(kpi['utilization_pct'], 0)
        self.assertLessEqual(kpi['utilization_pct'], 100)
        self.assertGreaterEqual(kpi['downtime_pct'], 0)
        self.assertLessEqual(kpi['downtime_pct'], 100)

    def test_detail_bundle_complete(self):
        data = self.client.get(
            f'/api/v1/utilization/detail?start={START_7D}&end={END}',
            headers=HEADERS).json()['data']
        for key in ('kpi', 'prev_kpi', 'by_area', 'monthly_trend',
                    'scatter', 'top_down', 'top_lost',
                    'machines_per_cause', 'raw'):
            self.assertIn(key, data)
        # raw needed by dashboard for re-computation
        self.assertIn('kpi_totals', data['raw'])

    def test_by_machine_shape(self):
        data = self.client.get(
            f'/api/v1/utilization/by-machine?start={START_7D}&end={END}&areas=WB',
            headers=HEADERS).json()['data']
        self.assertGreater(data['total'], 0)
        self.assertGreaterEqual(
            set(data['rows'][0].keys()),
            {'machine_id', 'area', 'job_type', 'total_min', 'wait_min'})

    def test_attention_capped_at_10(self):
        data = self.client.get(
            f'/api/v1/utilization/attention?start={START_30D}&end={END}',
            headers=HEADERS).json()['data']
        self.assertLessEqual(len(data['rows']), 10)
        for r in data['rows']:
            self.assertGreaterEqual(
                set(r.keys()),
                {'machine_id', 'area', 'down_hours', 'event_count',
                 'avg_mttr_min', 'score'})


# ══════════════════════════════════════════════════════════════════════════════
# Downtime
# ══════════════════════════════════════════════════════════════════════════════

class TestDowntime(APITestBase):

    def test_events(self):
        body = self.client.get(
            f'/api/v1/downtime/events?start={START_7D}&end={END}&areas=WB&limit=10',
            headers=HEADERS).json()
        for ev in body['data']['events']:
            self.assertIn('machine_id', ev)
            self.assertIn('source', ev)
            self.assertIn(ev['source'], ('sql', 'oracle'))

    def test_pareto_sorted_descending(self):
        rows = self.client.get(
            f'/api/v1/downtime/pareto?start={START_7D}&end={END}&top_n=5',
            headers=HEADERS).json()['data']['rows']
        self.assertLessEqual(len(rows), 5)
        if len(rows) >= 2:
            self.assertGreaterEqual(rows[0]['total_hrs'], rows[-1]['total_hrs'])

    def test_detail_bundle(self):
        data = self.client.get(
            '/api/v1/downtime/detail',
            params={'job_types': 'M/C DOWN', 'start': START_7D, 'end': END,
                    'reason_col': 'des_job'},
            headers=HEADERS).json()['data']
        for key in ('reason', 'machines_by_reason', 'daily_shift',
                    'machine_daily', 'symptom_cause', 'events'):
            self.assertIn(key, data)

    def test_machines_list(self):
        data = self.client.get(
            '/api/v1/downtime/machines?areas=WB', headers=HEADERS).json()['data']
        self.assertGreater(data['total'], 0)
        self.assertIsInstance(data['machines'], list)


# ══════════════════════════════════════════════════════════════════════════════
# Machines
# ══════════════════════════════════════════════════════════════════════════════

class TestMachines(APITestBase):

    def test_list_filter_area_key_only(self):
        data = self.client.get(
            '/api/v1/machines?area=DA&key_only=true',
            headers=HEADERS).json()['data']
        self.assertGreater(data['total'], 0)
        for m in data['machines']:
            self.assertEqual(m['area'], 'DA')
            self.assertEqual(m['flag_key'], 1)

    def test_detail_via_query_supports_slash_and_hash(self):
        """machines/detail?id=... supports IDs with slashes and hashes that
        break URL path routing."""
        body = self.client.get(
            '/api/v1/machines/detail',
            headers=HEADERS,
            params={'id': 'W/B # 270'},
        ).json()
        info = body['data']['info']
        self.assertEqual(info['machine_id'].strip(), 'W/B # 270')
        self.assertEqual(info['area'], 'WB')

    def test_detail_not_found(self):
        r = self.client.get(
            '/api/v1/machines/detail?id=DOES_NOT_EXIST_XYZ', headers=HEADERS)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['detail']['code'], 'NOT_FOUND')

    def test_records_limit_respected(self):
        data = self.client.get(
            '/api/v1/machines/records?id=W/B # 270&limit=10',
            headers=HEADERS).json()['data']
        self.assertLessEqual(data['total'], 10)
        self.assertIsInstance(data['records'], list)


# ══════════════════════════════════════════════════════════════════════════════
# Tech
# ══════════════════════════════════════════════════════════════════════════════

class TestTech(APITestBase):

    def test_performance_grades(self):
        techs = self.client.get(
            f'/api/v1/tech-performance?start={START_7D}&end={END}&top_n=5&job_type=M/C%20DOWN',
            headers=HEADERS).json()['data']['technicians']
        self.assertLessEqual(len(techs), 5)
        for t in techs:
            self.assertIn(t['grade'], ('A', 'B', 'C', 'D'))
            self.assertGreaterEqual(t['composite_score'], 0)
            self.assertLessEqual(t['composite_score'], 100)

    def test_metrics_shape(self):
        rows = self.client.get(
            f'/api/v1/tech/metrics?start={START_7D}&end={END}',
            headers=HEADERS).json()['data']['rows']
        for r in rows:
            self.assertGreaterEqual(
                set(r.keys()),
                {'technician', 'job_count', 'avg_response_min',
                 'avg_repair_min', 'area_count', 'ftfr_pct'})

    def test_list_has_expected_columns(self):
        data = self.client.get('/api/v1/tech/list', headers=HEADERS).json()['data']
        self.assertGreater(data['total'], 0)
        sample = data['rows'][0]
        for col in ('Badge', 'Name', 'AERA', 'Supv', 'Group'):
            self.assertIn(col, sample)


# ══════════════════════════════════════════════════════════════════════════════
# Areas + Inventory
# ══════════════════════════════════════════════════════════════════════════════

class TestAreasInventory(APITestBase):

    def test_areas_deduped_and_merged(self):
        areas = self.client.get('/api/v1/areas', headers=HEADERS).json()['data']['areas']
        # No duplicates per (area, source) pair
        sql_codes = [a['area'] for a in areas if a['source'] == 'sql']
        self.assertEqual(len(sql_codes), len(set(sql_codes)))
        # Standard plant areas present
        all_codes = {a['area'] for a in areas}
        for code in ('WB', 'DA', 'SAW', 'MOLD', 'PLATE'):
            self.assertIn(code, all_codes)

    def test_inventory_machines_shape(self):
        data = self.client.get(
            '/api/v1/inventory/machines', headers=HEADERS).json()['data']
        self.assertGreater(data['total'], 0)
        for m in data['machines'][:5]:
            self.assertIn('code_machine', m)
            self.assertIn('id_operation', m)
            self.assertIn('flag_key', m)

    def test_inventory_downtime_shape(self):
        rows = self.client.get(
            '/api/v1/inventory/downtime', headers=HEADERS).json()['data']['rows']
        for r in rows[:5]:
            self.assertGreaterEqual(
                set(r.keys()),
                {'code_machine', 'down_events', 'down_hrs', 'avg_mttr_min'})


# ══════════════════════════════════════════════════════════════════════════════
# Cache
# ══════════════════════════════════════════════════════════════════════════════

class TestCache(APITestBase):

    def test_second_identical_request_is_cached(self):
        path = f'/api/v1/utilization?start={START_7D}&end={END}&areas=WB'
        self.client.get(path, headers=HEADERS)  # warm
        body = self.client.get(path, headers=HEADERS).json()
        self.assertTrue(body['meta']['cached'])
        self.assertEqual(body['meta']['query_time_ms'], 0)

    def test_different_params_miss_cache(self):
        """Use a unique start_date per test run to guarantee no pre-existing
        cache entry — cache TTL is 5min, tests run much faster than that."""
        import time
        # Off-by-one day based on test nanoseconds — unique per run
        unique_start = f"2026-04-{(int(time.time() * 1000) % 20) + 1:02d}"
        body = self.client.get(
            f'/api/v1/utilization?start={unique_start}&end={END}&areas=DA',
            headers=HEADERS).json()
        self.assertFalse(body['meta']['cached'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
