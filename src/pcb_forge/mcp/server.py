"""MCP Server — 让AI Agent能直接操作code2pcb"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import __version__
from ..core.parser import CodeParser
from ..core.generator import SchemaGenerator
from ..core.placer import Placer
from ..core.router import Router
from ..exporters.kicad import KiCadExporter
from ..knowledge.component import ComponentLibrary


def create_server() -> FastMCP:
    """
    创建code2pcb MCP Server。
    
    暴露以下工具给AI Agent：
    - analyze_code: 分析代码仓库，推断硬件需求
    - text2pcb: 从自然语言描述生成PCB
    - search_component: 搜索器件知识库
    - generate_schematic: 生成KiCad原理图
    - generate_pcb: 生成KiCad PCB文件
    - list_peripherals: 列出检测到的外设
    
    使用方式：
    1. 命令行: code2pcb mcp
    2. Claude Desktop配置:
       {
         "mcpServers": {
           "code2pcb": {
             "command": "code2pcb",
             "args": ["mcp"]
           }
         }
       }
    """
    mcp = FastMCP(
        name="code2pcb",
    )
    
    @mcp.tool()
    def analyze_code(directory: str) -> str:
        """
        分析嵌入式代码仓库，自动推断硬件需求。
        
        Args:
            directory: 代码仓库路径
        
        Returns:
            硬件规格JSON
        """
        parser = CodeParser(directory)
        spec = parser.parse()
        return _spec_to_json(spec)
    
    @mcp.tool()
    def text2pcb(description: str, output_dir: str = "./output") -> str:
        """
        从自然语言描述生成PCB设计。
        
        Args:
            description: 硬件需求描述（中文或英文）
            output_dir: 输出目录
        
        Returns:
            生成结果摘要
        """
        # v0.1.0: 基于关键词匹配的简单文本解析
        from ..core.parser import HardwareSpec, DetectedComponent, ComponentType
        from ..utils.helpers import sanitize_component_name
        
        spec = HardwareSpec(name=sanitize_component_name(description[:30]))
        spec.notes.append(f"📝 输入描述: {description}")
        
        # 简单关键词检测
        desc_lower = description.lower()
        
        if any(m in desc_lower for m in ["esp32", "esp-32"]):
            spec.mcu = "ESP32-S3"
            spec.notes.append("✅ 检测到ESP32系列MCU")
        elif any(m in desc_lower for m in ["stm32", "stm-32"]):
            spec.mcu = "STM32F103C8T6"
            spec.notes.append("✅ 检测到STM32系列MCU")
        
        if any(s in desc_lower for s in ["温度", "湿度", "temp", "humidity", "dht", "bme", "aht"]):
            spec.components.append(DetectedComponent(
                name="temp_sensor", type=ComponentType.SENSOR,
                description="温湿度传感器", likely_part="AHT20",
                confidence=0.8,
            ))
        
        if any(s in description for s in ["OLED", "oled", "屏幕", "显示"]):
            spec.components.append(DetectedComponent(
                name="display", type=ComponentType.DISPLAY,
                description="0.96寸 OLED 128x64", likely_part="SSD1306",
                confidence=0.9,
            ))
        
        if any(s in description for s in ["电池", "battery", "锂电", "充电"]):
            spec.components.append(DetectedComponent(
                name="power", type=ComponentType.POWER,
                description="锂电池充电管理", likely_part="TP4056",
                confidence=0.8,
            ))
            spec.voltage_supply.append("电池(3.7V LiPo)")
        
        if any(s in desc_lower for s in ["wifi", "无线", "蓝牙", "bluetooth", "ble"]):
            spec.components.append(DetectedComponent(
                name="wireless", type=ComponentType.WIRELESS,
                description="WiFi+BLE无线模块 (MCU内置)", confidence=0.9,
            ))
        
        if any(s in desc_lower for s in ["gps", "定位"]):
            spec.components.append(DetectedComponent(
                name="gps", type=ComponentType.SENSOR,
                description="GPS定位模块", likely_part="AT6558",
                confidence=0.7,
            ))
        
        if not spec.mcu:
            spec.notes.append("⚠️ 未检测到MCU型号，将使用默认ESP32-S3")
            spec.mcu = "ESP32-S3"
        
        spec.notes.append("💡 v0.1.0 文本解析基于关键词匹配，v1.0将集成LLM提升理解能力")
        
        return _full_pipeline(spec, output_dir)
    
    @mcp.tool()
    def search_component(query: str) -> str:
        """
        搜索器件知识库。
        
        Args:
            query: 器件名称或描述
        
        Returns:
            匹配的器件列表
        """
        results = ComponentLibrary.search(query)
        if not results:
            return json.dumps({"error": f"未找到匹配 '{query}' 的器件"}, ensure_ascii=False, indent=2)
        
        output = []
        for comp in results:
            output.append({
                "name": comp.name,
                "manufacturer": comp.manufacturer,
                "description": comp.description,
                "package": comp.package,
                "voltage": f"{comp.voltage_min}-{comp.voltage_max}V",
                "interface": comp.interface,
                "lcsc_part": comp.lcsc_part,
                "alternatives": comp.alternatives,
                "notes": comp.notes,
            })
        
        return json.dumps(output, ensure_ascii=False, indent=2)
    
    @mcp.tool()
    def generate_schematic(spec_json: str, output_dir: str = "./output") -> str:
        """
        从硬件规格JSON生成KiCad原理图。
        
        Args:
            spec_json: HardwareSpec的JSON字符串
            output_dir: 输出目录
        
        Returns:
            生成的文件路径
        """
        from ..core.parser import HardwareSpec
        spec = HardwareSpec(**json.loads(spec_json))
        return _full_pipeline(spec, output_dir)
    
    @mcp.tool()
    def get_version() -> str:
        """获取code2pcb版本信息"""
        return json.dumps({
            "name": "code2pcb",
            "version": __version__,
            "description": "AI驱动的开源PCB设计工具",
            "author": "Liunian",
        }, ensure_ascii=False, indent=2)
    
    return mcp


def _spec_to_json(spec) -> str:
    """将HardwareSpec转为JSON字符串"""
    from ..core.parser import HardwareSpec, PeripheralUsage, DetectedComponent
    
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, (list, tuple)):
            return [to_dict(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        elif hasattr(obj, 'value'):
            return obj.value
        return obj
    
    return json.dumps(to_dict(spec), ensure_ascii=False, indent=2)


def _full_pipeline(spec, output_dir: str) -> str:
    """执行完整的设计流水线"""
    import os
    
    # Step 1: 生成原理图拓扑
    generator = SchemaGenerator(spec)
    design = generator.generate()
    
    # Step 2: 布局
    placer = Placer(design)
    placement = placer.place()
    
    # Step 3: 布线
    router = Router(design, placement)
    routing = router.route()
    
    # Step 4: 导出
    exporter = KiCadExporter(design)
    sch_path = exporter.export_schematic(output_dir, placement)
    pcb_path = exporter.export_pcb(output_dir, placement, routing)
    
    # 收集所有日志
    all_notes = (
        design.notes +
        placement.notes +
        routing.notes
    )
    
    result = {
        "status": "success",
        "output_dir": os.path.abspath(output_dir),
        "files": {
            "schematic": sch_path,
            "pcb": pcb_path,
        },
        "summary": {
            "mcu": spec.mcu,
            "components": len(design.components),
            "nets": len(design.nets),
            "tracks": len(routing.tracks),
            "routing_completion": f"{routing.completion_rate:.0f}%",
        },
        "notes": all_notes,
        "warnings": routing.warnings,
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)
