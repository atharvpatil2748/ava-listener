"""Supervisor process for AVAListener (Phase 6 implementation).

Spawns the Runtime Worker (`main.py`) as a subprocess, monitors its
stdout for heartbeat events, forwards worker JSON events to stdout, and
forwards stdin commands from the Node SDK to the worker stdin. Implements a
restart policy and heartbeat-driven restarts so the Supervisor survives
worker crashes or hangs.

This supervisor is intentionally simple and self-contained to satisfy the
Phase 6 Definition of Done. It may be extended later with IPC sockets,
structured control channels, and richer health reporting.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from typing import Optional

from utils.logger import get_logger
from runtime.supervisor.restart_policy import RestartPolicy, RecoveryPolicy
from runtime.ipc.channel import IPCServer
from runtime.transport.websocket_server import WSServer

log = get_logger("supervisor")


def _emit(payload: dict) -> None:
    line = json.dumps(payload, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


class Supervisor:
	def __init__(self, worker_cmd: list[str], heartbeat_timeout_s: float = 12.0,
				 worker_startup_timeout_s: float = 15.0,
			 restart_policy: Optional[RestartPolicy] = None,
			 ws_port: int = 5050, profile_path: Optional[str] = None) -> None:
		self.worker_cmd = worker_cmd
		self.heartbeat_timeout_s = heartbeat_timeout_s
		self.worker_startup_timeout_s = worker_startup_timeout_s
		self.restart_policy = restart_policy or RestartPolicy()
		self._recovery_policy = RecoveryPolicy()
		self.profile_path = profile_path
		self.debug = "--debug" in worker_cmd
		self._degraded = False

		self._worker_proc: Optional[subprocess.Popen] = None
		self._last_heartbeat: float = 0.0
		self._stop_event = threading.Event()
		self._stdout_thread: Optional[threading.Thread] = None
		self._stderr_thread: Optional[threading.Thread] = None
		self._monitor_thread: Optional[threading.Thread] = None
		# IPC server for Supervisor <-> Worker messages
		self._ipc_server: Optional[IPCServer] = None
		self._ipc_lock = threading.Lock()
		
		# WebSocket server for Node SDK
		self._ws_server = WSServer(host="127.0.0.1", port=ws_port)

	def start(self) -> None:
		_emit({"event": "supervisor_starting", "ts": time.time()})
		log.info("Supervisor starting, launching worker: %s", self.worker_cmd)
		self._stop_event.clear()
		
		# Start WS Server
		self._ws_server.on_message = self._on_ws_receive
		self._ws_server.start_in_thread()
		# Start IPC server and accept worker connection
		try:
			self._ipc_server = IPCServer(host="127.0.0.1", port=0)
			self._ipc_server.accept_async(self._on_ipc_receive)
		except Exception:
			log.exception("Failed to start IPC server")
		self._spawn_worker()
		self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="sup-monitor")
		self._monitor_thread.start()
		# Start stdin proxy loop on main thread
		try:
			for raw in sys.stdin:
				if self._worker_proc and self._worker_proc.stdin:
					try:
						self._worker_proc.stdin.write(raw)
						self._worker_proc.stdin.flush()
					except Exception:
						log.exception("Failed forwarding stdin to worker")
			
			log.debug("Supervisor stdin EOF, initiating shutdown")
			self.stop()
		except Exception:
			# stdin closed — shutdown supervisor
			log.debug("Supervisor stdin exception, initiating shutdown")
			self.stop()

	def _spawn_worker(self) -> None:
		# Close previous proc handles if any
		if self._worker_proc is not None:
			try:
				self._worker_proc.terminate()
			except Exception:
				pass

		env = os.environ.copy()
		env.pop("PYTHONPATH", None)
		env.pop("PYTHONHOME", None)
		# Ensure main.py is on the path when invoked as module
		# Build a fresh command to avoid mutating the original
		cmd = list(self.worker_cmd)
		# If IPC server is active, pass port to worker via CLI args and env
		if self._ipc_server is not None:
			cmd += ["--ipc-host", self._ipc_server.host, "--ipc-port", str(self._ipc_server.port)]

		self._worker_proc = subprocess.Popen(
			cmd,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			env=env,
			text=True,
			bufsize=1,
		)

		# Reset heartbeat timer
		self._last_heartbeat = time.monotonic()

		# Start reader threads
		self._stdout_thread = threading.Thread(target=self._reader_loop_stdout, daemon=True, name="worker-stdout")
		self._stderr_thread = threading.Thread(target=self._reader_loop_stderr, daemon=True, name="worker-stderr")
		self._stdout_thread.start()
		self._stderr_thread.start()

		_emit({"event": "worker_started", "pid": self._worker_proc.pid, "ts": time.time()})
		log.info("Spawned worker pid=%s", self._worker_proc.pid)

	def _reader_loop_stdout(self) -> None:
		assert self._worker_proc and self._worker_proc.stdout
		try:
			for raw in self._worker_proc.stdout:
				line = raw.strip()
				if not line:
					continue
				# Try to parse JSON from worker and forward it. If it's heartbeat,
				# update the internal timestamp so supervisor monitor can act.
				try:
					obj = json.loads(line)
					# Forward worker event to Node (stdout)
					_emit(obj)
					self._ws_server.broadcast(obj)
					if obj.get("event") == "heartbeat":
						self._last_heartbeat = time.monotonic()
				except Exception:
					# If the worker printed non-JSON lines, forward as generic message
					out_obj = {"event": "worker_output", "line": line, "ts": time.time()}
					_emit(out_obj)
					self._ws_server.broadcast(out_obj)
		except Exception:
			log.exception("Error reading worker stdout: %s", traceback.format_exc())

	def _on_ipc_receive(self, obj: dict) -> None:
		# Called from IPC accept loop when worker sends messages
		type_ = obj.get("type")
		payload = obj.get("payload", {}) or {}
		try:
			out_obj = None
			if type_ == "HEARTBEAT":
				out_obj = {"event": "heartbeat", **payload}
				self._last_heartbeat = time.monotonic()
			elif type_ == "STATUS":
				out_obj = {"event": "status", **payload}
			elif type_ == "WAKE":
				out_obj = {"event": "wake", **payload}
			elif type_ == "ERROR":
				out_obj = {"event": "error", **payload}
			elif type_ == "DIAGNOSTICS":
				out_obj = {"event": "diagnostics", **payload}
			else:
				out_obj = {"event": "ipc", "type": type_, "payload": payload, "ts": time.time()}
			
			if out_obj:
				_emit(out_obj)
				# Only broadcast stream/control events wrapped with WS envelope type
				# Let's map "event" to WS envelope "type"
				ws_msg = {
					"type": out_obj.get("event"),
					"payload": out_obj
				}
				self._ws_server.broadcast(ws_msg)
		except Exception:
			log.exception("Failed handling IPC message")

	def _on_ws_receive(self, msg: dict) -> None:
		# Handle incoming WebSocket commands from Node SDK
		# Forward them to the worker via IPC or stdin
		msg_type = msg.get("type")
		payload = msg.get("payload", {})
		log.debug(f"Received WS message: {msg_type}")
		
		# Handshake response (Phase 8 requirement)
		if msg_type == "handshake":
			resp = {
				"type": "handshake_ack",
				"schemaVersion": 1,
				"protocolVersion": "1.0",
				"manifest": {},
				"capabilities": {}
			}
			self._ws_server.broadcast(resp)
			return

		# Intercept diagnostics_request and validate_profile in supervisor as shim
		if msg_type == "diagnostics_request":
			req_type = payload.get("type")
			if req_type == "effective_config":
				from runtime.config.profile_loader import load_profile
				
				active_profile = {}
				if getattr(self, "profile_path", None):
					active_profile = load_profile(self.profile_path, debug_overlay=getattr(self, "debug", False))
					
				def flatten(d: dict, prefix: str = "") -> dict:
					res = {}
					for k, v in d.items():
						if isinstance(v, dict):
							res.update(flatten(v, prefix + k + "."))
						elif not isinstance(v, list):
							res[prefix + k] = v
					return res
					
				result = {"values": flatten(active_profile)}
				
				resp = {
					"type": "diagnostics_response",
					"correlationId": msg.get("correlationId"),
					"payload": {
						"correlationId": msg.get("correlationId"),
						"result": result
					}
				}
				self._ws_server.broadcast(resp)
			elif req_type == "metrics":
				from runtime.telemetry.metrics import MetricsCollector
				mc = MetricsCollector()
				result = mc.get_all_metrics()
				resp = {
					"type": "diagnostics_response",
					"correlationId": msg.get("correlationId"),
					"payload": {
						"correlationId": msg.get("correlationId"),
						"result": result
					}
				}
				self._ws_server.broadcast(resp)
			elif req_type == "health":
				resp = {
					"type": "diagnostics_response",
					"correlationId": msg.get("correlationId"),
					"payload": {
						"correlationId": msg.get("correlationId"),
						"result": {"status": "healthy"}
					}
				}
				self._ws_server.broadcast(resp)
			return
		
		if msg_type == "validate_profile":
			path = payload.get("path")
			from runtime.config.profile_validator import validate_profile
			res = validate_profile(path)
			resp = {
				"type": "validate_profile_response",
				"correlationId": msg.get("correlationId"),
				"payload": {
					"correlationId": msg.get("correlationId"),
					"result": {"valid": res.valid, "warnings": res.warnings, "errors": res.errors}
				}
			}
			self._ws_server.broadcast(resp)
			return

		if msg_type == "crash_worker":
			if self._worker_proc:
				log.warning("Test command received: crashing worker process")
				self._worker_proc.kill()
			return

		# For start/stop/configure, forward to worker
		if msg_type in ["start", "stop", "configure"]:
			if self._ipc_server:
				self._ipc_server.send({"type": msg_type.upper(), "payload": payload})
			elif self._worker_proc and self._worker_proc.stdin:
				# fallback to stdin if IPC not ready
				try:
					cmd = payload.get("command", msg_type)
					self._worker_proc.stdin.write(f"{cmd}\n")
					self._worker_proc.stdin.flush()
				except:
					pass
		elif msg_type == "shutdown":
			log.info("Shutdown requested via WS")
			self.stop()

	def _reader_loop_stderr(self) -> None:
		assert self._worker_proc and self._worker_proc.stderr
		try:
			for raw in self._worker_proc.stderr:
				# Forward worker stderr to supervisor stderr (human logs)
				sys.stderr.write(raw)
				sys.stderr.flush()
		except Exception:
			log.exception("Error reading worker stderr: %s", traceback.format_exc())

	def _monitor_loop(self) -> None:
		while not self._stop_event.is_set():
			try:
				# 1) Check worker liveness
				if self._worker_proc is None:
					time.sleep(0.5)
					continue

				ret = self._worker_proc.poll()
				if ret is not None:
					_emit({"event": "worker_exited", "code": ret, "ts": time.time()})
					log.warning("Worker exited with code=%s", ret)
					# Escalating recovery: record failure and act according to policy
					self._recovery_policy.record_failure()
					step = self._recovery_policy.current_step()
					backoff_ms = self._recovery_policy.next_backoff_ms()
					_emit({"event": "recovery_step", "step": step, "backoff_ms": backoff_ms, "ts": time.time()})
					if step == "fatal":
						# Ensure missing method doesn't crash the monitor loop in older runtimes.
						if hasattr(self, "_action_fatal"):
							self._action_fatal(ret)
						else:
							log.error("Recovery escalated to FATAL but _action_fatal is missing; shutting down supervisor")
							# best-effort shutdown fallback
							try:
								self.stop()
							except Exception:
								log.exception("Failed during fallback supervisor stop")
						return
					# wait backoff
					log.info("Waiting %.0fms before recovery action %s", backoff_ms, step)
					time.sleep(backoff_ms / 1000.0)
					# Map higher-level steps to actions
					log.debug("RestartPolicy action=%s", step)
					if step == "worker_restart":
						self._action_worker_restart(ret)
					elif step == "provider_reload":
						self._action_provider_reload(ret)
					elif step == "runtime_restart":
						self._action_runtime_restart(ret)
					elif step == "degraded_mode":
						self._action_degraded_mode(ret)
					# small sleep to avoid tight restart loop
					time.sleep(0.5)
					continue

				# 2) Heartbeat staleness
				age = time.monotonic() - self._last_heartbeat
				if age > self.heartbeat_timeout_s:
					log.warning("Heartbeat stale (%.1fs > %.1fs) — restarting worker", age, self.heartbeat_timeout_s)
					_emit({"event": "worker_heartbeat_stale", "age_s": round(age, 1), "ts": time.time()})
					self._restart_worker(reason="heartbeat_stale")

			except Exception:
				log.exception("Supervisor monitor loop error: %s", traceback.format_exc())
			time.sleep(1.0)

	def _handle_worker_exit(self, code: int) -> None:
		# If the worker exited unexpectedly, attempt restart using policy
		self._worker_proc = None
		if not self.restart_policy.can_restart():
			_emit({"event": "worker_restart_throttled", "ts": time.time()})
			log.error("Restart throttled by policy — giving up")
			return
		self.restart_policy.record_restart()
		self._spawn_worker()

	def _action_worker_restart(self, code: int) -> None:
		log.info("Recovery action: worker_restart (code=%s)", code)
		self._handle_worker_exit(code)

	def _action_provider_reload(self, code: int) -> None:
		log.info("Recovery action: provider_reload (code=%s) — attempting provider reload via IPC then restart", code)
		_emit({"event": "provider_reload_requested", "ts": time.time()})
		# Attempt in-band provider reload request via IPC; if unavailable, restart worker
		try:
			if self._ipc_server and self._ipc_server.send({"type": "PROVIDER_RELOAD", "payload": {"ts": time.time()}}):
				_emit({"event": "provider_reload_ipc_sent", "ts": time.time()})
		except Exception:
			log.exception("Failed sending provider_reload via IPC")
		# Ensure worker restarted to pick up provider changes
		self._handle_worker_exit(code)

	def _action_runtime_restart(self, code: int) -> None:
		log.info("Recovery action: runtime_restart (code=%s) — restarting runtime", code)
		_emit({"event": "runtime_restart", "ts": time.time()})
		# Reset recovery state and restart worker (runtime)
		try:
			self._recovery_policy.reset()
		except Exception:
			pass
		# Attempt graceful restart
		try:
			if self._worker_proc:
				self._worker_proc.terminate()
				try:
					self._worker_proc.wait(timeout=5.0)
				except subprocess.TimeoutExpired:
					self._worker_proc.kill()
		except Exception:
			log.exception("Error during runtime restart termination")
		# Spawn a fresh worker and reset restart counters
		self.restart_policy = RestartPolicy()
		self._spawn_worker()

	def _action_degraded_mode(self, code: int) -> None:
		_emit({"event": "runtime_degraded", "ts": time.time()})
		log.warning("Entering degraded mode — stopping automatic restarts")
		self._degraded = True
		# Stop monitoring / automatic restart
		self._stop_event.set()

	def _action_fatal(self, code: int) -> None:
		_emit({"event": "worker_fatal", "code": code, "ts": time.time()})
		log.error("Recovery escalated to FATAL — shutting down supervisor")
		self._degraded = True
		# Stop everything and exit monitor
		self.stop()

	def _restart_worker(self, reason: str = "manual") -> None:
		proc = self._worker_proc
		if proc is None:
			return
		try:
			_emit({"event": "worker_terminating", "reason": reason, "pid": proc.pid, "ts": time.time()})
			proc.terminate()
			try:
				proc.wait(timeout=5.0)
			except subprocess.TimeoutExpired:
				log.warning("Worker did not exit in time; killing")
				proc.kill()
			# Mark a restart attempt
			self.restart_policy.record_restart()
		except Exception:
			log.exception("Failed to terminate worker cleanly")
		finally:
			# Ensure fresh spawn
			self._spawn_worker()

	def stop(self) -> None:
		self._stop_event.set()
		if self._worker_proc:
			try:
				self._worker_proc.terminate()
			except Exception:
				pass
		try:
			if hasattr(self, "_ws_server"):
				self._ws_server.stop()
		except Exception:
			pass
		_emit({"event": "supervisor_stopped", "ts": time.time()})


def main(argv: list[str] | None = None) -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--profile", type=str, help="Path to profile JSON")
	parser.add_argument("--max-restarts", type=int, default=5)
	parser.add_argument("--restart-window", type=int, default=60)
	parser.add_argument("--heartbeat-timeout", type=float, default=12.0)
	parser.add_argument("--ws-port", type=int, default=5050)
	parser.add_argument("--debug", action="store_true")
	# Accept unknown args when invoked nested; allow caller to pass a trimmed argv list.
	args, _ = parser.parse_known_args(argv)

	worker_cmd = [sys.executable, "-m", "runtime.worker.worker_process"]
	if args.profile:
		worker_cmd += ["--profile", args.profile]
	if args.debug:
		worker_cmd += ["--debug"]
		from utils.logger import enable_trace
		enable_trace()

	policy = RestartPolicy(max_restarts=args.max_restarts, window_s=args.restart_window)
	sup = Supervisor(worker_cmd=worker_cmd, heartbeat_timeout_s=args.heartbeat_timeout, restart_policy=policy, ws_port=args.ws_port, profile_path=args.profile)

	try:
		sup.start()
	except KeyboardInterrupt:
		sup.stop()


if __name__ == "__main__":
	main()
