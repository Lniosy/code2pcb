"""KiCad 封装库 — 真实焊盘定义，用于 PCB 布局生成"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PadDef:
    """焊盘定义"""
    name: str           # "1", "2", "A1" 等
    pad_type: str       # "smd" | "tht" | "np_tht_hole" | "connect"
    shape: str          # "rect" | "roundrect" | "circle" | "oval" | "custom"
    at: tuple[float, float]  # (x, y) mm, 相对 footprint 原点
    size: tuple[float, float]  # (w, h) mm
    drill: Optional[float] = None  # 钻孔直径 (THT)
    layers: list[str] = field(default_factory=lambda: ["F.Cu", "F.Paste", "F.Mask"])
    roundrect_rratio: float = 0.25
    net: Optional[str] = None  # 分配的网络名


@dataclass
class FootprintDef:
    """完整封装定义"""
    name: str            # KiCad footprint 路径
    description: str
    pads: list[PadDef] = field(default_factory=list)
    courtyard: tuple[float, float, float, float] = field(default=(0, 0, 0, 0))  # x, y, w, h
    ref_offset: tuple[float, float] = (0, -2)
    value_offset: tuple[float, float] = (0, 2)
    body_rect: Optional[tuple[float, float, float, float]] = None  # x, y, w, h for silkscreen body


# ============================================================
# SMD 贴片封装
# ============================================================

def _cap_0402() -> FootprintDef:
    """0402 贴片电容/电阻 1.0×0.5mm"""
    return FootprintDef(
        name="Resistor_SMD:R_0402_1005Metric",
        description="0402 SMD 1.0x0.5mm",
        pads=[
            PadDef("1", "smd", "roundrect", (-0.5, 0), (0.5, 0.6), roundrect_rratio=0.25),
            PadDef("2", "smd", "roundrect", (0.5, 0), (0.5, 0.6), roundrect_rratio=0.25),
        ],
        courtyard=(-0.9, -0.7, 1.8, 1.4),
        body_rect=(-0.5, -0.25, 1.0, 0.5),
    )


def _cap_0603() -> FootprintDef:
    """0603 贴片电容/电阻 1.6×0.8mm"""
    return FootprintDef(
        name="Resistor_SMD:R_0603_1608Metric",
        description="0603 SMD 1.6x0.8mm",
        pads=[
            PadDef("1", "smd", "roundrect", (-0.85, 0), (1.0, 0.95), roundrect_rratio=0.25),
            PadDef("2", "smd", "roundrect", (0.85, 0), (1.0, 0.95), roundrect_rratio=0.25),
        ],
        courtyard=(-1.4, -0.95, 2.8, 1.9),
        body_rect=(-0.8, -0.4, 1.6, 0.8),
    )


def _cap_0805() -> FootprintDef:
    """0805 贴片电容 2.0×1.25mm"""
    return FootprintDef(
        name="Capacitor_SMD:C_0805_2012Metric",
        description="0805 SMD 2.0x1.25mm",
        pads=[
            PadDef("1", "smd", "roundrect", (-0.95, 0), (1.2, 1.45), roundrect_rratio=0.25),
            PadDef("2", "smd", "roundrect", (0.95, 0), (1.2, 1.45), roundrect_rratio=0.25),
        ],
        courtyard=(-1.65, -1.0, 3.3, 2.0),
        body_rect=(-1.0, -0.625, 2.0, 1.25),
    )


# ============================================================
# QFP 封装
# ============================================================

def _lqfp_48() -> FootprintDef:
    """LQFP-48 7×7mm pitch 0.5mm"""
    pads = []
    # 每边12个引脚，共48
    side = 12
    half = 7.0 / 2  # 3.5mm
    for i in range(side):
        offset = (i - (side - 1) / 2) * 0.5
        # Bottom (1-12), Left→Right
        pads.append(PadDef(str(i + 1), "smd", "rect", (offset, -half), (0.3, 1.2),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        # Right (13-24), Bottom→Top
        pads.append(PadDef(str(side + i + 1), "smd", "rect", (half, -offset), (1.2, 0.3),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        # Top (25-36), Right→Left
        pads.append(PadDef(str(2 * side + i + 1), "smd", "rect", (-offset, half), (0.3, 1.2),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        # Left (37-48), Top→Bottom
        pads.append(PadDef(str(3 * side + i + 1), "smd", "rect", (-half, offset), (1.2, 0.3),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
    return FootprintDef(
        name="Package_QFP:LQFP-48_7x7mm_P0.5mm",
        description="LQFP-48 7x7mm P0.5mm",
        pads=pads,
        courtyard=(-4.0, -4.0, 8.0, 8.0),
        body_rect=(-3.5, -3.5, 7.0, 7.0),
    )


def _lqfp_56() -> FootprintDef:
    """LQFP-56 7×7mm pitch 0.4mm"""
    pads = []
    side = 14
    half = 7.0 / 2
    for i in range(side):
        offset = (i - (side - 1) / 2) * 0.4
        pads.append(PadDef(str(i + 1), "smd", "rect", (offset, -half), (0.25, 1.0),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(side + i + 1), "smd", "rect", (half, -offset), (1.0, 0.25),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(2 * side + i + 1), "smd", "rect", (-offset, half), (0.25, 1.0),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(3 * side + i + 1), "smd", "rect", (-half, offset), (1.0, 0.25),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
    return FootprintDef(
        name="Package_QFP:LQFP-56_7x7mm_P0.4mm",
        description="LQFP-56 7x7mm P0.4mm",
        pads=pads,
        courtyard=(-4.2, -4.2, 8.4, 8.4),
        body_rect=(-3.5, -3.5, 7.0, 7.0),
    )


def _lqfp_64() -> FootprintDef:
    """LQFP-64 10×10mm pitch 0.5mm"""
    pads = []
    side = 16
    half = 10.0 / 2
    for i in range(side):
        offset = (i - (side - 1) / 2) * 0.5
        pads.append(PadDef(str(i + 1), "smd", "rect", (offset, -half), (0.3, 1.2),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(side + i + 1), "smd", "rect", (half, -offset), (1.2, 0.3),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(2 * side + i + 1), "smd", "rect", (-offset, half), (0.3, 1.2),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(3 * side + i + 1), "smd", "rect", (-half, offset), (1.2, 0.3),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
    return FootprintDef(
        name="Package_QFP:LQFP-64_10x10mm_P0.5mm",
        description="LQFP-64 10x10mm P0.5mm",
        pads=pads,
        courtyard=(-5.7, -5.7, 11.4, 11.4),
        body_rect=(-5.0, -5.0, 10.0, 10.0),
    )


# ============================================================
# DIP 封装
# ============================================================

def _dip_28() -> FootprintDef:
    """DIP-28 300mil"""
    pads = []
    for i in range(14):
        y = -16.51 + i * 2.54
        pads.append(PadDef(str(i + 1), "tht", "oval", (-7.62, y), (1.6, 1.6), drill=0.8,
                           layers=["*.Cu", "*.Mask"]))
        pads.append(PadDef(str(28 - i), "tht", "oval", (7.62, y), (1.6, 1.6), drill=0.8,
                           layers=["*.Cu", "*.Mask"]))
    return FootprintDef(
        name="Package_DIP:DIP-28_W7.62mm",
        description="DIP-28 7.62mm wide",
        pads=pads,
        courtyard=(-8.9, -17.9, 17.8, 35.8),
        body_rect=(-3.81, -16.51, 7.62, 33.02),
    )


# ============================================================
# 按钮封装
# ============================================================

def _btn_smd() -> FootprintDef:
    """SMD 贴片按钮 4.0×3.6mm"""
    return FootprintDef(
        name="Button_SMD:SW_Push_1P4x3.6mm",
        description="SMD Push Button 4.0x3.6mm",
        pads=[
            PadDef("1", "smd", "roundrect", (-2.25, -1.75), (1.3, 1.0), roundrect_rratio=0.25),
            PadDef("2", "smd", "roundrect", (2.25, -1.75), (1.3, 1.0), roundrect_rratio=0.25),
            PadDef("3", "smd", "roundrect", (-2.25, 1.75), (1.3, 1.0), roundrect_rratio=0.25),
            PadDef("4", "smd", "roundrect", (2.25, 1.75), (1.3, 1.0), roundrect_rratio=0.25),
        ],
        courtyard=(-3.2, -2.8, 6.4, 5.6),
        body_rect=(-2.0, -1.8, 4.0, 3.6),
    )


# ============================================================
# 晶振封装
# ============================================================

def _osc_smd_3225() -> FootprintDef:
    """SMD 晶振 ABC-3225 3.2×2.5mm"""
    return FootprintDef(
        name="Oscillator:Oscillator_SMD_ABC-3225-4Pin_3.2x2.5mm",
        description="SMD Oscillator 3.2x2.5mm 4-pin",
        pads=[
            PadDef("1", "smd", "rect", (-1.1, -0.7), (0.9, 1.0),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("2", "smd", "rect", (1.1, -0.7), (0.9, 1.0),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("3", "smd", "rect", (1.1, 0.7), (0.9, 1.0),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("4", "smd", "rect", (-1.1, 0.7), (0.9, 1.0),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
        ],
        courtyard=(-2.1, -1.8, 4.2, 3.6),
        body_rect=(-1.6, -1.25, 3.2, 2.5),
    )


# ============================================================
# PinHeader 封装
# ============================================================

def _pinheader_1x03() -> FootprintDef:
    """1×3 PinHeader 2.54mm"""
    pads = []
    for i in range(3):
        pads.append(PadDef(str(i + 1), "tht", "circle", (0, i * 2.54), (1.7, 1.7), drill=1.0,
                           layers=["*.Cu", "*.Mask"]))
    return FootprintDef(
        name="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
        description="PinHeader 1x03 P2.54mm Vertical",
        pads=pads,
        courtyard=(-1.5, -1.5, 3.0, 8.62),
    )


def _pinheader_1x04() -> FootprintDef:
    """1×4 PinHeader 2.54mm"""
    pads = []
    for i in range(4):
        pads.append(PadDef(str(i + 1), "tht", "circle", (0, i * 2.54), (1.7, 1.7), drill=1.0,
                           layers=["*.Cu", "*.Mask"]))
    return FootprintDef(
        name="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        description="PinHeader 1x04 P2.54mm Vertical",
        pads=pads,
        courtyard=(-1.5, -1.5, 3.0, 11.16),
    )


# ============================================================
# SOT-23 封装
# ============================================================

def _sot_23_6() -> FootprintDef:
    """SOT-23-6"""
    return FootprintDef(
        name="Package_TO_SOT_SMD:SOT-23-6",
        description="SOT-23-6",
        pads=[
            PadDef("1", "smd", "rect", (-0.95, -1.35), (0.65, 1.05),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("2", "smd", "rect", (0.0, -1.35), (0.65, 1.05),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("3", "smd", "rect", (0.95, -1.35), (0.65, 1.05),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("4", "smd", "rect", (0.95, 1.35), (0.65, 1.05),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("5", "smd", "rect", (0.0, 1.35), (0.65, 1.05),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
            PadDef("6", "smd", "rect", (-0.95, 1.35), (0.65, 1.05),
                   layers=["F.Cu", "F.Paste", "F.Mask"]),
        ],
        courtyard=(-1.7, -2.0, 3.4, 4.0),
        body_rect=(-1.45, -1.1, 2.9, 2.2),
    )


# ============================================================
# SOIC 封装
# ============================================================

def _soic_8() -> FootprintDef:
    """SOIC-8 3.9×4.9mm"""
    pads = []
    for i in range(4):
        x = -2.75 + i * 1.27
        pads.append(PadDef(str(i + 1), "smd", "rect", (x, -2.6), (0.6, 1.5),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
        pads.append(PadDef(str(8 - i), "smd", "rect", (x, 2.6), (0.6, 1.5),
                           layers=["F.Cu", "F.Paste", "F.Mask"]))
    return FootprintDef(
        name="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        description="SOIC-8 3.9x4.9mm P1.27mm",
        pads=pads,
        courtyard=(-2.95, -3.45, 5.9, 6.9),
        body_rect=(-1.95, -2.45, 3.9, 4.9),
    )


# ============================================================
# 封装查找表
# ============================================================

FOOTPRINT_DEFS: dict[str, FootprintDef] = {}


def _register_all():
    """注册所有封装定义"""
    defs = [
        _cap_0402(), _cap_0603(), _cap_0805(),
        _lqfp_48(), _lqfp_56(), _lqfp_64(),
        _dip_28(),
        _btn_smd(), _osc_smd_3225(),
        _pinheader_1x03(), _pinheader_1x04(),
        _sot_23_6(), _soic_8(),
    ]
    for fd in defs:
        FOOTPRINT_DEFS[fd.name] = fd


_register_all()


def get_footprint_def(footprint_name: str) -> Optional[FootprintDef]:
    """
    根据封装名查找定义，支持模糊匹配。
    
    Args:
        footprint_name: KiCad 封装名，如 "Resistor_SMD:R_0402_1005Metric"
    
    Returns:
        FootprintDef 或 None
    """
    # 精确匹配
    if footprint_name in FOOTPRINT_DEFS:
        return FOOTPRINT_DEFS[footprint_name]
    
    # 模糊匹配: 取最后一段
    short = footprint_name.split(":")[-1]
    for name, fd in FOOTPRINT_DEFS.items():
        if name.split(":")[-1] == short:
            return fd
    
    # 按关键词匹配
    name_lower = footprint_name.lower()
    if "0402" in name_lower:
        return _cap_0402()
    if "0603" in name_lower:
        return _cap_0603()
    if "0805" in name_lower:
        return _cap_0805()
    if "lqfp-48" in name_lower:
        return _lqfp_48()
    if "lqfp-56" in name_lower:
        return _lqfp_56()
    if "lqfp-64" in name_lower:
        return _lqfp_64()
    if "dip-28" in name_lower:
        return _dip_28()
    if "sw_push" in name_lower or "button" in name_lower:
        return _btn_smd()
    if "oscillator" in name_lower or "3225" in name_lower:
        return _osc_smd_3225()
    if "1x03" in name_lower or "pinheader_1x03" in name_lower:
        return _pinheader_1x03()
    if "1x04" in name_lower or "pinheader_1x04" in name_lower:
        return _pinheader_1x04()
    if "sot-23-6" in name_lower:
        return _sot_23_6()
    if "soic-8" in name_lower:
        return _soic_8()
    
    # 默认用 SOIC-8
    return _soic_8()
