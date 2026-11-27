"""Engine runner for CASIMPLE_WIN64.EXE, CADOUBLE_WIN64.EXE, and CATRIPLE_WIN64.EXE.

Runs the legacy .NET/DOS wrapper inside a hidden Windows console (SW_HIDE)
and interacts with it via AttachConsole + WriteConsoleInputW + ReadConsoleOutputCharacterW
so that NO console window is shown to the user and all results are captured in the GUI.
"""

import ctypes
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import List, Set

from .models import ExecutionResult, StructureType
from .results import merge_console_screens

# Detect if Windows API is available
IS_WINDOWS = sys.platform == "win32"
_k32 = None

if IS_WINDOWS:
    try:
        from ctypes import wintypes
        _k32 = ctypes.windll.kernel32
    except (AttributeError, OSError):
        _k32 = None

_CREATE_NEW_CONSOLE = 0x00000010
_STARTF_USESHOWWINDOW = 0x00000001
_SW_HIDE = 0
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value if hasattr(ctypes, "c_void_p") else None

if IS_WINDOWS and _k32:
    class _COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class _KEY_EVENT_RECORD(ctypes.Structure):
        _fields_ = [
            ("bKeyDown", wintypes.BOOL),
            ("wRepeatCount", wintypes.WORD),
            ("wVirtualKeyCode", wintypes.WORD),
            ("wVirtualScanCode", wintypes.WORD),
            ("UnicodeChar", wintypes.WCHAR),
            ("dwControlKeyState", wintypes.DWORD),
        ]

    class _INPUT_RECORD_EVENT(ctypes.Union):
        _fields_ = [("KeyEvent", _KEY_EVENT_RECORD)]

    class _INPUT_RECORD(ctypes.Structure):
        _fields_ = [
            ("EventType", wintypes.WORD),
            ("Event", _INPUT_RECORD_EVENT),
        ]

    class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", _COORD),
            ("dwCursorPosition", _COORD),
            ("wAttributes", wintypes.WORD),
            ("srWindow", wintypes.SMALL_RECT),
            ("dwMaximumWindowSize", _COORD),
        ]

    def _send_console_text(h_in, text: str) -> None:
        records = []
        for ch in text:
            vk = 0x0D if ch == "\r" else 0
            for down in (True, False):
                rec = _INPUT_RECORD()
                rec.EventType = 0x0001
                rec.Event.KeyEvent.bKeyDown = down
                rec.Event.KeyEvent.wRepeatCount = 1
                rec.Event.KeyEvent.wVirtualKeyCode = vk
                rec.Event.KeyEvent.wVirtualScanCode = 0
                rec.Event.KeyEvent.UnicodeChar = ch
                rec.Event.KeyEvent.dwControlKeyState = 0
                records.append(rec)
        arr = (_INPUT_RECORD * len(records))(*records)
        written = wintypes.DWORD()
        _k32.WriteConsoleInputW(h_in, arr, len(records), ctypes.byref(written))

    def _read_console_screen(h_out) -> str:
        csbi = _CONSOLE_SCREEN_BUFFER_INFO()
        if not _k32.GetConsoleScreenBufferInfo(h_out, ctypes.byref(csbi)):
            return ""
        w, h = csbi.dwSize.X, csbi.dwSize.Y
        lines: List[str] = []
        buf = ctypes.create_unicode_buffer(w + 1)
        read_chars = wintypes.DWORD()
        for y in range(min(h, 200)):
            if _k32.ReadConsoleOutputCharacterW(h_out, buf, w, _COORD(0, y), ctypes.byref(read_chars)):
                lines.append(buf.value[:read_chars.value].rstrip())
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


class EngineRunner:
    """Launches the calculation engine locally or remotely via Cloud API."""

    def __init__(self, legacy_bins_dir: Path, remote_api_url: str = "https://cad90.onrender.com/api/calculate"):
        self.legacy_bins_dir = legacy_bins_dir
        self.remote_api_url = remote_api_url

    def get_engine_path(self, structure_type: StructureType) -> Path:
        return self.legacy_bins_dir / structure_type.engine_filename

    def run_engine(
        self,
        structure_type: StructureType,
        data_file_path: Path,
        work_dir: Path,
        timeout_seconds: int = 45,
        params: dict = None,
    ) -> ExecutionResult:
        """Run the calculation engine locally or remotely via cloud API if not present."""
        engine_path = self.get_engine_path(structure_type)

        # Si le binaire local .EXE n'existe pas (cas de l'application client protégée),
        # basculer automatiquement sur le serveur cloud privé :
        if not engine_path.is_file():
            return self._run_engine_remote(
                structure_type=structure_type,
                params=params,
                data_file_path=data_file_path,
                work_dir=work_dir,
                timeout_seconds=max(timeout_seconds, 90),
            )

        # On non-Windows platforms (e.g. Linux container with Wine on Render), use Wine runner
        if _k32 is None:
            return self._run_engine_linux_wine(
                structure_type=structure_type,
                engine_path=engine_path,
                data_file_path=data_file_path,
                work_dir=work_dir,
                timeout_seconds=timeout_seconds,
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        engine_dir = engine_path.parent
        engine_data_file = engine_dir / data_file_path.name
        copied_to_engine_dir = False
        if data_file_path.resolve() != engine_data_file.resolve():
            shutil.copyfile(data_file_path, engine_data_file)
            copied_to_engine_dir = True

        before_files: Set[Path] = {p for p in work_dir.iterdir() if p.is_file()}
        before_engine_files: Set[Path] = {p for p in engine_dir.iterdir() if p.is_file()}
        start_ts = time.time()

        si = subprocess.STARTUPINFO()
        si.dwFlags |= _STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_HIDE

        try:
            proc = subprocess.Popen(
                [str(engine_path)],
                cwd=str(work_dir),
                startupinfo=si,
                creationflags=_CREATE_NEW_CONSOLE,
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                structure_type=structure_type,
                engine_path=str(engine_path),
                work_dir=str(work_dir),
                data_file_path=str(data_file_path),
                error_message=f"Impossible de démarrer le moteur : {exc}",
            )

        # Attach to the hidden console of the child process
        attached = False
        _k32.FreeConsole()
        for _ in range(30):
            if proc.poll() is not None:
                break
            if _k32.AttachConsole(proc.pid):
                attached = True
                break
            time.sleep(0.1)

        if not attached:
            if proc.poll() is None:
                proc.terminate()
            return ExecutionResult(
                success=False,
                structure_type=structure_type,
                engine_path=str(engine_path),
                work_dir=str(work_dir),
                data_file_path=str(data_file_path),
                exit_code=proc.returncode,
                error_message="Impossible de s'attacher à la console cachée du moteur.",
            )

        h_in = _k32.CreateFileW(
            "CONIN$", _GENERIC_READ | _GENERIC_WRITE,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE, None, _OPEN_EXISTING, 0, None,
        )
        h_out = _k32.CreateFileW(
            "CONOUT$", _GENERIC_READ | _GENERIC_WRITE,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE, None, _OPEN_EXISTING, 0, None,
        )

        captured_screens: List[str] = []
        sent_filename = False
        sent_output_choice = False
        last_screen = ""
        last_change_ts = time.time()
        enter_sent_for_screen = False
        deadline = time.time() + timeout_seconds

        try:
            while time.time() < deadline:
                if h_out != _INVALID_HANDLE_VALUE:
                    screen = _read_console_screen(h_out)
                    if screen and screen != last_screen:
                        last_screen = screen
                        last_change_ts = time.time()
                        enter_sent_for_screen = False
                        if not captured_screens or captured_screens[-1] != screen:
                            captured_screens.append(screen)

                    low = screen.lower()
                    if not sent_filename and "nom de votre fichier" in low:
                        _send_console_text(h_in, data_file_path.name + "\r")
                        sent_filename = True
                        last_change_ts = time.time()
                        enter_sent_for_screen = True
                        time.sleep(0.15)
                        continue

                    if sent_filename and not sent_output_choice and "entrez votre choix" in low:
                        _send_console_text(h_in, "1\r")
                        sent_output_choice = True
                        last_change_ts = time.time()
                        enter_sent_for_screen = True
                        time.sleep(0.15)
                        continue

                    if sent_output_choice and not enter_sent_for_screen:
                        # Send Enter ONCE per settled page to advance through results
                        if (time.time() - last_change_ts) >= 0.45:
                            _send_console_text(h_in, "\r")
                            enter_sent_for_screen = True

                if proc.poll() is not None:
                    # Final read before detaching
                    if h_out != _INVALID_HANDLE_VALUE:
                        screen = _read_console_screen(h_out)
                        if screen and (not captured_screens or captured_screens[-1] != screen):
                            captured_screens.append(screen)
                    break

                time.sleep(0.03)
            else:
                proc.terminate()
                return ExecutionResult(
                    success=False,
                    structure_type=structure_type,
                    engine_path=str(engine_path),
                    work_dir=str(work_dir),
                    data_file_path=str(data_file_path),
                    stdout="\n\n".join(captured_screens),
                    error_message=f"Délai d'exécution dépassé ({timeout_seconds}s).",
                )
        finally:
            if h_in != _INVALID_HANDLE_VALUE:
                _k32.CloseHandle(h_in)
            if h_out != _INVALID_HANDLE_VALUE:
                _k32.CloseHandle(h_out)
            _k32.FreeConsole()
            if copied_to_engine_dir and engine_data_file.exists():
                try:
                    engine_data_file.unlink()
                except OSError:
                    pass

        after_files = [
            p for p in work_dir.iterdir()
            if p.is_file() and (p not in before_files or p.stat().st_mtime >= start_ts - 1)
        ]
        for p in engine_dir.iterdir():
            if p.is_file() and p != engine_data_file and (p not in before_engine_files or p.stat().st_mtime >= start_ts - 1):
                if p.suffix.lower() != ".exe":
                    dest = work_dir / p.name
                    try:
                        shutil.move(str(p), str(dest))
                        after_files.append(dest)
                    except OSError:
                        after_files.append(p)

        clean_report = merge_console_screens(captured_screens)
        if clean_report:
            report_path = work_dir / f"{data_file_path.name}_resultat.txt"
            report_path.write_text(clean_report + "\r\n", encoding="utf-8")
            if report_path not in after_files:
                after_files.append(report_path)

        return ExecutionResult(
            success=(proc.returncode == 0),
            structure_type=structure_type,
            engine_path=str(engine_path),
            work_dir=str(work_dir),
            data_file_path=str(data_file_path),
            exit_code=proc.returncode,
            stdout=clean_report or "\n\n".join(captured_screens),
            generated_files=sorted(after_files),
            error_message="" if proc.returncode == 0 else f"Code retour : {proc.returncode}",
        )

    def _run_engine_linux_wine(
        self,
        structure_type: StructureType,
        engine_path: Path,
        data_file_path: Path,
        work_dir: Path,
        timeout_seconds: int = 45,
    ) -> ExecutionResult:
        """Run engine inside Linux container using Wine64 and pseudo-terminal (PTY)."""
        import os
        import select
        try:
            import pty
        except ImportError:
            pty = None

        work_dir.mkdir(parents=True, exist_ok=True)
        engine_dir = engine_path.parent
        engine_data_file = engine_dir / data_file_path.name
        copied_to_engine_dir = False
        if data_file_path.resolve() != engine_data_file.resolve():
            shutil.copyfile(data_file_path, engine_data_file)
            copied_to_engine_dir = True

        before_files: Set[Path] = {p for p in work_dir.iterdir() if p.is_file()}
        before_engine_files: Set[Path] = {p for p in engine_dir.iterdir() if p.is_file()}
        start_ts = time.time()

        wine_cmd = shutil.which("wine") or shutil.which("wine64") or "wine"
        env = dict(os.environ)
        env["WINEDEBUG"] = "-all"
        runtime_dir = Path("/root/.runtime")
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            pass
        env["XDG_RUNTIME_DIR"] = str(runtime_dir)
        env["DISPLAY"] = env.get("DISPLAY", ":99")

        captured_output: List[bytes] = []
        exit_code = 0

        if pty is not None:
            master, slave = pty.openpty()
            # Désactiver l'écho automatique du PTY pour éviter la boucle infinie
            try:
                import termios
                attrs = termios.tcgetattr(master)
                attrs[3] = attrs[3] & ~termios.ECHO
                termios.tcsetattr(master, termios.TCSANOW, attrs)
            except Exception:
                pass

            try:
                proc = subprocess.Popen(
                    [wine_cmd, str(engine_path.resolve())],
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    cwd=str(work_dir),
                    env=env,
                    close_fds=True,
                )
            except Exception as exc:
                os.close(slave)
                os.close(master)
                return ExecutionResult(
                    success=False,
                    structure_type=structure_type,
                    engine_path=str(engine_path),
                    work_dir=str(work_dir),
                    data_file_path=str(data_file_path),
                    error_message=f"Erreur lancement Wine : {exc}",
                )
            os.close(slave)

            sent_filename = False
            sent_choice = False
            last_screen = ""
            last_change_ts = time.time()
            enter_sent_for_screen = False
            deadline = time.time() + timeout_seconds

            try:
                while time.time() < deadline:
                    r, _, _ = select.select([master], [], [], 0.05)
                    if r:
                        try:
                            chunk = os.read(master, 2048)
                            if not chunk:
                                break
                            captured_output.append(chunk)
                            current_text = b"".join(captured_output).decode("latin1", errors="ignore")
                            if current_text != last_screen:
                                last_screen = current_text
                                last_change_ts = time.time()
                                enter_sent_for_screen = False

                            low = current_text.lower()
                            if not sent_filename and "nom de votre fichier" in low:
                                os.write(master, (data_file_path.name + "\r").encode("latin1"))
                                sent_filename = True
                                last_change_ts = time.time()
                                enter_sent_for_screen = True
                                time.sleep(0.15)
                                continue

                            if sent_filename and not sent_choice and "entrez votre choix" in low:
                                os.write(master, b"1\r")
                                sent_choice = True
                                last_change_ts = time.time()
                                enter_sent_for_screen = True
                                time.sleep(0.15)
                                continue

                            if sent_choice and not enter_sent_for_screen:
                                if (time.time() - last_change_ts) >= 0.45:
                                    os.write(master, b"\r")
                                    enter_sent_for_screen = True
                        except OSError:
                            break

                    if proc.poll() is not None:
                        while True:
                            r, _, _ = select.select([master], [], [], 0.05)
                            if not r:
                                break
                            try:
                                c = os.read(master, 2048)
                                if not c:
                                    break
                                captured_output.append(c)
                            except OSError:
                                break
                        break
            finally:
                os.close(master)
                if proc.poll() is None:
                    proc.terminate()
                exit_code = proc.returncode or 0
        else:
            try:
                proc = subprocess.Popen(
                    [wine_cmd, str(engine_path.resolve())],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(work_dir),
                    env=env,
                )
                stdin_data = (f"{data_file_path.name}\n1\n" + "\n" * 40).encode("latin1")
                stdout, stderr = proc.communicate(input=stdin_data, timeout=timeout_seconds)
                captured_output.append(stdout)
                exit_code = proc.returncode or 0
            except Exception as exc:
                return ExecutionResult(
                    success=False,
                    structure_type=structure_type,
                    engine_path=str(engine_path),
                    work_dir=str(work_dir),
                    data_file_path=str(data_file_path),
                    error_message=f"Erreur exécution Wine : {exc}",
                )

        if copied_to_engine_dir and engine_data_file.exists():
            try:
                engine_data_file.unlink()
            except OSError:
                pass

        after_files = [
            p for p in work_dir.iterdir()
            if p.is_file() and (p not in before_files or p.stat().st_mtime >= start_ts - 1)
        ]
        for p in engine_dir.iterdir():
            if p.is_file() and p != engine_data_file and (p not in before_engine_files or p.stat().st_mtime >= start_ts - 1):
                if p.suffix.lower() != ".exe":
                    dest = work_dir / p.name
                    try:
                        shutil.move(str(p), str(dest))
                        after_files.append(dest)
                    except OSError:
                        after_files.append(p)

        full_text = b"".join(captured_output).decode("cp850", errors="replace")
        report_path = work_dir / f"{data_file_path.name}_resultat.txt"
        report_path.write_text(full_text, encoding="utf-8")
        if report_path not in after_files:
            after_files.append(report_path)

        return ExecutionResult(
            success=(exit_code == 0),
            structure_type=structure_type,
            engine_path=str(engine_path),
            work_dir=str(work_dir),
            data_file_path=str(data_file_path),
            exit_code=exit_code,
            stdout=full_text,
            generated_files=sorted(after_files),
            error_message="" if exit_code == 0 else f"Code retour Wine: {exit_code}",
        )

    def _run_engine_remote(
        self,
        structure_type: StructureType,
        params: dict,
        data_file_path: Path,
        work_dir: Path,
        timeout_seconds: int = 60,
    ) -> ExecutionResult:
        """Exécution à distance sur le serveur privé Render (moteurs sécurisés hors du PC client)."""
        import json
        import urllib.request

        work_dir.mkdir(parents=True, exist_ok=True)
        api_url = self.remote_api_url or "https://cad90.onrender.com/api/calculate"

        payload = {
            "structure_type": structure_type.value,
            "params": params or {"nom_fichier": data_file_path.name},
        }

        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return ExecutionResult(
                success=False,
                structure_type=structure_type,
                engine_path=api_url,
                work_dir=str(work_dir),
                data_file_path=str(data_file_path),
                error_message=f"Impossible de contacter le serveur cloud ({api_url}) : {exc}",
            )

        stdout = data.get("stdout", "")
        generated_files = []

        report_path = work_dir / f"{data_file_path.name}_resultat.txt"
        if stdout:
            report_path.write_text(stdout, encoding="utf-8")
            generated_files.append(report_path)

        for fname, content in data.get("file_contents", {}).items():
            fp = work_dir / fname
            fp.write_text(content, encoding="utf-8")
            if fp not in generated_files:
                generated_files.append(fp)

        return ExecutionResult(
            success=data.get("success", False),
            structure_type=structure_type,
            engine_path=api_url,
            work_dir=str(work_dir),
            data_file_path=str(data_file_path),
            exit_code=data.get("exit_code", 0),
            stdout=stdout,
            generated_files=generated_files,
            error_message=data.get("error_message", ""),
        )
