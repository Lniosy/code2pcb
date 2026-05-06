# 技术架构

## 系统总览

PCB Forge 采用分层架构，每一层可独立替换和升级：

```
┌──────────────────────────────────────────────────────────┐
│                      接口层 (Interface)                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  CLI (Typer) │  │  MCP Server  │  │  Python API  │   │
│  │  pcb-forge   │  │  stdio/HTTP  │  │  import forge │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │            │
├─────────┼─────────────────┼─────────────────┼────────────┤
│         │           引擎层 (Engine)         │            │
│         ▼                 ▼                 ▼            │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 代码     │  │ 拓扑     │  │ 布局     │  │ 布线   │  │
│  │ 解析器   │→│ 生成器   │→│ 引擎     │→│ 引擎   │  │
│  │ (Parser) │  │ (Schema) │  │ (Placer) │  │(Router)│  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│         │                                               │
│         ▼                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 验证引擎 │  │ 修正引擎 │  │ 评估引擎 │              │
│  │ SI/PI/EMC│  │ DRC自动  │  │ 设计评分 │              │
│  │ (v1.0+)  │  │ 修复     │  │ (v2.0+)  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                      知识层 (Knowledge)                   │
│                                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐    │
│  │ 器件   │  │ 典型   │  │ 数据   │  │ 设计规则   │    │
│  │ 参数库 │  │ 电路库 │  │ 手册库 │  │ 库         │    │
│  │(Component)│ │(Pattern)│ │(Datasheet)│ │(Rules)   │    │
│  └────────┘  └────────┘  └────────┘  └────────────┘    │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                      导出层 (Export)                      │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ KiCad    │  │ Gerber   │  │ BOM      │  │ 3D模型 │  │
│  │ .sch/.pcb│  │ RS-274X  │  │ CSV+链接  │  │ STEP   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## 核心数据流

```
用户输入
  │
  ├── "做一个ESP32温湿度传感器"     (自然语言)
  ├── ./my-embedded-project/       (代码仓库)
  └── HardwareSpec JSON            (API调用)
  │
  ▼
┌─────────────────┐
│   CodeParser    │  静态分析代码 → HardwareSpec
│   (代码解析器)   │  或 NLP解析文本 → HardwareSpec
└────────┬────────┘
         │ HardwareSpec
         ▼
┌─────────────────┐
│ SchemaGenerator │  HardwareSpec → SchematicDesign
│ (原理图生成器)   │  器件选型 + 电路拓扑 + 网络连接
└────────┬────────┘
         │ SchematicDesign
         ▼
┌─────────────────┐
│    Placer       │  SchematicDesign → PlacementResult
│   (布局引擎)     │  功能分区 + 约束放置
└────────┬────────┘
         │ PlacementResult
         ▼
┌─────────────────┐
│    Router       │  PlacementResult → RoutingResult
│   (布线引擎)     │  走线 + 过孔 + DRC检查
└────────┬────────┘
         │ RoutingResult
         ▼
┌─────────────────┐
│  KiCadExporter  │  → .kicad_sch + .kicad_pcb + Gerber
│   (文件导出)     │
└─────────────────┘
```

## 核心数据结构

### HardwareSpec（硬件规格）

代码解析器的输出，贯穿整个流水线：

```python
@dataclass
class HardwareSpec:
    name: str                    # 项目名称
    mcu: str                     # MCU型号 (如 "ESP32-S3")
    framework: str               # 框架 (esp-idf/arduino/...)
    peripherals: list[PeripheralUsage]  # 使用的外设
    components: list[DetectedComponent]  # 外接器件
    voltage_supply: list[str]    # 供电需求
    features: list[str]          # 功能特征
    notes: list[str]             # 备注
```

### SchematicDesign（原理图设计）

原理图生成器的输出：

```python
@dataclass
class SchematicDesign:
    title: str                          # 标题
    components: list[SchematicComponent]  # 器件列表
    nets: list[SchematicNet]            # 网络连接
    notes: list[str]                    # 设计备注
```

## 代码解析器设计

### 多框架支持

```
代码文件 → 框架检测 → 模式匹配池 → 硬件需求推断
               │
               ├── CMakeLists.txt → ESP-IDF/Zephyr
               ├── platformio.ini → PlatformIO
               ├── *.ino → Arduino
               ├── machine.Pin* → MicroPython
               └── Cargo.toml → Rust Embedded
```

### 检测优先级

1. **MCU检测**：从构建系统(sdkconfig/CMakeLists.txt)→源码#include→代码模式
2. **外设检测**：API调用模式匹配（如 `i2c_master_write` → I2C外设）
3. **器件检测**：字符串模式匹配（如 `SSD1306` → OLED显示模块）
4. **供电推断**：电压引用 + 电池/USB关键词

## 知识库架构

### 器件参数库

```json
{
  "ESP32-S3-WROOM-1": {
    "manufacturer": "Espressif",
    "voltage": "3.0-3.6V",
    "package": "LQFP-56",
    "interface": "SPI/I2C/UART/USB",
    "lcsc_part": "C2913902",
    "typical_circuit": "标准最小系统：3.3V供电，40MHz晶振..."
  }
}
```

### 典型电路库（v1.0规划）

每种MCU/传感器的参考电路，以模板形式存储：

```
patterns/
├── mcu/
│   ├── esp32-s3-minimal.yaml      # ESP32-S3最小系统
│   ├── stm32f103-minimal.yaml     # STM32最小系统
│   └── rp2040-minimal.yaml        # RP2040最小系统
├── power/
│   ├── usb-5v-to-3v3.yaml         # USB 5V→3.3V
│   ├── battery-charge-tp4056.yaml # 电池充电电路
│   └── ldo-ams1117.yaml           # LDO稳压
├── interface/
│   ├── i2c-pullup.yaml            # I2C上拉
│   ├── spi-termination.yaml       # SPI终端
│   └── uart-level-shift.yaml      # UART电平转换
└── sensor/
    ├── dht22-circuit.yaml          # DHT22接口电路
    └── ssd1306-circuit.yaml        # SSD1306接口电路
```

## KiCad文件格式

PCB Forge直接生成KiCad S-expression格式文件，兼容KiCad 8/9。

### .kicad_sch（原理图）

```
(kicad_sch (version 20231120) (generator "PCB Forge v0.1.0")
  (uuid "...")
  (paper "A4")
  (title_block (title "...") (date "...") (rev "0.1.0"))
  (lib_symbols ...)
  (symbol (lib_id "...") (at x y 0)
    (property "Reference" "U1" ...)
    (property "Value" "ESP32-S3" ...)
    (property "Footprint" "..." ...)
  )
  (nets ...)
)
```

### .kicad_pcb（PCB布局）

```
(kicad_pcb (version 20221018) (generator "PCB Forge v0.1.0")
  (general (thickness 1.6))
  (gr_line ... (layer "Edge.Cuts"))   # 板框
  (net 1 "VCC")
  (footprint "..." (layer "F.Cu") ...)  # 器件
  (segment ... (layer "F.Cu"))          # 走线
)
```

## MCP Server协议

暴露给AI Agent的工具：

| 工具 | 说明 |
|------|------|
| `analyze_code` | 分析代码仓库，返回HardwareSpec |
| `text2pcb` | 自然语言→完整PCB设计 |
| `search_component` | 搜索器件知识库 |
| `generate_schematic` | 从JSON规格生成原理图 |
| `get_version` | 版本信息 |

## 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| CLI框架 | Typer + Rich | 现代、类型安全、美观输出 |
| 数据验证 | Pydantic v2 | 强类型约束、JSON序列化 |
| MCP协议 | mcp[cli] | 官方MCP SDK |
| 模板引擎 | Jinja2 | KiCad文件生成 |
| 布线后端(v1.0) | Freerouting | 成熟开源自动布线器 |
| 布局加速(v2.0) | Rust/CUDA | 性能关键路径 |
| RL框架(v2.0) | Stable-Baselines3 | 强化学习训练 |
| LLM(v0.2+) | OpenAI/Anthropic | 器件选型、文本理解 |
