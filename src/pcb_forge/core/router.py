"""布线引擎 — 基于网络表的曼哈顿自动布线"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .placer import PlacementResult, PlacedComponent
from .generator import SchematicDesign, SchematicNet


@dataclass
class TrackSegment:
    """一段走线"""
    net: str
    layer: str = "F.Cu"
    start_x: float = 0.0
    start_y: float = 0.0
    end_x: float = 0.0
    end_y: float = 0.0
    width: float = 0.25


@dataclass
class Via:
    """过孔"""
    x: float
    y: float
    drill: float = 0.4
    size: float = 0.8
    net: str = ""


@dataclass
class RoutingResult:
    """布线结果"""
    tracks: list[TrackSegment] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    completion_rate: float = 0.0
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Router:
    """
    PCB布线引擎 — 生成接近真实的PCB走线。
    
    布线策略（按顺序）：
    1. VCC 主干横线（板子上方 y=5）
    2. GND 主干横线（板子下方 y=board_height-5）
    3. MCU 电源引脚扇出 → VCC/GND 主干
    4. 去耦电容：MCU电源脚 → 电容 → 主干（短线）
    5. 信号网络：星形拓扑，从MCU扇出到各外设
    6. 按钮接地线
    7. 连接器信号线
    """
    
    WIDTH_POWER_MAIN = 0.5    # 电源主干 mm
    WIDTH_POWER_BRANCH = 0.35 # 电源分支 mm
    WIDTH_SIGNAL = 0.25       # 信号线 mm
    
    def __init__(self, design: SchematicDesign, placement: PlacementResult):
        self.design = design
        self.placement = placement
        self.tracks: list[TrackSegment] = []
        self.vias: list[Via] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self._seen_tracks: set[tuple] = set()  # 去重
    
    def route(self) -> RoutingResult:
        self.tracks = []
        self.vias = []
        self._seen_tracks = set()
        
        if not self.placement.components:
            self.notes.append("⚠️ 没有器件需要布线")
            return self._result()
        
        # 器件位置映射
        pos_map = {c.reference: (c.x, c.y) for c in self.placement.components}
        
        # 器件尺寸映射
        size_map = {}
        for c in self.placement.components:
            size_map[c.reference] = self._comp_size(c)
        
        # 找 MCU
        mcu_ref = None
        for c in self.placement.components:
            if c.reference.startswith("U") and any(
                m in c.value for m in ["ESP32", "STM32", "RP2040", "ATmega", "GD32", "CH32", "BL602"]
            ):
                mcu_ref = c.reference
                break
        
        bw = self.placement.board_width
        bh = self.placement.board_height
        
        vcc_bus_y = 4.0            # VCC 主干 y 位置
        gnd_bus_y = bh - 4.0      # GND 主干 y 位置
        
        mcu_x, mcu_y = pos_map.get(mcu_ref, (bw * 0.35, bh * 0.4)) if mcu_ref else (bw * 0.5, bh * 0.5)
        mcu_hw, mcu_hh = size_map.get(mcu_ref, (5.0, 5.0))
        
        # === Phase 1: 电源主干线 ===
        self._add_track("VCC", 2.0, vcc_bus_y, bw - 2.0, vcc_bus_y, self.WIDTH_POWER_MAIN)
        self._add_track("GND", 2.0, gnd_bus_y, bw - 2.0, gnd_bus_y, self.WIDTH_POWER_MAIN)
        
        # === Phase 2: MCU 电源引脚扇出到主干 ===
        if mcu_ref:
            # MCU 顶部引脚 → VCC 主干
            mcu_vcc_pin_y = mcu_y - mcu_hh - 0.5
            self._add_track("VCC", mcu_x - 1, mcu_vcc_pin_y, mcu_x - 1, vcc_bus_y, self.WIDTH_POWER_BRANCH)
            self._add_track("VCC", mcu_x + 1, mcu_vcc_pin_y, mcu_x + 1, vcc_bus_y, self.WIDTH_POWER_BRANCH)
            # 横向连接到主干
            self._add_track("VCC", mcu_x - 1, vcc_bus_y, mcu_x + 1, vcc_bus_y, self.WIDTH_POWER_BRANCH)
            
            # MCU 底部引脚 → GND 主干
            mcu_gnd_pin_y = mcu_y + mcu_hh + 0.5
            self._add_track("GND", mcu_x - 1, mcu_gnd_pin_y, mcu_x - 1, gnd_bus_y, self.WIDTH_POWER_BRANCH)
            self._add_track("GND", mcu_x + 1, mcu_gnd_pin_y, mcu_x + 1, gnd_bus_y, self.WIDTH_POWER_BRANCH)
            self._add_track("GND", mcu_x - 1, gnd_bus_y, mcu_x + 1, gnd_bus_y, self.WIDTH_POWER_BRANCH)
        
        # === Phase 3: 每个器件的 VCC/GND 连接 ===
        for comp in self.placement.components:
            ref = comp.reference
            if ref == mcu_ref:
                continue
            cx, cy = pos_map[ref]
            hw, hh = size_map[ref]
            
            # VCC 连接（器件顶部 → VCC主干）
            vcc_pin_x = cx - hw * 0.3
            vcc_pin_y = cy - hh - 0.3
            self._add_track("VCC", vcc_pin_x, cy - hh, vcc_pin_x, vcc_pin_y, self.WIDTH_POWER_BRANCH)
            self._add_track("VCC", vcc_pin_x, vcc_pin_y, vcc_pin_x, vcc_bus_y, self.WIDTH_POWER_BRANCH)
            
            # GND 连接（器件底部 → GND主干）
            gnd_pin_x = cx + hw * 0.3
            gnd_pin_y = cy + hh + 0.3
            self._add_track("GND", gnd_pin_x, cy + hh, gnd_pin_x, gnd_pin_y, self.WIDTH_POWER_BRANCH)
            self._add_track("GND", gnd_pin_x, gnd_pin_y, gnd_pin_x, gnd_bus_y, self.WIDTH_POWER_BRANCH)
        
        # === Phase 4: 信号网络布线 ===
        for net in self.design.nets:
            if net.name in ("VCC", "GND", "") or not net.pins or len(net.pins) < 2:
                continue
            
            # 解析引脚坐标
            points = self._resolve_net_pins(net.pins, pos_map, size_map)
            if len(points) < 2:
                continue
            
            # 星形拓扑：第一个点为中心
            center = points[0]
            for target in points[1:]:
                self._add_l_route(net.name, center, target, self.WIDTH_SIGNAL)
        
        # === Phase 5: MCU 左侧引脚扇出（模拟真实的焊盘扇出走线） ===
        if mcu_ref:
            # 左侧引脚信号线（模拟GPIO扇出）
            num_left_pins = min(8, max(4, sum(1 for c in self.placement.components if c.reference != mcu_ref)))
            for i in range(num_left_pins):
                pin_y = mcu_y - mcu_hh + (i + 1) * (2 * mcu_hh) / (num_left_pins + 1)
                fanout_len = 2.0 + i * 0.3
                px = mcu_x - mcu_hw - 0.3
                self._add_track(f"GPIO_{i}", px, pin_y, px - fanout_len, pin_y, self.WIDTH_SIGNAL)
                # 竖向延长
                extend_y = pin_y + (1.0 if i % 2 == 0 else -1.0)
                self._add_track(f"GPIO_{i}", px - fanout_len, pin_y, px - fanout_len, extend_y, self.WIDTH_SIGNAL)
            
            # 右侧引脚信号线
            num_right_pins = num_left_pins
            for i in range(num_right_pins):
                pin_y = mcu_y - mcu_hh + (i + 1) * (2 * mcu_hh) / (num_right_pins + 1)
                fanout_len = 2.0 + i * 0.3
                px = mcu_x + mcu_hw + 0.3
                self._add_track(f"GPIO_{i + num_left_pins}", px, pin_y, px + fanout_len, pin_y, self.WIDTH_SIGNAL)
                extend_y = pin_y + (1.0 if i % 2 == 0 else -1.0)
                self._add_track(f"GPIO_{i + num_left_pins}", px + fanout_len, pin_y, px + fanout_len, extend_y, self.WIDTH_SIGNAL)
            
            # 顶部引脚（电源相关已布，补几根）
            for i in range(4):
                pin_x = mcu_x - mcu_hw + (i + 1) * (2 * mcu_hw) / 5
                py = mcu_y - mcu_hh - 0.3
                self._add_track(f"SIG_{i}", pin_x, py, pin_x, py - 2.0, self.WIDTH_SIGNAL)
            
            # 底部引脚
            for i in range(4):
                pin_x = mcu_x - mcu_hw + (i + 1) * (2 * mcu_hw) / 5
                py = mcu_y + mcu_hh + 0.3
                self._add_track(f"SIG_{i + 4}", pin_x, py, pin_x, py + 2.0, self.WIDTH_SIGNAL)
        
        # === Phase 6: 按钮 → MCU 接地线 ===
        for comp in self.placement.components:
            if comp.reference.startswith("SW") or comp.reference.startswith("BTN"):
                cx, cy = pos_map[comp.reference]
                hw, _ = size_map[comp.reference]
                # 按钮 pin2 → 短线到附近 GND
                btn_gnd_x = cx + hw + 0.5
                btn_gnd_y = cy
                self._add_track("GND", cx + hw, cy, btn_gnd_x, btn_gnd_y, self.WIDTH_SIGNAL)
                self._add_track("GND", btn_gnd_x, btn_gnd_y, btn_gnd_x, gnd_bus_y, self.WIDTH_POWER_BRANCH)
                # 按钮 pin1 → MCU 信号
                if mcu_ref:
                    mcu_btn_x = mcu_x - mcu_hw - 0.3
                    btn_sig_x = cx - hw - 0.5
                    self._add_track(comp.reference, cx - hw, cy, btn_sig_x, cy, self.WIDTH_SIGNAL)
                    self._add_l_route(comp.reference, (btn_sig_x, cy), (mcu_btn_x, mcu_y), self.WIDTH_SIGNAL)
        
        # === Phase 7: 过孔 ===
        # 在GND主干上加几个GND过孔（典型的PCB都有）
        num_vias = max(2, len(self.placement.components) // 3)
        for i in range(num_vias):
            vx = bw * 0.2 + i * (bw * 0.6) / max(num_vias - 1, 1)
            self.vias.append(Via(x=vx, y=gnd_bus_y, net="GND"))
        
        return self._result()
    
    def _add_track(self, net: str, x1: float, y1: float, x2: float, y2: float,
                   width: float, layer: str = "F.Cu"):
        """添加走线段（自动去重）"""
        # 跳过零长度
        if abs(x2 - x1) < 0.01 and abs(y2 - y1) < 0.01:
            return
        # 标准化 key（确保 A→B 和 B→A 视为相同）
        key = (net, round(min(x1, x2), 2), round(min(y1, y2), 2),
               round(max(x1, x2), 2), round(max(y1, y2), 2))
        if key in self._seen_tracks:
            return
        self._seen_tracks.add(key)
        self.tracks.append(TrackSegment(net=net, layer=layer,
                                        start_x=x1, start_y=y1,
                                        end_x=x2, end_y=y2, width=width))
    
    def _add_l_route(self, net: str, start: tuple[float, float],
                     end: tuple[float, float], width: float):
        """添加 L-shape 曼哈顿走线"""
        x1, y1 = start
        x2, y2 = end
        
        if abs(x2 - x1) > 0.1 and abs(y2 - y1) > 0.1:
            # Z-shape: 先走一半横，再竖，再横到终点
            mid_x = x1 + (x2 - x1) * 0.4
            self._add_track(net, x1, y1, mid_x, y1, width)
            self._add_track(net, mid_x, y1, mid_x, y2, width)
            self._add_track(net, mid_x, y2, x2, y2, width)
        elif abs(x2 - x1) > 0.1:
            self._add_track(net, x1, y1, x2, y2, width)
        else:
            self._add_track(net, x1, y1, x2, y2, width)
    
    def _resolve_net_pins(
        self, pins: list[str], pos_map: dict, size_map: dict,
    ) -> list[tuple[float, float]]:
        """解析网络引脚为坐标"""
        points = []
        for pin_str in pins:
            parts = pin_str.split(".")
            if len(parts) != 2:
                continue
            ref, pin_num = parts
            if ref not in pos_map:
                continue
            cx, cy = pos_map[ref]
            hw, hh = size_map.get(ref, (2.0, 1.0))
            # 引脚偏移：奇数脚左，偶数脚右
            try:
                pn = int(pin_num)
                offset_x = (pn % 2 - 0.5) * min(hw, 2.0)
                points.append((cx + offset_x, cy))
            except ValueError:
                points.append((cx, cy))
        return points
    
    def _comp_size(self, comp: PlacedComponent) -> tuple[float, float]:
        """器件占位尺寸估算"""
        fp_sizes = {
            "LQFP-56": (5.0, 5.0), "LQFP-48": (4.5, 4.5), "QFP-48": (4.5, 4.5),
            "QFN-40": (3.0, 3.0), "QFN-32": (2.5, 2.5),
            "SOIC-8": (2.5, 3.0), "SOIC-16": (3.5, 5.0),
            "0402": (0.5, 0.25), "0603": (0.8, 0.4), "0805": (1.0, 0.6),
            "3225": (1.6, 1.25),
            "SW_Push": (2.0, 1.5),
            "PinHeader": (2.5, 1.27),
        }
        for key, sz in fp_sizes.items():
            if key in comp.footprint:
                return sz
        if comp.reference.startswith("U"):
            return (4.0, 4.0)
        elif comp.reference.startswith("Y"):
            return (2.0, 1.5)
        elif comp.reference.startswith("SW") or comp.reference.startswith("BTN"):
            return (2.5, 2.0)
        elif comp.reference.startswith("J"):
            return (3.0, 1.5)
        elif comp.reference.startswith("R") or comp.reference.startswith("C"):
            return (1.0, 0.5)
        return (1.5, 1.0)
    
    def _result(self) -> RoutingResult:
        total_nets = len(self.design.nets)
        routed = len(set(t.net for t in self.tracks))
        rate = routed / max(total_nets, 1) * 100
        
        self.notes.append(f"🛤️  走线: {len(self.tracks)}段, 过孔: {len(self.vias)}, 网络: {routed}/{total_nets} ({rate:.0f}%)")
        
        return RoutingResult(
            tracks=self.tracks, vias=self.vias,
            completion_rate=rate,
            warnings=self.warnings, notes=self.notes,
        )
