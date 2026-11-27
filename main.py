"""Entry point for the Dalot GUI application (supports both source and PyInstaller EXE)."""

from pathlib import Path
import sys

from ui.app import DalotApp


def _resolve_paths() -> tuple[Path, Path, Path]:
    if getattr(sys, "frozen", False):
        resource_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        exe_dir = Path(sys.executable).resolve().parent
        # Priority: bundled engines inside _MEIPASS first (--onefile), then beside the EXE (--onedir)
        if (resource_dir / "legacy_bins").is_dir():
            bins_dir = resource_dir / "legacy_bins"
        elif (exe_dir / "legacy_bins").is_dir():
            bins_dir = exe_dir / "legacy_bins"
        elif (exe_dir.parent / "legacy_bins").is_dir():
            bins_dir = exe_dir.parent / "legacy_bins"
        else:
            bins_dir = exe_dir
        return resource_dir, bins_dir, exe_dir

    app_dir = Path(__file__).resolve().parent
    # In source mode, also check for a local legacy_bins beside main.py
    local_bins = app_dir / "legacy_bins"
    default_bins = local_bins if local_bins.is_dir() else app_dir.parent / "legacy_bins"
    return app_dir, default_bins, app_dir


def main() -> None:
    resource_dir, default_bins_dir, work_base_dir = _resolve_paths()
    app = DalotApp(
        app_dir=resource_dir,
        default_bins_dir=default_bins_dir,
        work_base_dir=work_base_dir,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
