"""
配置项元数据定义
为未来 UI 化提供必要的展示信息
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class ImpactType(Enum):
    """影响类型"""
    PERFORMANCE = "performance"  # 性能影响
    COST = "cost"  # 成本影响
    QUALITY = "quality"  # 质量影响
    ALL = "all"  # 全方位影响


@dataclass
class ConfigMetadata:
    """配置项元数据"""
    key: str  # 配置键路径，如 "chunk.size"
    display_name: str  # UI 显示名称
    description: str  # 详细说明（tooltip）
    impact: List[ImpactType]  # 影响维度
    recommended_value: Any  # 推荐值
    value_type: str  # 值类型：int, float, bool, str, enum
    value_range: tuple = None  # 值范围（min, max）或枚举选项
    unit: str = ""  # 单位，如 "tokens", "seconds"


# 配置项元数据定义
CONFIG_METADATA: Dict[str, ConfigMetadata] = {
    # ==================== Chunk 配置 ====================
    "chunk.size": ConfigMetadata(
        key="chunk.size",
        display_name="Chunk Size",
        description="每个文本块的大小（以 token 为单位）。较小的 chunk 提供更精确的检索，但会增加存储和计算成本。",
        impact=[ImpactType.QUALITY, ImpactType.COST],
        recommended_value=800,
        value_type="int",
        value_range=(200, 2000),
        unit="tokens"
    ),
    
    "chunk.overlap": ConfigMetadata(
        key="chunk.overlap",
        display_name="Chunk Overlap",
        description="相邻 chunk 之间的重叠大小。重叠可以避免信息在边界处被切断，但会增加存储成本。",
        impact=[ImpactType.QUALITY, ImpactType.COST],
        recommended_value=150,
        value_type="int",
        value_range=(0, 500),
        unit="tokens"
    ),
    
    "chunk.min_chunk_size": ConfigMetadata(
        key="chunk.min_chunk_size",
        display_name="Minimum Chunk Size",
        description="最小 chunk 大小。小于此值的 chunk 将被丢弃，避免产生无意义的碎片。",
        impact=[ImpactType.QUALITY],
        recommended_value=100,
        value_type="int",
        value_range=(50, 500),
        unit="tokens"
    ),
    
    "chunk.split_by": ConfigMetadata(
        key="chunk.split_by",
        display_name="Split Method",
        description="切分方式。token: 按 token 数切分（推荐）；sentence: 按句子切分；char: 按字符切分。",
        impact=[ImpactType.QUALITY, ImpactType.PERFORMANCE],
        recommended_value="token",
        value_type="enum",
        value_range=("token", "sentence", "char")
    ),
    
    "chunk.respect_sentence_boundary": ConfigMetadata(
        key="chunk.respect_sentence_boundary",
        display_name="Respect Sentence Boundary",
        description="是否尽量在句子边界处切分。启用可提高 chunk 的语义完整性，但可能导致 chunk 大小不均匀。",
        impact=[ImpactType.QUALITY],
        recommended_value=True,
        value_type="bool"
    ),
    
    # ==================== Quality 配置 ====================
    "quality.min_length": ConfigMetadata(
        key="quality.min_length",
        display_name="Minimum Length",
        description="chunk 的最小字符长度。低于此值的 chunk 会被过滤掉。",
        impact=[ImpactType.QUALITY],
        recommended_value=200,
        value_type="int",
        value_range=(50, 1000),
        unit="characters"
    ),
    
    "quality.max_noise_ratio": ConfigMetadata(
        key="quality.max_noise_ratio",
        display_name="Max Noise Ratio",
        description="最大噪声比例（特殊字符占比）。超过此值的 chunk 会被认为是噪声。",
        impact=[ImpactType.QUALITY],
        recommended_value=0.3,
        value_type="float",
        value_range=(0.0, 1.0)
    ),
    
    "quality.min_info_density": ConfigMetadata(
        key="quality.min_info_density",
        display_name="Min Information Density",
        description="最小信息密度（有效词汇占比）。低于此值的 chunk 被认为信息量不足。",
        impact=[ImpactType.QUALITY],
        recommended_value=0.3,
        value_type="float",
        value_range=(0.0, 1.0)
    ),
    
    "quality.max_repetition_ratio": ConfigMetadata(
        key="quality.max_repetition_ratio",
        display_name="Max Repetition Ratio",
        description="最大重复比例。超过此值的 chunk 被认为是重复内容。",
        impact=[ImpactType.QUALITY],
        recommended_value=0.5,
        value_type="float",
        value_range=(0.0, 1.0)
    ),
    
    "quality.garble_detection.enabled": ConfigMetadata(
        key="quality.garble_detection.enabled",
        display_name="Enable Garble Detection",
        description="是否启用乱码检测。可以过滤掉 PDF 解析错误产生的乱码内容。",
        impact=[ImpactType.QUALITY],
        recommended_value=True,
        value_type="bool"
    ),
    
    "quality.garble_detection.max_garble_ratio": ConfigMetadata(
        key="quality.garble_detection.max_garble_ratio",
        display_name="Max Garble Ratio",
        description="最大乱码比例。超过此值的 chunk 会被认为是乱码。",
        impact=[ImpactType.QUALITY],
        recommended_value=0.1,
        value_type="float",
        value_range=(0.0, 0.5)
    ),
    
    "quality.llm_validation.enabled": ConfigMetadata(
        key="quality.llm_validation.enabled",
        display_name="Enable LLM Validation",
        description="是否启用 LLM 语义校验。可以提高质量但会增加处理时间和成本。",
        impact=[ImpactType.QUALITY, ImpactType.COST, ImpactType.PERFORMANCE],
        recommended_value=True,
        value_type="bool"
    ),
    
    "quality.llm_validation.only_edge_chunks": ConfigMetadata(
        key="quality.llm_validation.only_edge_chunks",
        display_name="Only Validate Edge Chunks",
        description="是否仅对边缘 chunk（规则得分较低的）进行 LLM 校验。可以显著降低成本。",
        impact=[ImpactType.COST, ImpactType.PERFORMANCE],
        recommended_value=True,
        value_type="bool"
    ),
    
    "quality.llm_validation.edge_threshold": ConfigMetadata(
        key="quality.llm_validation.edge_threshold",
        display_name="Edge Threshold",
        description="边缘判定阈值。规则得分低于此值的 chunk 会被送入 LLM 校验。",
        impact=[ImpactType.COST],
        recommended_value=0.6,
        value_type="float",
        value_range=(0.0, 1.0)
    ),
    
    # ==================== LLM 配置 ====================
    "llm.enabled": ConfigMetadata(
        key="llm.enabled",
        display_name="Enable LLM",
        description="是否启用 LLM 功能（用于质量校验）。需要本地运行 Ollama 或其他 LLM 服务。",
        impact=[ImpactType.QUALITY, ImpactType.COST, ImpactType.PERFORMANCE],
        recommended_value=True,
        value_type="bool"
    ),
    
    "llm.provider": ConfigMetadata(
        key="llm.provider",
        display_name="LLM Provider",
        description="LLM 提供商。目前支持 ollama。",
        impact=[ImpactType.ALL],
        recommended_value="ollama",
        value_type="enum",
        value_range=("ollama",)
    ),
    
    "llm.model": ConfigMetadata(
        key="llm.model",
        display_name="LLM Model",
        description="使用的模型名称。如 qwen:7b, llama2:13b 等。",
        impact=[ImpactType.QUALITY, ImpactType.COST, ImpactType.PERFORMANCE],
        recommended_value="qwen:7b",
        value_type="str"
    ),
    
    "llm.endpoint": ConfigMetadata(
        key="llm.endpoint",
        display_name="LLM Endpoint",
        description="LLM 服务的 API 端点地址。",
        impact=[ImpactType.ALL],
        recommended_value="http://localhost:11434",
        value_type="str"
    ),
    
    "llm.max_calls": ConfigMetadata(
        key="llm.max_calls",
        display_name="Max LLM Calls",
        description="最大 LLM 调用次数。达到此限制后将停止 LLM 校验。",
        impact=[ImpactType.COST, ImpactType.PERFORMANCE],
        recommended_value=500,
        value_type="int",
        value_range=(0, 10000),
        unit="calls"
    ),
    
    "llm.timeout": ConfigMetadata(
        key="llm.timeout",
        display_name="LLM Timeout",
        description="单次 LLM 调用的超时时间。",
        impact=[ImpactType.PERFORMANCE],
        recommended_value=60,
        value_type="int",
        value_range=(10, 300),
        unit="seconds"
    ),
    
    "llm.temperature": ConfigMetadata(
        key="llm.temperature",
        display_name="LLM Temperature",
        description="LLM 温度参数。较低的值使输出更确定性，适合质量判断任务。",
        impact=[ImpactType.QUALITY],
        recommended_value=0.1,
        value_type="float",
        value_range=(0.0, 1.0)
    ),
    
    # ==================== Parsing 配置 ====================
    "parsing.extract_tables": ConfigMetadata(
        key="parsing.extract_tables",
        display_name="Extract Tables",
        description="是否提取表格内容。表格会被转换为结构化文本。",
        impact=[ImpactType.QUALITY, ImpactType.PERFORMANCE],
        recommended_value=True,
        value_type="bool"
    ),
    
    "parsing.extract_images": ConfigMetadata(
        key="parsing.extract_images",
        display_name="Extract Images",
        description="是否记录图片占位信息。注意：目前不进行 OCR，仅记录位置。",
        impact=[ImpactType.QUALITY],
        recommended_value=False,
        value_type="bool"
    ),
    
    "parsing.table_strategy": ConfigMetadata(
        key="parsing.table_strategy",
        display_name="Table Strategy",
        description="表格识别策略。lines: 基于线条；text: 基于文本位置；lines_strict: 严格线条模式。",
        impact=[ImpactType.QUALITY, ImpactType.PERFORMANCE],
        recommended_value="lines",
        value_type="enum",
        value_range=("lines", "text", "lines_strict")
    ),
    
    # ==================== Runtime 配置 ====================
    "runtime.batch_size": ConfigMetadata(
        key="runtime.batch_size",
        display_name="Batch Size",
        description="批处理大小（页数）。较大的批次可以提高效率但会占用更多内存。",
        impact=[ImpactType.PERFORMANCE],
        recommended_value=10,
        value_type="int",
        value_range=(1, 100),
        unit="pages"
    ),
    
    "runtime.save_interval": ConfigMetadata(
        key="runtime.save_interval",
        display_name="Save Interval",
        description="保存间隔（页数）。每处理多少页保存一次检查点。",
        impact=[ImpactType.PERFORMANCE],
        recommended_value=50,
        value_type="int",
        value_range=(10, 500),
        unit="pages"
    ),
    
    "runtime.enable_checkpoint": ConfigMetadata(
        key="runtime.enable_checkpoint",
        display_name="Enable Checkpoint",
        description="是否启用断点续传。启用后可以在中断后继续处理。",
        impact=[ImpactType.PERFORMANCE],
        recommended_value=True,
        value_type="bool"
    ),
}


def get_config_metadata(key: str) -> ConfigMetadata:
    """
    获取配置项的元数据
    
    Args:
        key: 配置键路径
        
    Returns:
        ConfigMetadata 对象，如果不存在则返回 None
    """
    return CONFIG_METADATA.get(key)


def get_all_metadata() -> Dict[str, ConfigMetadata]:
    """
    获取所有配置项的元数据
    
    Returns:
        元数据字典
    """
    return CONFIG_METADATA.copy()


def get_metadata_by_impact(impact_type: ImpactType) -> List[ConfigMetadata]:
    """
    根据影响类型筛选配置项
    
    Args:
        impact_type: 影响类型
        
    Returns:
        配置项元数据列表
    """
    return [
        metadata for metadata in CONFIG_METADATA.values()
        if impact_type in metadata.impact or ImpactType.ALL in metadata.impact
    ]
