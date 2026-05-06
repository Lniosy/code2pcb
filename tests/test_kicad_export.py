"""KiCad导出器测试"""

import os
import tempfile
from pathlib import Path

from pcb_forge.core.parser import HardwareSpec, DetectedComponent, ComponentType
from pcb_forge.core.generator import SchemaGenerator, SchematicDesign
from pcb_forge.core.placer import Placer
from pcb_forge.exporters.kicad import KiCadExporter


class TestKiCadExporter:
    """测试KiCad文件导出"""
    
    def _make_test_spec(self) -> HardwareSpec:
        """创建测试用硬件规格"""
        return HardwareSpec(
            name="test_board",
            mcu="ESP32-S3",
            components=[
                DetectedComponent(
                    name="oled", type=ComponentType.DISPLAY,
                    description="SSD1306 OLED", likely_part="SSD1306",
                    confidence=0.9,
                ),
                DetectedComponent(
                    name="sensor", type=ComponentType.SENSOR,
                    description="DHT22 温湿度", likely_part="DHT22",
                    confidence=0.9,
                ),
            ],
            voltage_supply=["3.3V", "USB 5V"],
        )
    
    def test_schematic_export(self):
        """测试原理图导出"""
        spec = self._make_test_spec()
        generator = SchemaGenerator(spec)
        design = generator.generate()
        placer = Placer(design)
        placement = placer.place()
        
        exporter = KiCadExporter(design)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = exporter.export_schematic(tmpdir, placement)
            
            assert os.path.exists(output_path)
            assert output_path.endswith(".kicad_sch")
            
            content = Path(output_path).read_text()
            assert "kicad_sch" in content
            assert "PCB Forge" in content
            assert "VCC" in content
            assert "GND" in content
    
    def test_pcb_export(self):
        """测试PCB导出"""
        spec = self._make_test_spec()
        generator = SchemaGenerator(spec)
        design = generator.generate()
        placer = Placer(design)
        placement = placer.place()
        
        from pcb_forge.core.router import Router
        router = Router(design, placement)
        routing = router.route()
        
        exporter = KiCadExporter(design)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = exporter.export_pcb(tmpdir, placement, routing)
            
            assert os.path.exists(output_path)
            assert output_path.endswith(".kicad_pcb")
            
            content = Path(output_path).read_text()
            assert "kicad_pcb" in content
            assert "Edge.Cuts" in content
    
    def test_design_has_components(self):
        """测试生成的设计包含器件"""
        spec = self._make_test_spec()
        generator = SchemaGenerator(spec)
        design = generator.generate()
        
        assert len(design.components) > 0
        refs = [c.reference for c in design.components]
        assert any(r.startswith("U") for r in refs)  # MCU
        assert any(r.startswith("C") for r in refs)  # 去耦电容


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
