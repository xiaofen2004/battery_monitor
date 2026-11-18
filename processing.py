"""时间对齐、应变低通及降采样；不改变任何源文件。"""
from dataclasses import dataclass, field, replace
import re
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import butter, sosfilt, sosfilt_zi
from data_io import BatteryData, check_cancel


@dataclass(frozen=True)
class Settings:
    channel: str = "CH05"
    strain_hz: float = 0.0  # 0 = 根据时间自动识别
    output_hz: float = 1.0
    cutoff_hz: float = 0.2
    median_points: int = 5
    delta: bool = True
    alignment: str = "absolute"
    offset_s: float = 0.0
    battery_mode: str = "auto"
    include_battery: bool = True
    plot_layout: str = "overlay"
    time_unit: str = "min"

    @property
    def selected_channels(self):
        tokens = re.split(r"[,，;；\s]+", self.channel.strip())
        channels = []
        for token in tokens:
            match = re.fullmatch(r"(?:CH)?(\d{1,2})", token, re.I)
            if not match or not 1 <= int(match[1]) <= 20:
                raise ValueError("应变通道须为 CH01～CH20。")
            channels.append(f"CH{int(match[1]):02d}")
        if not 1 <= len(channels) <= 3 or len(set(channels)) != len(channels):
            raise ValueError("请选择 1～3 个不同的应变通道，不能重复。")
        return tuple(channels)

    def validate(self):
        self.selected_channels
        if self.plot_layout not in ("overlay", "subplots"):
            raise ValueError("请选择同图叠加或分通道子图。")
        if self.time_unit not in ("min", "s"):
            raise ValueError("时间单位须为 min 或 s。")
        if not all(np.isfinite(v) for v in (self.strain_hz, self.output_hz, self.cutoff_hz, self.offset_s)):
            raise ValueError("频率和偏移必须为有限数字。")
        if self.strain_hz < 0 or self.output_hz <= 0 or self.cutoff_hz < 0:
            raise ValueError("采样频率须为正数；自动采样率及关闭滤波请填 0。")
        if self.median_points < 1 or self.median_points % 2 == 0 or self.median_points > 501:
            raise ValueError("中值滤波点数须为 1～501 的奇数，填 1 关闭。")
        if self.alignment not in ("absolute", "first"):
            raise ValueError("未知时间对齐方式")


def infer_rate(t):
    """用整段密度识别 1/100 Hz；比单个时间差对采集抖动更稳健。"""
    if len(t) < 3 or t[-1] <= t[0]:
        raise ValueError("至少需要 3 条不同时间的应变记录才能自动判断采样率。")
    d = np.diff(t)
    positive = d[d > 0]
    if not len(positive):
        raise ValueError("应变时间戳不足以判断采样率，请手动填写。")
    dt = float(np.median(positive))
    typical = d[(d >= 0) & (d < max(5 * dt, 0.5))]
    measured = 1 / np.mean(typical) if len(typical) and np.mean(typical) > 0 else 1 / dt
    nominal = min((1., 100.), key=lambda n: abs(np.log(n / measured)))
    if abs(measured / nominal - 1) > .25:
        raise ValueError(f"估计应变采样率约 {measured:.3f} Hz，不能确认为 1/100 Hz，请手动填写。")
    return nominal, measured


def preprocess(t, y, cfg, cancel=None):
    cfg.validate()
    if not len(t):
        raise ValueError("应变数据为空。")
    baseline = float(y[0])
    if cfg.strain_hz:
        fs = cfg.strain_hz
        measured = (len(t) - 1) / (t[-1] - t[0]) if t[-1] > t[0] else fs
    else:
        fs, measured = infer_rate(t)
    target = cfg.output_hz
    if target > fs * (1 + 1e-6):
        raise ValueError(f"输出频率 {target:g} Hz 高于应变输入 {fs:g} Hz；本软件不做升采样。")
    if cfg.cutoff_hz and cfg.cutoff_hz >= min(fs, target) / 2:
        raise ValueError("低通截止频率必须小于输入及输出采样频率的一半。")
    # 即使用户关闭平滑，降采样前也保留抗混叠低通。
    cutoff = cfg.cutoff_hz or (.4 * target if target < fs else 0)
    notes = [f"应变输入按 {fs:g} Hz，时间记录估计 {measured:.3f} Hz；输出 {target:g} Hz",
             f"{cfg.channel} 原始首值 {baseline:.6f} με；" + ("绘制 Δμε" if cfg.delta else "绘制原始 με")]
    if cfg.strain_hz and abs(measured / fs - 1) > .25:
        notes.append("手动采样率与时间记录差异较大；保留真实时间，采样率仅控制滤波/重采样网格")
    if cutoff:
        notes.append(f"6 阶因果低通 {cutoff:g} Hz（存在相位延迟）；前置因果中值 {cfg.median_points} 点")
    if target < fs and not cfg.cutoff_hz:
        notes.append("平滑已关闭，但降采样仍启用抗混叠低通")
    duplicate = int(np.sum(np.diff(t) == 0))
    if duplicate:
        # 同时间样本取均值，而非人为编造子毫秒时间。
        unique, inv = np.unique(t, return_inverse=True)
        y = np.bincount(inv, weights=y) / np.bincount(inv)
        t = unique
        notes.append(f"{duplicate} 个重复时间的应变记录已按同时间均值合并")
    breaks = np.flatnonzero(np.diff(t) > max(5 / fs, .5)) + 1
    boundaries = np.r_[0, breaks, len(t)]
    times, values = [], []
    if len(breaks):
        notes.append(f"应变存在 {len(breaks)} 个采样间断；断点处留白并重启滤波")
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        check_cancel(cancel)
        local_t, local_y = t[a:b], y[a:b]
        if cfg.delta:
            local_y = local_y - baseline
        length = int(np.floor((local_t[-1] - local_t[0]) * fs + 1e-5)) + 1
        if length > 25_000_000:
            raise ValueError("单段重采样点数超过 2500 万，请检查采样率或缩短文件。")
        grid = np.arange(length, dtype=float) / fs
        uniform = np.interp(grid, local_t - local_t[0], local_y)
        if cfg.median_points > 1:
            uniform = median_filter(uniform, size=cfg.median_points,
                                    origin=cfg.median_points // 2, mode="nearest")
        if cutoff:
            sos = butter(6, cutoff, fs=fs, output="sos")
            uniform, _ = sosfilt(sos, uniform, zi=sosfilt_zi(sos) * uniform[0])
        output_grid = np.arange(int(np.floor(grid[-1] * target + 1e-6)) + 1) / target
        out = np.interp(output_grid, grid, uniform)
        if times:
            times.append(np.array([local_t[0]]))
            values.append(np.array([np.nan]))
        times.append(local_t[0] + output_grid)
        values.append(out)
    return np.concatenate(times), np.concatenate(values), baseline, notes


def stage_kind(name):
    text = str(name).lower()
    if "放电" in text or "discharge" in text:
        return "放电"
    if "充电" in text or "charge" in text:
        return "充电"
    if any(x in text for x in ("搁置", "静置", "休息", "rest", "idle")):
        return "搁置"
    return "未知"


def stage_spans(t, stages):
    if not len(t):
        return []
    kinds = np.array([stage_kind(x) for x in stages])
    changes = np.r_[0, np.flatnonzero(kinds[1:] != kinds[:-1]) + 1, len(t)]
    # 保存间隔异常长时不猜测缺失区间的工步。
    positive = np.diff(t)
    positive = positive[positive > 0]
    gap = 5 * np.median(positive) if len(positive) else np.inf
    breaks = np.flatnonzero(np.diff(t) > gap) + 1
    changes = np.unique(np.r_[changes, breaks])
    spans = []
    for a, b in zip(changes[:-1], changes[1:]):
        end = t[b] if b < len(t) and b not in breaks else t[b - 1]
        if end > t[a]:
            spans.append((float(t[a]), float(end), kinds[a]))
    return spans


@dataclass
class PlotData:
    strain_t: np.ndarray
    strain: np.ndarray
    battery_t: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    spans: list
    origin: float
    baseline: float
    notes: list[str]
    settings: Settings
    strains: dict[str, np.ndarray] = field(default_factory=dict)
    baselines: dict[str, float] = field(default_factory=dict)


def make_plot_data(t, y, battery: BatteryData | None, cfg: Settings, cancel=None):
    cfg.validate()
    channels = cfg.selected_channels
    matrix = np.asarray(y)
    if matrix.ndim == 1:
        matrix = matrix[:, None]
    if matrix.shape != (len(t), len(channels)):
        raise ValueError("应变数据列数与所选通道数不一致。")
    strains, baselines, notes = {}, {}, []
    for i, channel in enumerate(channels):
        st, sy, baseline, channel_notes = preprocess(t, matrix[:, i], replace(cfg, channel=channel), cancel)
        strains[channel], baselines[channel] = sy, baseline
        notes.extend(n for n in channel_notes if n not in notes)
    first = channels[0]
    if not cfg.include_battery:
        origin = float(t[0])
        notes.append(f"仅应变模式：以应变首条记录为 0 秒；{len(channels)} 个通道分别滤波及扣除各自初值")
        notes.append(f"应变读取 {len(t):,} 行，每通道处理后 {len(st):,} 点；未读取电池文件")
        empty = np.array([], dtype=float)
        return PlotData(st - origin, strains[first], empty, empty, empty, [], origin,
                        baselines[first], notes, cfg, strains, baselines)
    if battery is None:
        raise ValueError("联合绘图需要选择电池文件。")
    bt = battery.time.copy()
    if cfg.alignment == "first":
        st = st - t[0] + cfg.offset_s
        bt -= bt[0]
        origin = 0.
        notes.append("两文件首点人为对齐；不代表实际同时发生")
    else:
        st += cfg.offset_s
        origin = max(float(t[0] + cfg.offset_s), float(bt[0]))
        if min(float(st[-1]), float(bt[-1])) < origin:
            raise ValueError("两文件实际时间没有重叠；请核对文件或选择首点对齐。")
        st -= origin
        bt -= origin
    spans = stage_spans(bt, battery.stages)
    spans = [(max(0., a), b, kind) for a, b, kind in spans if b > 0]
    sm, bm = st >= 0, bt >= 0
    # 以共同起点裁剪显示，不对记录结束后的数据作延长或预测。
    notes.extend(battery.notes)
    unknown = sorted(set(str(s) for s in battery.stages if stage_kind(s) == "未知"))
    if unknown:
        notes.append("未知工步不着色：" + ", ".join(unknown))
    notes.append(f"应变读取 {len(t):,} 点，处理后 {int(sm.sum()):,} 点；电压电流保留全部记录")
    strains = {channel: values[sm] for channel, values in strains.items()}
    return PlotData(st[sm], strains[first], bt[bm], battery.voltage[bm], battery.current[bm],
                    spans, origin, baselines[first], notes, cfg, strains, baselines)
