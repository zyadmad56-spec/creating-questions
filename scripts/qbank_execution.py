"""Local execution of audited educational code variants, with honest limits.

The runner executes only code that passed the static educational screen: no
network, no process launching, no filesystem access, no dynamic execution.
The screen, the isolated interpreter, the temporary working directory, and the
timeout are the enforcement for this audited-educational-code contract. Hostile
or unaudited snippets are refused (status "unavailable"), never sandboxed.
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import qbank_schema
from qbank_schema import SchemaError

FORBIDDEN_MODULES = {
    "subprocess", "socket", "ssl", "urllib", "http", "ftplib", "telnetlib",
    "smtplib", "xmlrpc", "ctypes", "multiprocessing", "asyncio", "httpx",
    "requests", "webbrowser", "shutil", "pathlib", "io", "os", "sys", "glob",
    "tempfile", "pickle", "shelve", "importlib",
}
FORBIDDEN_ATTRIBUTES = {"system", "popen", "spawn", "spawnl", "spawnv", "fork",
                        "exec", "execv", "execve", "remove", "unlink", "mkdir",
                        "rmdir", "rename", "makedirs", "write_text", "read_text"}
FORBIDDEN_CALLS = {"open", "eval", "exec", "compile", "__import__"}


class RuntimeUnavailableError(Exception):
    """Raised when no local runtime can execute the requested language."""


def screen_code(code_text, language="python"):
    """Static educational screen. Returns (allowed, violations).

    Syntax errors are reported for the caller to classify (a deliberately
    broken exercise is not executed, but it is also not a screening failure).
    """
    if language != "python":
        return True, []
    try:
        tree = ast.parse(code_text)
    except SyntaxError as error:
        return False, [f"does not parse: line {error.lineno}: {error.msg}"]
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    violations.append(f"import of {alias.name} is outside the "
                                      "educational contract")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_MODULES:
                violations.append(f"import from {node.module} is outside the "
                                  "educational contract")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in FORBIDDEN_CALLS:
            violations.append(f"call to {node.func.id}() is outside the educational contract")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            violations.append(f"attribute .{node.attr} is outside the educational contract")
    return not violations, violations


def discover_runtime(language):
    """Locate a local runtime and record its identity; raises when absent."""
    if language == "python":
        version = sys.version_info
        return {"language": "python",
                "version": f"{version.major}.{version.minor}.{version.micro}",
                "executable": sys.executable,
                "enforcement": ("static educational screen + isolated interpreter "
                                "(-I) + temp working directory + timeout")}
    for command, flag, name in (("gcc", "-std=c11", "gcc"), ("clang", "-std=c11", "clang")):
        path = shutil.which(command)
        if path:
            result = subprocess.run([command, "--version"], capture_output=True,
                                    text=True, timeout=30)
            return {"language": "c", "version": result.stdout.splitlines()[0],
                    "executable": path, "standard": flag,
                    "enforcement": "compile to temp binary; screen not applicable"}
    raise RuntimeUnavailableError(f"No local {language} runtime is available")


def package_versions(names):
    versions = {}
    for name in names:
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "unknown")
        except ImportError:
            continue
    return versions


def run_c(code_text, language, runtime, timeout_s=10):
    """Compile with the declared standard and warnings, then run the binary."""
    scratch = Path(tempfile.mkdtemp(prefix="qbank_exec_"))
    try:
        suffix = ".c" if language == "c" else ".cpp"
        source = scratch / f"variant{suffix}"
        source.write_text(code_text, encoding="utf-8")
        binary_name = "variant_program.exe" if os.name == "nt" else "variant_program"
        binary = scratch / binary_name
        standard = runtime.get("standard", "-std=c11")
        compile_command = [runtime["executable"], standard, "-Wall", "-Wextra",
                           str(source), "-o", str(binary)]
        compiled = subprocess.run(compile_command, capture_output=True, text=True,
                                  timeout=120, cwd=str(scratch))
        if compiled.returncode != 0 or not binary.exists():
            return {"exit_status": compiled.returncode, "stdout": "",
                    "stderr": compiled.stderr, "timeout": False,
                    "compile_failed": True}
        environment = {"PATH": os.environ.get("PATH", "")}
        observed = subprocess.run([str(binary)], capture_output=True, text=True,
                                  timeout=timeout_s, cwd=str(scratch), env=environment,
                                  input="")
        return {"exit_status": observed.returncode, "stdout": observed.stdout,
                "stderr": observed.stderr, "timeout": False}
    except subprocess.TimeoutExpired:
        return {"exit_status": None, "stdout": "", "stderr": f"timeout after {timeout_s}s",
                "timeout": True}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def run_python(code_text, stdin_text="", timeout_s=10):
    """Run screened Python in a fresh temp directory with a bounded timeout."""
    scratch = Path(tempfile.mkdtemp(prefix="qbank_exec_"))
    try:
        script = scratch / "variant.py"
        script.write_text(code_text, encoding="utf-8")
        environment = {"PATH": os.environ.get("PATH", ""),
                       "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                       "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", ""),
                       "PYTHONIOENCODING": "utf-8"}
        completed = subprocess.run(
            [sys.executable, "-I", str(script)], input=stdin_text,
            capture_output=True, text=True, timeout=timeout_s, cwd=str(scratch),
            env=environment)
        return {"exit_status": completed.returncode, "stdout": completed.stdout,
                "stderr": completed.stderr, "timeout": False}
    except subprocess.TimeoutExpired as expired:
        return {"exit_status": None, "stdout": (expired.stdout or b"").decode("utf-8",
                                                                            "replace")
                if isinstance(expired.stdout, bytes) else (expired.stdout or ""),
                "stderr": "timeout after {}s".format(timeout_s), "timeout": True}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def last_exception_name(stderr):
    for line in reversed(stderr.strip().splitlines()):
        candidate = line.split(":")[0].strip()
        if candidate and " " not in candidate and candidate[0].isupper():
            return candidate
    return None


def case_matches(case, observation):
    """Compare only what the prompt asks about; expected exceptions are answers."""
    if "expected_exception" in case:
        return observation["exit_status"] != 0 and \
            last_exception_name(observation["stderr"]) == case["expected_exception"]
    if "expected_stdout" in case:
        return observation["stdout"] == case["expected_stdout"]
    if "expected_exit_status" in case:
        return observation["exit_status"] == case["expected_exit_status"]
    return False


def run_question(model, question, runtime=None, timeout_s=10, stdin_text=""):
    """Execute the exact effective variant of a question and record the result.

    Returns an execution record. The record states what ran and what was
    observed; execution_verified becomes true only after case comparison.
    """
    question_id = question["id"]
    block_id = question.get("code_block_id")
    record = {"question_id": question_id, "program_hash": None,
              "runtime": runtime or {"language": "unknown", "version": None},
              "status": "not_run", "execution_verified": False, "reason": None,
              "cases": []}
    if question.get("variant"):
        code_text, _ = qbank_schema.effective_program(
            model, block_id, question["variant"])
    else:
        code_text, _ = qbank_schema.effective_program(model, block_id)
    record["program_hash"] = qbank_schema.code_hash(code_text)
    language = model["code_blocks"][block_id]["language"]
    record["runtime"]["language"] = language
    if language != "python":
        try:
            runtime = runtime or discover_runtime(language)
        except RuntimeUnavailableError as error:
            record.update({"status": "unavailable", "reason": str(error)})
            return record
        record["runtime"] = runtime
        observation = run_c(code_text, language, runtime, timeout_s)
        if observation.get("compile_failed"):
            record.update({"status": "unavailable",
                           "reason": "The variant did not compile: "
                                     + observation["stderr"][-200:]})
            return record
        declared_cases = question.get("execution", {}).get("cases") or []
        if not declared_cases:
            record["cases"] = [{"observation": observation}]
            record["status"] = "passed" if observation["exit_status"] == 0 else "failed"
            record["execution_verified"] = observation["exit_status"] == 0
            return record
        matched_all = True
        for case in declared_cases:
            matched = case_matches(case, observation)
            matched_all = matched_all and matched
            record["cases"].append({**case, "observed": observation, "match": matched})
        record.update({"status": "passed" if matched_all else "failed",
                       "execution_verified": matched_all,
                       "reason": None if matched_all else "At least one case did not match"})
        return record
    allowed, violations = screen_code(code_text)
    if not allowed:
        record.update({"status": "unavailable",
                       "reason": "Educational screen refused this variant: "
                                 + "; ".join(violations)})
        return record
    try:
        observation = run_python(code_text, stdin_text=stdin_text, timeout_s=timeout_s)
    except RuntimeUnavailableError as error:
        record.update({"status": "unavailable", "reason": str(error)})
        return record
    declared_cases = question.get("execution", {}).get("cases") or []
    if not declared_cases:
        record["cases"] = [{"observation": observation}]
        record["status"] = "passed" if observation["exit_status"] == 0 else "failed"
        record["execution_verified"] = observation["exit_status"] == 0
        record["reason"] = None if observation["exit_status"] == 0 else \
            f"exit status {observation['exit_status']}: {observation['stderr'][-200:]}"
        return record
    matched_all = True
    for case in declared_cases:
        matched = case_matches(case, observation)
        matched_all = matched_all and matched
        record["cases"].append({**case, "observed": {"stdout": observation["stdout"],
                                                     "stderr": observation["stderr"],
                                                     "exit_status": observation["exit_status"]},
                                "match": matched})
    record.update({"status": "passed" if matched_all else "failed",
                   "execution_verified": matched_all,
                   "reason": None if matched_all else "At least one case did not match"})
    return record


def stale_execution_records(model):
    """Questions whose recorded passed execution no longer matches their code."""
    stale = []
    for question in model["questions"].values():
        record = question.get("execution") or {}
        if record.get("status") != "passed" or not question.get("code_block_id"):
            continue
        code_text, _ = qbank_schema.effective_program(
            model, question["code_block_id"], question.get("variant"))
        if record.get("program_hash") and record["program_hash"] != qbank_schema.code_hash(code_text):
            stale.append(question["id"])
    return stale


def write_record(record, path):
    Path(path).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
