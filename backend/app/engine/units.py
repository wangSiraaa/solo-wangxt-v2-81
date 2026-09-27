"""单位换算。

教学系统内部统一使用：
- 体积: 立方米 m^3
- 流量(强度): m^3/s（需配合时段长度换算为体积）
- 蒸发: m^3（体积）或 mm（水深，需配合水库水面面积换算）
"""
from __future__ import annotations

from enum import Enum


class FlowUnit(str, Enum):
    CMS = "m3/s"          # 立方米每秒
    CMD = "m3/d"          # 立方米每天
    CMH = "m3/month"      # 立方米每月（直接给整月体积）


class VolumeUnit(str, Enum):
    M3 = "m3"
    M3_X10_4 = "10^4m3"   # 万立方米
    M3_X10_8 = "10^8m3"   # 亿立方米


class EvapUnit(str, Enum):
    M3 = "m3"             # 直接给蒸发体积
    MM = "mm"             # 蒸发水深，乘以水面面积 m^2
    CM = "cm"


# 体积单位 -> 乘子（换算到 m^3）
VOLUME_FACTORS: dict[str, float] = {
    VolumeUnit.M3: 1.0,
    VolumeUnit.M3_X10_4: 1.0e4,
    VolumeUnit.M3_X10_8: 1.0e8,
}

EVAP_DEPTH_FACTORS: dict[str, float] = {
    EvapUnit.MM: 0.001,
    EvapUnit.CM: 0.01,
}


def flow_to_volume(value: float, unit: str, seconds: float) -> float:
    """把一个时段的平均流量强度换算成该时段的体积（m^3）。

    m3/month 视为"该月总体积"直接取值；如时段长度不是一个月，
    调用方应改用 m3 或在输入侧自行处理。
    """
    if unit == FlowUnit.CMS:
        return value * seconds
    if unit == FlowUnit.CMD:
        return value * (seconds / 86400.0)
    if unit == FlowUnit.CMH:
        return value
    raise ValueError(f"不支持的流量单位: {unit}")


def volume_to_canonical(value: float, unit: str) -> float:
    try:
        return value * VOLUME_FACTORS[unit]
    except KeyError as exc:
        raise ValueError(f"不支持的体积单位: {unit}") from exc


def evap_to_volume(value: float, unit: str, surface_area_m2: float | None) -> float:
    """蒸发量换算为 m^3。水深模式必须提供水面面积。"""
    if unit == EvapUnit.M3:
        return value
    if unit in EVAP_DEPTH_FACTORS:
        if not surface_area_m2:
            raise ValueError("蒸发以水深给定时必须提供水库水面面积 surface_area_m2")
        return value * EVAP_DEPTH_FACTORS[unit] * surface_area_m2
    raise ValueError(f"不支持的蒸发单位: {unit}")
