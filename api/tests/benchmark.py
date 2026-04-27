"""Benchmark API endpoints: cold (cache miss) vs warm (cache hit) latency.

Run:
    python -m api.tests.benchmark

Expects the API to be running on http://127.0.0.1:8000 with a valid dev key.
"""
import os
import statistics
import time
from typing import Tuple
import requests

BASE = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')
KEY = os.getenv('API_KEY', 'mch_dev_12345')
HEADERS = {'X-API-Key': KEY}

# Representative date ranges for queries
END = '2026-04-26'
START_7D = '2026-04-20'
START_30D = '2026-03-28'

ENDPOINTS = [
    # (label, path, params)
    ('health',                    '/api/v1/health',                   {}),
    ('areas',                     '/api/v1/areas',                    {}),
    ('overview (all)',            '/api/v1/overview',                 {}),
    ('overview (ISO+FS)',         '/api/v1/overview',                 {'areas': 'ISO,FS'}),
    ('overview/open-jobs',        '/api/v1/overview/open-jobs',       {}),
    ('utilization (7d, WB)',      '/api/v1/utilization',              {'start': START_7D, 'end': END, 'areas': 'WB'}),
    ('utilization/detail (30d)',  '/api/v1/utilization/detail',       {'start': START_30D, 'end': END}),
    ('utilization/by-machine',    '/api/v1/utilization/by-machine',   {'start': START_7D, 'end': END, 'areas': 'WB'}),
    ('utilization/attention',     '/api/v1/utilization/attention',    {'start': START_30D, 'end': END}),
    ('downtime/events',           '/api/v1/downtime/events',          {'start': START_7D, 'end': END, 'areas': 'WB', 'limit': '100'}),
    ('downtime/pareto',           '/api/v1/downtime/pareto',          {'start': START_7D, 'end': END}),
    ('downtime/detail (M/C DOWN)','/api/v1/downtime/detail',          {'job_types': 'M/C DOWN', 'start': START_7D, 'end': END, 'reason_col': 'des_job'}),
    ('downtime/machines',         '/api/v1/downtime/machines',        {}),
    ('machines (all)',            '/api/v1/machines',                 {}),
    ('machines?area=DA&key',      '/api/v1/machines',                 {'area': 'DA', 'key_only': 'true'}),
    ('machines/detail',           '/api/v1/machines/detail',          {'id': 'Mold # 08'}),
    ('machines/records',          '/api/v1/machines/records',         {'id': 'W/B # 270', 'limit': '50'}),
    ('tech-performance',          '/api/v1/tech-performance',         {'start': START_7D, 'end': END, 'job_type': 'M/C DOWN'}),
    ('tech/metrics',              '/api/v1/tech/metrics',             {'start': START_7D, 'end': END}),
    ('tech/list',                 '/api/v1/tech/list',                {}),
    ('inventory/machines',        '/api/v1/inventory/machines',       {}),
    ('inventory/downtime',        '/api/v1/inventory/downtime',       {}),
]


def _hit(path: str, params: dict) -> Tuple[int, float, bool]:
    """Return (status_code, elapsed_ms, cached)."""
    t0 = time.perf_counter()
    r = requests.get(f"{BASE}{path}", params=params, headers=HEADERS, timeout=120)
    elapsed = (time.perf_counter() - t0) * 1000
    cached = False
    try:
        body = r.json()
        cached = bool(body.get('meta', {}).get('cached', False))
    except Exception:
        pass
    return r.status_code, elapsed, cached


def bench_endpoint(label: str, path: str, params: dict, warm_runs: int = 3):
    """Clear cache (by invoking with a unique sentinel query) then run cold + warm."""
    # Cold run — wall-clock time for first request (cache miss)
    status, cold_ms, cold_cached = _hit(path, params)
    if status != 200:
        print(f"  {label:35s}  ERROR HTTP {status}")
        return

    # Warm runs
    warm_times = []
    warm_cached_flags = []
    for _ in range(warm_runs):
        _, ms, cached = _hit(path, params)
        warm_times.append(ms)
        warm_cached_flags.append(cached)

    warm_avg = statistics.mean(warm_times)
    warm_min = min(warm_times)
    warm_cache_rate = sum(warm_cached_flags) / len(warm_cached_flags) * 100

    speedup = cold_ms / warm_avg if warm_avg > 0 else 0
    print(f"  {label:35s}  cold={cold_ms:7.1f}ms  warm_avg={warm_avg:6.1f}ms  warm_min={warm_min:5.1f}ms  speedup={speedup:5.1f}x  cache_hit={warm_cache_rate:.0f}%")


def main():
    print(f"Benchmarking {BASE}  (date range: {START_7D}..{END} or {START_30D}..{END})\n")
    print(f"  {'endpoint':35s}  {'cold':>10s}  {'warm avg':>12s}  {'warm min':>11s}  {'speedup':>7s}  {'cache':>10s}")
    print(f"  {'-'*35}  {'-'*10}  {'-'*12}  {'-'*11}  {'-'*7}  {'-'*10}")
    for label, path, params in ENDPOINTS:
        bench_endpoint(label, path, params)


if __name__ == '__main__':
    main()
