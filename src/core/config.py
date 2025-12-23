"""
配置管理模块
负责加载和验证 YAML 配置文件
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dataclasses import dataclass, field


@dataclass
class PDFConfig:
    """PDF 输入配置"""
    path: str
    start_page: int = 0
    end_page: Optional[int] = None


@dataclass
class ParsingConfig:
    """解析配置"""
    extract_tables: bool = True
    extract_images: bool = False
    table_strategy: str = "lines"


@dataclass
class NormalizationConfig:
    """规范化配置"""
    remove_headers_footers: bool = True
    merge_broken_lines: bool = True
    normalize_whitespace: bool = True
    normalize_punctuation: bool = True
    header_footer_max_lines: int = 3
    min_line_length: int = 5


@dataclass
class ChunkConfig:
    """切片配置"""
    size: int = 800
    overlap: int = 150
    min_chunk_size: int = 100
    split_by: str = "token"
    respect_sentence_boundary: bool = True


@dataclass
class GarbleDetectionConfig:
    """乱码检测配置"""
    enabled: bool = True
    max_garble_ratio: float = 0.1


@dataclass
class LLMValidationConfig:
    """LLM 校验配置"""
    enabled: bool = True
    only_edge_chunks: bool = True
    edge_threshold: float = 0.6


@dataclass
class QualityConfig:
    """质量校验配置"""
    min_length: int = 200
    max_noise_ratio: float = 0.3
    min_info_density: float = 0.3
    max_repetition_ratio: float = 0.5
    garble_detection: GarbleDetectionConfig = field(default_factory=GarbleDetectionConfig)
    llm_validation: LLMValidationConfig = field(default_factory=LLMValidationConfig)


@dataclass
class LLMConfig:
    """LLM 配置"""
    enabled: bool = True
    provider: str = "ollama"
    model: str = "qwen:7b"
    endpoint: str = "http://localhost:11434"
    max_calls: int = 500
    timeout: int = 60
    retry_times: int = 3
    temperature: float = 0.1


@dataclass
class OutputConfig:
    """输出配置"""
    dir: str = "data/output"
    pages_file: str = "pages.jsonl"
    chunks_file: str = "chunks.jsonl"
    rejected_file: str = "rejected.jsonl"
    stats_file: str = "stats.json"
    checkpoint_file: str = "checkpoint.json"


@dataclass
class RuntimeConfig:
    """运行时配置"""
    batch_size: int = 10
    log_level: str = "INFO"
    save_interval: int = 50
    enable_checkpoint: bool = True


class Config:
    """
    配置管理器
    从 YAML 文件加载配置，提供类型安全的访问接口
    """
    
    def __init__(self, config_path: str):
        """
        初始化配置管理器
        
        Args:
            config_path: YAML 配置文件路径
        """
        self.config_path = Path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self._load_config()
        self._parse_config()
    
    def _load_config(self) -> None:
        """加载 YAML 配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._raw_config = yaml.safe_load(f)
    
    def _parse_config(self) -> None:
        """解析配置到数据类"""
        # PDF 配置
        pdf_cfg = self._raw_config.get('pdf', {})
        self.pdf = PDFConfig(
            path=pdf_cfg.get('path', ''),
            start_page=pdf_cfg.get('start_page', 0),
            end_page=pdf_cfg.get('end_page')
        )
        
        # 解析配置
        parsing_cfg = self._raw_config.get('parsing', {})
        self.parsing = ParsingConfig(
            extract_tables=parsing_cfg.get('extract_tables', True),
            extract_images=parsing_cfg.get('extract_images', False),
            table_strategy=parsing_cfg.get('table_strategy', 'lines')
        )
        
        # 规范化配置
        norm_cfg = self._raw_config.get('normalization', {})
        self.normalization = NormalizationConfig(
            remove_headers_footers=norm_cfg.get('remove_headers_footers', True),
            merge_broken_lines=norm_cfg.get('merge_broken_lines', True),
            normalize_whitespace=norm_cfg.get('normalize_whitespace', True),
            normalize_punctuation=norm_cfg.get('normalize_punctuation', True),
            header_footer_max_lines=norm_cfg.get('header_footer_max_lines', 3),
            min_line_length=norm_cfg.get('min_line_length', 5)
        )
        
        # 切片配置
        chunk_cfg = self._raw_config.get('chunk', {})
        self.chunk = ChunkConfig(
            size=chunk_cfg.get('size', 800),
            overlap=chunk_cfg.get('overlap', 150),
            min_chunk_size=chunk_cfg.get('min_chunk_size', 100),
            split_by=chunk_cfg.get('split_by', 'token'),
            respect_sentence_boundary=chunk_cfg.get('respect_sentence_boundary', True)
        )
        
        # 质量配置
        quality_cfg = self._raw_config.get('quality', {})
        garble_cfg = quality_cfg.get('garble_detection', {})
        llm_val_cfg = quality_cfg.get('llm_validation', {})
        
        self.quality = QualityConfig(
            min_length=quality_cfg.get('min_length', 200),
            max_noise_ratio=quality_cfg.get('max_noise_ratio', 0.3),
            min_info_density=quality_cfg.get('min_info_density', 0.3),
            max_repetition_ratio=quality_cfg.get('max_repetition_ratio', 0.5),
            garble_detection=GarbleDetectionConfig(
                enabled=garble_cfg.get('enabled', True),
                max_garble_ratio=garble_cfg.get('max_garble_ratio', 0.1)
            ),
            llm_validation=LLMValidationConfig(
                enabled=llm_val_cfg.get('enabled', True),
                only_edge_chunks=llm_val_cfg.get('only_edge_chunks', True),
                edge_threshold=llm_val_cfg.get('edge_threshold', 0.6)
            )
        )
        
        # LLM 配置
        llm_cfg = self._raw_config.get('llm', {})
        self.llm = LLMConfig(
            enabled=llm_cfg.get('enabled', True),
            provider=llm_cfg.get('provider', 'ollama'),
            model=llm_cfg.get('model', 'qwen:7b'),
            endpoint=llm_cfg.get('endpoint', 'http://localhost:11434'),
            max_calls=llm_cfg.get('max_calls', 500),
            timeout=llm_cfg.get('timeout', 60),
            retry_times=llm_cfg.get('retry_times', 3),
            temperature=llm_cfg.get('temperature', 0.1)
        )
        
        # 输出配置
        output_cfg = self._raw_config.get('output', {})
        self.output = OutputConfig(
            dir=output_cfg.get('dir', 'data/output'),
            pages_file=output_cfg.get('pages_file', 'pages.jsonl'),
            chunks_file=output_cfg.get('chunks_file', 'chunks.jsonl'),
            rejected_file=output_cfg.get('rejected_file', 'rejected.jsonl'),
            stats_file=output_cfg.get('stats_file', 'stats.json'),
            checkpoint_file=output_cfg.get('checkpoint_file', 'checkpoint.json')
        )
        
        # 运行时配置
        runtime_cfg = self._raw_config.get('runtime', {})
        self.runtime = RuntimeConfig(
            batch_size=runtime_cfg.get('batch_size', 10),
            log_level=runtime_cfg.get('log_level', 'INFO'),
            save_interval=runtime_cfg.get('save_interval', 50),
            enable_checkpoint=runtime_cfg.get('enable_checkpoint', True)
        )
    
    def get_absolute_pdf_path(self, base_dir: Path) -> Path:
        """获取 PDF 文件的绝对路径"""
        pdf_path = Path(self.pdf.path)
        if pdf_path.is_absolute():
            return pdf_path
        return base_dir / pdf_path
    
    def get_output_dir(self, base_dir: Path) -> Path:
        """获取输出目录的绝对路径"""
        output_path = Path(self.output.dir)
        if output_path.is_absolute():
            return output_path
        return base_dir / output_path
    
    def validate(self, base_dir: Path) -> List[str]:
        """
        验证配置有效性
        
        Returns:
            错误信息列表，空列表表示配置有效
        """
        errors = []
        
        # 验证 PDF 路径
        pdf_path = self.get_absolute_pdf_path(base_dir)
        if not pdf_path.exists():
            errors.append(f"PDF 文件不存在: {pdf_path}")
        
        # 验证切片配置
        if self.chunk.size <= 0:
            errors.append("chunk.size 必须大于 0")
        if self.chunk.overlap >= self.chunk.size:
            errors.append("chunk.overlap 必须小于 chunk.size")
        
        # 验证质量配置
        if not 0 <= self.quality.max_noise_ratio <= 1:
            errors.append("quality.max_noise_ratio 必须在 0-1 之间")
        
        return errors
    
    def __repr__(self) -> str:
        return f"Config(pdf={self.pdf.path}, chunk_size={self.chunk.size})"
