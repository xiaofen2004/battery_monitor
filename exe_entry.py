"""Standalone entry point; never use the one-file extraction folder for settings."""
import contextlib
import os
from pathlib import Path
import sys
import traceback


def main():
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    try:
        import app
        app.ROOT = root
        if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
            import unittest
            import test_monitor
            import test_app_modes
            report = Path(sys.argv[2]).resolve()
            with report.open("w", encoding="utf-8") as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                print("Frozen:", getattr(sys, "frozen", False))
                print("Executable:", sys.executable)
                print("Settings folder:", app.ROOT)
                suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module)
                                           for module in (test_monitor, test_app_modes))
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
                if not result.wasSuccessful():
                    return 1
                # Exercise bundled Excel engine and image/PDF export at runtime.
                import tempfile
                import pandas as pd
                import openpyxl
                import xlrd
                from matplotlib.figure import Figure
                with tempfile.TemporaryDirectory() as folder:
                    target = Path(folder)
                    frame = pd.DataFrame({"test": [1, 2, 3]})
                    frame.to_excel(target / "test.xlsx", index=False, engine="openpyxl")
                    assert pd.read_excel(target / "test.xlsx", engine="openpyxl").equals(frame)
                    fig = Figure()
                    fig.subplots().plot([0, 1, 2], [1, 3, 2])
                    for extension in ("png", "pdf"):
                        fig.savefig(target / ("test." + extension))
                        assert (target / ("test." + extension)).stat().st_size > 100
                print("Excel read/write and PNG/PDF export: OK")
            return 0
        app.MonitorApp().mainloop()
        return 0
    except Exception:
        detail = traceback.format_exc()
        log = root / "startup_error.log"
        try:
            log.write_text(detail, encoding="utf-8")
        except OSError:
            log = Path(os.environ.get("TEMP", str(root))) / "battery_strain_monitor_startup_error.log"
            log.write_text(detail, encoding="utf-8")
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "程序启动失败，错误详情已保存到：\n" + str(log), "电池监测", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
