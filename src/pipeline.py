"""
流水线编排模块
协调各处理阶段，实现完整的 PDF 预处理流程
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from .core.config import Config
from .core.models import (
    PageBlock, Chunk, ProcessingStats, Checkpoint, BlockType
)
from .stages.input_loader import InputLoader
from .stages.parser import PDFParser
from .stages.normalizer import Normalizer
from .stages.chunker import Chunker
from .stages.validator import Validator
from .stages.output_writer import OutputWriter, BatchWriter


class Pipeline:
    """
    PDF RAG 预处理流水线
    
    流程：
    1. 输入层：流式读取 PDF
    2. 解析层：提取文本、表格、图片
    3. 规范化层：清洗和规范化
    4. 切片层：切分为 chunks
    5. 校验层：质量校验和路由
    6. 输出层：写入结果文件
    """
    
    def __init__(self, config_path: str, base_dir: Optional[str] = None):
        """
        初始化流水线
        
        Args:
            config_path: 配置文件路径
            base_dir: 项目基础目录，默认为配置文件所在目录的父目录
        """
        self.config = Config(config_path)
        
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(config_path).parent.parent
        
        self.logger = self._setup_logger()
        
        # 初始化各阶段处理器
        self.input_loader: Optional[InputLoader] = None
        self.parser: Optional[PDFParser] = None
        self.normalizer: Optional[Normalizer] = None
        self.chunker: Optional[Chunker] = None
        self.validator: Optional[Validator] = None
        self.output_writer: Optional[OutputWriter] = None
        
        # 统计信息
        self.stats = ProcessingStats()
        
        # 断点续传
        self.checkpoint: Optional[Checkpoint] = None
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("Pipeline")
        logger.setLevel(getattr(logging, self.config.runtime.log_level.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(getattr(logging, self.config.runtime.log_level.upper()))
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _init_stages(self) -> None:
        """初始化各处理阶段"""
        self.logger.info("初始化处理阶段...")
        
        self.input_loader = InputLoader(self.config, self.base_dir)
        self.parser = PDFParser(self.config)
        self.normalizer = Normalizer(self.config)
        self.chunker = Chunker(self.config, self.input_loader.filename)
        self.validator = Validator(self.config)
        self.output_writer = OutputWriter(self.config, self.base_dir)
    
    def _validate_config(self) -> bool:
        """验证配置"""
        errors = self.config.validate(self.base_dir)
        if errors:
            for error in errors:
                self.logger.error(f"配置错误: {error}")
            return False
        return True
    
    def run(self, resume: bool = True) -> ProcessingStats:
        """
        运行流水线
        
        Args:
            resume: 是否从断点续传
        
        Returns:
            处理统计信息
        """
        self.logger.info("=" * 60)
        self.logger.info("PDF RAG 预处理流水线启动")
        self.logger.info("=" * 60)
        
        # 验证配置
        if not self._validate_config():
            raise ValueError("配置验证失败")
        
        # 初始化
        self._init_stages()
        
        # 记录开始时间
        start_time = time.time()
        self.stats.start_time = datetime.now().isoformat()
        self.stats.source_file = self.input_loader.filename
        
        try:
            # 打开输入文件
            self.input_loader.open()
            self.stats.total_pages = self.input_loader.total_pages
            
            # 检查断点续传
            start_page = 0
            if resume and self.config.runtime.enable_checkpoint:
                self.checkpoint = self.output_writer.load_checkpoint()
                if self.checkpoint:
                    start_page = self.checkpoint.last_processed_page + 1
                    self.logger.info(f"从页码 {start_page} 继续处理")
            
            # 打开输出文件
            append_mode = start_page > 0
            self.output_writer.open_files(append=append_mode)
            
            # 创建批量写入器
            batch_writer = BatchWriter(
                self.output_writer, 
                batch_size=self.config.runtime.batch_size * 10
            )
            
            # 处理页面
            self._process_pages(start_page, batch_writer)
            
            # 刷新剩余数据
            batch_writer.flush_all()
            
            # 清除检查点
            if self.config.runtime.enable_checkpoint:
                self.output_writer.clear_checkpoint()
            
        except KeyboardInterrupt:
            self.logger.warning("用户中断处理")
            if self.config.runtime.enable_checkpoint:
                self._save_checkpoint()
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            if self.config.runtime.enable_checkpoint:
                self._save_checkpoint()
            raise
        finally:
            # 关闭文件
            if self.input_loader:
                self.input_loader.close()
            if self.output_writer:
                self.output_writer.close_files()
        
        # 记录结束时间
        end_time = time.time()
        self.stats.end_time = datetime.now().isoformat()
        self.stats.duration_seconds = end_time - start_time
        
        # 写入统计信息
        self.output_writer.write_stats(self.stats)
        
        # 输出摘要
        self._print_summary()
        
        return self.stats
    
    def _process_pages(self, start_page: int, batch_writer: BatchWriter) -> None:
        """
        处理 PDF 页面
        
        Args:
            start_page: 起始页码
            batch_writer: 批量写入器
        """
        # 用于累积 chunks 的缓冲区
        page_blocks_buffer: Dict[int, List[PageBlock]] = {}
        buffer_size = self.config.runtime.batch_size
        
        last_checkpoint_page = start_page - 1
        
        for page_num, page in self.input_loader.iter_pages(start_page=start_page):
            try:
                # 1. 解析页面
                blocks = self.parser.parse_page(page_num, page)
                
                # 更新统计
                self._update_block_stats(blocks)
                
                # 2. 规范化
                normalized_blocks = self.normalizer.normalize_page_blocks(blocks, page_num)
                
                # 3. 写入页面块
                batch_writer.add_page_blocks(normalized_blocks)
                
                # 4. 累积到缓冲区
                page_blocks_buffer[page_num] = normalized_blocks
                
                # 5. 当缓冲区满时，创建 chunks
                if len(page_blocks_buffer) >= buffer_size:
                    self._process_buffer(page_blocks_buffer, batch_writer)
                    
                    # 保留最后一页用于重叠
                    last_page = max(page_blocks_buffer.keys())
                    page_blocks_buffer = {last_page: page_blocks_buffer[last_page]}
                
                # 更新进度
                self.stats.processed_pages += 1
                
                # 定期保存检查点
                if (self.config.runtime.enable_checkpoint and 
                    page_num - last_checkpoint_page >= self.config.runtime.save_interval):
                    self._save_checkpoint(page_num)
                    last_checkpoint_page = page_num
                
                # 输出进度
                if (page_num + 1) % 10 == 0:
                    progress = (page_num + 1) / self.stats.total_pages * 100
                    self.logger.info(
                        f"进度: {page_num + 1}/{self.stats.total_pages} "
                        f"({progress:.1f}%) - "
                        f"Chunks: {self.stats.total_chunks}"
                    )
                
            except Exception as e:
                self.logger.error(f"处理页面 {page_num} 失败: {e}")
                self.stats.failed_pages += 1
                continue
        
        # 处理剩余缓冲区
        if page_blocks_buffer:
            self._process_buffer(page_blocks_buffer, batch_writer)
    
    def _process_buffer(
        self, 
        page_blocks_buffer: Dict[int, List[PageBlock]],
        batch_writer: BatchWriter
    ) -> None:
        """
        处理页面块缓冲区，创建和校验 chunks
        
        Args:
            page_blocks_buffer: 页面块缓冲区
            batch_writer: 批量写入器
        """
        # 创建 chunks
        chunks = self.chunker.create_chunks(page_blocks_buffer)
        
        if not chunks:
            return
        
        # 校验 chunks
        accepted, rejected = self.validator.validate_chunks(chunks)
        
        # 写入结果
        batch_writer.add_chunks(accepted)
        batch_writer.add_rejected(rejected)
        
        # 更新统计
        self.stats.total_chunks += len(chunks)
        self.stats.accepted_chunks += len(accepted)
        self.stats.rejected_chunks += len(rejected)
        self.stats.llm_calls = self.validator.llm_call_count
    
    def _update_block_stats(self, blocks: List[PageBlock]) -> None:
        """更新块统计"""
        self.stats.total_blocks += len(blocks)
        for block in blocks:
            if block.type == BlockType.TEXT:
                self.stats.text_blocks += 1
            elif block.type == BlockType.TABLE:
                self.stats.table_blocks += 1
            elif block.type == BlockType.IMAGE:
                self.stats.image_blocks += 1
    
    def _save_checkpoint(self, page_num: Optional[int] = None) -> None:
        """保存检查点"""
        if page_num is None:
            page_num = self.stats.processed_pages - 1
        
        checkpoint = Checkpoint(
            last_processed_page=page_num,
            total_pages=self.stats.total_pages,
            processed_chunks=self.stats.total_chunks,
            llm_calls_used=self.validator.llm_call_count if self.validator else 0
        )
        self.output_writer.save_checkpoint(checkpoint)
    
    def _print_summary(self) -> None:
        """输出处理摘要"""
        self.logger.info("=" * 60)
        self.logger.info("处理完成")
        self.logger.info("=" * 60)
        self.logger.info(f"源文件: {self.stats.source_file}")
        self.logger.info(f"总页数: {self.stats.total_pages}")
        self.logger.info(f"处理页数: {self.stats.processed_pages}")
        self.logger.info(f"失败页数: {self.stats.failed_pages}")
        self.logger.info("-" * 40)
        self.logger.info(f"总块数: {self.stats.total_blocks}")
        self.logger.info(f"  - 文本块: {self.stats.text_blocks}")
        self.logger.info(f"  - 表格块: {self.stats.table_blocks}")
        self.logger.info(f"  - 图片块: {self.stats.image_blocks}")
        self.logger.info("-" * 40)
        self.logger.info(f"总 Chunks: {self.stats.total_chunks}")
        self.logger.info(f"  - 通过: {self.stats.accepted_chunks}")
        self.logger.info(f"  - 拒绝: {self.stats.rejected_chunks}")
        self.logger.info(f"LLM 调用次数: {self.stats.llm_calls}")
        self.logger.info("-" * 40)
        self.logger.info(f"处理时间: {self.stats.duration_seconds:.1f} 秒")
        self.logger.info("=" * 60)
        
        # 输出文件摘要
        summary = self.output_writer.get_output_summary()
        self.logger.info(f"输出目录: {summary['output_dir']}")
        for name, info in summary.get('files', {}).items():
            if info.get('lines'):
                self.logger.info(f"  - {name}: {info['lines']} 行, {info['size_kb']:.1f} KB")
            else:
                self.logger.info(f"  - {name}: {info['size_kb']:.1f} KB")


class PipelineBuilder:
    """
    流水线构建器
    提供流式 API 来配置和构建流水线
    """
    
    def __init__(self):
        self._config_path: Optional[str] = None
        self._base_dir: Optional[str] = None
        self._overrides: Dict[str, Any] = {}
    
    def with_config(self, config_path: str) -> "PipelineBuilder":
        """设置配置文件路径"""
        self._config_path = config_path
        return self
    
    def with_base_dir(self, base_dir: str) -> "PipelineBuilder":
        """设置基础目录"""
        self._base_dir = base_dir
        return self
    
    def with_pdf(self, pdf_path: str) -> "PipelineBuilder":
        """覆盖 PDF 路径"""
        self._overrides['pdf.path'] = pdf_path
        return self
    
    def with_chunk_size(self, size: int, overlap: int) -> "PipelineBuilder":
        """覆盖切片配置"""
        self._overrides['chunk.size'] = size
        self._overrides['chunk.overlap'] = overlap
        return self
    
    def with_llm(self, enabled: bool) -> "PipelineBuilder":
        """覆盖 LLM 配置"""
        self._overrides['llm.enabled'] = enabled
        return self
    
    def build(self) -> Pipeline:
        """构建流水线"""
        if not self._config_path:
            raise ValueError("必须指定配置文件路径")
        
        pipeline = Pipeline(self._config_path, self._base_dir)
        
        # 应用覆盖配置
        for key, value in self._overrides.items():
            parts = key.split('.')
            obj = pipeline.config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
        
        return pipeline
