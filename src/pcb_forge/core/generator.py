"""原理图生成器 — 从硬件规格生成电路拓扑"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .parser import HardwareSpec, DetectedComponent, ComponentType, PeripheralType


@dataclass
class SchematicComponent:
    """原理图中的器件"""
    reference: str       # 如 "U1", "R1", "C1"
    value: str           # 如 "10kΩ", "100nF", "ESP32-S3"
    footprint: str       # KiCad封装名
    library: str         # KiCad库名
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0


@dataclass
class SchematicNet:
    """原理图中的网络连接"""
    name: str
    pins: list[str] = field(default_factory=list)  # ["U1.3V3", "C1.1", ...]


@dataclass
class SchematicDesign:
    """完整的原理图设计"""
    title: str
    components: list[SchematicComponent] = field(default_factory=list)
    nets: list[SchematicNet] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class SchemaGenerator:
    """
    电路拓扑生成器。
    
    将 CodeParser 输出的 HardwareSpec 转换为
    完整的器件清单和网络连接列表。
    
    Phase 2 将集成 LLM 进行智能推理，当前版本基于规则引擎。
    """
    
    # 去耦电容自动添加规则
    DECOUPLING_CAPS = {
        "100nF": {"footprint": "Capacitor_SMD:C_0402_1005Metric", "library": "Device"},
        "10uF": {"footprint": "Capacitor_SMD:C_0603_1608Metric", "library": "Device"},
        "4.7uF": {"footprint": "Capacitor_SMD:C_0603_1608Metric", "library": "Device"},
    }
    
    # MCU最小系统默认器件
    MCU_MIN_SYSTEM = {
        "crystal": {"value": "40MHz", "footprint": "Oscillator:Oscillator_SMD_ABC-3225-4Pin_3.2x2.5mm"},
        "reset_btn": {"value": " tactile switch", "footprint": "Button_SMD:SW_Push_1P4x3.6mm"},
        "boot_btn": {"value": " tactile switch", "footprint": "Button_SMD:SW_Push_1P4x3.6mm"},
    }
    
    def __init__(self, spec: HardwareSpec):
        self.spec = spec
        self._ref_counters: dict[str, int] = {}
        self._design = SchematicDesign(title=spec.name or "code2pcb Design")
    
    def _next_ref(self, prefix: str) -> str:
        """生成下一个引用编号，如 R1→R2, C1→C2"""
        count = self._ref_counters.get(prefix, 0) + 1
        self._ref_counters[prefix] = count
        return f"{prefix}{count}"
    
    def generate(self) -> SchematicDesign:
        """
        主入口：从硬件规格生成完整原理图设计。
        
        流程：
        1. 添加MCU主控
        2. 添加最小系统器件（晶振、复位、Boot）
        3. 为MCU添加去耦电容
        4. 添加用户代码中检测到的器件
        5. 添加必要的外围电路（上拉、滤波等）
        6. 生成网络连接
        """
        self._design = SchematicDesign(title=self.spec.name or "code2pcb Design")
        
        # Step 1: MCU
        mcu_ref = self._add_mcu()
        
        # Step 2: 最小系统
        self._add_minimal_system(mcu_ref)
        
        # Step 3: 去耦电容
        self._add_decoupling_caps(mcu_ref)
        
        # Step 4: 用户器件
        self._add_detected_components()
        
        # Step 5: 外围电路
        self._add_peripheral_circuits()
        
        # Step 6: 网络
        self._generate_nets()
        
        return self._design
    
    def _add_mcu(self) -> Optional[str]:
        """添加MCU主控器件"""
        if not self.spec.mcu:
            self._design.notes.append("⚠️ 未检测到MCU，请手动添加主控芯片")
            return None
        
        ref = self._next_ref("U")
        mcu = SchematicComponent(
            reference=ref,
            value=self.spec.mcu,
            footprint=self._get_mcu_footprint(self.spec.mcu),
            library="MCU_Microchip_SAMD",
            x=100.0,
            y=100.0,
        )
        self._design.components.append(mcu)
        return ref
    
    def _get_mcu_footprint(self, mcu: str) -> str:
        """根据MCU型号推断封装"""
        mcu_lower = mcu.lower()
        
        if "esp32-s3" in mcu_lower:
            return "Package_QFP:LQFP-56_7x7mm_P0.4mm"
        elif "esp32" in mcu_lower:
            return "Package_QFP:LQFP-48_7x7mm_P0.5mm"
        elif "stm32f103c8" in mcu_lower:
            return "Package_QFP:LQFP-48_7x7mm_P0.5mm"
        elif "stm32f407" in mcu_lower:
            return "Package_QFP:LQFP-100_14x14mm_P0.5mm"
        elif "rp2040" in mcu_lower:
            return "Package_QFP:LQFP-56_7x7mm_P0.4mm"
        elif "atmega328" in mcu_lower:
            return "Package_DIP:DIP-28_W7.62mm"
        elif "stm32" in mcu_lower:
            return "Package_QFP:LQFP-64_10x10mm_P0.5mm"
        else:
            return "Package_QFP:LQFP-48_7x7mm_P0.5mm"
    
    def _add_minimal_system(self, mcu_ref: Optional[str]):
        """添加MCU最小系统电路"""
        if not mcu_ref:
            return
        
        # 晶振（ESP32系列通常外接晶振）
        if "ESP32" in self.spec.mcu:
            crystal = SchematicComponent(
                reference=self._next_ref("Y"),
                value="40MHz",
                footprint="Oscillator:Oscillator_SMD_ABC-3225-4Pin_3.2x2.5mm",
                library="Device",
                x=150.0,
                y=80.0,
            )
            self._design.components.append(crystal)
            self._design.notes.append("✅ 添加40MHz晶振")
        
        # 复位按钮
        reset_btn = SchematicComponent(
            reference=self._next_ref("SW"),
            value="Reset",
            footprint="Button_SMD:SW_Push_1P4x3.6mm",
            library="Button_SMD",
            x=80.0,
            y=60.0,
        )
        self._design.components.append(reset_btn)
        self._design.notes.append("✅ 添加复位按钮")
        
        # Boot按钮（ESP32系列）
        if "ESP32" in self.spec.mcu:
            boot_btn = SchematicComponent(
                reference=self._next_ref("SW"),
                value="Boot",
                footprint="Button_SMD:SW_Push_1P4x3.6mm",
                library="Button_SMD",
                x=80.0,
                y=80.0,
            )
            self._design.components.append(boot_btn)
            self._design.notes.append("✅ 添加Boot按钮")
    
    def _add_decoupling_caps(self, mcu_ref: Optional[str]):
        """为MCU和IC添加去耦电容"""
        if not mcu_ref:
            return
        
        # 每个电源引脚对添加去耦
        for cap_value, cap_info in self.DECOUPLING_CAPS.items():
            cap = SchematicComponent(
                reference=self._next_ref("C"),
                value=cap_value,
                footprint=cap_info["footprint"],
                library=cap_info["library"],
            )
            self._design.components.append(cap)
        
        self._design.notes.append("✅ 添加MCU去耦电容 (100nF + 10µF + 4.7µF)")
    
    def _add_detected_components(self):
        """添加代码中检测到的外部器件"""
        for comp in self.spec.components:
            ref_prefix = self._get_ref_prefix(comp.type)
            if not ref_prefix:
                continue
            
            ref = self._next_ref(ref_prefix)
            footprint = self._get_component_footprint(comp)
            
            sch_comp = SchematicComponent(
                reference=ref,
                value=comp.likely_part or comp.description.split("(")[0].strip(),
                footprint=footprint,
                library=self._get_component_library(comp),
            )
            self._design.components.append(sch_comp)
            self._design.notes.append(f"✅ 添加 {comp.description} → {ref}")
    
    def _get_ref_prefix(self, ctype: ComponentType) -> str:
        """根据器件类型返回引用前缀"""
        mapping = {
            ComponentType.SENSOR: "U",
            ComponentType.DISPLAY: "U",
            ComponentType.WIRELESS: "U",
            ComponentType.POWER: "U",
            ComponentType.STORAGE: "U",
            ComponentType.AUDIO: "U",
            ComponentType.MOTOR: "U",
            ComponentType.CONNECTOR: "J",
            ComponentType.LED: "D",
            ComponentType.BUTTON: "SW",
            ComponentType.IC: "U",
            ComponentType.PASSIVE: "R",
        }
        return mapping.get(ctype, "U")
    
    def _get_component_footprint(self, comp: DetectedComponent) -> str:
        """推断器件封装"""
        desc = comp.description.lower()
        
        if "oled" in desc:
            return "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
        elif "dht" in desc:
            return "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
        elif "i2c" in desc and "sensor" in desc:
            return "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
        elif "relay" in desc:
            return "Relay_THT:Relay_SPDT_HJR-4102"
        elif "servo" in desc:
            return "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
        elif "buzzer" in desc:
            return "Buzzer_Beeper:Buzzer_12x9.5RM7.6"
        elif "tp4056" in desc:
            return "Package_TO_SOT_SMD:SOT-23-6"
        elif "sd" in desc and "card" in desc:
            return "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5"
        
        return "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
    
    def _get_component_library(self, comp: DetectedComponent) -> str:
        """推断器件所在KiCad库"""
        if comp.type == ComponentType.SENSOR:
            return "Sensor"
        elif comp.type == ComponentType.DISPLAY:
            return "Display"
        elif comp.type == ComponentType.WIRELESS:
            return "RF"
        elif comp.type == ComponentType.POWER:
            return "Regulator_Linear"
        elif comp.type in (ComponentType.LED, ComponentType.BUTTON):
            return "Device"
        elif comp.type == ComponentType.CONNECTOR:
            return "Connector"
        return "Device"
    
    def _add_peripheral_circuits(self):
        """根据使用的外设添加必要的被动器件"""
        for periph in self.spec.peripherals:
            if periph.type == PeripheralType.I2C:
                # I2C上拉电阻
                for _ in range(2):
                    r = SchematicComponent(
                        reference=self._next_ref("R"),
                        value="4.7kΩ",
                        footprint="Resistor_SMD:R_0402_1005Metric",
                        library="Device",
                    )
                    self._design.components.append(r)
                self._design.notes.append("✅ 添加I2C上拉电阻 (2x 4.7kΩ)")
            
            elif periph.type == PeripheralType.SPI:
                # SPI无强制上拉，但可以加终端电阻
                pass
    
    def _generate_nets(self):
        """生成网络连接（Phase 2 将基于真实引脚映射）"""
        # v0.1.0: 生成基本的电源网络
        self._design.nets.append(SchematicNet(name="VCC", pins=[]))
        self._design.nets.append(SchematicNet(name="GND", pins=[]))
        
        if self.spec.voltage_supply:
            for v in self.spec.voltage_supply:
                v_clean = v.replace(" ", "_").replace("(", "").replace(")", "")
                self._design.nets.append(SchematicNet(name=f"VIN_{v_clean}", pins=[]))
        
        self._design.notes.append(
            f"📊 设计包含 {len(self._design.components)} 个器件, "
            f"{len(self._design.nets)} 个网络"
        )
