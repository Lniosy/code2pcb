"""code2pcb CLI — AI驱动的开源PCB设计工具"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .. import __version__

app = typer.Typer(
    name="code2pcb",
    help="🔧 AI驱动的开源PCB设计工具 — 代码/自然语言到电路板的全自动生成",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _print_banner():
    console.print(
        Panel(
            f"[bold cyan]code2pcb[/bold cyan] v{__version__}\n"
            "[dim]AI驱动的开源PCB设计工具 — 代码/自然语言到电路板[/dim]\n"
            "[dim]中文优先 · 开源免费 · CLI原生 · MCP集成[/dim]",
            border_style="cyan",
        )
    )

# 全局标记：是否静默模式（JSON输出时使用）
# (reserved for future use)


def _spec_to_table(spec) -> Table:
    """将 HardwareSpec 转为 Rich 表格"""
    table = Table(title=f"📊 硬件需求分析报告 — {spec.name}", show_lines=True)
    table.add_column("项目", style="bold cyan", width=16)
    table.add_column("内容", style="white")

    table.add_row("MCU", spec.mcu or "❓ 未检测到")
    table.add_row("框架", spec.framework or "❓ 未知")

    if spec.peripherals:
        periph_str = ", ".join(p.type.value if hasattr(p.type, 'value') else str(p.type) for p in spec.peripherals)
        table.add_row("外设", periph_str)
    else:
        table.add_row("外设", "—")

    if spec.components:
        for comp in spec.components:
            name = comp.likely_part or comp.name
            confidence = f"{'🟢' if comp.confidence >= 0.9 else '🟡' if comp.confidence >= 0.7 else '🔴'} {comp.confidence:.0%}"
            table.add_row(f"器件 {comp.type.value}", f"{comp.description}\n[dim]置信度: {confidence} | 来源: {comp.source_file}[/dim]")
    else:
        table.add_row("器件", "—")

    if spec.voltage_supply:
        table.add_row("供电", ", ".join(spec.voltage_supply))
    else:
        table.add_row("供电", "—")

    if spec.notes:
        table.add_row("备注", "\n".join(spec.notes))

    return table


@app.command()
def analyze(
    directory: str = typer.Argument(..., help="嵌入式代码仓库路径"),
    json_output: bool = typer.Option(False, "--json", "-j", help="输出JSON格式"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="同时生成KiCad文件到指定目录"),
):
    """🔍 分析嵌入式代码仓库，自动推断硬件需求"""
    if json_output:
        # 纯JSON输出（不走Rich，方便管道处理）
        import io
        json_console = Console(file=io.StringIO(), force_terminal=False)
        # 直接用 typer.echo 输出纯文本
        from ..core.parser import CodeParser
        parser = CodeParser(directory)
        spec = parser.parse()
        typer.echo(_spec_to_json_str(spec))
        return

    _print_banner()

    path = Path(directory)
    if not path.exists():
        console.print(f"[red]❌ 目录不存在: {directory}[/red]")
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task("扫描代码文件...", total=None)
        from ..core.parser import CodeParser
        parser = CodeParser(directory)
        spec = parser.parse()

    console.print(_spec_to_table(spec))

    if output_dir:
        _run_full_pipeline(spec, output_dir)


@app.command()
def generate(
    description: str = typer.Argument(..., help="硬件需求描述（中文或英文）"),
    output: str = typer.Option("./output", "--output", "-o", help="输出目录"),
    json_output: bool = typer.Option(False, "--json", "-j", help="输出JSON格式"),
):
    """💬 从自然语言描述生成PCB设计"""
    # 直接调用流水线（不依赖MCP内部实现）
    from ..core.parser import HardwareSpec, DetectedComponent, ComponentType
    from ..utils.helpers import sanitize_component_name

    spec = HardwareSpec(name=sanitize_component_name(description[:30]))
    spec.notes.append(f"📝 输入描述: {description}")
    desc_lower = description.lower()

    if any(m in desc_lower for m in ["esp32", "esp-32"]):
        spec.mcu = "ESP32-S3"
    elif any(m in desc_lower for m in ["stm32", "stm-32"]):
        spec.mcu = "STM32F103C8T6"
    else:
        spec.mcu = "ESP32-S3"

    if any(s in desc_lower for s in ["温度", "湿度", "temp", "humidity", "dht", "bme", "aht"]):
        spec.components.append(DetectedComponent(
            name="temp_sensor", type=ComponentType.SENSOR,
            description="温湿度传感器", likely_part="AHT20", confidence=0.8,
        ))
    if any(s in description for s in ["OLED", "oled", "屏幕", "显示"]):
        spec.components.append(DetectedComponent(
            name="display", type=ComponentType.DISPLAY,
            description="0.96寸 OLED 128x64", likely_part="SSD1306", confidence=0.9,
        ))
    if any(s in description for s in ["电池", "battery", "锂电", "充电"]):
        spec.components.append(DetectedComponent(
            name="power", type=ComponentType.POWER,
            description="锂电池充电管理", likely_part="TP4056", confidence=0.8,
        ))
        spec.voltage_supply.append("电池(3.7V LiPo)")

    if any(s in desc_lower for s in ["wifi", "蓝牙", "bluetooth", "ble"]):
        spec.components.append(DetectedComponent(
            name="wireless", type=ComponentType.WIRELESS,
            description="WiFi+BLE无线模块 (MCU内置)", confidence=0.9,
        ))

    # 生成
    from ..core.generator import SchemaGenerator
    from ..core.placer import Placer
    from ..core.router import Router
    from ..exporters.kicad import KiCadExporter

    generator = SchemaGenerator(spec)
    design = generator.generate()

    placer = Placer(design)
    placement = placer.place()

    router = Router(design, placement)
    routing = router.route()

    exporter = KiCadExporter(design)
    sch_path = exporter.export_schematic(output, placement)
    pcb_path = exporter.export_pcb(output, placement, routing)

    result = {
        "status": "success",
        "output_dir": str(Path(output).absolute()),
        "files": {"schematic": sch_path, "pcb": pcb_path},
        "summary": {
            "mcu": spec.mcu,
            "components": len(design.components),
            "nets": len(design.nets),
            "tracks": len(routing.tracks),
            "routing_completion": f"{routing.completion_rate:.0f}%",
        },
        "notes": design.notes + placement.notes + routing.notes,
        "warnings": routing.warnings,
    }

    if json_output:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    _print_banner()

    # 显示结果
    summary = result["summary"]
    console.print(Panel(
        f"[green]✅ 设计生成成功[/green]\n\n"
        f"📁 输出目录: {result['output_dir']}\n"
        f"📄 原理图: [cyan]{result['files']['schematic']}[/cyan]\n"
        f"🔧 PCB文件: [cyan]{result['files']['pcb']}[/cyan]\n\n"
        f"📊 统计:\n"
        f"   MCU: {summary['mcu']}\n"
        f"   器件: {summary['components']}个\n"
        f"   网络: {summary['nets']}个\n"
        f"   走线: {summary['tracks']}条\n"
        f"   布线率: {summary['routing_completion']}",
        title="🎉 生成报告",
        border_style="green",
    ))

    if result.get("warnings"):
        console.print("[yellow]⚠️ 警告:[/yellow]")
        for w in result["warnings"]:
            console.print(f"   • {w}")

    if result.get("notes"):
        console.print("[dim]📝 备注:[/dim]")
        for n in result["notes"]:
            console.print(f"   {n}")


@app.command()
def search(
    query: str = typer.Argument(..., help="器件名称或描述"),
    json_output: bool = typer.Option(False, "--json", "-j", help="输出JSON格式"),
):
    """📚 搜索器件知识库"""
    from ..knowledge.component import ComponentLibrary

    results = ComponentLibrary.search(query)

    if not results:
        console.print(f"[yellow]未找到匹配 '{query}' 的器件[/yellow]")
        return

    if json_output:
        typer.echo(_components_to_json_str(results))
        return

    table = Table(title=f"📚 器件搜索结果 — '{query}'", show_lines=True)
    table.add_column("名称", style="bold cyan")
    table.add_column("厂商", style="dim")
    table.add_column("描述")
    table.add_column("封装", style="green")
    table.add_column("接口")
    table.add_column("立创SKU", style="yellow")

    for comp in results:
        alt = f" [dim]替代: {', '.join(comp.alternatives)}[/dim]" if comp.alternatives else ""
        table.add_row(
            comp.name,
            comp.manufacturer,
            comp.description + alt,
            comp.package,
            comp.interface,
            comp.lcsc_part or "—",
        )

    console.print(table)


@app.command()
def version():
    """显示版本信息"""
    console.print(
        f"[bold cyan]code2pcb[/bold cyan] v{__version__}\n"
        f"[dim]AI驱动的开源PCB设计工具\n"
        f"MIT License · 中文优先 · 开源免费[/dim]"
    )


@app.command()
def mcp():
    """🤖 启动MCP Server（供AI Agent调用）"""
    from ..mcp.server import create_server
    server = create_server()
    server.run()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        _print_banner()
        console.print("\n使用 [bold cyan]code2pcb --help[/bold cyan] 查看所有命令\n")


def _spec_to_json_str(spec) -> str:
    """将 HardwareSpec 转为 JSON 字符串"""
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


def _components_to_json_str(components) -> str:
    """将器件列表转为 JSON 字符串"""
    output = []
    for comp in components:
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


def _run_full_pipeline(spec, output_dir: str):
    """执行完整设计流水线"""
    from ..core.generator import SchemaGenerator
    from ..core.placer import Placer
    from ..core.router import Router
    from ..exporters.kicad import KiCadExporter

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("生成原理图拓扑...", total=None)

        generator = SchemaGenerator(spec)
        design = generator.generate()

        progress.update(task, description="智能布局...")
        placer = Placer(design)
        placement = placer.place()

        progress.update(task, description="自动布线...")
        router = Router(design, placement)
        routing = router.route()

        progress.update(task, description="导出KiCad文件...")
        exporter = KiCadExporter(design)
        sch_path = exporter.export_schematic(output_dir, placement)
        pcb_path = exporter.export_pcb(output_dir, placement, routing)

    console.print(Panel(
        f"[green]✅ KiCad文件已生成[/green]\n"
        f"📄 原理图: [cyan]{sch_path}[/cyan]\n"
        f"🔧 PCB: [cyan]{pcb_path}[/cyan]\n"
        f"📊 {len(design.components)}个器件, {len(routing.tracks)}条走线, "
        f"布线率 {routing.completion_rate:.0%}",
        title="🎉 导出成功",
        border_style="green",
    ))


if __name__ == "__main__":
    app()
