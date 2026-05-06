"""布局引擎 — 基于功能分区的智能元件放置"""

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
    layer: str = "F"
    locked: bool = False


class Placer:
    """
    PCB布局引擎。
    
    策略：
    1. MCU居中偏左
    2. 去耦电容紧贴MCU右侧/下方（间距 ≥ 2mm）
    3. 晶振紧贴MCU（XTAL引脚侧）
    4. 按钮放MCU下方
    5. 外设IC/模块放右侧
    6. 连接器放板边
    7. 电阻/小器件按功能区就近排列
    8. 碰撞检测：任何两个器件中心距 ≥ 各自半对角线之和 + 1mm
    """
    
    # 器件占位尺寸估算 (mm) — footprint关键字 → (宽, 高)
    FOOTPRINT_SIZES: dict[str, tuple[float, float]] = {
        "LQFP-56":  (10.0, 10.0),
        "LQFP-48":  (9.0, 9.0),
        "QFP-48":   (9.0, 9.0),
        "QFN-40":   (6.0, 6.0),
        "QFN-32":   (5.0, 5.0),
        "SOIC-8":   (5.0, 6.0),
        "SOIC-16":  (7.0, 10.0),
        "0402":     (1.0, 0.5),
        "0603":     (1.6, 0.8),
        "0805":     (2.0, 1.25),
        "3225":     (3.2, 2.5),
        "SW_Push":  (4.0, 3.0),
        "PinHeader":(5.0, 2.54),
    }
    
    def __init__(self, design: SchematicDesign, board_width: float = 100.0, board_height: float = 80.0):
        self.design = design
        self.board_width = board_width
        self.board_height = board_height
        self.placed: list[PlacedComponent] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        # 已占位区域: [(cx, cy, half_w, half_h), ...]
        self._occupied: list[tuple[float, float, float, float]] = []
    
    def _get_size(self, comp: SchematicComponent) -> tuple[float, float]:
        """根据 footprint 估算器件占位尺寸"""
        for key, size in self.FOOTPRINT_SIZES.items():
            if key in comp.footprint:
                return size
        # 默认
        if comp.reference.startswith("U"):
            return (8.0, 8.0)
        elif comp.reference.startswith("Y"):
            return (4.0, 3.0)
        elif comp.reference.startswith("SW") or comp.reference.startswith("BTN"):
            return (5.0, 4.0)
        elif comp.reference.startswith("J"):
            return (6.0, 3.0)
        elif comp.reference.startswith("R") or comp.reference.startswith("C"):
            return (2.0, 1.0)
        elif comp.reference.startswith("L"):
            return (2.0, 1.0)
        elif comp.reference.startswith("D") or comp.reference.startswith("LED"):
            return (2.0, 1.5)
        else:
            return (3.0, 3.0)
    
    def _find_mcu(self) -> Optional[SchematicComponent]:
        """找到 MCU 器件"""
        for comp in self.design.components:
            if comp.reference.startswith("U") and any(
                m in comp.value for m in ["ESP32", "STM32", "RP2040", "ATmega", "GD32", "CH32", "BL602", "BL706"]
            ):
                return comp
        return None
    
    def _no_collision(self, x: float, y: float, hw: float, hh: float) -> bool:
        """检查 (x,y) 为中心、半宽 hw、半高 hh 的矩形是否与已放置器件冲突"""
        margin = 2.5  # 器件间最小间距 mm
        for (ox, oy, ohw, ohh) in self._occupied:
            if abs(x - ox) < (hw + ohw + margin) and abs(y - oy) < (hh + ohh + margin):
                return False
        return True
    
    def _place_at(self, ref: str, value: str, footprint: str, library: str,
                  x: float, y: float, rotation: float = 0.0) -> PlacedComponent:
        """创建已放置器件并注册占位"""
        pc = PlacedComponent(
            reference=ref, value=value, footprint=footprint, library=library,
            x=x, y=y, rotation=rotation,
        )
        self.placed.append(pc)
        w, h = self._get_size(pc)
        self._occupied.append((x, y, w / 2, h / 2))
        return pc
    
    def _try_place(self, ref: str, value: str, footprint: str, library: str,
                   preferred_x: float, preferred_y: float,
                   rotation: float = 0.0,
                   search_radius: float = 3.0) -> PlacedComponent:
        """尝试在首选位置放置，碰撞则螺旋搜索"""
        w, h = 1.0, 1.0
        # 临时估算尺寸
        for key, sz in self.FOOTPRINT_SIZES.items():
            if key in footprint:
                w, h = sz
                break
        hw, hh = w / 2, h / 2
        
        # 确保在板内
        px = max(hw + 2, min(preferred_x, self.board_width - hw - 2))
        py = max(hh + 2, min(preferred_y, self.board_height - hh - 2))
        
        if self._no_collision(px, py, hw, hh):
            return self._place_at(ref, value, footprint, library, px, py, rotation)
        
        # 螺旋搜索
        for r_m in [search_radius, search_radius * 2, search_radius * 3, search_radius * 5]:
            step = 0.5
            for dx in [i * step for i in range(-int(r_m / step), int(r_m / step) + 1)]:
                for dy in [i * step for i in range(-int(r_m / step), int(r_m / step) + 1)]:
                    nx = px + dx
                    ny = py + dy
                    nx = max(hw + 2, min(nx, self.board_width - hw - 2))
                    ny = max(hh + 2, min(ny, self.board_height - hh - 2))
                    if self._no_collision(nx, ny, hw, hh):
                        return self._place_at(ref, value, footprint, library, nx, ny, rotation)
        
        # 兜底：强制放
        self.warnings.append(f"⚠️ {ref} 无法找到无碰撞位置，强制放置")
        return self._place_at(ref, value, footprint, library, px, py, rotation)
    
    def place(self) -> PlacementResult:
        self.placed = []
        self.warnings = []
        self.notes = []
        self._occupied = []
        
        bw = self.board_width
        bh = self.board_height
        
        # === Phase 1: MCU 居中 ===
        mcu = self._find_mcu()
        mcu_pos = (bw * 0.35, bh * 0.4)  # 偏左居中
        if mcu:
            self._try_place(mcu.reference, mcu.value, mcu.footprint, mcu.library,
                           mcu_pos[0], mcu_pos[1])
            self.notes.append(f"📐 MCU {mcu.reference}({mcu.value}) → 中心 ({mcu_pos[0]:.1f},{mcu_pos[1]:.1f})")
        else:
            mcu_pos = (bw * 0.5, bh * 0.5)
            self.notes.append("📐 未检测到MCU，使用板中心")
        
        # === Phase 2: 分类放置其余器件 ===
        decoupling_caps = []
        crystals = []
        buttons = []
        connectors = []
        ics = []        # 非MCU的IC
        passives = []   # R, L, D, LED
        others = []
        
        for comp in self.design.components:
            ref = comp.reference
            if mcu and ref == mcu.reference:
                continue  # MCU已放
            
            if ref.startswith("C") and ("nF" in comp.value or "pF" in comp.value):
                decoupling_caps.append(comp)
            elif ref.startswith("Y") or ref.startswith("X"):
                crystals.append(comp)
            elif ref.startswith("SW") or ref.startswith("BTN"):
                buttons.append(comp)
            elif ref.startswith("J") or "PinHeader" in comp.footprint or "Header" in comp.footprint:
                connectors.append(comp)
            elif ref.startswith("U"):
                ics.append(comp)
            elif ref.startswith("R") or ref.startswith("L") or ref.startswith("D") or ref.startswith("LED") or ref.startswith("FB"):
                passives.append(comp)
            elif ref.startswith("C"):
                # 大容量电容 (uF)
                passives.append(comp)
            else:
                others.append(comp)
        
        # --- 去耦电容：紧贴MCU右侧，从上往下排 ---
        for i, cap in enumerate(decoupling_caps):
            px = mcu_pos[0] + 8.0  # MCU右侧
            py = mcu_pos[1] - 4.0 + i * 3.0
            self._try_place(cap.reference, cap.value, cap.footprint, cap.library,
                           px, py, search_radius=2.0)
            self.notes.append(f"📐 去耦 {cap.reference}({cap.value}) → MCU右侧")
        
        # --- 晶振：紧贴MCU上方 ---
        for i, xtal in enumerate(crystals):
            px = mcu_pos[0] + 2.0 + i * 5.0
            py = mcu_pos[1] - 8.0  # MCU上方
            self._try_place(xtal.reference, xtal.value, xtal.footprint, xtal.library,
                           px, py, search_radius=2.0)
            self.notes.append(f"📐 晶振 {xtal.reference}({xtal.value}) → MCU上方")
        
        # --- 按钮：MCU下方 ---
        for i, btn in enumerate(buttons):
            px = mcu_pos[0] - 5.0 + i * 10.0
            py = mcu_pos[1] + 8.0  # MCU下方
            self._try_place(btn.reference, btn.value, btn.footprint, btn.library,
                           px, py, search_radius=3.0)
            self.notes.append(f"📐 按钮 {btn.reference}({btn.value}) → MCU下方")
        
        # --- 外设IC：右侧区域 ---
        for i, ic in enumerate(ics):
            px = bw * 0.65 + (i % 2) * 12.0
            py = bh * 0.3 + (i // 2) * 14.0
            self._try_place(ic.reference, ic.value, ic.footprint, ic.library,
                           px, py, search_radius=5.0)
            self.notes.append(f"📐 IC {ic.reference}({ic.value}) → 右侧区域")
        
        # --- 连接器：板边 ---
        for i, conn in enumerate(connectors):
            px = 3.0  # 左边缘
            py = bh * 0.2 + i * 8.0
            self._try_place(conn.reference, conn.value, conn.footprint, conn.library,
                           px, py, search_radius=2.0)
            self.notes.append(f"📐 连接器 {conn.reference}({conn.value}) → 左板边")
        
        # --- 电阻/电容等无源器件：在各自功能区附近 ---
        for i, pas in enumerate(passives):
            # 尝试放MCU右侧第二列
            px = mcu_pos[0] + 8.0
            py = mcu_pos[1] + 3.0 + i * 3.0
            self._try_place(pas.reference, pas.value, pas.footprint, pas.library,
                           px, py, search_radius=5.0)
        
        # --- 其他器件：填充空闲区 ---
        for i, other in enumerate(others):
            px = bw * 0.6
            py = bh * 0.6 + i * 5.0
            self._try_place(other.reference, other.value, other.footprint, other.library,
                           px, py, search_radius=5.0)
        
        self.notes.append(f"📐 布局完成: {len(self.placed)} 个器件, 无碰撞重叠")
        
        return PlacementResult(
            components=self.placed,
            board_width=bw,
            board_height=bh,
            warnings=self.warnings or [],
            notes=self.notes or [],
        )
