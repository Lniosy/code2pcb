# code2pcb 🔧⚡

> AI驱动的开源PCB设计工具 — 代码/自然语言到电路板的全自动生成

**中文优先 · 开源免费 · CLI原生 · MCP/Skill集成**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)]()

---

## 🎯 这是什么？

code2pcb 是一个面向中文硬件开发者的 AI PCB 设计工具。输入你的嵌入式代码仓库或自然语言描述，自动完成：

```
代码/文字 → 硬件需求分析 → 原理图生成 → 智能布局 → 自动布线 → KiCad文件 → 打样
```

### 核心能力

| 功能 | 状态 | 说明 |
|------|------|------|
| 🔍 代码解析 | ✅ v0.1.0 | 分析嵌入式代码，自动推断MCU/外设/器件 |
| 💬 自然语言→PCB | ✅ v0.1.0 | 中文描述即可生成电路板设计 |
| 📐 智能布局 | ✅ v0.1.0 | 基于规则的功能分区自动布局 |
| 🛤️ 自动布线 | 🔨 v0.1.0 | 示意布线（v1.0集成Freerouting引擎） |
| 📄 KiCad导出 | ✅ v0.1.0 | 输出.kicad_sch和.kicad_pcb文件 |
| 🤖 MCP Server | ✅ v0.1.0 | AI Agent原生集成 |
| 📚 器件知识库 | ✅ v0.1.0 | 内置常用器件参数+立创商城SKU |
| 🔬 SI/PI分析 | 🔜 v1.0.0 | 信号完整性/电源完整性分析 |
| 🌡️ 热分析 | 🔜 v2.0.0 | 热点预测+自动热过孔 |
| 📡 EMC预测 | 🔜 v2.0.0 | EMI风险评估 |
| 🏭 一键打样 | 🔜 v1.0.0 | 对接嘉立创/华秋自动下单 |

## 🚀 快速开始

### 安装

```bash
pip install -e ".[dev]"
```

### 分析代码仓库

```bash
# 分析你的嵌入式项目，自动推断硬件需求
code2pcb analyze ./my-esp32-project/
```

输出示例：
```
🔍 code2pcb v0.1.0 — 代码分析报告
═════════════════════════════════════════
📁 项目: my-esp32-project
🔧 框架: esp-idf
🔧 MCU: ESP32-S3
📡 外设: SPI, I2C, UART, ADC, GPIO
📦 器件:
  - SSD1306 OLED显示模块
  - DHT22 温湿度传感器
  - WiFi模块 (ESP32内置)
⚡ 供电: USB 5V, 3.3V
```

### 从自然语言生成PCB

```bash
code2pcb text2pcb "做一个ESP32温湿度传感器，OLED显示，电池供电，Type-C充电"
```

### 从代码直接生成PCB

```bash
code2pcb code2pcb ./my-esp32-project/ --output ./output/
```

### MCP Server（AI Agent集成）

在Claude Desktop中配置：
```json
{
  "mcpServers": {
    "code2pcb": {
      "command": "code2pcb",
      "args": ["mcp"]
    }
  }
}
```

## 🏗️ 架构概览

```
┌──────────────────────────────────────────────────┐
│                    用户接口                        │
│   CLI (code2pcb)  │  MCP Server  │  Python API  │
├──────────────────────────────────────────────────┤
│                    AI 引擎层                       │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │ 代码   │ │ 需求   │ │ 智能   │ │ 智能   │    │
│  │ 解析器 │ │→拓扑   │ │ 布局   │ │ 布线   │    │
│  └────────┘ └────────┘ └────────┘ └────────┘    │
│  ┌────────┐ ┌────────┐ ┌────────┐               │
│  │SI/PI   │ │EMC     │ │ 热     │               │
│  │ 分析   │ │ 预测   │ │ 分析   │               │
│  └────────┘ └────────┘ └────────┘               │
├──────────────────────────────────────────────────┤
│                    知识层                         │
│  数据手册库 │ 典型电路库 │ 器件参数库 │ 设计规则库  │
├──────────────────────────────────────────────────┤
│                    导出层                         │
│  KiCad (.sch/.pcb) │ Gerber │ BOM (含立创链接)   │
└──────────────────────────────────────────────────┘
```

## 📁 项目结构

```
code2pcb/
├── src/pcb_forge/           # 核心源码
│   ├── cli/main.py          # CLI入口 (Typer)
│   ├── core/
│   │   ├── parser.py        # 代码解析器
│   │   ├── generator.py     # 原理图生成器
│   │   ├── placer.py        # 布局引擎
│   │   └── router.py        # 布线引擎
│   ├── exporters/
│   │   └── kicad.py         # KiCad文件导出
│   ├── knowledge/
│   │   └── component.py     # 器件知识库
│   ├── mcp/
│   │   └── server.py        # MCP Server
│   └── utils/
│       └── helpers.py       # 工具函数
├── tests/                   # 测试
├── docs/                    # 文档
│   ├── ARCHITECTURE.md      # 技术架构
│   └── ROADMAP.md           # 开发路线图
├── examples/                # 示例
├── pyproject.toml           # 包配置
└── Makefile                 # 构建脚本
```

## 🛣️ 路线图

- **v0.1.0** (当前) — MVP：代码解析 + 规则引擎 + KiCad导出 + MCP
- **v0.2.0** — LLM集成：自然语言→原理图、器件智能选型
- **v1.0.0** — 完整流水线：Freerouting布线 + SI/PI分析 + 对接嘉立创打样
- **v2.0.0** — RL智能布线 + EMC预测 + 热分析
- **v3.0.0** — 全流程自动化：代码→板子一键完成

详见 [ROADMAP.md](docs/ROADMAP.md)

## 🤝 参与贡献

欢迎贡献代码、提交Issue、完善器件库！

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 开源协议

MIT License — 自由使用、修改、分发。

## 🙏 致谢

- [KiCad](https://kicad.org/) — 开源EDA基座
- [Freerouting](https://github.com/freerouting/freerouting) — 自动布线引擎
- [MCP](https://modelcontextprotocol.io/) — AI Agent通信协议
- [Trace](https://github.com/buildwithtrace/trace) — AI PCB设计灵感参考

---

**Made with ⚡ by [Liunian](https://github.com/liunian)**
