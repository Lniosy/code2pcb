"""通用工具函数"""

import os
import re
from pathlib import Path
from typing import Optional


def generate_uuid() -> str:
    """生成短UUID，用于KiCad组件标识"""
    import uuid
    return uuid.uuid4().hex[:12]


def find_code_files(directory: str) -> list[Path]:
    """
    递归扫描目录，找出嵌入式代码文件。
    
    支持的格式：
    - C/C++: .c, .h, .cpp, .hpp
    - Arduino: .ino
    - Python: .py
    - Rust: .rs
    """
    extensions = {".c", ".h", ".cpp", ".hpp", ".ino", ".py", ".rs"}
    code_files: list[Path] = []
    
    root = Path(directory)
    if not root.exists():
        return code_files
    
    # 跳过常见非源码目录
    skip_dirs = {
        "node_modules", ".git", "__pycache__", "build", "dist",
        "venv", ".venv", "env", ".eggs", ".idea", ".vscode",
        "components", "managed_components",  # ESP-IDF managed deps
    }
    
    for path in root.rglob("*"):
        if any(skip in path.parts for skip in skip_dirs):
            continue
        if path.suffix in extensions:
            code_files.append(path)
    
    return sorted(code_files)


def detect_framework(files: list[Path]) -> Optional[str]:
    """根据项目文件结构检测嵌入式框架"""
    # 从代码文件反推项目根目录
    roots = set()
    for f in files:
        roots.add(f.parent)
    # 也检查代码文件的祖父目录（common: main/main.c）
    for f in files:
        if f.parent.name in ("main", "src", "lib", "components"):
            roots.add(f.parent.parent)
    
    # 在项目根目录搜索构建系统文件
    for root in roots:
        # ESP-IDF: CMakeLists.txt with idf_component_register
        for cmake in root.glob("CMakeLists.txt"):
            try:
                content = cmake.read_text(errors="ignore")[:2000]
                if "idf_component_register" in content or "esp-idf" in content.lower():
                    return "esp-idf"
                if "ZEPHYR" in content or "zephyr_" in content:
                    return "zephyr"
            except OSError:
                continue
        
        # PlatformIO
        if (root / "platformio.ini").exists():
            return "platformio"
        
        # STM32 HAL (check for HAL headers or .ioc files)
        for hal_file in list(root.glob("*.ioc")) + list(root.glob("**/stm32f*_hal_conf.h")):
            return "stm32-hal"
        
        # RP2040 Pico SDK
        for pico in list(root.glob("pico_sdk_import.cmake")) + list(root.glob("CMakeLists.txt")):
            try:
                content = pico.read_text(errors="ignore")[:2000]
                if "pico_sdk" in content:
                    return "pico-sdk"
            except OSError:
                continue
    
    # 检测 .ino 文件
    if any(f.suffix == ".ino" for f in files):
        return "arduino"
    
    # 检测 Cargo.toml（Rust嵌入式）
    if any(f.name == "Cargo.toml" for f in files):
        return "rust-embedded"
    
    # 检测 MicroPython 特征
    for f in files:
        if f.suffix == ".py":
            content = f.read_text(errors="ignore")[:500]
            if "machine." in content and ("Pin" in content or "I2C" in content):
                return "micropython"
    
    return None


def sanitize_component_name(name: str) -> str:
    """将组件名转为合法的KiCad引用标识"""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "COMP"
