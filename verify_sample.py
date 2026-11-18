"""可选：对用户示例执行真实文件集成检查。"""
import hashlib
import json
import sys
from tempfile import TemporaryDirectory
import time
from pathlib import Path
from dataclasses import replace
from data_io import StrainReader, BatteryReader, stamp
from processing import Settings, make_plot_data
from plotting import draw_plot, clock_text


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def main(output_folder):
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parent
    source = root.parent / "data/20261111"
    strain = source / "20261110-strain.xls"
    battery = source / "20261011-battery-0003.xlsx"
    before = {p.name: (stamp(p), sha256(p)) for p in [strain, battery]}
    begin = time.perf_counter()
    reader = StrainReader(strain, "CH05")
    t, y = reader.update()
    b = BatteryReader().update(battery)
    data = make_plot_data(t, y, b, Settings())
    duration = time.perf_counter() - begin
    output = Path(output_folder)
    output.mkdir(exist_ok=True)
    figure = draw_plot(data)
    figure.savefig(output / "sample_preview.png", dpi=140)
    begin = time.perf_counter()
    t2, y2 = reader.update()
    assert len(t) == len(t2) and (y == y2).all()
    unchanged_seconds = time.perf_counter() - begin
    after = {p.name: (stamp(p), sha256(p)) for p in [strain, battery]}
    assert before == after, "Source files changed"
    report = {"strain_rows": len(t), "channels": reader.channels,
              "strain_first": clock_text(t[0]), "strain_last": clock_text(t[-1]),
              "baseline_CH05": float(y[0]), "battery_rows": b.rows,
              "battery_first": clock_text(b.time[0]), "battery_last": clock_text(b.time[-1]),
              "first_refresh_seconds": duration, "unchanged_read_seconds": unchanged_seconds,
              "sources_unchanged_sha256": True, "source_hashes": {k: v[1] for k, v in before.items()},
              "notes": data.notes}
    (output / "sample_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    with TemporaryDirectory() as folder:
        main(folder)
