"""布线引擎 — 智能自动布线（基于真实网络连接的曼哈顿布线）"""

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
    PCB布线引擎。
    
    v0.1.0: 基于网络连接的曼哈顿布线（L-shape 走线）
    v1.0.0 计划: 集成 Freerouting 作为后端引擎
    v2.0.0 计划: 基于PathFinder的GPU加速布线
    
    布线策略：
    1. 先布电源线（宽线，底层）
    2. 电源分配网络（PDN）：从MCU到每个器件的VCC/GND
    3. 信号线：基于网络连接的曼哈顿L-shape
    4. 自动过孔切换层
    """
    
    # 默认线宽规则
    WIDTH_RULES = {
        "power": 0.5,      # 电源主干 0.5mm
        "power_dist": 0.35, # 电源分支 0.35mm
        "signal": 0.25,     # 信号线 0.25mm
        "high_speed": 0.2,  # 高速信号 0.2mm
    }
    
    def __init__(self, design: SchematicDesign, placement: PlacementResult):
        self.design = design
        self.placement = placement
        self.tracks: list[TrackSegment] = []
        self.vias: list[Via] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
    
    def route(self) -> RoutingResult:
        """
        执行自动布线。
        
        基于设计中的网络连接，为每个网络生成曼哈顿走线。
        """
        self.tracks = []
        self.vias = []
        self.warnings = []
        self.notes = []
        
        if not self.placement.components:
            self.notes.append("⚠️ 没有器件需要布线")
            return RoutingResult(
                tracks=[], vias=[], completion_rate=0.0,
                warnings=self.warnings, notes=self.notes,
            )
        
        # 构建器件位置映射
        pos_map: dict[str, tuple[float, float]] = {}
        for comp in self.placement.components:
            pos_map[comp.reference] = (comp.x, comp.y)
        
        # Phase 1: 电源主干线
        self._route_power_main()
        
        # Phase 2: 电源分配（从MCU到每个器件）
        self._route_power_distribution(pos_map)
        
        # Phase 3: 信号线布线
        self._route_signal_nets(pos_map)
        
        # Phase 4: 自动连接所有器件的电源（确保每个器件有 VCC/GND 连接）
        self._auto_connect_power(pos_map)
        
        # 统计
        total_nets = len(self.design.nets)
        routed_nets = len(set(t.net for t in self.tracks))
        completion = routed_nets / max(total_nets, 1) * 100
        
        self.notes.append(f"🛤️  布线完成: {routed_nets}/{total_nets} 网络 ({completion:.0f}%)")
        self.notes.append(f"🛤️  走线段数: {len(self.tracks)}, 过孔: {len(self.vias)}")
        
        return RoutingResult(
            tracks=self.tracks,
            vias=self.vias,
            completion_rate=completion,
            warnings=self.warnings,
            notes=self.notes,
        )
    
    def _route_power_main(self):
        """Phase 1: 电源主干线（贯穿板面）"""
        bw = self.placement.board_width
        bh = self.placement.board_height
        margin = 2.0
        pw = self.WIDTH_RULES["power"]
        
        # VCC 主干线 — 板子上方 y=20
        self.tracks.append(TrackSegment(
            net="VCC", layer="F.Cu",
            start_x=margin, start_y=20.0,
            end_x=bw - margin, end_y=20.0,
            width=pw,
        ))
        
        # GND 主干线 — 板子下方 y=board_height-20
        self.tracks.append(TrackSegment(
            net="GND", layer="B.Cu",
            start_x=margin, start_y=bh - 20.0,
            end_x=bw - margin, end_y=bh - 20.0,
            width=pw,
        ))
    
    def _route_power_distribution(self, pos_map: dict[str, tuple[float, float]]):
        """Phase 2: 从电源主干到每个器件的 VCC/GND 分配"""
        pw = self.WIDTH_RULES["power_dist"]
        
        # 找 MCU
        mcu_pos = None
        for comp in self.placement.components:
            if comp.reference.startswith("U") and any(
                m in comp.value for m in ["ESP32", "STM32", "RP2040", "ATmega"]
            ):
                mcu_pos = (comp.x, comp.y)
                break
        
        if mcu_pos:
            # MCU → VCC 主干
            self._add_l_route("VCC", mcu_pos, (mcu_pos[0], 20.0), pw, "F.Cu")
            # MCU → GND 主干（过孔切换到底层）
            self._add_l_route("GND", mcu_pos, (mcu_pos[0], self.placement.board_height - 20.0), pw, "B.Cu")
            self.vias.append(Via(x=mcu_pos[0], y=mcu_pos[1] + 6, net="GND"))
        
        # 其他器件 → VCC/GND（竖向分支连接到主干）
        for comp in self.placement.components:
            ref = comp.reference
            if ref.startswith("U") and mcu_pos and (comp.x, comp.y) == mcu_pos:
                continue
            
            cx, cy = (comp.x, comp.y)
            
            # VCC 分支
            self.tracks.append(TrackSegment(
                net="VCC", layer="F.Cu",
                start_x=cx, start_y=cy,
                end_x=cx, end_y=20.0,
                width=pw,
            ))
            
            # GND 分支
            self.tracks.append(TrackSegment(
                net="GND", layer="B.Cu",
                start_x=cx, start_y=cy,
                end_x=cx, end_y=self.placement.board_height - 20.0,
                width=pw,
            ))
    
    def _route_signal_nets(self, pos_map: dict[str, tuple[float, float]]):
        """Phase 3: 信号网络布线"""
        sw = self.WIDTH_RULES["signal"]
        
        for net in self.design.nets:
            if net.name in ("VCC", "GND", ""):
                continue
            if not net.pins or len(net.pins) < 2:
                continue
            
            # 获取连接的引脚坐标
            points = self._resolve_net_pins(net.pins, pos_map)
            if len(points) < 2:
                continue
            
            # 星形拓扑：第一个点为中心，其余点连到中心
            center = points[0]
            for target in points[1:]:
                self._add_l_route(net.name, center, target, sw, "F.Cu")
    
    def _auto_connect_power(self, pos_map: dict[str, tuple[float, float]]):
        """Phase 4: 确保每个器件都有 VCC/GND 引脚到主干的连接可视化"""
        # 为没有显式网络连接的器件生成电源分配线
        pw = self.WIDTH_RULES["power_dist"]
        bh = self.placement.board_height
        
        for comp in self.placement.components:
            ref = comp.reference
            cx, cy = (comp.x, comp.y)
            
            # VCC 引脚（器件上方）
            vcc_pin = (cx, cy - 1.5)
            # GND 引脚（器件下方）
            gnd_pin = (cx, cy + 1.5)
            
            # 短连接线到器件
            self.tracks.append(TrackSegment(
                net="VCC", layer="F.Cu",
                start_x=cx, start_y=cy,
                end_x=cx, end_y=vcc_pin[1],
                width=0.2,
            ))
            self.tracks.append(TrackSegment(
                net="GND", layer="B.Cu",
                start_x=cx, start_y=cy,
                end_x=cx, end_y=gnd_pin[1],
                width=0.2,
            ))
    
    def _resolve_net_pins(
        self,
        pins: list[str],
        pos_map: dict[str, tuple[float, float]],
    ) -> list[tuple[float, float]]:
        """
        解析网络引脚列表为坐标点。
        
        pins 格式: ["U1.1", "R1.1", "U2.3"] (ref.pin)
        """
        points = []
        for pin_str in pins:
            parts = pin_str.split(".")
            if len(parts) != 2:
                continue
            ref, pin_num = parts
            if ref in pos_map:
                cx, cy = pos_map[ref]
                # 根据引脚号偏移位置（简化：奇数脚左，偶数脚右）
                try:
                    pn = int(pin_num)
                    offset = (pn % 2 - 0.5) * 2
                    points.append((cx + offset, cy))
                except ValueError:
                    points.append((cx, cy))
        return points
    
    def _add_l_route(
        self,
        net: str,
        start: tuple[float, float],
        end: tuple[float, float],
        width: float,
        layer: str,
    ):
        """添加 L-shape 曼哈顿走线（先横后竖）"""
        x1, y1 = start
        x2, y2 = end
        
        if abs(x2 - x1) > 0.1 and abs(y2 - y1) > 0.1:
            # L-shape: 先横再竖
            self.tracks.append(TrackSegment(
                net=net, layer=layer,
                start_x=x1, start_y=y1,
                end_x=x2, end_y=y1,
                width=width,
            ))
            self.tracks.append(TrackSegment(
                net=net, layer=layer,
                start_x=x2, start_y=y1,
                end_x=x2, end_y=y2,
                width=width,
            ))
        else:
            # 直线
            self.tracks.append(TrackSegment(
                net=net, layer=layer,
                start_x=x1, start_y=y1,
                end_x=x2, end_y=y2,
                width=width,
            ))
