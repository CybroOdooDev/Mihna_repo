"""Code execution sandboxes.

Production: a self-hosted Judge0 (isolated, no network, CPU/memory/time limits,
never on the Odoo server – FRD §8). ``dev_local`` runs code in a subprocess on
the Odoo host and is ONLY for development; it refuses to run unless explicitly
enabled on the provider record.
"""
import base64
import os
import resource
import shutil
import subprocess
import tempfile
import time

import requests

LANGUAGES = {
    "python": {"label": "Python 3", "judge0_id": 71},
    "c": {"label": "C (GCC)", "judge0_id": 50},
    "cpp": {"label": "C++ (G++ 17)", "judge0_id": 54},
    "javascript": {"label": "JavaScript (Node.js)", "judge0_id": 63},
}

# Default per-test time limits in seconds (Python/JS are slower than C/C++).
DEFAULT_TIME_LIMITS = {"python": 2.0, "javascript": 2.0, "c": 1.0, "cpp": 1.0}


class SandboxError(Exception):
    pass


def normalize_output(text):
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").strip().split("\n")]
    return "\n".join(lines)


def _result(test, stdout, stderr, status, time_ms):
    passed = status == "ok" and normalize_output(stdout) == normalize_output(test["stdout"])
    return {"passed": passed, "status": status if status != "ok" or passed else "wrong_answer",
            "stdout": (stdout or "")[:2000], "stderr": (stderr or "")[:2000], "time_ms": time_ms,
            "hidden": test.get("hidden", True)}


class MockSandbox:
    """Pretends every non-empty program passes; used when no sandbox is configured."""

    def __init__(self, config):
        self.config = config

    def run(self, language, code, tests):
        ok = bool((code or "").strip())
        return [{"passed": ok, "status": "ok" if ok else "compile_error", "stdout": t["stdout"] if ok else "",
                 "stderr": "" if ok else "empty program", "time_ms": 1, "hidden": t.get("hidden", True)}
                for t in tests]


class Judge0Sandbox:
    def __init__(self, config):
        self.config = config
        self.base = (config.get("base_url") or "http://localhost:2358").rstrip("/")
        self.language_ids = {**{k: v["judge0_id"] for k, v in LANGUAGES.items()},
                             **(config.get("language_ids") or {})}
        self.time_limits = {**DEFAULT_TIME_LIMITS, **(config.get("time_limits") or {})}

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.config.get("api_key"):
            headers["X-Auth-Token"] = self.config["api_key"]
        return headers

    def run(self, language, code, tests):
        if language not in self.language_ids:
            raise SandboxError(f"Language {language} not supported")
        b64 = lambda s: base64.b64encode((s or "").encode()).decode()
        submissions = [{
            "language_id": self.language_ids[language], "source_code": b64(code), "stdin": b64(t["stdin"]),
            "expected_output": b64(t["stdout"]), "cpu_time_limit": self.time_limits.get(language, 2.0),
            "memory_limit": 128000, "enable_network": False,
        } for t in tests]
        try:
            resp = requests.post(f"{self.base}/submissions/batch?base64_encoded=true",
                                 json={"submissions": submissions}, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            tokens = [s["token"] for s in resp.json()]
            deadline = time.time() + 60
            while True:
                poll = requests.get(f"{self.base}/submissions/batch", headers=self._headers(), timeout=30, params={
                    "tokens": ",".join(tokens), "base64_encoded": "true",
                    "fields": "token,stdout,stderr,compile_output,status,time"})
                poll.raise_for_status()
                subs = poll.json()["submissions"]
                if all(s["status"]["id"] not in (1, 2) for s in subs) or time.time() > deadline:
                    break
                time.sleep(0.5)
        except requests.RequestException as exc:
            raise SandboxError(f"Judge0 unreachable: {exc}") from exc
        dec = lambda s: base64.b64decode(s).decode(errors="replace") if s else ""
        results = []
        for test, sub in zip(tests, subs):
            sid = sub["status"]["id"]
            status = {3: "ok", 4: "ok", 5: "timeout", 6: "compile_error"}.get(sid, "runtime_error")
            stderr = dec(sub.get("compile_output")) or dec(sub.get("stderr"))
            results.append(_result(test, dec(sub.get("stdout")), stderr, status,
                                   int(float(sub.get("time") or 0) * 1000)))
        return results


class DevLocalSandbox:
    """DEVELOPMENT ONLY: compiles/runs code in a subprocess with rlimits and no stdin network guard."""

    COMMANDS = {
        "python": (None, ["python3", "-I", "main.py"], "main.py"),
        "c": (["gcc", "-O2", "-std=c11", "-o", "main", "main.c", "-lm"], ["./main"], "main.c"),
        "cpp": (["g++", "-O2", "-std=c++17", "-o", "main", "main.cpp"], ["./main"], "main.cpp"),
        "javascript": (None, ["node", "--max-old-space-size=256", "--v8-pool-size=1", "main.js"], "main.js"),
    }

    def __init__(self, config):
        if not config.get("allow_dev_local"):
            raise SandboxError("The local development sandbox is disabled. Configure Judge0 for production.")
        self.config = config
        self.time_limits = {**DEFAULT_TIME_LIMITS, **(config.get("time_limits") or {})}

    @classmethod
    def available(cls, language):
        compile_cmd, run_cmd, _ = cls.COMMANDS[language]
        return shutil.which((compile_cmd or run_cmd)[0]) is not None

    @staticmethod
    def _limits(language):
        """rlimits for the child. No RLIMIT_NPROC: it counts every process of the OS user (a desktop
        session alone exceeds any small cap), so it breaks multi-threaded runtimes like Node. Node's
        V8 reserves a large virtual address space, so its memory is capped with --max-old-space-size
        instead of RLIMIT_AS. Real isolation (processes, network) needs Judge0."""
        if language != "javascript":
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def run(self, language, code, tests):
        compile_cmd, run_cmd, filename = self.COMMANDS[language]
        if not self.available(language):
            raise SandboxError(f"No local toolchain for {language}")
        with tempfile.TemporaryDirectory(prefix="linda_sbx_") as tmp:
            with open(os.path.join(tmp, filename), "w") as fh:
                fh.write(code or "")
            if compile_cmd:
                comp = subprocess.run(compile_cmd, cwd=tmp, capture_output=True, text=True, timeout=30)
                if comp.returncode != 0:
                    return [_result(t, "", comp.stderr, "compile_error", 0) for t in tests]
            results = []
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
            for test in tests:
                started = time.time()
                try:
                    proc = subprocess.run(run_cmd, cwd=tmp, input=test["stdin"], capture_output=True, text=True,
                                          timeout=self.time_limits.get(language, 2.0), env=env,
                                          preexec_fn=lambda: self._limits(language))
                    status = "ok" if proc.returncode == 0 else "runtime_error"
                    results.append(_result(test, proc.stdout, proc.stderr, status,
                                           int((time.time() - started) * 1000)))
                except subprocess.TimeoutExpired:
                    results.append(_result(test, "", "Time limit exceeded", "timeout",
                                           int((time.time() - started) * 1000)))
            return results


SANDBOXES = {"judge0": Judge0Sandbox, "dev_local": DevLocalSandbox, "mock": MockSandbox}


def get_sandbox(config):
    kind = config.get("kind") or "mock"
    if kind not in SANDBOXES:
        raise SandboxError(f"Unknown sandbox kind '{kind}'")
    return SANDBOXES[kind](config)
