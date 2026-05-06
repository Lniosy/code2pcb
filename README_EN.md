# code2pcb 🔧⚡

> AI-powered open-source PCB design tool — From code/natural language to circuit board in one step

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)]()

## What is it?

code2pcb is an AI-driven PCB design tool for embedded developers. Feed it your firmware codebase or a natural language description, and it automatically generates:

```
Code/Text → Hardware Analysis → Schematic → Layout → Routing → KiCad Files → Fabrication
```

## Quick Start

```bash
pip install -e .

# Analyze embedded code to detect hardware requirements
code2pcb analyze ./my-esp32-project/

# Generate PCB from natural language
code2pcb text2pcb "ESP32 temperature sensor with OLED and battery"

# Generate PCB from code repository
code2pcb code2pcb ./my-esp32-project/
```

## MCP Server

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

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Code Parsing | ✅ v0.1 | Detect MCU/peripherals/components from firmware |
| Text→PCB | ✅ v0.1 | Natural language to PCB design |
| Auto Layout | ✅ v0.1 | Rule-based functional zone layout |
| Auto Routing | 🔨 v0.1 | Schematic routing (Freerouting integration in v1.0) |
| KiCad Export | ✅ v0.1 | .kicad_sch and .kicad_pcb files |
| MCP Server | ✅ v0.1 | Native AI Agent integration |
| Component DB | ✅ v0.1 | Common parts with LCSC SKUs |

## Architecture

Built on KiCad's open-source foundation with an AI-native design pipeline:
- **Parser**: Static analysis of ESP-IDF/Arduino/Zephyr/MicroPython code
- **Generator**: Hardware spec → schematic topology
- **Placer**: Functional zone-based component placement
- **Router**: Track routing with DRC awareness
- **Exporter**: KiCad S-expression file generation

## License

MIT License
