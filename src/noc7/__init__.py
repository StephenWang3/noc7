"""noc7：NOC 故障七要素提取与报告生成。

核心包不依赖 Web 框架和存储；命令行与 Web 只是入口。
"""

__version__ = "0.1.0"

# 契约版本号。schema 或工单包格式发生不兼容变化时递增，并在 docs/decisions/ 记录原因。
SCHEMA_VERSION = "1.0"
BUNDLE_FORMAT_VERSION = "1.0"
