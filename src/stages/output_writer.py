"""
输出层模块
负责将处理结果写入文件
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..core.config import Config, OutputConfig
from ..core.models import PageBlock, Chunk, ProcessingStats, Checkpoint


class OutputWriter:
    """
    输出写入器
    将处理结果写入 JSONL 和 JSON 文件
    """
    
    def __init__(self, config: Config, base_dir: Path):
        """
        初始化输出写入器
        
        Args:
            config: 配置对象
            base_dir: 项目基础目录
        """
        self.config = config
        self.output_config: OutputConfig = config.output
        self.base_dir = base_dir
        self.logger = logging.getLogger(__name__)
        
        # 获取输出目录
        self.output_dir = config.get_output_dir(base_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径
        self.pages_path = self.output_dir / self.output_config.pages_file
        self.chunks_path = self.output_dir / self.output_config.chunks_file
        self.rejected_path = self.output_dir / self.output_config.rejected_file
        self.stats_path = self.output_dir / self.output_config.stats_file
        self.checkpoint_path = self.output_dir / self.output_config.checkpoint_file
        
        # 文件句柄（用于流式写入）
        self._pages_file = None
        self._chunks_file = None
        self._rejected_file = None
    
    def open_files(self, append: bool = False) -> None:
        """
        打开输出文件
        
        Args:
            append: 是否追加模式（用于断点续传）
        """
        mode = 'a' if append else 'w'
        
        self._pages_file = open(self.pages_path, mode, encoding='utf-8')
        self._chunks_file = open(self.chunks_path, mode, encoding='utf-8')
        self._rejected_file = open(self.rejected_path, mode, encoding='utf-8')
        
        self.logger.info(f"输出文件已打开: {self.output_dir}")
    
    def close_files(self) -> None:
        """关闭输出文件"""
        if self._pages_file:
            self._pages_file.close()
            self._pages_file = None
        if self._chunks_file:
            self._chunks_file.close()
            self._chunks_file = None
        if self._rejected_file:
            self._rejected_file.close()
            self._rejected_file = None
        
        self.logger.info("输出文件已关闭")
    
    def write_page_blocks(self, blocks: List[PageBlock]) -> None:
        """
        写入页面块到 pages.jsonl
        
        Args:
            blocks: PageBlock 列表
        """
        if not self._pages_file:
            raise RuntimeError("输出文件未打开，请先调用 open_files()")
        
        for block in blocks:
            self._pages_file.write(block.to_json() + '\n')
        
        self._pages_file.flush()
    
    def write_chunks(self, chunks: List[Chunk]) -> None:
        """
        写入 chunks 到 chunks.jsonl
        
        Args:
            chunks: Chunk 列表
        """
        if not self._chunks_file:
            raise RuntimeError("输出文件未打开，请先调用 open_files()")
        
        for chunk in chunks:
            self._chunks_file.write(chunk.to_json() + '\n')
        
        self._chunks_file.flush()
    
    def write_rejected(self, chunks: List[Chunk]) -> None:
        """
        写入被拒绝的 chunks 到 rejected.jsonl
        
        Args:
            chunks: 被拒绝的 Chunk 列表
        """
        if not self._rejected_file:
            raise RuntimeError("输出文件未打开，请先调用 open_files()")
        
        for chunk in chunks:
            self._rejected_file.write(chunk.to_json() + '\n')
        
        self._rejected_file.flush()
    
    def write_stats(self, stats: ProcessingStats) -> None:
        """
        写入处理统计到 stats.json
        
        Args:
            stats: 处理统计对象
        """
        with open(self.stats_path, 'w', encoding='utf-8') as f:
            f.write(stats.to_json())
        
        self.logger.info(f"统计信息已写入: {self.stats_path}")
    
    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """
        保存断点续传检查点
        
        Args:
            checkpoint: 检查点对象
        """
        checkpoint.save(str(self.checkpoint_path))
        self.logger.debug(f"检查点已保存: 页码 {checkpoint.last_processed_page}")
    
    def load_checkpoint(self) -> Optional[Checkpoint]:
        """
        加载断点续传检查点
        
        Returns:
            检查点对象，不存在返回 None
        """
        checkpoint = Checkpoint.load(str(self.checkpoint_path))
        if checkpoint:
            self.logger.info(
                f"加载检查点: 上次处理到页码 {checkpoint.last_processed_page}"
            )
        return checkpoint
    
    def clear_checkpoint(self) -> None:
        """清除检查点文件"""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            self.logger.info("检查点已清除")
    
    def get_output_summary(self) -> Dict[str, Any]:
        """
        获取输出文件摘要
        
        Returns:
            摘要信息字典
        """
        summary = {
            "output_dir": str(self.output_dir),
            "files": {}
        }
        
        for name, path in [
            ("pages", self.pages_path),
            ("chunks", self.chunks_path),
            ("rejected", self.rejected_path),
            ("stats", self.stats_path)
        ]:
            if path.exists():
                summary["files"][name] = {
                    "path": str(path),
                    "size_kb": path.stat().st_size / 1024,
                    "lines": self._count_lines(path) if path.suffix == '.jsonl' else None
                }
        
        return summary
    
    def _count_lines(self, path: Path) -> int:
        """计算文件行数"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def __enter__(self):
        """上下文管理器入口"""
        self.open_files()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close_files()
        return False


class BatchWriter:
    """
    批量写入器
    用于大文件处理时的批量写入，减少 I/O 操作
    """
    
    def __init__(self, output_writer: OutputWriter, batch_size: int = 100):
        """
        初始化批量写入器
        
        Args:
            output_writer: 输出写入器
            batch_size: 批量大小
        """
        self.writer = output_writer
        self.batch_size = batch_size
        
        self._pages_buffer: List[PageBlock] = []
        self._chunks_buffer: List[Chunk] = []
        self._rejected_buffer: List[Chunk] = []
    
    def add_page_blocks(self, blocks: List[PageBlock]) -> None:
        """添加页面块到缓冲区"""
        self._pages_buffer.extend(blocks)
        if len(self._pages_buffer) >= self.batch_size:
            self.flush_pages()
    
    def add_chunks(self, chunks: List[Chunk]) -> None:
        """添加 chunks 到缓冲区"""
        self._chunks_buffer.extend(chunks)
        if len(self._chunks_buffer) >= self.batch_size:
            self.flush_chunks()
    
    def add_rejected(self, chunks: List[Chunk]) -> None:
        """添加被拒绝的 chunks 到缓冲区"""
        self._rejected_buffer.extend(chunks)
        if len(self._rejected_buffer) >= self.batch_size:
            self.flush_rejected()
    
    def flush_pages(self) -> None:
        """刷新页面块缓冲区"""
        if self._pages_buffer:
            self.writer.write_page_blocks(self._pages_buffer)
            self._pages_buffer = []
    
    def flush_chunks(self) -> None:
        """刷新 chunks 缓冲区"""
        if self._chunks_buffer:
            self.writer.write_chunks(self._chunks_buffer)
            self._chunks_buffer = []
    
    def flush_rejected(self) -> None:
        """刷新被拒绝 chunks 缓冲区"""
        if self._rejected_buffer:
            self.writer.write_rejected(self._rejected_buffer)
            self._rejected_buffer = []
    
    def flush_all(self) -> None:
        """刷新所有缓冲区"""
        self.flush_pages()
        self.flush_chunks()
        self.flush_rejected()
