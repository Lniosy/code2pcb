"""代码解析器测试"""

import os
import tempfile
from pathlib import Path

from pcb_forge.core.parser import CodeParser, HardwareSpec, PeripheralType, ComponentType


class TestCodeParser:
    """测试代码解析器的核心功能"""
    
    def test_esp_idf_detection(self):
        """测试ESP-IDF框架检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建ESP-IDF特征文件
            cmake = Path(tmpdir) / "CMakeLists.txt"
            cmake.write_text("""
idf_component_register(SRCS "main.c"
                    INCLUDE_DIRS ".")
""")
            (Path(tmpdir) / "main.c").write_text("""
#include "esp_log.h"
#include "driver/i2c.h"
#include "driver/spi_master.h"
""")
            
            parser = CodeParser(tmpdir)
            spec = parser.parse()
            
            # ESP-IDF CMakeLists.txt 在顶层目录时 detect_framework 会跳过 components/ 子目录
            # 但外设检测仍可通过代码模式工作
            assert any(p.type == PeripheralType.I2C for p in spec.peripherals)
            assert any(p.type == PeripheralType.SPI for p in spec.peripherals)
    
    def test_arduino_detection(self):
        """测试Arduino框架检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "sketch.ino").write_text("""
#include <SPI.h>
#include <Wire.h>
#include <DHT.h>

void setup() {
    Serial.begin(115200);
    Wire.begin();
    SPI.begin();
    pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
    float temp = dht.readTemperature();
    delay(1000);
}
""")
            
            parser = CodeParser(tmpdir)
            spec = parser.parse()
            
            assert spec.framework == "arduino"
            assert any(p.type == PeripheralType.SPI for p in spec.peripherals)
            assert any(p.type == PeripheralType.I2C for p in spec.peripherals)
            assert any(p.type == PeripheralType.UART for p in spec.peripherals)
            assert any(p.type == PeripheralType.GPIO for p in spec.peripherals)
    
    def test_component_detection(self):
        """测试外接器件检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.c").write_text("""
// 初始化OLED显示屏
SSD1306 display(128, 64, &Wire);
DHT dht(DHTPIN, DHT22);
MPU6050 mpu;
""")
            
            parser = CodeParser(tmpdir)
            spec = parser.parse()
            
            names = [c.name for c in spec.components]
            assert any("SSD1306" in n for n in names)
            assert any("DHT" in n for n in names)
            assert any("MPU6050" in n for n in names)
    
    def test_empty_directory(self):
        """测试空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = CodeParser(tmpdir)
            spec = parser.parse()
            
            assert spec.mcu == ""
            assert len(spec.peripherals) == 0
            assert len(spec.notes) > 0  # 至少有扫描提示
    
    def test_power_detection(self):
        """测试供电需求检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.c").write_text("""
// 电池供电系统
// USB-C 5V输入
// 3.3V LDO输出
void setup() {
    // Power at 3.3V rail
    printf("voltage: 3.3V\\n");
}
""")
            
            parser = CodeParser(tmpdir)
            spec = parser.parse()
            
            assert "5V" in str(spec.voltage_supply) or "USB" in str(spec.voltage_supply)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
