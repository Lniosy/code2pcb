"""CLI 命令测试"""

from __future__ import annotations

import json
import os
import tempfile

import pytest
from typer.testing import CliRunner

from pcb_forge.cli.main import app

runner = CliRunner()


class TestAnalyzeCommand:
    """analyze 命令测试"""

    def test_analyze_esp_idf(self):
        """分析ESP-IDF项目"""
        result = runner.invoke(app, ["analyze", "test_projects/esp-idf/"])
        assert result.exit_code == 0
        assert "ESP32" in result.output

    def test_analyze_arduino(self):
        """分析Arduino项目"""
        result = runner.invoke(app, ["analyze", "test_projects/arduino-weather-dht22-bmp180-16x2/"])
        assert result.exit_code == 0

    def test_analyze_nonexistent_dir(self):
        """分析不存在的目录"""
        result = runner.invoke(app, ["analyze", "/nonexistent/path/"])
        assert result.exit_code != 0
        assert "不存在" in result.output

    def test_analyze_json_output(self):
        """JSON格式输出"""
        result = runner.invoke(app, ["analyze", "test_projects/esp-idf/", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "mcu" in data
        assert data["mcu"] != ""


class TestGenerateCommand:
    """generate 命令测试"""

    def test_generate_basic(self):
        """基本生成命令"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["generate", "ESP32温度监测", "-o", tmpdir])
            assert result.exit_code == 0
            assert "成功" in result.output

    def test_generate_creates_files(self):
        """生成命令创建文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["generate", "ESP32-S3 OLED显示", "-o", tmpdir])
            assert result.exit_code == 0
            files = os.listdir(tmpdir)
            assert any(f.endswith(".kicad_sch") for f in files)
            assert any(f.endswith(".kicad_pcb") for f in files)

    def test_generate_json_output(self):
        """JSON格式输出"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["generate", "ESP32", "-o", tmpdir, "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["status"] == "success"
            assert "files" in data

    def test_generate_stm32(self):
        """STM32项目生成"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["generate", "STM32蜂鸣器报警", "-o", tmpdir])
            assert result.exit_code == 0
            assert "STM32" in result.output


class TestSearchCommand:
    """search 命令测试"""

    def test_search_existing(self):
        """搜索已有器件"""
        result = runner.invoke(app, ["search", "ESP32"])
        assert result.exit_code == 0
        assert "Espressif" in result.output

    def test_search_nonexistent(self):
        """搜索不存在的器件"""
        result = runner.invoke(app, ["search", "XXXNONEXISTENT999"])
        assert result.exit_code == 0
        assert "未找到" in result.output

    def test_search_json(self):
        """JSON格式搜索"""
        result = runner.invoke(app, ["search", "DHT22", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_search_by_interface(self):
        """按接口搜索"""
        result = runner.invoke(app, ["search", "I2C"])
        assert result.exit_code == 0


class TestVersionCommand:
    """version 命令测试"""

    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "code2pcb" in result.output


class TestHelpCommand:
    """帮助信息测试"""

    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "generate" in result.output

    def test_analyze_help(self):
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0


class TestKnowledgeBase:
    """器件知识库测试"""

    def test_all_components_loaded(self):
        """内置器件全部加载"""
        from pcb_forge.knowledge.component import ComponentLibrary
        comps = ComponentLibrary.all_components()
        assert len(comps) >= 8

    def test_get_specific_component(self):
        """精确获取器件"""
        from pcb_forge.knowledge.component import ComponentLibrary
        esp = ComponentLibrary.get("ESP32-S3-WROOM-1")
        assert esp is not None
        assert esp.manufacturer == "Espressif"
        assert esp.lcsc_part != ""

    def test_get_nonexistent(self):
        """获取不存在的器件"""
        from pcb_forge.knowledge.component import ComponentLibrary
        assert ComponentLibrary.get("NOTEXIST") is None

    def test_component_has_datasheet(self):
        """主要器件有数据手册链接"""
        from pcb_forge.knowledge.component import ComponentLibrary
        esp = ComponentLibrary.get("ESP32-S3-WROOM-1")
        assert esp.datasheet_url.startswith("http")

    def test_component_alternatives(self):
        """器件有替代品信息"""
        from pcb_forge.knowledge.component import ComponentLibrary
        stm = ComponentLibrary.get("STM32F103C8T6")
        assert len(stm.alternatives) >= 2
