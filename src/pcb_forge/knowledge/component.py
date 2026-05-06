"""器件知识库 — 元件参数、推荐电路、封装信息"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ComponentInfo:
    """器件信息"""
    name: str
    manufacturer: str = ""
    description: str = ""
    package: str = ""
    voltage_min: float = 0.0
    voltage_max: float = 0.0
    current_max: float = 0.0
    interface: str = ""  # SPI, I2C, UART, etc.
    typical_circuit: str = ""  # 推荐应用电路描述
    datasheet_url: str = ""
    lcsc_part: str = ""  # 立创商城SKU（便于采购）
    alternatives: list[str] = field(default_factory=list)
    notes: str = ""


class ComponentLibrary:
    """
    器件知识库。
    
    v0.1.0: 内置常用器件数据（ESP32系列、常用传感器等）
    v1.0.0 计划: 支持数据手册PDF自动解析入库
    v2.0.0 计划: 支持立创商城/得捷API实时查询库存和价格
    
    所有器件数据以中文描述为主，面向国内硬件开发者。
    """
    
    # 内置器件数据库
    _COMPONENTS: dict[str, ComponentInfo] = {}
    
    @classmethod
    def _init_builtin(cls):
        """初始化内置器件数据"""
        if cls._COMPONENTS:
            return
        
        components = [
            ComponentInfo(
                name="ESP32-S3-WROOM-1",
                manufacturer="Espressif",
                description="ESP32-S3 双核MCU，WiFi+BLE，支持AI向量指令",
                package="LQFP-56",
                voltage_min=3.0,
                voltage_max=3.6,
                current_max=0.5,
                interface="SPI/I2C/UART/USB/SDIO",
                typical_circuit="标准最小系统：3.3V供电，40MHz晶振，IO0拉低进入下载模式",
                datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf",
                lcsc_part="C2913902",
                alternatives=["ESP32-S3-WROOM-1-N8R2", "ESP32-S3-WROOM-1-N4R2"],
                notes="推荐用于AIoT项目，自带向量扩展指令集",
            ),
            ComponentInfo(
                name="ESP32-WROOM-32E",
                manufacturer="Espressif",
                description="ESP32 双核MCU，WiFi+BLE，经典款",
                package="LQFP-48",
                voltage_min=3.0,
                voltage_max=3.6,
                current_max=0.5,
                interface="SPI/I2C/UART/ADC/DAC",
                typical_circuit="标准最小系统：3.3V供电，40MHz晶振，EN引脚10kΩ上拉",
                datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32e_datasheet_en.pdf",
                lcsc_part="C473050",
                alternatives=["ESP32-WROOM-32D"],
                notes="最通用的ESP32，社区资源丰富",
            ),
            ComponentInfo(
                name="STM32F103C8T6",
                manufacturer="STMicroelectronics",
                description="STM32F1系列主流MCU，72MHz Cortex-M3",
                package="LQFP-48",
                voltage_min=2.0,
                voltage_max=3.6,
                current_max=0.15,
                interface="SPI/I2C/UART/ADC/USB",
                typical_circuit="最小系统：3.3V供电，8MHz晶振+PLL倍频，BOOT0/BOOT1配置",
                datasheet_url="https://www.st.com/resource/en/datasheet/stm32f103c8.pdf",
                lcsc_part="C8734",
                alternatives=["STM32F103C6T6", "GD32F103C8T6"],
                notes="蓝 pill 板标配MCU，Cortex-M3入门首选",
            ),
            ComponentInfo(
                name="SSD1306",
                manufacturer="Solomon Systech",
                description="0.96寸/1.3寸 OLED 128x64/128x32 驱动IC",
                package="COB",
                voltage_min=1.65,
                voltage_max=3.3,
                interface="I2C/SPI",
                typical_circuit="I2C模式：VCC→3.3V, SDA/SCL接MCU, 4.7kΩ上拉电阻",
                lcsc_part="C91184",
                alternatives=["SH1106", "SSD1305"],
                notes="最常用的OLED驱动，Adafruit/GFX库支持良好",
            ),
            ComponentInfo(
                name="DHT22",
                manufacturer="Aosong",
                description="高精度温湿度传感器，温度±0.5°C 湿度±2%",
                package="TO-92",
                voltage_min=3.3,
                voltage_max=5.5,
                interface="单总线",
                typical_circuit="VCC→3.3V-5V, DATA接MCU GPIO, 4.7kΩ上拉",
                lcsc_part="C75245",
                alternatives=["DHT11", "AHT20", "SHT30"],
                notes="相比DHT11精度更高，但价格略贵。推荐替代品AHT20 (I2C)",
            ),
            ComponentInfo(
                name="TP4056",
                manufacturer="NanJing Top Power",
                description="1A线性锂电池充电管理IC",
                package="SOT-23-6",
                voltage_min=4.25,
                voltage_max=8.0,
                interface="电源管理",
                typical_circuit="USB 5V输入→TP4056→LED指示→电池，PROG引脚接1kΩ设置充电电流",
                lcsc_part="C16581",
                alternatives=["TP4057", "IP2312"],
                notes="最经典的锂电池充电IC，但效率低发热大。大电流推荐SY6912",
            ),
            ComponentInfo(
                name="AMS1117-3.3",
                manufacturer="Advanced Monolithic Systems",
                description="1A低压差线性稳压器 3.3V固定输出",
                package="SOT-223",
                voltage_max=15.0,
                interface="电源管理",
                typical_circuit="输入接10µF钽电容，输出接22µF钽电容",
                lcsc_part="C6186",
                alternatives=["AMS1117-5.0", "HT7333", "XC6206"],
                notes="LDO效率低但纹波小，适合低功耗场合。大压差推荐Buck",
            ),
            ComponentInfo(
                name="MPU6050",
                manufacturer="InvenSense (TDK)",
                description="六轴IMU（三轴加速度计+三轴陀螺仪）",
                package="QFN-24",
                voltage_min=2.375,
                voltage_max=3.46,
                interface="I2C/SPI",
                typical_circuit="VCC→3.3V, SDA/SCL接MCU, AD0接地选择地址0x68",
                lcsc_part="C24112",
                alternatives=["MPU6500", "ICM20948", "LSM6DS3"],
                notes="运动检测经典芯片，注意I2C上拉电阻必须加",
            ),
        ]
        
        for comp in components:
            cls._COMPONENTS[comp.name.upper()] = comp
    
    @classmethod
    def search(cls, query: str) -> list[ComponentInfo]:
        """
        搜索器件。
        
        支持按名称、描述、接口类型搜索。
        """
        cls._init_builtin()
        query_upper = query.upper()
        
        results = []
        for name, comp in cls._COMPONENTS.items():
            if query_upper in name:
                results.append(comp)
            elif query.upper() in comp.description.upper():
                results.append(comp)
            elif query.upper() in comp.interface.upper():
                results.append(comp)
        
        return results
    
    @classmethod
    def get(cls, name: str) -> Optional[ComponentInfo]:
        """按名称获取器件信息"""
        cls._init_builtin()
        return cls._COMPONENTS.get(name.upper())
    
    @classmethod
    def all_components(cls) -> list[ComponentInfo]:
        """获取所有内置器件"""
        cls._init_builtin()
        return list(cls._COMPONENTS.values())
