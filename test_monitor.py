import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
import numpy as np

from data_io import StrainReader, BatteryData, parse_times, snapshot
from processing import Settings, infer_rate, preprocess, make_plot_data, stage_spans


class ProcessingTests(unittest.TestCase):
    def test_subplots_share_time_but_scale_independently(self):
        from plotting import draw_plot
        t = 1700000000 + np.arange(10.)
        y = np.column_stack([np.arange(10.), 100 * np.arange(10.), -1000 * np.arange(10.)])
        b = BatteryData(t, np.ones(10) * 4, np.ones(10) * 30, np.array(["恒流充电"] * 10), [], 10)
        cfg = Settings(channel="1,2,3", strain_hz=1, cutoff_hz=0, median_points=1,
                       plot_layout="subplots", include_battery=False)
        for combined in (False, True):
            data = make_plot_data(t, y, b if combined else None, replace(cfg, include_battery=combined))
            fig = draw_plot(data)
            self.assertEqual(len(fig.axes), 5 if combined else 3)
            first = fig.axes[0]
            for axis in fig.axes[1:]:
                self.assertTrue(first.get_shared_x_axes().joined(first, axis))
            self.assertFalse(first.get_shared_y_axes().joined(first, fig.axes[1]))
            self.assertLess(first.get_ylim()[1], fig.axes[1].get_ylim()[1] / 10)
            first.set_xlim(.02, .08)
            for axis in fig.axes:
                np.testing.assert_allclose(axis.get_xlim(), [.02, .08])
            if combined:
                self.assertTrue(all(len(axis.patches) > 0 for axis in fig.axes[:4]))

    def test_three_channels_strain_only_baselines_axes_and_export(self):
        from plotting import draw_plot
        from exporting import export_frame
        t = 1700000000 + np.arange(10.)
        y = np.column_stack([728 + np.arange(10.), -9000 + 2 * np.arange(10.), 851 - np.arange(10.)])
        cfg = Settings(channel="5,17,8", strain_hz=1, cutoff_hz=0, median_points=1,
                       include_battery=False, alignment="first", offset_s=999)
        data = make_plot_data(t, y, None, cfg)
        self.assertEqual(data.baselines, {"CH05": 728, "CH17": -9000, "CH08": 851})
        np.testing.assert_allclose(data.strain_t, np.arange(10.))
        for channel, expected in zip(data.strains, (np.arange(10.), 2 * np.arange(10.), -np.arange(10.))):
            np.testing.assert_allclose(data.strains[channel], expected)
        self.assertEqual(len(data.battery_t), 0)
        fig = draw_plot(data)
        self.assertEqual(len(fig.axes), 1)
        self.assertEqual(len(fig.axes[0].lines), 3)
        self.assertEqual(len(fig.axes[0].patches), 0)
        exported = export_frame(data)
        self.assertEqual(len(exported), 30)
        self.assertEqual(set(exported.series), {"strain"})
        self.assertEqual(set(exported.strain_channel), {"CH05", "CH08", "CH17"})
        raw = make_plot_data(t, y, None, replace(cfg, delta=False))
        for channel in data.strains:
            np.testing.assert_allclose(raw.strains[channel] - data.strains[channel], data.baselines[channel])

    def test_three_channels_combined_crop(self):
        from plotting import draw_plot
        t = 1700000000 + np.arange(10.)
        y = np.column_stack([np.arange(10.) + n for n in (10, 20, 30)])
        b = BatteryData(t[3:], np.ones(7), np.ones(7), np.array(["搁置"] * 7), [], 7)
        cfg = Settings(channel="CH01,CH02,CH03", strain_hz=1, cutoff_hz=0, median_points=1)
        data = make_plot_data(t, y, b, cfg)
        for values in data.strains.values():
            np.testing.assert_allclose(values, np.arange(3., 10.))
        fig = draw_plot(data)
        self.assertEqual(len(fig.axes), 3)
        self.assertEqual(len(fig.axes[0].lines), 3)
        with self.assertRaises(ValueError):
            make_plot_data(t, y, None, cfg)

    def test_channel_selection_validation(self):
        for value in ("", "CH05,5", "1,2,3,4", "CH21"):
            with self.assertRaises(ValueError):
                Settings(channel=value).validate()
    def test_detect_1_and_100_hz(self):
        for rate in (1, 100):
            t = 1700000000 + np.arange(1000) / rate
            self.assertEqual(infer_rate(t)[0], rate)

    def test_delta_is_original_first_before_crop(self):
        t = 1700000000 + np.arange(10.)
        y = 728 + np.arange(10.)
        cfg = Settings(strain_hz=1, cutoff_hz=0, median_points=1)
        b = BatteryData(t[3:], np.ones(7), np.ones(7), np.array(["搁置"] * 7), [], 7)
        result = make_plot_data(t, y, b, cfg)
        self.assertEqual(result.baseline, 728)
        self.assertEqual(result.strain[0], 3)
        original = make_plot_data(t, y, b, replace(cfg, delta=False))
        np.testing.assert_allclose(original.strain - result.strain, 728)

    def test_first_alignment_and_offset(self):
        t = 1700000000 + np.arange(10.)
        b = BatteryData(t + 100, np.ones(10), np.ones(10), np.array(["搁置"] * 10), [], 10)
        cfg = Settings(strain_hz=1, cutoff_hz=0, median_points=1, alignment="first", offset_s=2)
        result = make_plot_data(t, np.arange(10.), b, cfg)
        self.assertEqual(result.strain_t[0], 2)
        self.assertEqual(result.battery_t[0], 0)

    def test_antialias_and_dc(self):
        t = np.arange(20000) / 100
        y = 728 + np.sin(2 * np.pi * 10.1 * t)
        cfg = Settings(strain_hz=100, output_hz=1, cutoff_hz=0, median_points=1, delta=False)
        tt, yy, _, _ = preprocess(t, y, cfg)
        self.assertEqual(len(tt), 200)
        self.assertLess(np.std(yy[30:]), .001)
        self.assertAlmostEqual(np.mean(yy[30:]), 728, places=3)

    def test_causal_prefix_stability(self):
        t = np.arange(2000) / 100
        y = np.sin(t) + 20
        cfg = Settings(strain_hz=100)
        first = preprocess(t[:1000], y[:1000], cfg)[1]
        full = preprocess(t, y, cfg)[1]
        np.testing.assert_allclose(first, full[:len(first)])

    def test_gap_and_bounds(self):
        t = np.r_[np.arange(10.), 20 + np.arange(10.)]
        result = preprocess(t, np.ones(20), Settings(strain_hz=1))
        self.assertTrue(np.isnan(result[1]).any())
        with self.assertRaises(ValueError):
            preprocess(t, np.ones(20), Settings(strain_hz=1, output_hz=100))

    def test_stage_backgrounds_and_gap(self):
        spans = stage_spans(np.array([0, 1, 2, 3, 4, 10, 11.]),
                            ["搁置", "恒流放电", "恒流放电", "恒流恒压充电", "恒流恒压充电", "搁置", "搁置"])
        self.assertEqual(spans, [(0, 1, "搁置"), (1, 3, "放电"), (3, 4, "充电"), (10, 11, "搁置")])


class ReaderTests(unittest.TestCase):
    def test_multiple_channels_order_increment_and_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "strain.xls"
            header = b"\tCH01-\tCH05-\tCH08-\n"
            line1 = b"26/11/10 18:17:58.000\t1\t728\t850\n"
            line2 = b"26/11/10 18:17:59.000\t2\t730\t851\n"
            path.write_bytes(header + line1)
            reader = StrainReader(path, ("CH08", "CH01", "CH05"))
            self.assertEqual(reader.update()[1].tolist(), [[850, 1, 728]])
            with path.open("ab") as f:
                f.write(line2)
            self.assertEqual(reader.update()[1].tolist(), [[850, 1, 728], [851, 2, 730]])
            path.write_bytes(header + line1.replace(b"728", b"900"))
            self.assertEqual(reader.update()[1].tolist(), [[850, 1, 900]])
            with self.assertRaises(ValueError):
                StrainReader(path, ("CH17", "CH05")).update()
    def test_incremental_partial_row_rewrite_and_channel(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "strain.xls"
            header = b"\tCH01-\tCH05-\n"
            line1 = b"26/11/10 18:17:58.000\t1\t728\n"
            line2 = b"26/11/10 18:17:59.000\t2\t730\n"
            path.write_bytes(header + line1 + line2[:12])
            reader = StrainReader(path, "CH05")
            t, y = reader.update()
            self.assertEqual(y.tolist(), [728])
            with path.open("ab") as f:
                f.write(line2[12:])
            t, y = reader.update()
            self.assertEqual(y.tolist(), [728, 730])
            np.testing.assert_equal(reader.update()[1], y)
            self.assertEqual(StrainReader(path, "CH01").update()[1].tolist(), [1, 2])
            path.write_bytes(header + line1.replace(b"728", b"900"))
            self.assertEqual(reader.update()[1].tolist(), [900])

    def test_snapshot_and_backward_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "strain.xls"
            data = b"\tCH01-\tCH05-\n26/11/10 18:17:59.000\t1\t2\n26/11/10 18:17:58.000\t1\t2\n"
            path.write_bytes(data)
            with snapshot(path) as copy:
                self.assertEqual(copy.read_bytes(), data)
            self.assertFalse(copy.exists())
            with self.assertRaises(ValueError):
                StrainReader(path, "CH05").update()
            self.assertEqual(path.read_bytes(), data)

    def test_timestamp_units(self):
        t = parse_times(["2026-11-10 18:10:27", "2026-11-10 18:10:28"])
        self.assertAlmostEqual(t[1] - t[0], 1)
        self.assertGreater(t[0], 1_700_000_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
