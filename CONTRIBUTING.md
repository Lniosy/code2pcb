# 贡献指南

感谢你对 PCB Forge 的关注！以下是参与贡献的方式。

## 开发环境搭建

```bash
# 克隆项目
git clone https://github.com/liunian/pcb-forge.git
cd pcb-forge

# 安装依赖（开发模式）
pip install -e ".[dev,llm]"

# 验证安装
pcb-forge --version
```

## 项目结构

```
src/pcb_forge/
├── cli/        # CLI入口命令
├── core/       # 核心引擎（解析/生成/布局/布线）
├── exporters/  # 文件导出（KiCad/Gerber）
├── knowledge/  # 知识库（器件参数/典型电路）
├── mcp/        # MCP Server
└── utils/      # 工具函数
```

## 开发规范

### 代码风格

```bash
# 检查
make lint

# 自动格式化
make format
```

- 使用 `ruff` 进行代码检查和格式化
- 使用 type hints
- 中文注释优先
- 文档字符串用中文

### 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
refactor: 重构
test: 测试相关
chore: 构建/工具链
```

### 测试

```bash
# 运行所有测试
make test

# 运行特定测试
pytest tests/test_parser.py -v
```

## 贡献方式

### 最受欢迎的贡献

1. **扩充器件知识库** — 在 `knowledge/component.py` 中添加新器件
2. **添加代码解析模式** — 在 `core/parser.py` 中添加新的MCU/传感器/外设检测模式
3. **完善典型电路库** — 添加常见电路的参考设计
4. **文档翻译** — 中英文文档互译和补充
5. **Bug修复** — 提交Issue并附上复现步骤

### 添加新器件到知识库

```python
# 在 src/pcb_forge/knowledge/component.py 的 _COMPONENTS 列表中添加：
ComponentInfo(
    name="你的器件型号",
    manufacturer="厂商",
    description="中文描述",
    package="封装",
    voltage_min=3.0,
    voltage_max=3.6,
    interface="通信接口",
    typical_circuit="推荐应用电路描述",
    lcsc_part="立创商城SKU",  # 方便采购
    alternatives=["替代品1", "替代品2"],
    notes="使用注意事项",
)
```

### 添加代码解析模式

```python
# 在 src/pcb_forge/core/parser.py 中：

# 1. 添加MCU检测
MCU_PATTERNS["新型号MCU"] = [r"型号正则1", r"型号正则2"]

# 2. 添加器件检测
COMPONENT_PATTERNS[r"器件型号正则"] = (
    ComponentType.SENSOR,  # 器件类型
    "中文描述",
    0.9,  # 置信度
)

# 3. 添加外设检测
PERIPHERAL_PATTERNS[r"API调用正则"] = [PeripheralType.SPI]
```

## Issue 提交

提交Issue时请包含：
- 使用的版本号
- 复现步骤
- 期望行为 vs 实际行为
- 相关的代码仓库/文件（如有）

## License

贡献的代码将采用 MIT License 发布。
