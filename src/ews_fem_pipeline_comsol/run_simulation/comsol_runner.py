"""COMSOL batch execution, progress reporting, and postprocess orchestration.

The runner receives generated JSON case inputs from ``pipeline.py``. It can
build a Java-generated MPH, solve the configured study, run auxiliary Java
verification/postprocess classes, and prune duplicate heavyweight artefacts.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from ews_fem_pipeline_comsol.paths import ensure_output_tree
from ews_fem_pipeline_comsol.reporting import generate_case_report
from ews_fem_pipeline_comsol.settings import Settings

logger = logging.getLogger(__name__)


def _normalize_timeout_seconds(value: int | None, minimum_if_enabled: int) -> int | None:
    if value is None:
        return None
    if int(value) <= 0:
        return None
    return max(minimum_if_enabled, int(value))


class COMSOLRunner:
    """Run COMSOL build, solve, verification, and postprocess steps for cases."""

    @staticmethod
    def _console(message: str) -> None:
        print(f"[COMSOL pipeline] {message}", flush=True)

    @staticmethod
    def _display_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            return path.name

    @staticmethod
    def _case_name_from_input(input_file: Path) -> str:
        name = input_file.stem
        suffix = "_comsol_input"
        return name[: -len(suffix)] if name.endswith(suffix) else name

    @staticmethod
    def _aux_phase_label(java_file: Path) -> str:
        stem = java_file.stem.lower()
        if "reuse_patch" in stem:
            return "reuse patch"
        if "verify_build" in stem:
            return "verify build"
        if "verify_solve" in stem:
            return "verify solve"
        if "postprocess" in stem:
            return "postprocess"
        return "auxiliary step"

    @staticmethod
    def _finish_progress_line() -> None:
        return

    @staticmethod
    def _console_progress(message: str) -> None:
        print(f"[COMSOL pipeline] {message}", flush=True)

    @staticmethod
    def _progress_message_from_line(line: str) -> tuple[str, bool, int | None] | None:
        stripped = line.strip()
        if not stripped:
            return None
        if "Current Progress:" in stripped:
            match = re.search(r"Current Progress:\s*(\d+)\s*%\s*-\s*(.*)", stripped)
            if match:
                pct = max(0, min(100, int(match.group(1))))
                description = match.group(2).strip()
                if len(description) > 48:
                    description = description[:45].rstrip() + "..."
                width = 20
                filled = round(width * pct / 100)
                bar = "#" * filled + "." * (width - filled)
                return f"[{bar}] {pct:3d}% - {description}".rstrip(), True, pct
            return stripped, True, None
        if stripped.startswith("COMSOL_POSTPROCESS_STATUS"):
            return stripped.replace("COMSOL_POSTPROCESS_STATUS", "postprocess"), False, None
        if stripped.startswith("COMSOL_IMAGE_EXPORT"):
            return stripped, False, None
        if stripped.startswith("TUMOR_PREVIEW_COMPONENT_READY"):
            return stripped, False, None
        if stripped.startswith("Minimum element quality:"):
            return stripped, False, None
        if stripped.startswith("Number of degrees of freedom solved for:"):
            return stripped, False, None
        if stripped.startswith("Solution time:") or stripped.startswith("Run time:"):
            return stripped, False, None
        if stripped.startswith("Error ") or "Error running java class" in stripped:
            return stripped, False, None
        if "Failed to generate mesh" in stripped or "Intersecting face elements" in stripped:
            return stripped, False, None
        return None

    @classmethod
    def _tail_progress_log(
        cls,
        *,
        log_path: Path | None,
        position: int,
        last_message: str | None,
        last_progress_pct: int | None,
        label: str,
    ) -> tuple[int, str | None, int | None]:
        if log_path is None or not log_path.exists():
            return position, last_message, last_progress_pct
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(position)
                chunk = handle.read()
                position = handle.tell()
        except OSError:
            return position, last_message, last_progress_pct
        for line in chunk.splitlines():
            parsed = cls._progress_message_from_line(line)
            if parsed is None:
                continue
            message, inline, pct = parsed
            if message and message != last_message:
                if inline:
                    if pct is not None:
                        if last_progress_pct is not None and pct < last_progress_pct:
                            continue
                        if (
                            last_progress_pct is not None
                            and pct < 100
                            and pct - last_progress_pct < 10
                        ):
                            continue
                        last_progress_pct = pct
                    cls._console_progress(f"{label}: {message}")
                else:
                    cls._console(f"{label}: {message}")
                last_message = message
        return position, last_message, last_progress_pct

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _safe_rmtree(path: Path) -> None:
        try:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass

    def _prune_output_artefacts(
        self,
        *,
        case_name: str,
        output_paths: dict[str, Path],
        prepare_artefacts: dict[str, str],
        input_file: Path,
        settings: Settings,
    ) -> None:
        if not settings.comsol.compact_output:
            return

        root_dir = output_paths["root"]
        build_dir = output_paths["build"]
        solve_dir = output_paths["solve"]
        logs_dir = output_paths["logs"]

        removable_prepare_keys = (
            "source_settings_expanded_toml",
            "mesh_nodes_csv",
            "mesh_data_npz",
            "mesh_summary_json",
            "lobules_json",
            "comsol_build_plan_json",
            "prepare_status_json",
            "comsol_builder_java",
            "comsol_builder_readme",
        )
        for key in removable_prepare_keys:
            value = prepare_artefacts.get(key)
            if not value:
                continue
            path = Path(value)
            self._safe_unlink(path)
            if path.suffix == ".java":
                self._safe_unlink(path.with_suffix(".class"))

        self._safe_unlink(build_dir / f"{case_name}_comsol_input.json")
        self._safe_unlink(root_dir / f"{case_name}_all_settings.toml")

        for pattern in (
            "*.comsol_command.txt",
            "*debug*.log",
            "*javac*.log",
            "*compile*.log",
        ):
            for path in logs_dir.glob(pattern):
                if "javac" in path.name.lower():
                    continue
                self._safe_unlink(path)

        for pattern in (
            "*.status",
            "*.recovery",
            "*.lock",
            "*postprocess_output*.mph",
        ):
            for path in solve_dir.glob(pattern):
                self._safe_unlink(path)
            for path in build_dir.glob(pattern):
                self._safe_unlink(path)

        self._safe_rmtree(build_dir / "comsol_configuration")

    @staticmethod
    def _detect_license_error(text: str) -> bool:
        lower = text.lower()
        return "license error" in lower or "cannot connect to license server" in lower

    @staticmethod
    def _write_metrics_from_aux_stdout(aux_stdout: str, metrics_target: Path | None) -> bool:
        if not metrics_target:
            return False
        begin_marker = "COMSOL_METRICS_JSON_BEGIN"
        end_marker = "COMSOL_METRICS_JSON_END"
        start_idx = aux_stdout.find(begin_marker)
        end_idx = aux_stdout.find(end_marker)
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return False
        metrics_json = aux_stdout[start_idx + len(begin_marker):end_idx].strip()
        metrics_target.parent.mkdir(parents=True, exist_ok=True)
        metrics_target.write_text(metrics_json + "\n", encoding="utf-8")
        return True

    @staticmethod
    def _java_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @classmethod
    def _reuse_parameter_overrides_from_builder(cls, builder_java: Path | None) -> list[tuple[str, str]]:
        """Extract non-geometric TOML-driven COMSOL parameters from generated Java."""
        if not builder_java or not builder_java.exists():
            return []
        text = builder_java.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r'model\.param\(\)\.set\("([^"]+)",\s*"([^"]+)"\);', text)
        overrides: list[tuple[str, str]] = []
        for name, value in matches:
            material_like = (
                name.endswith("_density")
                or name.endswith("_bulk_modulus")
                or name.endswith("_c10")
                or name.endswith("_c01")
                or name.endswith("_E")
                or name.endswith("_nu")
            )
            dynamic_like = (
                name in {
                    "g_acc",
                    "pulse_acc_amp",
                    "mass_damping_alpha",
                    "stiffness_damping_beta",
                    "t_output_step",
                    "t_pulse_output_step",
                    "t_gravity_end",
                    "t_dynamic_start",
                    "t_dynamic_end",
                    "t_jump_hold",
                    "t_jump_start",
                    "t_jump_duration",
                    "t_pulse_duration",
                    "t_excitation_duration",
                    "jump_v0",
                    "jump_amp",
                }
            )
            tumor_like = name.startswith("tumor_")
            if material_like or dynamic_like or tumor_like:
                overrides.append((name, value))
        return overrides

    def _write_reuse_mph_patch_java(
        self,
        *,
        case_name: str,
        java_file: Path,
        source_mph: Path,
        patched_mph: Path,
        overrides: list[tuple[str, str]],
    ) -> None:
        lines = [
            "import com.comsol.model.*;",
            "import com.comsol.model.util.*;",
            "",
            f"public class {java_file.stem} {{",
            "  public static Model run() throws Exception {",
            '    System.out.println("COMSOL_REUSE_PATCH_STATUS init_start");',
            "    ModelUtil.initStandalone(true);",
            '    System.out.println("COMSOL_REUSE_PATCH_STATUS load_start");',
            f'    Model model = ModelUtil.load("model", "{self._java_string(str(source_mph.resolve()))}");',
            '    System.out.println("COMSOL_REUSE_PATCH_STATUS parameters_start");',
        ]
        for name, value in overrides:
            lines.append(
                f'    model.param().set("{self._java_string(name)}", "{self._java_string(value)}");'
            )
        lines.extend(
            [
                f'    System.out.println("COMSOL_REUSE_PATCH_STATUS parameters_done count={len(overrides)}");',
                '    System.out.println("COMSOL_REUSE_PATCH_STATUS save_start");',
                f'    model.save("{self._java_string(str(patched_mph.resolve()))}");',
                '    System.out.println("COMSOL_REUSE_PATCH_STATUS done");',
                "    return model;",
                "  }",
                "",
                "  public static void main(String[] args) throws Exception {",
                "    run();",
                "    ModelUtil.disconnect();",
                "  }",
                "}",
                "",
            ]
        )
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("\n".join(lines), encoding="utf-8")

    def _prepare_reused_mph_with_parameter_overrides(
        self,
        *,
        case_name: str,
        case_dir: Path,
        build_dir: Path,
        logs_dir: Path,
        configuration_dir: Path,
        batch_executable: str,
        source_mph: Path,
        builder_java: Path | None,
        settings: Settings,
    ) -> tuple[Path | None, str]:
        """Copy a built MPH conceptually by loading it, applying TOML params, and saving a patched MPH."""
        overrides = self._reuse_parameter_overrides_from_builder(builder_java)
        if not overrides:
            return None, "No TOML parameter overrides could be extracted from generated builder Java."
        patch_java = build_dir / f"{case_name}_comsol_reuse_patch.java"
        patched_mph = build_dir / f"{case_name}_reuse_parameter_patched.mph"
        self._safe_unlink(patched_mph)
        self._write_reuse_mph_patch_java(
            case_name=case_name,
            java_file=patch_java,
            source_mph=source_mph,
            patched_mph=patched_mph,
            overrides=overrides,
        )
        self._console(f"reuse MPH + TOML parameter override ({len(overrides)} params)")
        ok, reason, _ = self._run_aux_java_class(
            case_name=case_name,
            case_dir=case_dir,
            logs_dir=logs_dir,
            configuration_dir=configuration_dir,
            batch_executable=batch_executable,
            java_file=patch_java,
            settings=settings,
        )
        if not ok:
            return None, reason
        if not patched_mph.exists():
            return None, "Reuse MPH patch class ran but did not save patched MPH."
        return patched_mph.resolve(), ""

    def _resolve_configuration_dir(self, settings: Settings, output_dir: Path) -> Path:
        if settings.comsol.configuration_dir:
            candidate = Path(settings.comsol.configuration_dir)
            if not candidate.is_absolute():
                candidate = (output_dir / candidate).resolve()
            else:
                candidate = candidate.resolve()
        elif "COMSOL_CONFIGURATION_DIR" in os.environ:
            candidate = Path(os.environ["COMSOL_CONFIGURATION_DIR"]).resolve()
        else:
            candidate = (output_dir / "comsol_configuration").resolve()
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    @staticmethod
    def _resolve_auxiliary_configuration_dir(base_configuration_dir: Path, java_file: Path) -> Path:
        """Use a fresh COMSOL cache for generated postprocess/verification classes.

        Interrupted COMSOL batch runs can leave stale OSGi/cache files behind. A
        fresh, short auxiliary configuration path prevents those stale files from
        blocking the Java class before its first status print.
        """
        stem = java_file.stem.lower()
        if "postprocess" in stem:
            role = "postprocess"
        elif "reuse_patch" in stem:
            role = "reuse"
        else:
            role = "verify"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        aux_root = base_configuration_dir.parent / "comsol_aux_config"
        candidate = (aux_root / f"{role}_{stamp}_{os.getpid()}").resolve()
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    @staticmethod
    def _resolve_generated_mph_candidate(generated_mph: Path) -> Path | None:
        fallback = generated_mph.with_name(f"{generated_mph.stem}_Model{generated_mph.suffix}")
        candidates = [candidate for candidate in (generated_mph, fallback) if candidate.exists()]
        if not candidates:
            return None
        try:
            return max(candidates, key=lambda candidate: candidate.stat().st_mtime).resolve()
        except OSError:
            return candidates[-1].resolve()

    @classmethod
    def _resolve_fresh_generated_mph_candidate(cls, generated_mph: Path, started_at: float) -> Path | None:
        fallback = generated_mph.with_name(f"{generated_mph.stem}_Model{generated_mph.suffix}")
        candidates = [candidate for candidate in (generated_mph, fallback) if candidate.exists()]
        fresh_candidates: list[Path] = []
        if not candidates:
            return None
        # COMSOL may leave stale generated MPH files behind after a failed
        # rebuild. Only accept files written during this build attempt.
        for candidate in candidates:
            try:
                if candidate.stat().st_mtime >= started_at - 1.0:
                    fresh_candidates.append(candidate)
            except OSError:
                continue
        if not fresh_candidates:
            return None
        try:
            return max(fresh_candidates, key=lambda candidate: candidate.stat().st_mtime).resolve()
        except OSError:
            return None

    def _cleanup_duplicate_mph_outputs(
        self,
        *,
        build_dir: Path,
        generated_mph_target: Path | None,
        preferred_generated_mph: Path | None,
        settings: Settings,
    ) -> None:
        """
        Remove large COMSOL duplicate MPH artefacts after build/solve/postprocess.

        This runs only after COMSOL has completed the relevant step. It never
        touches solve/*_result.mph, metrics, plots, reports, TOMLs, or logs.
        """
        if generated_mph_target is not None:
            fallback = generated_mph_target.with_name(
                f"{generated_mph_target.stem}_Model{generated_mph_target.suffix}"
            )
            preferred = preferred_generated_mph.resolve() if preferred_generated_mph else None
            for candidate in (generated_mph_target, fallback):
                try:
                    candidate_resolved = candidate.resolve()
                except OSError:
                    candidate_resolved = candidate
                if not candidate.exists():
                    continue
                if preferred is not None and candidate_resolved == preferred:
                    continue
                # Keep one openable generated MPH for geometry screenshots, but
                # remove the duplicate created by COMSOL's Java/class fallback.
                if generated_mph_target.exists() and fallback.exists():
                    self._safe_unlink(candidate)

        if not settings.comsol.postprocess_write_auxiliary_mph:
            for pattern in (
                "*postprocess*PostModel.mph",
                "*postprocess*_output.mph",
            ):
                for path in build_dir.glob(pattern):
                    self._safe_unlink(path)

    def check_license(self, settings: Settings, workdir: Path) -> tuple[bool, str]:
        """
        Fast COMSOL license probe.
        Returns (ok, message).
        """
        batch_executable = self._resolve_batch_executable(settings)
        if not batch_executable:
            return False, "COMSOL batch executable not found."

        output_paths = ensure_output_tree(workdir, settings)
        build_dir = output_paths["build"]
        logs_dir = output_paths["logs"]
        configuration_dir = self._resolve_configuration_dir(settings, build_dir)
        log_file = logs_dir / "comsol_license_check.log"
        debug_file = logs_dir / "comsol_license_check_debug.log"

        # Intentionally pass a non-existing input file:
        # - If license is down: COMSOL returns license error (-15 etc.)
        # - If license is up: COMSOL proceeds further and reports file/read issue.
        dummy_input = build_dir / "__license_probe_input__.mph"
        args = [
            str(batch_executable),
            "-configuration",
            str(configuration_dir),
            "-inputfile",
            str(dummy_input),
            "-batchlog",
            str(log_file),
        ]
        code, out, err = self._run_logged_command(args, workdir, debug_file, timeout_s=40)
        text_parts = [out, err]
        if log_file.exists():
            text_parts.append(log_file.read_text(encoding="utf-8", errors="replace"))
        combined = "\n".join(text_parts).lower()

        if self._detect_license_error(combined):
            return False, "License check failed: COMSOL cannot reach a valid license."

        if code == 124:
            return False, "License check timed out (possible environment/VPN/session issue)."

        # No license error found; treat as license reachable.
        return True, "License check passed: no COMSOL license error detected."

    def _resolve_batch_executable(self, settings: Settings) -> str | None:
        if settings.comsol.batch_executable:
            return settings.comsol.batch_executable
        if "COMSOL_BATCH_EXE" in os.environ:
            return os.environ["COMSOL_BATCH_EXE"]

        for candidate in ("comsolbatch", "comsol"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def _resolve_comsol_executable(self, settings: Settings, batch_executable: str | None) -> str | None:
        if settings.comsol.comsol_executable:
            return settings.comsol.comsol_executable
        if "COMSOL_EXE" in os.environ:
            return os.environ["COMSOL_EXE"]
        resolved = shutil.which("comsol")
        if resolved:
            return resolved
        if batch_executable:
            batch_path = Path(batch_executable)
            candidate = batch_path.with_name("comsol.exe")
            if candidate.exists():
                return str(candidate)
        return None

    def _resolve_comsolcompile_executable(self, batch_executable: str | None) -> str | None:
        resolved = shutil.which("comsolcompile")
        if resolved:
            return resolved
        if batch_executable:
            batch_path = Path(batch_executable)
            candidate = batch_path.with_name("comsolcompile.exe")
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _resolve_javac_executable(jdk_root: str | None) -> str | None:
        if not jdk_root:
            return None
        candidate = Path(jdk_root) / "bin" / "javac.exe"
        if candidate.exists():
            return str(candidate)
        return None

    @classmethod
    def _run_logged_command(
        cls,
        proc_args: list[str],
        cwd: Path,
        debug_path: Path,
        timeout_s: int | None = 120,
        *,
        progress_log: Path | None = None,
        progress_label: str | None = None,
        announce: bool = True,
        no_progress_notice_s: float | None = None,
    ) -> tuple[int, str, str]:
        """Run a subprocess, write a debug log, and stream selected COMSOL progress."""
        started = time.time()
        label = progress_label or Path(proc_args[0]).name
        if announce:
            cls._console(f"{label}: start")
        log_position = 0
        last_progress: str | None = None
        last_progress_pct: int | None = None
        last_log_activity = started
        last_no_progress_notice = started
        stdout_path = debug_path.with_suffix(debug_path.suffix + ".stdout.txt")
        stderr_path = debug_path.with_suffix(debug_path.suffix + ".stderr.txt")
        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
                "w", encoding="utf-8", errors="replace"
            ) as stderr_file:
                process = subprocess.Popen(
                    proc_args,
                    cwd=str(cwd),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                deadline = time.time() + timeout_s if timeout_s and timeout_s > 0 else None
                while process.poll() is None:
                    previous_log_position = log_position
                    log_position, last_progress, last_progress_pct = cls._tail_progress_log(
                        log_path=progress_log,
                        position=log_position,
                        last_message=last_progress,
                        last_progress_pct=last_progress_pct,
                        label=label,
                    )
                    now = time.time()
                    if log_position != previous_log_position:
                        last_log_activity = now
                    if (
                        no_progress_notice_s is not None
                        and no_progress_notice_s > 0
                        and now - last_log_activity >= no_progress_notice_s
                        and now - last_no_progress_notice >= no_progress_notice_s
                    ):
                        cls._console(
                            f"{label}: geen nieuwe COMSOL batchlog-output sinds "
                            f"{(now - last_log_activity) / 60:.1f} min"
                        )
                        last_no_progress_notice = now
                    if deadline is not None and time.time() > deadline:
                        process.kill()
                        process.wait()
                        code = 124
                        break
                    time.sleep(5.0)
                else:
                    code = process.returncode
            log_position, last_progress, last_progress_pct = cls._tail_progress_log(
                log_path=progress_log,
                position=log_position,
                last_message=last_progress,
                last_progress_pct=last_progress_pct,
                label=label,
            )
            stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
            if code == 124:
                stderr = ((stderr or "") + "\nCommand timed out.").strip()
        except subprocess.TimeoutExpired as exc:
            code = 124
            if isinstance(exc.stdout, bytes):
                stdout = exc.stdout.decode("utf-8", errors="replace")
            else:
                stdout = exc.stdout or ""
            if isinstance(exc.stderr, bytes):
                stderr = exc.stderr.decode("utf-8", errors="replace")
            else:
                stderr = exc.stderr or ""
            stderr = (stderr + "\nCommand timed out.").strip()
        elapsed_s = time.time() - started
        cls._finish_progress_line()
        if announce or code != 0:
            status = "klaar" if code == 0 else f"failed code {code}"
            cls._console(f"{label}: {status} after {elapsed_s/60:.1f} min")

        debug_path.write_text(
            "\n".join(
                [
                    f"Command: {' '.join(proc_args)}",
                    f"Timeout seconds: {timeout_s if timeout_s and timeout_s > 0 else 'disabled'}",
                    f"Return code: {code}",
                    "",
                    "=== STDOUT ===",
                    stdout or "<empty>",
                    "",
                    "=== STDERR ===",
                    stderr or "<empty>",
                ]
            ),
            encoding="utf-8",
        )
        return code, stdout, stderr

    def _try_build_mph_from_java(
        self,
        *,
        case_name: str,
        case_dir: Path,
        output_dir: Path,
        configuration_dir: Path,
        batch_executable: str,
        comsol_executable: str | None,
        comsolcompile_executable: str | None,
        builder_java: Path,
        generated_mph: Path,
        settings: Settings,
    ) -> tuple[bool, str]:
        """Compile/run the generated COMSOL Java builder and report build status."""
        build_log = output_dir / f"{case_name}_comsol_build.log"
        class_file = builder_java.with_suffix(".class")
        jdk_root = settings.comsol.jdk_root or os.environ.get("JAVA_HOME")
        javac_executable = self._resolve_javac_executable(jdk_root)
        multiphysics_root = Path(batch_executable).resolve().parents[2]
        plugins_dir = multiphysics_root / "plugins"

        def _detect_build_error(text: str) -> str:
            lowered = text.lower()
            mesh_error_markers = [
                "error running java class",
                "failed to generate mesh",
                "a problem occurred when building mesh feature",
                "failed to respect boundary element",
                "internal error in boundary respecting",
            ]
            if any(marker in lowered for marker in mesh_error_markers):
                return "COMSOL build saved an MPH but reported a mesh/build error. Check *_comsol_build.log before using the model."
            return ""

        # Preferred route: plain javac with COMSOL plugin jars on classpath.
        if javac_executable and plugins_dir.exists():
            javac_cp = str(plugins_dir / "*")
            javac_args = [
                str(javac_executable),
                "-proc:none",
                "-cp",
                javac_cp,
                "-d",
                str(builder_java.parent.resolve()),
                str(builder_java.resolve()),
            ]
            javac_debug = output_dir / f"{case_name}_javac_compile_debug.log"
            javac_code, javac_out, javac_err = self._run_logged_command(
                javac_args,
                case_dir,
                javac_debug,
                timeout_s=_normalize_timeout_seconds(settings.comsol.java_compile_timeout_s, 30),
                announce=False,
            )
            if javac_code == 0 and class_file.exists():
                class_args = [
                    str(batch_executable),
                    "-configuration",
                    str(configuration_dir),
                    "-inputfile",
                    str(class_file.resolve()),
                    "-outputfile",
                    str(generated_mph.resolve()),
                    "-batchlog",
                    str(build_log.resolve()),
                    *settings.comsol.extra_args,
                ]
                class_debug = output_dir / f"{case_name}_comsol_build_class_debug.log"
                class_started_at = time.time()
                class_code, class_out, class_err = self._run_logged_command(
                    class_args,
                    case_dir,
                    class_debug,
                    timeout_s=_normalize_timeout_seconds(settings.comsol.java_build_timeout_s, 60),
                    progress_log=build_log,
                    progress_label="build",
                )
                class_log_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log.exists() else ""
                class_text = "\n".join([class_out, class_err, class_log_text])
                generated_candidate = self._resolve_fresh_generated_mph_candidate(generated_mph, class_started_at)
                build_error = _detect_build_error(class_text)
                if build_error:
                    return False, build_error
                if class_code == 0 and generated_candidate is not None:
                    return True, ""
                if class_code == 124:
                    return False, "Class-based COMSOL build timed out before saving the MPH. Increase build timeout or simplify geometry."
                if self._detect_license_error(class_text):
                    return False, "COMSOL license error during class-based MPH build (license server unreachable)."
                if "model file is damaged or not valid" in class_text.lower():
                    return False, "COMSOL rejected compiled class input. Check class execution route."
                return False, "Class-based build executed but no MPH file was produced."

            javac_text = "\n".join([javac_out, javac_err])
            if "error:" in javac_text.lower():
                return False, "javac compile failed. See *_javac_compile_debug.log for details."

        # Secondary route: COMSOL's own compiler.
        if comsolcompile_executable:
            compile_args = [str(comsolcompile_executable)]
            if jdk_root:
                compile_args.extend(["-jdkroot", str(jdk_root)])
            compile_args.append(str(builder_java.resolve()))
            compile_debug = output_dir / f"{case_name}_comsol_compile_debug.log"
            compile_code, compile_out, compile_err = self._run_logged_command(
                compile_args,
                case_dir,
                compile_debug,
                timeout_s=_normalize_timeout_seconds(settings.comsol.java_compile_timeout_s, 30),
                announce=False,
            )
            compile_text = "\n".join([compile_out, compile_err])
            if self._detect_license_error(compile_text):
                return False, "COMSOL license error during Java compile step (license server unreachable)."
            if compile_code == 124:
                return False, "comsolcompile timed out. Check *_comsol_compile_debug.log."
            if compile_code == 0 and class_file.exists():
                class_args = [
                    str(batch_executable),
                    "-configuration",
                    str(configuration_dir),
                    "-inputfile",
                    str(class_file.resolve()),
                    "-outputfile",
                    str(generated_mph.resolve()),
                    "-batchlog",
                    str(build_log.resolve()),
                    *settings.comsol.extra_args,
                ]
                class_debug = output_dir / f"{case_name}_comsol_build_class_debug.log"
                class_started_at = time.time()
                class_code, class_out, class_err = self._run_logged_command(
                    class_args,
                    case_dir,
                    class_debug,
                    timeout_s=_normalize_timeout_seconds(settings.comsol.java_build_timeout_s, 60),
                    progress_log=build_log,
                    progress_label="build",
                )
                class_log_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log.exists() else ""
                class_text = "\n".join([class_out, class_err, class_log_text])
                generated_candidate = self._resolve_fresh_generated_mph_candidate(generated_mph, class_started_at)
                build_error = _detect_build_error(class_text)
                if build_error:
                    return False, build_error
                if class_code == 0 and generated_candidate is not None:
                    return True, ""
                if class_code == 124:
                    return False, "Class-based COMSOL build timed out before saving the MPH. Increase build timeout or simplify geometry."
                if self._detect_license_error(class_text):
                    return False, "COMSOL license error during class-based MPH build (license server unreachable)."
                return False, "Class-based build after comsolcompile did not produce MPH."

        if settings.comsol.java_compile_first:
            if not comsolcompile_executable and not javac_executable:
                return False, "No Java compiler available. Install JDK and set JAVA_HOME (or comsol.jdk_root)."
            if jdk_root and not javac_executable:
                return False, "JDK root configured but javac.exe not found under jdk_root/bin."
            return False, "Java compile failed: no .class generated. Check compile debug logs."

        # Fallback route: direct Java source as input file (often unsupported).
        direct_args = [
            str(batch_executable),
            "-configuration",
            str(configuration_dir),
            "-inputfile",
            str(builder_java.resolve()),
            "-outputfile",
            str(generated_mph.resolve()),
            "-batchlog",
            str(build_log.resolve()),
            *settings.comsol.extra_args,
        ]
        direct_debug = output_dir / f"{case_name}_comsol_build_direct_debug.log"
        direct_started_at = time.time()
        code, stdout, stderr = self._run_logged_command(
            direct_args,
            case_dir,
            direct_debug,
            timeout_s=_normalize_timeout_seconds(settings.comsol.java_build_timeout_s, 60),
            progress_log=build_log,
            progress_label="build",
        )
        build_log_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log.exists() else ""
        direct_text = "\n".join([stdout, stderr, build_log_text])
        generated_candidate = self._resolve_fresh_generated_mph_candidate(generated_mph, direct_started_at)
        build_error = _detect_build_error(direct_text)
        if build_error:
            return False, build_error
        if code == 0 and generated_candidate is not None:
            return True, ""
        if self._detect_license_error(direct_text):
            return False, "COMSOL license error during Java->MPH build (license server unreachable)."
        if "model file is damaged or not valid" in direct_text.lower():
            return False, "Direct Java input is not accepted by this COMSOL batch setup. Use comsolcompile + class route."

        return False, "Java builder ran but no MPH file was produced."

    def _run_aux_java_class(
        self,
        *,
        case_name: str,
        case_dir: Path,
        logs_dir: Path,
        configuration_dir: Path,
        batch_executable: str,
        java_file: Path,
        settings: Settings,
    ) -> tuple[bool, str, str]:
        """Compile and run a generated verification or postprocess Java class."""
        class_file = java_file.with_suffix(".class")
        jdk_root = settings.comsol.jdk_root or os.environ.get("JAVA_HOME")
        javac_executable = self._resolve_javac_executable(jdk_root)
        multiphysics_root = Path(batch_executable).resolve().parents[2]
        plugins_dir = multiphysics_root / "plugins"

        if not javac_executable or not plugins_dir.exists():
            return False, "No Java compiler available for COMSOL postprocess step.", ""

        javac_args = [
            str(javac_executable),
            "-proc:none",
            "-cp",
            str(plugins_dir / "*"),
            "-d",
            str(java_file.parent.resolve()),
            str(java_file.resolve()),
        ]
        javac_debug = logs_dir / f"{case_name}_{java_file.stem}_javac_debug.log"
        javac_code, javac_out, javac_err = self._run_logged_command(
            javac_args,
            case_dir,
            javac_debug,
            timeout_s=_normalize_timeout_seconds(settings.comsol.java_compile_timeout_s, 30),
            announce=False,
        )
        if javac_code != 0 or not class_file.exists():
            return False, f"Failed to compile auxiliary COMSOL Java class {java_file.name}.", ""

        run_log = logs_dir / f"{case_name}_{java_file.stem}.log"
        self._safe_unlink(run_log)
        aux_configuration_dir = self._resolve_auxiliary_configuration_dir(configuration_dir, java_file)
        phase_label = self._aux_phase_label(java_file)
        logger.debug("%s %s auxiliary COMSOL configuration: %s", case_name, phase_label, aux_configuration_dir)
        class_args = [
            str(batch_executable),
            "-configuration",
            str(aux_configuration_dir),
            "-inputfile",
            str(class_file.resolve()),
            "-batchlog",
            str(run_log.resolve()),
            *settings.comsol.extra_args,
        ]
        if settings.comsol.postprocess_write_auxiliary_mph:
            class_args[5:5] = [
                "-outputfile",
                str(class_file.with_name(f"{java_file.stem}_output.mph").resolve()),
            ]
        class_debug = logs_dir / f"{case_name}_{java_file.stem}_debug.log"
        postprocess_timeout_s = _normalize_timeout_seconds(settings.comsol.postprocess_timeout_s, 60)
        if postprocess_timeout_s is None and phase_label == "postprocess":
            postprocess_timeout_s = 1800
        class_code, class_out, class_err = self._run_logged_command(
            class_args,
            case_dir,
            class_debug,
            timeout_s=postprocess_timeout_s,
            progress_log=run_log,
            progress_label=phase_label,
            no_progress_notice_s=120.0,
        )
        run_log_text = run_log.read_text(encoding="utf-8", errors="replace") if run_log.exists() else ""
        run_text = "\n".join([class_out, class_err, run_log_text])
        if class_code != 0:
            return False, f"Auxiliary COMSOL Java class {java_file.name} failed.", class_out
        if "error loading java class" in run_text.lower():
            return False, f"Auxiliary COMSOL Java class {java_file.name} could not be loaded by COMSOL batch.", class_out
        if self._detect_license_error(run_text):
            return False, "COMSOL license error during postprocess metrics export.", class_out
        return True, "", class_out

    def run(self, input_files: tuple[Path, ...], settings_map: dict[Path, Settings], *, build_only: bool = False) -> tuple[Path, ...]:
        completed: list[Path] = []
        total = len(input_files)
        mode = "build-only" if build_only else "run"
        for index, input_file in enumerate(input_files, start=1):
            self._console(f"({index}/{total}) {mode}: {self._case_name_from_input(input_file)}")
            settings = settings_map[input_file]
            if self.run_case(input_file, settings, build_only=build_only):
                completed.append(input_file)
        return tuple(completed)

    def postprocess(self, input_files: tuple[Path, ...], settings_map: dict[Path, Settings]) -> tuple[Path, ...]:
        completed: list[Path] = []
        total = len(input_files)
        for index, input_file in enumerate(input_files, start=1):
            self._console(f"({index}/{total}) postprocess-only: {self._case_name_from_input(input_file)}")
            settings = settings_map[input_file]
            if self.postprocess_case(input_file, settings):
                completed.append(input_file)
        return tuple(completed)

    def _capture_verification_json(
        self,
        *,
        case_name: str,
        case_dir: Path,
        logs_dir: Path,
        configuration_dir: Path,
        batch_executable: str,
        verification_java: Path | None,
        verification_target: Path | None,
        settings: Settings,
    ) -> tuple[bool, str]:
        if not verification_java or not verification_java.exists() or verification_target is None:
            return False, "Verification Java or target missing."
        ok, reason, aux_stdout = self._run_aux_java_class(
            case_name=case_name,
            case_dir=case_dir,
            logs_dir=logs_dir,
            configuration_dir=configuration_dir,
            batch_executable=batch_executable,
            java_file=verification_java,
            settings=settings,
        )
        if not ok:
            logger.warning("%s: %s", case_name, reason)
            return False, reason
        begin_marker = "COMSOL_VERIFICATION_JSON_BEGIN"
        end_marker = "COMSOL_VERIFICATION_JSON_END"
        start_idx = aux_stdout.find(begin_marker)
        end_idx = aux_stdout.find(end_marker)
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return False, "Verification Java ran but did not emit JSON markers."
        verification_json = aux_stdout[start_idx + len(begin_marker):end_idx].strip()
        verification_target.parent.mkdir(parents=True, exist_ok=True)
        verification_target.write_text(verification_json + "\n", encoding="utf-8")
        return True, ""

    def _write_fallback_verification_json(
        self,
        *,
        case_name: str,
        verification_target: Path | None,
        prepare_artefacts: dict[str, str],
        loaded_model_path: Path | None,
        phase: str,
        reason: str,
    ) -> None:
        if verification_target is None:
            return
        builder_java = Path(prepare_artefacts.get("comsol_builder_java", "")) if prepare_artefacts.get("comsol_builder_java") else None
        selection_hints_json = (
            Path(prepare_artefacts.get("comsol_selection_hints_json", ""))
            if prepare_artefacts.get("comsol_selection_hints_json")
            else None
        )
        builder_text = builder_java.read_text(encoding="utf-8", errors="replace") if builder_java and builder_java.exists() else ""
        payload = {
            "case_name": case_name,
            "verification_mode": "fallback_builder_artifacts",
            "phase": phase,
            "reason": reason,
            "loaded_model_path": str(loaded_model_path.resolve()) if loaded_model_path and loaded_model_path.exists() else "",
            "loaded_model_exists": bool(loaded_model_path and loaded_model_path.exists()),
            "builder_java_exists": bool(builder_java and builder_java.exists()),
            "selection_hints_exists": bool(selection_hints_json and selection_hints_json.exists()),
            "builder_signals": {
                "solid_hmat_adipose": '"hmat_adipose"' in builder_text,
                "solid_hmat_glandular": '"hmat_glandular"' in builder_text,
                "shell_hmat_skin": '"hmat_skin"' in builder_text,
                "solid_thin_connection": '"sthin1"' in builder_text,
                "mat_chest": '"mat_chest"' in builder_text,
                "mooney_rivlin_parameters": all(
                    token in builder_text
                    for token in ('"skin_c10"', '"adipose_c10"', '"glandular_c10"', '"skin_bulk_modulus"')
                ),
            },
        }
        verification_target.parent.mkdir(parents=True, exist_ok=True)
        verification_target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def run_case(self, input_file: Path, settings: Settings, *, build_only: bool = False) -> bool:
        """Build and optionally solve a single generated COMSOL case input."""
        assert input_file.suffix == ".json", "COMSOL runner expects JSON case input files."
        payload = json.loads(input_file.read_text(encoding="utf-8"))
        case_name = payload["case_name"]
        case_dir = Path(payload["case_dir"])
        output_paths = ensure_output_tree(case_dir, settings)
        build_dir = output_paths["build"]
        solve_dir = output_paths["solve"]
        logs_dir = output_paths["logs"]
        self._console(f"output root: {self._display_path(output_paths['root'])}")
        command_preview_file = logs_dir / f"{case_name}.comsol_command.txt"
        prepare_artefacts = payload.get("prepare_artefacts", {})
        auxiliary_verification_enabled = bool(getattr(settings.comsol, "enable_auxiliary_verification", False))
        configuration_dir = self._resolve_configuration_dir(settings, build_dir)
        build_verification_java = (
            Path(prepare_artefacts.get("comsol_build_verification_java", ""))
            if prepare_artefacts.get("comsol_build_verification_java")
            else None
        )
        solve_verification_java = (
            Path(prepare_artefacts.get("comsol_solve_verification_java", ""))
            if prepare_artefacts.get("comsol_solve_verification_java")
            else None
        )
        build_verification_target = (
            Path(prepare_artefacts.get("comsol_build_verification_json_target", ""))
            if prepare_artefacts.get("comsol_build_verification_json_target")
            else None
        )
        solve_verification_target = (
            Path(prepare_artefacts.get("comsol_solve_verification_json_target", ""))
            if prepare_artefacts.get("comsol_solve_verification_json_target")
            else None
        )

        batch_executable = self._resolve_batch_executable(settings)
        comsol_executable = self._resolve_comsol_executable(settings, batch_executable)
        comsolcompile_executable = self._resolve_comsolcompile_executable(batch_executable)
        mph_file = settings.comsol.mph_file or ""

        if not batch_executable:
            logger.warning("Skipping %s: COMSOL batch executable not found.", case_name)
            return False

        configured_mph = Path(mph_file).resolve() if mph_file else None
        builder_java = Path(prepare_artefacts.get("comsol_builder_java", "")) if prepare_artefacts.get("comsol_builder_java") else None
        generated_mph_target = Path(prepare_artefacts.get("comsol_generated_mph_target", "")) if prepare_artefacts.get("comsol_generated_mph_target") else None

        source_mph = configured_mph if configured_mph and configured_mph.exists() else None
        planned_commands: list[str] = []
        build_failure_reason = ""
        build_attempted = False
        build_succeeded = False

        if source_mph is None and settings.comsol.auto_build_from_java and builder_java and generated_mph_target:
            build_attempted = True
            build_log = logs_dir / f"{case_name}_comsol_build.log"
            planned_build_cmd = " ".join(
                [
                    str(batch_executable),
                    "-configuration",
                    str(configuration_dir),
                    "-inputfile",
                    str(builder_java.resolve()),
                    "-outputfile",
                    str(generated_mph_target.resolve()),
                    "-batchlog",
                    str(build_log.resolve()),
                    *settings.comsol.extra_args,
                ]
            )
            planned_commands.append(planned_build_cmd)
            if settings.comsol.java_compile_first and comsol_executable:
                planned_commands.append(f"{comsol_executable} compile {builder_java.resolve()}")

            if True:
                logger.debug("Building MPH from Java scaffold for %s", case_name)
                self._console("build: Java -> MPH")
                built, reason = self._try_build_mph_from_java(
                    case_name=case_name,
                    case_dir=case_dir,
                    output_dir=logs_dir,
                    configuration_dir=configuration_dir,
                    batch_executable=batch_executable,
                    comsol_executable=comsol_executable,
                    comsolcompile_executable=comsolcompile_executable,
                    builder_java=builder_java,
                    generated_mph=generated_mph_target,
                    settings=settings,
                )
                if built:
                    build_succeeded = True
                    source_mph = self._resolve_generated_mph_candidate(generated_mph_target)
                else:
                    build_failure_reason = reason
                    recoverable_mph = self._resolve_generated_mph_candidate(generated_mph_target)
                    if recoverable_mph is not None:
                        logger.warning(
                            "%s: COMSOL build reported a warning/error but saved %s; continuing with the saved MPH.",
                            case_name,
                            recoverable_mph,
                        )
                        source_mph = recoverable_mph

        if source_mph is None and configured_mph and configured_mph.exists():
            source_mph = configured_mph
        if source_mph is None and generated_mph_target and not build_attempted:
            source_mph = self._resolve_generated_mph_candidate(generated_mph_target)
        if source_mph is None and generated_mph_target and build_attempted and build_succeeded:
            source_mph = self._resolve_generated_mph_candidate(generated_mph_target)
        if source_mph is None:
            if build_failure_reason:
                logger.warning("%s: %s", case_name, build_failure_reason)
            if not build_only and settings.comsol.execute:
                logger.warning(
                    "Skipping %s: no readable MPH available. Configure comsol.mph_file or enable Java auto-build with generated artefacts.",
                    case_name,
                )
            else:
                logger.info(
                    "Prepared build command for %s (execute=false, MPH not built yet).",
                    case_name,
                )
            if planned_commands:
                command_preview_file.write_text("\n".join(planned_commands) + "\n", encoding="utf-8")
            return False

        if settings.comsol.reuse_mph_apply_toml_parameters:
            patched_source_mph, patch_reason = self._prepare_reused_mph_with_parameter_overrides(
                case_name=case_name,
                case_dir=case_dir,
                build_dir=build_dir,
                logs_dir=logs_dir,
                configuration_dir=configuration_dir,
                batch_executable=batch_executable,
                source_mph=source_mph,
                builder_java=builder_java,
                settings=settings,
            )
            if patched_source_mph is None:
                logger.error("%s: failed to prepare reused MPH with TOML parameters: %s", case_name, patch_reason)
                return False
            source_mph = patched_source_mph

        output_mph = solve_dir / f"{case_name}_result.mph"
        log_file = logs_dir / f"{case_name}_comsol.log"
        self._safe_unlink(output_mph.with_suffix(output_mph.suffix + ".lock"))

        proc_args = [
            str(batch_executable),
            "-configuration",
            str(configuration_dir),
            "-inputfile",
            str(source_mph),
            "-outputfile",
            str(output_mph.resolve()),
            "-study",
            settings.comsol.study,
            "-batchlog",
            str(log_file.resolve()),
            *settings.comsol.extra_args,
        ]
        planned_commands.append(" ".join(proc_args))
        command_preview_file.write_text("\n".join(planned_commands) + "\n", encoding="utf-8")

        if build_only:
            if auxiliary_verification_enabled:
                self._console("build-only: verification")
                verify_ok, verify_reason = self._capture_verification_json(
                    case_name=case_name,
                    case_dir=case_dir,
                    logs_dir=logs_dir,
                    configuration_dir=configuration_dir,
                    batch_executable=batch_executable,
                    verification_java=build_verification_java,
                    verification_target=build_verification_target,
                    settings=settings,
                )
                if not verify_ok:
                    self._write_fallback_verification_json(
                        case_name=case_name,
                        verification_target=build_verification_target,
                        prepare_artefacts=prepare_artefacts,
                        loaded_model_path=source_mph,
                        phase="build_only",
                        reason=verify_reason,
                    )
            logger.info("Built COMSOL MPH for %s without starting solve.", case_name)
            self._console("build-only: complete")
            self._prune_output_artefacts(
                case_name=case_name,
                output_paths=output_paths,
                prepare_artefacts=prepare_artefacts,
                input_file=input_file,
                settings=settings,
            )
            self._cleanup_duplicate_mph_outputs(
                build_dir=build_dir,
                generated_mph_target=generated_mph_target,
                preferred_generated_mph=source_mph,
                settings=settings,
            )
            return True

        if not settings.comsol.execute:
            logger.info("Prepared COMSOL command for %s (execute=false).", case_name)
            return True

        logger.info("Running COMSOL for %s", case_name)
        self._console("solve: start")
        debug_path = logs_dir / f"{case_name}_comsol_runner_debug.log"
        code, _, _ = self._run_logged_command(
            proc_args,
            case_dir,
            debug_path,
            timeout_s=_normalize_timeout_seconds(settings.comsol.solve_timeout_s, 120),
            progress_log=log_file,
            progress_label="solve",
        )
        if code != 0:
            if output_mph.exists():
                logger.warning(
                    "%s: COMSOL returned a nonzero status, but a result MPH was saved; continuing with postprocess. Debug: %s",
                    case_name,
                    debug_path,
                )
            else:
                logger.error("COMSOL failed for %s. Debug: %s", case_name, debug_path)
                return False

        postprocess_java = (
            Path(prepare_artefacts.get("comsol_postprocess_java", ""))
            if prepare_artefacts.get("comsol_postprocess_java")
            else None
        )
        postprocess_mode = str(getattr(settings.comsol, "postprocess_mode", "full") or "full").strip().lower().replace("-", "_")
        skip_postprocess = postprocess_mode in {"none", "skip", "off", "disabled", "false"}
        if skip_postprocess:
            self._console(f"postprocess: skipped by postprocess_mode={postprocess_mode}")
        elif postprocess_java and postprocess_java.exists():
            self._console("postprocess: metrics/export")
            ok, reason, aux_stdout = self._run_aux_java_class(
                case_name=case_name,
                case_dir=case_dir,
                logs_dir=logs_dir,
                configuration_dir=configuration_dir,
                batch_executable=batch_executable,
                java_file=postprocess_java,
                settings=settings,
            )
            metrics_target = (
                Path(prepare_artefacts.get("comsol_metrics_json_target", ""))
                if prepare_artefacts.get("comsol_metrics_json_target")
                else None
            )
            metrics_written = self._write_metrics_from_aux_stdout(aux_stdout, metrics_target)
            if not ok:
                logger.warning("%s: %s", case_name, reason)
            elif not metrics_written:
                logger.info("%s: postprocess did not emit metrics markers; keeping existing/fallback reporting flow.", case_name)

        if auxiliary_verification_enabled:
            verify_ok, verify_reason = self._capture_verification_json(
                case_name=case_name,
                case_dir=case_dir,
                logs_dir=logs_dir,
                configuration_dir=configuration_dir,
                batch_executable=batch_executable,
                verification_java=solve_verification_java,
                verification_target=solve_verification_target,
                settings=settings,
            )
            if not verify_ok:
                self._write_fallback_verification_json(
                    case_name=case_name,
                    verification_target=solve_verification_target,
                    prepare_artefacts=prepare_artefacts,
                    loaded_model_path=output_mph,
                    phase="solve",
                    reason=verify_reason,
                )

        metrics_target = (
            Path(prepare_artefacts.get("comsol_metrics_json_target", ""))
            if prepare_artefacts.get("comsol_metrics_json_target")
            else None
        )
        if metrics_target and metrics_target.exists():
            try:
                generate_case_report(
                    case_name=case_name,
                    metrics_path=metrics_target,
                    verification_path=(
                        solve_verification_target
                        if auxiliary_verification_enabled and solve_verification_target and solve_verification_target.exists()
                        else None
                    ),
                    log_path=log_file if log_file.exists() else None,
                    output_dir=solve_dir,
                    settings=settings,
                )
            except Exception:
                logger.exception("%s: failed to generate COMSOL summary report.", case_name)

        self._prune_output_artefacts(
            case_name=case_name,
            output_paths=output_paths,
            prepare_artefacts=prepare_artefacts,
            input_file=input_file,
            settings=settings,
        )
        self._cleanup_duplicate_mph_outputs(
            build_dir=build_dir,
            generated_mph_target=generated_mph_target,
            preferred_generated_mph=source_mph,
            settings=settings,
        )
        self._console("run: complete")
        return True

    def postprocess_case(self, input_file: Path, settings: Settings) -> bool:
        """Run postprocess-only on a solved result MPH for one generated case."""
        assert input_file.suffix == ".json", "COMSOL runner expects JSON case input files."
        payload = json.loads(input_file.read_text(encoding="utf-8"))
        case_name = payload["case_name"]
        case_dir = Path(payload["case_dir"])
        output_paths = ensure_output_tree(case_dir, settings)
        solve_dir = output_paths["solve"]
        logs_dir = output_paths["logs"]
        prepare_artefacts = payload.get("prepare_artefacts", {})
        auxiliary_verification_enabled = bool(getattr(settings.comsol, "enable_auxiliary_verification", False))
        configuration_dir = self._resolve_configuration_dir(settings, output_paths["build"])
        batch_executable = self._resolve_batch_executable(settings)
        if not batch_executable:
            logger.warning("Skipping postprocess for %s: COMSOL batch executable not found.", case_name)
            return False

        postprocess_java = (
            Path(prepare_artefacts.get("comsol_postprocess_java", ""))
            if prepare_artefacts.get("comsol_postprocess_java")
            else None
        )
        result_mph = solve_dir / f"{case_name}_result.mph"
        if not postprocess_java or not postprocess_java.exists():
            logger.warning("Skipping postprocess for %s: generated postprocess Java is missing.", case_name)
            return False
        if not result_mph.exists():
            logger.warning("Skipping postprocess for %s: result MPH does not exist at %s.", case_name, result_mph)
            return False

        ok, reason, aux_stdout = self._run_aux_java_class(
            case_name=case_name,
            case_dir=case_dir,
            logs_dir=logs_dir,
            configuration_dir=configuration_dir,
            batch_executable=batch_executable,
            java_file=postprocess_java,
            settings=settings,
        )
        metrics_target = (
            Path(prepare_artefacts.get("comsol_metrics_json_target", ""))
            if prepare_artefacts.get("comsol_metrics_json_target")
            else None
        )
        if metrics_target:
            metrics_written = self._write_metrics_from_aux_stdout(aux_stdout, metrics_target)
            if not metrics_written:
                if not ok:
                    logger.warning("%s: %s", case_name, reason)
                    return False
                logger.warning("%s: postprocess did not emit metrics markers.", case_name)
                return False
            if not ok:
                logger.warning(
                    "%s: postprocess emitted metrics, but auxiliary Java ended with: %s",
                    case_name,
                    reason,
                )

        solve_verification_target = (
            Path(prepare_artefacts.get("comsol_solve_verification_json_target", ""))
            if prepare_artefacts.get("comsol_solve_verification_json_target")
            else None
        )
        log_file = logs_dir / f"{case_name}_comsol.log"
        if metrics_target and metrics_target.exists():
            try:
                generate_case_report(
                    case_name=case_name,
                    metrics_path=metrics_target,
                    verification_path=(
                        solve_verification_target
                        if auxiliary_verification_enabled and solve_verification_target and solve_verification_target.exists()
                        else None
                    ),
                    log_path=log_file if log_file.exists() else None,
                    output_dir=solve_dir,
                    settings=settings,
                )
            except Exception:
                logger.exception("%s: failed to generate COMSOL summary report after postprocess-only.", case_name)
                return False
        generated_mph_target = (
            Path(prepare_artefacts.get("comsol_generated_mph_target", ""))
            if prepare_artefacts.get("comsol_generated_mph_target")
            else None
        )
        self._cleanup_duplicate_mph_outputs(
            build_dir=output_paths["build"],
            generated_mph_target=generated_mph_target,
            preferred_generated_mph=self._resolve_generated_mph_candidate(generated_mph_target) if generated_mph_target else None,
            settings=settings,
        )
        return True
