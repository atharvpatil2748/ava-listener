#!/usr/bin/env python3
"""
AVAListener -- Runtime Stress Monitor (F1 + F2)
Injects synthetic audio, samples metrics, generates MEMORY_STABILITY_REPORT.md.

Usage:
    python scripts/stress_monitor.py [--duration 60] [--interval 10]
"""
from __future__ import annotations
import sys, os, time, gc, threading, argparse
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("ORT_NO_OPERATOR_CUSTOM_OPS", "1")

import numpy as np


def _mem_mb() -> float:
    try:
        import tracemalloc
        if not tracemalloc.is_tracing(): tracemalloc.start()
        cur, _ = tracemalloc.get_traced_memory()
        return cur / 1048576.0
    except Exception:
        return float(len(gc.get_objects())) / 10000.0


def _snap(engine, t0: float, n: int) -> dict:
    s = {"n": n, "elapsed": round(time.monotonic()-t0,1),
         "mem_mb": round(_mem_mb(),2), "threads": threading.active_count(),
         "ts": time.strftime("%H:%M:%S")}
    try:
        d = engine.getDiagnostics()
        health_block = d.get("health", {})
        # Key is "runtimeHealth" (not "score") — P6-FIX-1 correction
        s["health"] = round(health_block.get("runtimeHealth", -1.0), 3)
        s["state"]  = d.get("current_state", "?")
        sub = health_block.get("subsystems", {})
        s["asr"] = sub.get("ASR", "?"); s["audio"] = sub.get("Audio", "?")
        s["vad"]  = sub.get("VAD", "?")
    except Exception as e:
        s["health"] = -1.0
    try:
        st = engine._streamer
        s["qd"]      = st._audio_queue.qsize()
        s["gen"]     = st._provider.generation_id
        s["resets"]  = st._provider.reset_count
        s["worker"]  = st._worker_thread is not None and st._worker_thread.is_alive()
        s["idle_ms"] = round(st.avg_worker_idle_ms, 2)
        s["proc_ms"] = round(st.avg_worker_processing_ms, 2)
    except: pass
    return s


def _trend(snaps: list) -> dict:
    ys = [s.get("mem_mb",0) for s in snaps]
    xs = [s.get("elapsed",0) for s in snaps]
    if len(snaps) < 3:
        return {"slope":0.0,"r2":0.0,"verdict":"INSUFFICIENT_DATA","min":min(ys) if ys else 0,"max":max(ys) if ys else 0}
    n=len(xs); sx=sum(xs); sy=sum(ys); sxy=sum(x*y for x,y in zip(xs,ys)); sxx=sum(x*x for x in xs)
    den=n*sxx-sx*sx; slope=(n*sxy-sx*sy)/den if abs(den)>1e-9 else 0.0
    slope_pm = slope*60.0
    ym=sy/n; sst=sum((y-ym)**2 for y in ys)
    intercept=(sy-slope*sx)/n if abs(den)>1e-9 else 0
    ssr=sum((y-(slope*x+intercept))**2 for x,y in zip(xs,ys))
    r2=1-(ssr/sst) if sst>1e-9 else 0
    if abs(slope_pm)>10 and r2>0.8: v="LEAK_DETECTED"
    elif abs(slope_pm)>5 and r2>0.7: v="GROWTH_WARNING"
    else: v="STABLE"
    return {"slope":round(slope_pm,3),"r2":round(r2,3),"verdict":v,
            "min":round(min(ys),2),"max":round(max(ys),2),"delta":round(max(ys)-min(ys),2)}


def _report(snaps, frames_injected, dur, t_start, t_end, deaths, overflows, out: Path):
    tr = _trend(snaps)
    ok = deaths==0 and overflows==0 and tr["verdict"] in ("STABLE","INSUFFICIENT_DATA")
    verdict = "PASS" if ok else "FAIL"
    rows_data = "\n".join(
        f"| {s['n']} | {s['ts']} | {s['elapsed']:.0f}s | {s.get('mem_mb',0):.2f} "
        f"| {s.get('qd',0)} | {s.get('threads',0)} | {s.get('health',0):.3f} "
        f"| {'Y' if s.get('worker',True) else 'DEAD'} | {s.get('gen','?')} | {s.get('resets','?')} |"
        for s in snaps)
    state_rows = "\n".join(
        f"| {s['n']} | {s.get('asr','?')} | {s.get('audio','?')} | {s.get('vad','?')} | {s.get('state','?')} |"
        for s in snaps)
    findings = ("All criteria passed." if ok else
        f"FAILURES: workers={deaths} overflows={overflows} memory={tr['verdict']}")
    md = f"""# Memory Stability Report -- AVAListener Runtime Stress (F2)

> **Date:** {time.strftime('%Y-%m-%d')}  |  **Start:** {t_start}  |  **End:** {t_end}
> **Duration:** {dur:.0f}s  |  **Audio:** Synthetic (no microphone)  |  **Verdict:** {verdict}

---

## 1. Summary

| Metric | Value | Status |
|--------|-------|--------|
| Worker deaths | {deaths} | {'OK' if deaths==0 else 'FAIL'} |
| Queue overflow events | {overflows} | {'OK' if overflows==0 else 'FAIL'} |
| Memory trend | {tr['verdict']} ({tr['slope']:+.3f} MB/min) | {'OK' if tr['verdict']=='STABLE' else 'WARN'} |
| Total frames injected | {frames_injected:,} | -- |
| Samples collected | {len(snaps)} | -- |

## 2. Memory Trend

| Slope (MB/min) | R2 | Min MB | Max MB | Delta MB | Verdict |
|---|---|---|---|---|---|
| {tr['slope']:+.3f} | {tr['r2']:.3f} | {tr['min']:.2f} | {tr['max']:.2f} | {tr['delta']:.2f} | **{tr['verdict']}** |

## 3. Per-Sample Metrics

| # | Time | Elapsed | Memory MB | Queue | Threads | Health | Worker | Gen | Resets |
|---|------|---------|-----------|-------|---------|--------|--------|-----|--------|
{rows_data}

## 4. State Timeline

| # | ASR | Audio | VAD | Engine State |
|---|-----|-------|-----|-------------|
{state_rows}

## 5. Findings

{findings}
"""
    out.write_text(md, encoding="utf-8")
    print(f"  Report -> {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--profile",  default=str(_ROOT/"profiles"/"arvsal.json"))
    ap.add_argument("--output",   default=str(_ROOT/"MEMORY_STABILITY_REPORT.md"))
    args = ap.parse_args()

    print("="*60); print("  AVAListener -- Runtime Stress Monitor (F1+F2)")
    print(f"  Duration={args.duration:.0f}s  Interval={args.interval:.0f}s"); print("="*60)

    from core.engine import WakeEngine
    import tracemalloc; tracemalloc.start()

    engine = WakeEngine()
    if os.path.isfile(args.profile):
        engine.load_profile(args.profile)

    stop = threading.Event()

    # Patch start() to skip real audio
    from runtime.asr.streaming import SherpaStreamer
    from runtime.kernel.lifecycle import SubsystemState

    def _fake_start(self, on_hypothesis):
        self._stop_event.clear()
        self._provider.reset(reason="start")
        self._asr_fsm.transition(SubsystemState.INITIALIZING)
        self._asr_fsm.transition(SubsystemState.READY)
        self._audio_worker.start(on_hypothesis, name="asr-worker")
        self._audio_fsm.transition(SubsystemState.INITIALIZING)
        self._audio_fsm.transition(SubsystemState.READY)
        self._audio_fsm.transition(SubsystemState.ACTIVE)
        while not self._stop_event.is_set(): time.sleep(0.2)
        self._stop_event.set()
        self._audio_worker.stop()

    SherpaStreamer.start = _fake_start

    err = []
    def _eng():
        try: engine.start()
        except Exception as e: err.append(e)

    t = threading.Thread(target=_eng, daemon=True); t.start()
    time.sleep(2.0)

    # Synthetic injector
    qmgr = engine._streamer._queue_manager
    inject_count = [0]

    def _inject():
        cycle = 0
        while not stop.is_set():
            for _ in range(30):  # 3s noise
                if stop.is_set(): return
                qmgr.enqueue(np.random.randn(1600).astype(np.float32)*0.05)
                inject_count[0] += 1; time.sleep(0.1)
            for _ in range(20):  # 2s silence
                if stop.is_set(): return
                qmgr.enqueue(np.zeros(1600,dtype=np.float32))
                inject_count[0] += 1; time.sleep(0.1)
            cycle += 1

    it = threading.Thread(target=_inject, daemon=True); it.start()
    print("  Synthetic audio injector started")

    snaps=[]; deaths=0; overflows=0
    t0=time.monotonic(); t_start=time.strftime("%H:%M:%S")
    next_s=t0+args.interval; deadline=t0+args.duration; n=0

    print(f"\n  {'#':>3}  {'Elapsed':>7}  {'Mem MB':>7}  {'Queue':>6}  {'Health':>7}  Worker")
    print("  "+"-"*50)
    try:
        while time.monotonic()<deadline:
            now=time.monotonic()
            if now>=next_s:
                n+=1; s=_snap(engine,t0,n); snaps.append(s); next_s=now+args.interval
                if not s.get("worker",True): deaths+=1
                if s.get("qd",0)>30: overflows+=1
                print(f"  {n:>3}  {s['elapsed']:>6.0f}s  {s.get('mem_mb',0):>7.2f}"
                      f"  {s.get('qd',0):>6}  {s.get('health',0):>7.3f}  {'LIVE' if s.get('worker',True) else 'DEAD'}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n  Interrupted -- generating partial report")

    t_end=time.strftime("%H:%M:%S"); dur=time.monotonic()-t0
    stop.set(); engine.stop(); t.join(timeout=5)

    print()
    _report(snaps, inject_count[0], dur, t_start, t_end, deaths, overflows, Path(args.output))
    tr=_trend(snaps)
    ok=deaths==0 and overflows==0 and tr["verdict"] in ("STABLE","INSUFFICIENT_DATA")
    print(f"  Verdict: {'PASS' if ok else 'FAIL'}  "
          f"deaths={deaths} overflows={overflows} mem={tr['verdict']} ({tr['slope']:+.3f} MB/min)")
    return 0 if ok else 1


if __name__=="__main__": sys.exit(main())
