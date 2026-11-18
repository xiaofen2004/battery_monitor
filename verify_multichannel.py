"""真实示例的三通道/单独应变/联合模式验证与预览。"""
import json
import sys
from tempfile import TemporaryDirectory
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np
from data_io import StrainReader, BatteryReader, stamp
from processing import Settings, make_plot_data
from plotting import draw_plot
from exporting import export_frame
from verify_sample import sha256


def main(output_folder):
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parent
    source = root.parent / "data/20261111"
    strain = source / "20261110-strain.xls"
    battery = source / "20261011-battery-0003.xlsx"
    before = {p.name: (stamp(p), sha256(p)) for p in (strain, battery)}
    start = perf_counter()
    reader = StrainReader(strain, ("CH05", "CH08", "CH17"))
    t, y = reader.update()
    cfg = Settings(channel="CH05,CH08,CH17", include_battery=False)
    data = make_plot_data(t, y, None, cfg)
    out = Path(output_folder)
    out.mkdir(exist_ok=True)
    draw_plot(data).savefig(out / "three_channels_strain_only.png", dpi=140)
    split_data = replace(data, settings=replace(data.settings, plot_layout="subplots"))
    draw_plot(split_data).savefig(out / "three_channels_subplots.png", dpi=160)
    frame = export_frame(data)
    assert set(frame.series) == {"strain"}
    assert len(frame) == 3 * len(data.strain_t)
    assert all(values[0] == 0 for values in data.strains.values())
    raw = make_plot_data(t, y, None, replace(cfg, delta=False))
    for channel in data.strains:
        np.testing.assert_allclose(raw.strains[channel] - data.strains[channel], data.baselines[channel], atol=1e-5)
    b = BatteryReader().update(battery)
    combined = make_plot_data(t, y, b, replace(cfg, include_battery=True))
    draw_plot(combined).savefig(out / "three_channels_combined.png", dpi=140)
    split_combined = replace(combined, settings=replace(combined.settings, plot_layout="subplots"))
    draw_plot(split_combined).savefig(out / "three_channels_subplots_combined.png", dpi=160)
    after = {p.name: (stamp(p), sha256(p)) for p in (strain, battery)}
    assert before == after
    report = {"channels": list(data.strains), "strain_rows": len(t),
              "output_points_per_channel": len(data.strain_t), "baselines": data.baselines,
              "export_rows": len(frame), "source_files_unchanged": True,
              "all_three_modes_elapsed_s": perf_counter() - start, "notes": data.notes}
    (out / "multichannel_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    with TemporaryDirectory() as folder:
        main(folder)
