"""
A minimalistic statistical debugging helper.
"""

import time
import json
import functools
import inspect
import os
from typing import Callable, Any, List, Dict
import numpy as np

# ------------------------------------------------------------------
# 1. In-memory store (replaceable with a CSV writer, DB client, etc.)
# ------------------------------------------------------------------
CALL_LOG: List[Dict[str, Any]] = []

# ------------------------------------------------------------------
# 2. Decorator to capture timing & exceptions
# ------------------------------------------------------------------
import os
import json

class TelemetryLogger:
    """Lightweight logger for matching server/client bottlenecks."""
    ENABLED = os.environ.get("VELOX_PROFILING") == "1"
    
    @staticmethod
    def log_frame(timestamp: int, event: str, duration_ms: float, metadata: dict = None):
        if not TelemetryLogger.ENABLED:
            return
        
        entry = {
            "ts": timestamp,
            "ev": event,
            "dur": round(duration_ms, 2)
        }
        if metadata:
            entry.update(metadata)
            
        # Log to standard debug output with a specific prefix for easy grepping
        print(f"PROFILER_DATA: {json.dumps(entry)}")

def stat_capture(func: Callable) -> Callable:
    """Wrap a function to record execution time, success/failure, and arguments."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = None
        exc = None
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            exc = e
        elapsed = time.perf_counter() - start

        # Log the call
        CALL_LOG.append({
            'function': func.__qualname__,
            'time': elapsed,
            'success': exc is None,
            'exception': str(exc) if exc else None,
            'args': _serialize(args),
            'kwargs': _serialize(kwargs),
        })

        if exc:
            raise exc
        return result
    return wrapper

# ------------------------------------------------------------------
# 3. Helper: simple JSON-serialisable conversion
# ------------------------------------------------------------------
def _serialize(obj):
    """Recursively make objects JSON-serialisable."""
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    try:
        json.dumps(obj)  # test serialisability
        return obj
    except TypeError:
        return str(obj)

# ------------------------------------------------------------------
# 4. Persist log to CSV (optional)
# ------------------------------------------------------------------
def write_log_to_csv(path: str):
    import csv
    if not CALL_LOG:
        return
    keys = CALL_LOG[0].keys()
    with open(path, 'w', newline='') as f:
        dict_writer = csv.DictWriter(f, keys)
        dict_writer.writeheader()
        dict_writer.writerows(CALL_LOG)

# ------------------------------------------------------------------
# 5. Statistical analysis (mean, std, z-score)
# ------------------------------------------------------------------
def analyze_log():
    """Return a dict mapping function name -> stats."""
    import numpy as np
    stats = {}
    # group by function
    from collections import defaultdict
    d = defaultdict(list)
    for rec in CALL_LOG:
        d[rec['function']].append(rec)
    
    for func_name, records in d.items():
        times = np.array([r['time'] for r in records])
        success_count = sum(r['success'] for r in records)
        total = len(records)
        # Basic stats
        stats[func_name] = {
            'n_calls': total,
            'n_success': success_count,
            'mean_time': times.mean(),
            'std_time': times.std(ddof=1) if total > 1 else 0.0,
            'p95_time': np.percentile(times, 95),
            'error_rate': (total - success_count) / total,
            'z_scores': _z_scores(times),
        }
    return stats

def _z_scores(arr: np.ndarray):
    mean = arr.mean()
    std = arr.std(ddof=1)
    if std == 0:
        return [0]*len(arr)
    return [(x - mean)/std for x in arr]

# ------------------------------------------------------------------
# 6. Pretty report
# ------------------------------------------------------------------
def report_anomalies(threshold: float = 3.0):
    """Print functions whose mean time > threshold * std or high error rate."""
    stats = analyze_log()
    print("\n=== Statistical Debugging Report ===\n")
    for func, s in sorted(stats.items(), key=lambda kv: kv[1]['mean_time'], reverse=True):
        anomaly = False
        # High mean vs std
        if s['std_time'] > 0 and s['mean_time'] > threshold * s['std_time']:
            anomaly = True
        # High error rate
        if s['error_rate'] > 0.1:   # 10% errors
            anomaly = True
        if anomaly:
            print(f"[ANOMALY] {func}")
            print(f"  Calls: {s['n_calls']}  Successes: {s['n_success']}  Errors: {s['n_calls']-s['n_success']}")
            print(f"  Mean time: {s['mean_time']:.6f}s  Std: {s['std_time']:.6f}s  P95: {s['p95_time']:.6f}s")
            print(f"  Error rate: {s['error_rate']*100:.1f}%")
    print("\n=== End of Report ===\n")

def flush_to_telemetry():
    """Summarizes current stats and logs them to the telemetry system."""
    from .telemetry import telemetry
    stats = analyze_log()
    for func_name, s in stats.items():
        telemetry.log_event(
            action="performance_summary",
            module="pipeline_engine",
            execution_metrics={
                "function": func_name,
                "n_calls": s['n_calls'],
                "duration_ms": round(s['mean_time'] * 1000, 2),
                "p95_ms": round(s['p95_time'] * 1000, 2),
                "error_rate": s['error_rate']
            },
            tags=["performance", "bottleneck-detection"]
        )
    # Clear log after flushing to prevent memory bloat
    global CALL_LOG
    CALL_LOG = []
