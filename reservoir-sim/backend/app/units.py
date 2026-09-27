"""单位换算：所有外部输入先换算为 SI（m、m³、m³/s）再进入引擎。

支持的单位：
  * 流量：m3/s、L/s、m3/h、万m3/d
  * 水量（库容）：m3、万m3、百万m3
  * 蒸发：mm/step（每步毫米）、mm/d（每天毫米，按步长折算）
"""
from __future__ import annotations

FLOW_TO_SI = {
    "m3/s": 1.0,
    "L/s": 1e-3,
    "m3/h": 1.0 / 3600.0,
    "万m3/d": 1e4 / 86400.0,
}

VOLUME_TO_SI = {
    "m3": 1.0,
    "万m3": 1e4,
    "百万m3": 1e6,
}

EVAP_UNITS = ("mm/step", "mm/d")


def flow_factor(unit: str) -> float:
    if unit not in FLOW_TO_SI:
        raise ValueError(f"不支持的流量单位：{unit}（可选：{list(FLOW_TO_SI)}）")
    return FLOW_TO_SI[unit]


def volume_factor(unit: str) -> float:
    if unit not in VOLUME_TO_SI:
        raise ValueError(f"不支持的库容单位：{unit}（可选：{list(VOLUME_TO_SI)}）")
    return VOLUME_TO_SI[unit]


def flow_to_si(values: list[float | None], unit: str) -> list[float | None]:
    """流量序列 → m³/s，缺测值（None）原样保留。"""
    f = flow_factor(unit)
    return [None if v is None else v * f for v in values]


def volume_to_si(value: float, unit: str) -> float:
    return value * volume_factor(unit)


def evap_to_si(values: list[float], unit: str, dt_seconds: float) -> list[float]:
    """蒸发序列 → m/步。"""
    if unit == "mm/step":
        return [v * 1e-3 for v in values]
    if unit == "mm/d":
        return [v * 1e-3 * dt_seconds / 86400.0 for v in values]
    raise ValueError(f"不支持的蒸发单位：{unit}（可选：{list(EVAP_UNITS)}）")
