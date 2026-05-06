"""嵌入式代码解析器 — 从固件代码推断硬件需求"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..utils.helpers import find_code_files, detect_framework


class PeripheralType(str, Enum):
    """硬件外设类型"""
    SPI = "SPI"
    I2C = "I2C"
    UART = "UART"
    ADC = "ADC"
    PWM = "PWM"
    GPIO = "GPIO"
    CAN = "CAN"
    SDIO = "SDIO"
    USB = "USB"
    ETHERNET = "Ethernet"
    DAC = "DAC"
    TIMER = "Timer"


class ComponentType(str, Enum):
    """器件类型"""
    MCU = "MCU"
    SENSOR = "Sensor"
    DISPLAY = "Display"
    WIRELESS = "Wireless"
    POWER = "Power"
    STORAGE = "Storage"
    AUDIO = "Audio"
    MOTOR = "Motor"
    LED = "LED"
    BUTTON = "Button"
    CONNECTOR = "Connector"
    PASSIVE = "Passive"  # R/C/L
    IC = "IC"  # 其他IC


@dataclass
class DetectedComponent:
    """检测到的器件"""
    name: str
    type: ComponentType
    description: str = ""
    quantity: int = 1
    likely_part: str = ""  # 可能的器件型号
    confidence: float = 0.5  # 置信度 0-1
    source_file: str = ""  # 来源文件


@dataclass
class PeripheralUsage:
    """外设使用信息"""
    type: PeripheralType
    instance: str = ""  # 如 SPI1, I2C0
    pins: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)


@dataclass
class HardwareSpec:
    """
    硬件规格 — 代码解析的完整输出。
    这是 code2pcb 的核心数据结构，贯穿整个设计流水线。
    """
    name: str = "unnamed"
    mcu: str = ""  # 如 "ESP32-S3", "STM32F103C8T6"
    framework: str = ""
    peripherals: list[PeripheralUsage] = field(default_factory=list)
    components: list[DetectedComponent] = field(default_factory=list)
    voltage_supply: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class CodeParser:
    """
    嵌入式代码解析器。
    
    通过静态分析固件代码，自动推断所需的：
    - MCU型号
    - 使用的外设（SPI/I2C/UART等）
    - 外接器件（传感器、显示屏等）
    - 供电需求
    
    支持框架：ESP-IDF, Arduino, PlatformIO, Zephyr, MicroPython, 通用C
    """
    
    # MCU检测模式
    MCU_PATTERNS: dict[str, list[str]] = {
        "ESP32-S3": [r"ESP32[_-]?S3", r"CONFIG_IDF_TARGET_ESP32S3"],
        "ESP32-S2": [r"ESP32[_-]?S2", r"CONFIG_IDF_TARGET_ESP32S2"],
        "ESP32-C3": [r"ESP32[_-]?C3", r"CONFIG_IDF_TARGET_ESP32C3"],
        "ESP32-C6": [r"ESP32[_-]?C6", r"CONFIG_IDF_TARGET_ESP32C6"],
        "ESP32-H2": [r"ESP32[_-]?H2", r"CONFIG_IDF_TARGET_ESP32H2"],
        "ESP32": [r"ESP32(?![-_SC])", r"#include.*esp32"],
        "ESP8266": [r"ESP8266", r"esp8266"],
        "STM32F103C8T6": [r"STM32F103C8", r"BluePill"],
        "STM32F407": [r"STM32F407", r"STM32F4"],
        "STM32F103": [r"STM32F103"],
        "STM32H7": [r"STM32H7"],
        "STM32G4": [r"STM32G4"],
        "RP2040": [r"RP2040", r"raspberry_pi_pico", r"pico"],
        "ATmega328P": [r"ATmega328[Pp]", r"Arduino\s+Uno", r"BOARD_UNO"],
        "ATmega2560": [r"ATmega2560", r"Arduino\s+Mega"],
        "ATmega32U4": [r"ATmega32U4", r"Arduino\s+(Leonardo|Micro|Pro\s+Micro)", r"BOARD_LEONARDO"],
        "nRF52840": [r"nRF52840", r"NRF52840"],
        "nRF52832": [r"nRF52832", r"NRF52832"],
        "STM32": [r"STM32"],  # 通用STM32兜底
    }
    
    # 外设检测模式
    PERIPHERAL_PATTERNS: dict[str, list[PeripheralType]] = {
        # 通用 include 检测（最宽泛，放最前面）
        r'["<]driver/i2c\.h[">]': [PeripheralType.I2C],
        r'["<]driver/spi_master\.h[">]': [PeripheralType.SPI],
        r'["<]driver/uart\.h[">]': [PeripheralType.UART],
        r'["<]driver/adc\.h[">]': [PeripheralType.ADC],
        r'["<]driver/gpio\.h[">]': [PeripheralType.GPIO],
        # ESP-IDF
        r"spi_bus_[a-z_]*|spi_device_": [PeripheralType.SPI],
        r"i2c_master_|i2c_driver_": [PeripheralType.I2C],
        r"uart_driver_|uart_param_|esp_uart": [PeripheralType.UART],
        r"adc1_get_raw|adc1_config|esp_adc": [PeripheralType.ADC],
        r"ledc_|ledc_timer": [PeripheralType.PWM],
        r"gpio_set_level|gpio_config|gpio_pad": [PeripheralType.GPIO],
        r"sdio_|sdmmc_": [PeripheralType.SDIO],
        r"esp_usb|tinyusb": [PeripheralType.USB],
        r"esp_eth": [PeripheralType.ETHERNET],
        # Arduino
        r"SPI\.begin|SPI\.transfer": [PeripheralType.SPI],
        r"Wire\.begin|Wire\.requestFrom": [PeripheralType.I2C],
        r"[\"<]Wire\.h[\">]": [PeripheralType.I2C],
        r"[\"<]SPI\.h[\">]": [PeripheralType.SPI],
        r"Serial\.begin|Serial[0-9]\.begin": [PeripheralType.UART],
        r"analogRead|analogWrite": [PeripheralType.ADC],
        r"analogWrite.*PWM": [PeripheralType.PWM],
        r"pinMode|digitalWrite|digitalRead": [PeripheralType.GPIO],
        # Zephyr
        r"spi_.*_config|SPI_.*_DT": [PeripheralType.SPI],
        r"i2c_.*_config|I2C_.*_DT": [PeripheralType.I2C],
        # STM32 HAL
        r"HAL_I2C_[A-Z]|hi2c\d": [PeripheralType.I2C],
        r"HAL_SPI_[A-Z]|hspi\d": [PeripheralType.SPI],
        r"HAL_UART_[A-Z]|huart\d": [PeripheralType.UART],
        r"HAL_ADC_[A-Z]|hadc\d": [PeripheralType.ADC],
        r"HAL_TIM_PWM|htim\d|HAL_DAC_": [PeripheralType.PWM],
        r"HAL_GPIO_[A-Z]": [PeripheralType.GPIO],
        r"HAL_SD_|h_sdmmc|HAL_SDIO_": [PeripheralType.SDIO],
        r"HAL_USB_": [PeripheralType.USB],
        # STM32 寄存器级操作 (NOHAL)
        r"I2C\d?->CR\d|SPI\d?->CR\d|USART\d?->|ADC\d?->": [PeripheralType.GPIO],
        r"I2C\d->SR\d|I2C\d->DR": [PeripheralType.I2C],
        r"SPI\d->DR|SPI\d->SR": [PeripheralType.SPI],
        # RP2040 Pico SDK
        r"i2c_init|pico_i2c|i2c_write_blocking": [PeripheralType.I2C],
        r"spi_init|pico_spi|spi_write_blocking": [PeripheralType.SPI],
        r"uart_init|pico_uart|uart_putc": [PeripheralType.UART],
        r"adc_init|pico_adc|adc_read": [PeripheralType.ADC],
        r"pwm_set_gpio_level|pwm_init|pico_pwm": [PeripheralType.PWM],
        # MicroPython
        r"machine\.SPI|machine\.SoftSPI": [PeripheralType.SPI],
        r"machine\.I2C|machine\.SoftI2C": [PeripheralType.I2C],
        r"machine\.UART": [PeripheralType.UART],
        r"machine\.ADC|machine\.Pin.*ADC": [PeripheralType.ADC],
        r"machine\.PWM": [PeripheralType.PWM],
    }
    
    # 器件检测模式（按优先级排序）
    COMPONENT_PATTERNS: dict[str, tuple[ComponentType, str, float]] = {
        # 显示
        r"SSD1306|ssd1306|Sh1106|sh1106": (ComponentType.DISPLAY, "0.96寸/1.3寸 OLED 128x64 (I2C/SPI)", 0.95),
        r"ST7789|st7789|ILI9341|ili9341": (ComponentType.DISPLAY, "TFT LCD 彩屏 (SPI)", 0.95),
        r"ST7920|LCD12864": (ComponentType.DISPLAY, "LCD12864 中文字符屏", 0.90),
        r"TM1637|tm1637": (ComponentType.DISPLAY, "TM1637 4位数码管", 0.90),
        r"MAX7219|max7219": (ComponentType.DISPLAY, "MAX7219 LED点阵驱动", 0.90),
        r"LCD1602|lcd1602|LiquidCrystal_I2C|PCF8574": (ComponentType.DISPLAY, "1602字符LCD (I2C/并行)", 0.90),
        r"SSD1351|ssd1351": (ComponentType.DISPLAY, "SSD1351 1.5寸OLED (SPI)", 0.90),
        r"WS2812|ws2812|NeoPixel|neopixel": (ComponentType.LED, "WS2812 全彩LED灯带", 0.95),
        # 传感器
        r"DHT\d+|dht_\d+|DHT sensor": (ComponentType.SENSOR, "DHT系列温湿度传感器", 0.95),
        r"BME280|bme280|BME\b": (ComponentType.SENSOR, "BME280 温湿度气压传感器", 0.95),
        r"BMP280|bmp280": (ComponentType.SENSOR, "BMP280 气压传感器", 0.90),
        r"MPU6050|mpu6050": (ComponentType.SENSOR, "MPU6050 六轴IMU", 0.95),
        r"MPU9250|mpu9250": (ComponentType.SENSOR, "MPU9250 九轴IMU", 0.90),
        r"VL53L0|vl53l0": (ComponentType.SENSOR, "VL53L0X 激光测距传感器", 0.95),
        r"HCSR04|hcsr04|ultrasonic": (ComponentType.SENSOR, "HC-SR04 超声波测距", 0.90),
        r"MQ-?2|MQ-?135|mq[0-9]": (ComponentType.SENSOR, "MQ系列气体传感器", 0.85),
        r"DS18B20|ds18b20|OneWire": (ComponentType.SENSOR, "DS18B20 单总线温度传感器", 0.95),
        r"LSM6DS|lsm6ds": (ComponentType.SENSOR, "LSM6DS系列六轴IMU", 0.90),
        r"AHT10|aht10|AHT20|aht20": (ComponentType.SENSOR, "AHT系列温湿度传感器", 0.90),
        # 无线
        r"WiFi\.begin|esp_wifi|WIFI": (ComponentType.WIRELESS, "WiFi模块 (ESP32内置)", 0.99),
        r"\bBLE\b|\bbluetooth\b|\besp_ble\b|\bNimBLE\b": (ComponentType.WIRELESS, "蓝牙BLE模块", 0.99),
        r"LoRa|lora|SX1278|sx1278": (ComponentType.WIRELESS, "LoRa无线模块", 0.90),
        r"NRF24|nrf24": (ComponentType.WIRELESS, "NRF24L01 无线模块", 0.90),
        r"MQTT|mqtt_client": (ComponentType.WIRELESS, "MQTT协议栈", 0.85),
        # 电源
        r"battery|Battery|BATTERY": (ComponentType.POWER, "电池供电", 0.80),
        r"solar|Solar": (ComponentType.POWER, "太阳能充电", 0.80),
        r"TP4056|tp4056|CHG4056|chg4056": (ComponentType.POWER, "TP4056 锂电池充电管理", 0.95),
        r"AXP202|axp202|AXP192|axp192": (ComponentType.POWER, "AXP系列电源管理IC", 0.90),
        r"AMS1117|ams1117|LDO": (ComponentType.POWER, "LDO线性稳压", 0.75),
        r"MP1584|mp1584|buck": (ComponentType.POWER, "Buck降压模块", 0.80),
        # 存储
        r"SD_?card|fatfs|f_mount|SD_MMC": (ComponentType.STORAGE, "SD卡/TF卡", 0.90),
        r"SPIFFS|spiffs|LittleFS|littlefs|nvs_": (ComponentType.STORAGE, "Flash存储", 0.85),
        r"W25Q|w25q|AT24C|at24c": (ComponentType.STORAGE, "外部Flash/EEPROM", 0.90),
        r"u8g2|U8G2|U8x8": (ComponentType.DISPLAY, "u8g2通用显示库(支持多屏)", 0.85),
        # 其他
        r"servo|Servo|SERVO": (ComponentType.MOTOR, "舵机", 0.85),
        r"stepper|Stepper": (ComponentType.MOTOR, "步进电机", 0.85),
        r"buzzer|Buzzer": (ComponentType.AUDIO, "蜂鸣器", 0.90),
        r"relay|Relay": (ComponentType.CONNECTOR, "继电器", 0.90),
        r"GPS|gps\.init|TinyGPS": (ComponentType.SENSOR, "GPS模块", 0.90),
    }
    
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.files = find_code_files(str(self.directory))
        self.framework = detect_framework(self.files)
        self._file_contents: dict[Path, str] = {}
    
    def _read_file(self, path: Path) -> str:
        """读取文件内容（带缓存）"""
        if path not in self._file_contents:
            try:
                self._file_contents[path] = path.read_text(errors="ignore")
            except OSError:
                self._file_contents[path] = ""
        return self._file_contents[path]
    
    def _search_all_files(self, pattern: str) -> list[tuple[str, Path]]:
        """在所有源文件中搜索正则模式，返回 (匹配文本, 文件路径) 列表"""
        regex = re.compile(pattern, re.IGNORECASE)
        results: list[tuple[str, Path]] = []
        for path in self.files:
            content = self._read_file(path)
            for match in regex.finditer(content):
                results.append((match.group(), path))
        return results
    
    def detect_mcu(self) -> str:
        """检测MCU型号"""
        # 优先从配置文件中检测（sdkconfig, .ioc等可能不在代码文件列表中）
        config_patterns = ["sdkconfig", "*.ioc", "CMakeLists.txt"]
        for cfg in config_patterns:
            for f in self.directory.rglob(cfg):
                content = self._read_file(f)
                for mcu, patterns in self.MCU_PATTERNS.items():
                    if mcu == "STM32":
                        continue
                    for p in patterns:
                        if re.search(p, content):
                            return mcu
        
        # 然后从源码中检测
        for mcu, patterns in self.MCU_PATTERNS.items():
            if mcu in ("STM32",):  # 通用模式放最后
                continue
            for p in patterns:
                if self._search_all_files(p):
                    return mcu
        
        # 通用STM32兜底
        if self._search_all_files(r"STM32"):
            return "STM32"
        
        return ""
    
    def detect_peripherals(self) -> list[PeripheralUsage]:
        """检测使用的外设"""
        found: dict[PeripheralType, PeripheralUsage] = {}
        
        for pattern, periph_types in self.PERIPHERAL_PATTERNS.items():
            matches = self._search_all_files(pattern)
            for ptype in periph_types:
                if matches and ptype not in found:
                    found[ptype] = PeripheralUsage(type=ptype)
        
        return list(found.values())
    
    def detect_components(self) -> list[DetectedComponent]:
        """检测外接器件"""
        components: dict[str, DetectedComponent] = {}
        
        for pattern, (ctype, desc, confidence) in self.COMPONENT_PATTERNS.items():
            matches = self._search_all_files(pattern)
            if matches:
                # 从匹配文本中提取具体型号
                match_text = matches[0][0]
                cleaned = re.sub(r"[^a-zA-Z0-9-]", "", match_text)
                likely = cleaned if cleaned else ""
                name = likely if likely else desc.split("(")[0].strip()
                key = f"{ctype.value}:{name}"

                if key not in components:
                    source = str(matches[0][1].relative_to(self.directory))
                    components[key] = DetectedComponent(
                        name=name,
                        type=ctype,
                        description=desc,
                        likely_part=likely,
                        confidence=confidence,
                        source_file=source,
                    )
        
        return list(components.values())
    
    def detect_power(self) -> list[str]:
        """推断供电需求"""
        voltages = set()
        
        # 检测明确的电压引用
        for match, _ in self._search_all_files(r"(\d+\.?\d*)\s*[Vv]"):
            try:
                v = float(match)
                # 只保留常见的逻辑电压
                for common in [3.3, 5.0, 1.8, 12.0, 3.0, 1.2, 24.0, 9.0]:
                    if abs(v - common) < 0.5:
                        voltages.add(f"{common}V")
                        break
            except ValueError:
                continue
        
        # 如果有电池引用
        if self._search_all_files(r"battery|Battery|锂电池|LiPo"):
            voltages.add("电池(3.7V LiPo)")
        
        if self._search_all_files(r"USB|usb"):
            voltages.add("USB 5V")
        
        return sorted(voltages)
    
    def parse(self) -> HardwareSpec:
        """
        执行完整解析，返回硬件规格。
        
        这是 CodeParser 的主入口方法。
        """
        if not self.files:
            return HardwareSpec(
                name=self.directory.name,
                notes=[f"⚠️ 未在 {self.directory} 中找到代码文件"],
            )
        
        spec = HardwareSpec(
            name=self.directory.name,
            framework=self.framework or "unknown",
        )
        
        # 检测MCU
        spec.mcu = self.detect_mcu()
        
        # 检测外设
        spec.peripherals = self.detect_peripherals()
        
        # 检测器件
        spec.components = self.detect_components()
        
        # 检测供电
        spec.voltage_supply = self.detect_power()
        
        # 生成特征摘要
        spec.features = self._generate_features(spec)
        
        # 生成备注
        spec.notes = self._generate_notes(spec)
        
        return spec
    
    def _generate_features(self, spec: HardwareSpec) -> list[str]:
        """根据检测结果生成功能特征列表"""
        features = []
        
        if spec.mcu:
            features.append(f"主控: {spec.mcu}")
        
        periph_names = [p.type.value for p in spec.peripherals]
        if periph_names:
            features.append(f"外设: {', '.join(periph_names)}")
        
        comp_names = [c.description for c in spec.components]
        if comp_names:
            features.append(f"器件: {', '.join(comp_names)}")
        
        return features
    
    def _generate_notes(self, spec: HardwareSpec) -> list[str]:
        """生成设计备注和建议"""
        notes = []
        notes.append(f"📁 扫描了 {len(self.files)} 个源文件")
        
        if spec.framework:
            notes.append(f"🔧 检测到框架: {spec.framework}")
        
        if not spec.mcu:
            notes.append("⚠️ 未能自动检测MCU型号，请在生成的规格中手动指定")
        
        if not spec.voltage_supply:
            notes.append("💡 建议确认供电方案（USB/电池/外部电源）")
        
        # 检查是否需要去耦电容
        has_ic = any(c.type in (ComponentType.IC, ComponentType.MCU) for c in spec.components)
        if has_ic or spec.mcu:
            notes.append("💡 将自动为每个IC电源引脚添加去耦电容 (100nF + 10µF)")
        
        return notes
