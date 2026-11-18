"""导出各通道自己的处理数据和初值，不生成虚构的电池记录。"""
import pandas as pd
from plotting import clock_text


def export_frame(data):
    frames = []
    strains = data.strains or {data.settings.channel: data.strain}
    for channel, values in strains.items():
        frames.append(pd.DataFrame({
            "series": "strain", "elapsed_s": data.strain_t, "value": values,
            "unit": "delta_microstrain" if data.settings.delta else "microstrain",
            "strain_channel": channel,
            "strain_baseline_microstrain": data.baselines.get(channel, data.baseline),
        }))
    if data.settings.include_battery:
        for series, values, unit in [("voltage", data.voltage, "V"), ("current", data.current, "A")]:
            frames.append(pd.DataFrame({"series": series, "elapsed_s": data.battery_t,
                                        "value": values, "unit": unit,
                                        "strain_channel": "", "strain_baseline_microstrain": float("nan")}))
    result = pd.concat(frames, ignore_index=True)
    result["alignment"] = data.settings.alignment if data.settings.include_battery else "strain_start"
    result["origin"] = clock_text(data.origin) if data.origin else "first_sample"
    return result
