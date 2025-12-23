"""
数据模型定义
定义流水线中使用的所有数据结构
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Literal, Union
from enum import Enum
import json
from datetime import datetime


class BlockType(str, Enum):
    """内容块类型"""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"


class QualityLevel(str, Enum):
    """质量等级"""
    GOOD = "good"
    LOW = "low"
    REJECT = "reject"


@dataclass
class PageBlock:
    """
    页面内容块
    表示从 PDF 单页提取的一个内容单元
    """
    page: int                           # 页码（0-indexed）
    type: BlockType                     # 内容类型
    content: Union[str, Dict[str, Any]]  # 文本内容或结构化数据
    confidence: float = 1.0             # 置信度 0.0-1.0
    bbox: Optional[tuple] = None        # 边界框 (x0, y0, x1, y1)
    block_id: Optional[str] = None      # 块 ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "page": self.page,
            "type": self.type.value if isinstance(self.type, BlockType) else self.type,
            "content": self.content,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "block_id": self.block_id,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageBlock":
        """从字典创建"""
        return cls(
            page=data["page"],
            type=BlockType(data["type"]) if isinstance(data["type"], str) else data["type"],
            content=data["content"],
            confidence=data.get("confidence", 1.0),
            bbox=tuple(data["bbox"]) if data.get("bbox") else None,
            block_id=data.get("block_id"),
            metadata=data.get("metadata", {})
        )


@dataclass
class Chunk:
    """
    文本切片
    表示可直接用于向量化的文本单元
    """
    chunk_id: str                       # 唯一标识
    content: str                        # 文本内容
    source: str                         # 来源文件名
    page_start: int                     # 起始页码
    page_end: int                       # 结束页码
    token_count: int = 0                # token 数量
    char_count: int = 0                 # 字符数量
    
    # 质量相关
    rule_score: float = 1.0             # 规则校验得分
    llm_quality: Optional[QualityLevel] = None  # LLM 质量判定
    llm_confidence: float = 0.0         # LLM 置信度
    llm_reason: str = ""                # LLM 判定原因
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "source": self.source,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "rule_score": self.rule_score,
            "llm_quality": self.llm_quality.value if self.llm_quality else None,
            "llm_confidence": self.llm_confidence,
            "llm_reason": self.llm_reason,
            "metadata": self.metadata,
            "created_at": self.created_at
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        """从字典创建"""
        return cls(
            chunk_id=data["chunk_id"],
            content=data["content"],
            source=data["source"],
            page_start=data["page_start"],
            page_end=data["page_end"],
            token_count=data.get("token_count", 0),
            char_count=data.get("char_count", 0),
            rule_score=data.get("rule_score", 1.0),
            llm_quality=QualityLevel(data["llm_quality"]) if data.get("llm_quality") else None,
            llm_confidence=data.get("llm_confidence", 0.0),
            llm_reason=data.get("llm_reason", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().isoformat())
        )


@dataclass
class ValidationResult:
    """
    校验结果
    包含规则校验和 LLM 校验的结果
    """
    quality: QualityLevel               # 质量等级
    confidence: float                   # 置信度
    reason: str                         # 原因说明
    
    # 详细指标
    length: int = 0                     # 文本长度
    noise_ratio: float = 0.0            # 噪声比例
    info_density: float = 0.0           # 信息密度
    garble_ratio: float = 0.0           # 乱码比例
    repetition_ratio: float = 0.0       # 重复比例
    
    # 来源
    source: str = "rule"                # 校验来源: rule, llm
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "quality": self.quality.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "length": self.length,
            "noise_ratio": self.noise_ratio,
            "info_density": self.info_density,
            "garble_ratio": self.garble_ratio,
            "repetition_ratio": self.repetition_ratio,
            "source": self.source
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ProcessingStats:
    """
    处理统计信息
    记录整个流水线的处理统计
    """
    # 基本信息
    source_file: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    
    # 页面统计
    total_pages: int = 0
    processed_pages: int = 0
    failed_pages: int = 0
    
    # 块统计
    total_blocks: int = 0
    text_blocks: int = 0
    table_blocks: int = 0
    image_blocks: int = 0
    
    # Chunk 统计
    total_chunks: int = 0
    accepted_chunks: int = 0
    rejected_chunks: int = 0
    
    # LLM 统计
    llm_calls: int = 0
    llm_good: int = 0
    llm_low: int = 0
    llm_reject: int = 0
    
    # 质量统计
    avg_chunk_length: float = 0.0
    avg_rule_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def update_averages(self, chunks: List[Chunk]) -> None:
        """更新平均值统计"""
        if not chunks:
            return
        self.avg_chunk_length = sum(c.char_count for c in chunks) / len(chunks)
        self.avg_rule_score = sum(c.rule_score for c in chunks) / len(chunks)


@dataclass
class Checkpoint:
    """
    断点续传检查点
    记录处理进度，支持中断后恢复
    """
    last_processed_page: int = -1       # 最后处理的页码
    total_pages: int = 0                # 总页数
    processed_chunks: int = 0           # 已处理的 chunk 数
    llm_calls_used: int = 0             # 已使用的 LLM 调用次数
    timestamp: str = ""                 # 时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """从字典创建"""
        return cls(
            last_processed_page=data.get("last_processed_page", -1),
            total_pages=data.get("total_pages", 0),
            processed_chunks=data.get("processed_chunks", 0),
            llm_calls_used=data.get("llm_calls_used", 0),
            timestamp=data.get("timestamp", "")
        )
    
    @classmethod
    def load(cls, path: str) -> Optional["Checkpoint"]:
        """从文件加载检查点"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return cls.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def save(self, path: str) -> None:
        """保存检查点到文件"""
        self.timestamp = datetime.now().isoformat()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
