"""布局引擎 — 智能元件放置（v0.1.0 基于规则的占位实现）"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .generator import SchematicDesign, SchematicComponent


@dataclass
class PlacementResult:
    """布局结果"""
    components: list[PlacedComponent]
    board_width: float = 100.0
    board_height: float = 80.0
    warnings: list[str] = None
    notes: list[str] = None


@dataclass
class PlacedComponent(SchematicComponent):
    """已放置的器件（含坐标和旋转）"""
    layer: str = "F"  # F=顶层, B=底层
    locked: bool = False


class Placer:
    """
    PCB布局引擎。
    
    v0.1.0: 基于规则的简单布局
    v1.0.0 计划: 基于GNN的约束感知智能布局
    v2.0.0 计划: 基于强化学习的物理驱动布局（对标Quilter）
    
    布局策略：
    1. MCU居中
    2. 相关器件就近放置（功能分区）
    3. 接口器件放边缘
    4. 去耦电容贴IC放置
    5. 连接器放板边
    """
    
    # 功能分区定义
    ZONES = {
        "power": {"x": 10, "y": 60, "desc": "电源区（左上）"},
        "mcu": {"x": 40, "y": 30, "desc": "主控区（中心）"},
        "sensors": {"x": 80, "y": 30, "desc": "传感器区（右侧）"},
        "display": {"x": 80, "y": 60, "desc": "显示区（右上）"},
        "connectors": {"x": 10, "y": 10, "desc": "接口区（左侧）"},
        "wireless": {"x": 40, "y": 70, "desc": "无线区（上方）"},
    }
    
    def __init__(self, design: SchematicDesign, board_width: float = 100.0, board_height: float = 80.0):
        self.design = design
        self.board_width = board_width
        self.board_height = board_height
        self.placed: list[PlacedComponent] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
    
    def place(self) -> PlacementResult:
        self.placed = []
        self.warnings = []
        self.notes = []
        
        col_offset = 0
        row_offset = 0
        
        for comp in self.design.components:
            ref = comp.reference
            
            # 判断器件类别并决定位置
            if ref.startswith("U") and any(
                mcu in comp.value for mcu in ["ESP32", "STM32", "RP2040", "ATmega"]
            ):
                # MCU放中心
                x = 50.0
                y = 40.0
                self.notes.append(f"📐 MCU {ref}({comp.value}) → 中心位置 ({x},{y})")
                
            elif ref.startswith("C") and "nF" in comp.value:
                # 去耦电容贴MCU
                x = 55.0 + col_offset * 8
                y = 35.0
                col_offset += 1
                self.notes.append(f"📐 去耦 {ref}({comp.value}) → 靠近MCU")
                
            elif ref.startswith("J") or "PinHeader" in comp.footprint:
                # 连接器放板边
                x = 5.0
                y = 20.0 + row_offset * 15
                row_offset += 1
                self.notes.append(f"📐 接口 {ref} → 板边 ({x},{y})")
                
            elif ref.startswith("SW") or ref.startswith("BTN"):
                # 按钮放边缘方便操作
                x = 30.0 + col_offset * 12
                y = 15.0
                col_offset += 1
                self.notes.append(f"📐 按钮 {ref}({comp.value}) → 操作区")
                
            else:
                # 其他器件网格排列
                x = 20.0 + (len(self.placed) % 4) * 18
                y = 50.0 + (len(self.placed) // 4) * 15
            
            # 确保在板内
            x = max(5, min(x, self.board_width - 5))
            y = max(5, min(y, self.board_height - 5))
            
            placed = PlacedComponent(
                reference=ref,
                value=comp.value,
                footprint=comp.footprint,
                library=comp.library,
                x=x,
                y=y,
                rotation=0,
            )
            self.placed.append(placed)
        
        self.notes.append(f"📐 布局完成: {len(self.placed)} 个器件")
        
        return PlacementResult(
            components=self.placed,
            board_width=self.board_width,
            board_height=self.board_height,
            warnings=self.warnings or [],
            notes=self.notes or [],
        )
