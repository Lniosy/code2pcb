"""布线引擎 — 智能自动布线（v0.1.0 占位实现）"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .placer import PlacementResult, PlacedComponent
from .generator import SchematicDesign


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
class RoutingResult:
    """布线结果"""
    tracks: list[TrackSegment] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    completion_rate: float = 0.0
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Via:
    """过孔"""
    x: float
    y: float
    drill: float = 0.4
    size: float = 0.8


class Router:
    """
    PCB布线引擎。
    
    v0.1.0: 基于曼哈顿距离的简单直连布线（示意）
    v1.0.0 计划: 集成 Freerouting 作为后端引擎
    v2.0.0 计划: 基于PathFinder的GPU加速布线（对标OrthoRoute）
    v3.0.0 计划: 神经网络引导的SI感知布线
    
    布线策略：
    1. 先布电源线（宽线）
    2. 再布关键信号（差分对、时钟）
    3. 最后布普通信号
    4. 自动DRC修复
    """
    
    # 默认线宽规则
    WIDTH_RULES = {
        "power": 0.5,    # 电源线 0.5mm
        "signal": 0.25,  # 信号线 0.25mm
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
        
        v0.1.0 生成示意性走线，展示布线引擎框架。
        """
        self.tracks = []
        self.vias = []
        self.warnings = []
        self.notes = []
        
        if not self.placement.components:
            self.notes.append("⚠️ 没有器件需要布线")
            return RoutingResult(
                tracks=[],
                vias=[],
                completion_rate=0.0,
                warnings=self.warnings,
                notes=self.notes,
            )
        
        # 生成示意性电源走线
        self._add_power_tracks()
        
        # 统计
        total_nets = len(self.design.nets)
        routed_nets = min(total_nets, len(self.tracks))
        completion = routed_nets / max(total_nets, 1) * 100
        
        self.notes.append(f"🛤️  布线完成: {routed_nets}/{total_nets} 网络 ({completion:.0f}%)")
        self.notes.append(f"🛤️  走线段数: {len(self.tracks)}")
        
        self.warnings.append(
            "⚠️ v0.1.0 布线为示意性实现，仅生成电源走线。"
            "完整布线功能将在 v1.0.0 通过集成 Freerouting 引擎提供。"
        )
        
        return RoutingResult(
            tracks=self.tracks,
            vias=self.vias,
            completion_rate=completion,
            warnings=self.warnings,
            notes=self.notes,
        )
    
    def _add_power_tracks(self):
        """添加电源走线（示意）"""
        if not self.placement.components:
            return
        
        # VCC 走线（水平贯穿）
        self.tracks.append(TrackSegment(
            net="VCC",
            layer="F.Cu",
            start_x=0.0,
            start_y=25.0,
            end_x=self.placement.board_width,
            end_y=25.0,
            width=self.WIDTH_RULES["power"],
        ))
        
        # GND 走线（水平贯穿）
        self.tracks.append(TrackSegment(
            net="GND",
            layer="F.Cu",
            start_x=0.0,
            start_y=self.placement.board_height - 25.0,
            end_x=self.placement.board_width,
            end_y=self.placement.board_height - 25.0,
            width=self.WIDTH_RULES["power"],
        ))
        
        # 从MCU到电源线的短连接
        for comp in self.placement.components:
            if comp.reference.startswith("U") and any(
                m in comp.value for m in ["ESP32", "STM32", "RP2040"]
            ):
                # VCC连接
                self.tracks.append(TrackSegment(
                    net="VCC",
                    start_x=comp.x,
                    start_y=comp.y - 5,
                    end_x=comp.x,
                    end_y=25.0,
                    width=0.3,
                ))
                # GND连接
                self.tracks.append(TrackSegment(
                    net="GND",
                    start_x=comp.x,
                    start_y=comp.y + 5,
                    end_x=comp.x,
                    end_y=self.placement.board_height - 25.0,
                    width=0.3,
                ))
