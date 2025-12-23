"""
输入层模块
负责流式读取超大 PDF 文件
"""
import fitz  # PyMuPDF
from pathlib import Path
from typing import Generator, Optional
import logging

from ..core.config import Config


class InputLoader:
    """
    PDF 输入加载器
    支持流式逐页读取，不一次性加载全文件
    """
    
    def __init__(self, config: Config, base_dir: Path):
        """
        初始化输入加载器
        
        Args:
            config: 配置对象
            base_dir: 项目基础目录
        """
        self.config = config
        self.base_dir = base_dir
        self.logger = logging.getLogger(__name__)
        
        self.pdf_path = config.get_absolute_pdf_path(base_dir)
        self._doc: Optional[fitz.Document] = None
        self._total_pages: int = 0
    
    def open(self) -> None:
        """打开 PDF 文件"""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {self.pdf_path}")
        
        self.logger.info(f"打开 PDF 文件: {self.pdf_path}")
        self._doc = fitz.open(str(self.pdf_path))
        self._total_pages = len(self._doc)
        self.logger.info(f"PDF 总页数: {self._total_pages}")
    
    def close(self) -> None:
        """关闭 PDF 文件"""
        if self._doc:
            self._doc.close()
            self._doc = None
            self.logger.info("PDF 文件已关闭")
    
    @property
    def total_pages(self) -> int:
        """获取总页数"""
        return self._total_pages
    
    @property
    def filename(self) -> str:
        """获取文件名"""
        return self.pdf_path.name
    
    def get_page_range(self, start_page: Optional[int] = None) -> tuple[int, int]:
        """
        获取要处理的页码范围
        
        Args:
            start_page: 覆盖配置的起始页（用于断点续传）
        
        Returns:
            (起始页, 结束页) 元组
        """
        if start_page is not None:
            page_start = start_page
        else:
            page_start = self.config.pdf.start_page
        
        page_end = self.config.pdf.end_page
        if page_end is None or page_end > self._total_pages:
            page_end = self._total_pages
        
        return page_start, page_end
    
    def iter_pages(
        self, 
        start_page: Optional[int] = None,
        batch_size: Optional[int] = None
    ) -> Generator[tuple[int, fitz.Page], None, None]:
        """
        流式迭代 PDF 页面
        
        Args:
            start_page: 起始页码（用于断点续传）
            batch_size: 批处理大小（暂未使用，预留接口）
        
        Yields:
            (页码, 页面对象) 元组
        """
        if self._doc is None:
            self.open()
        
        page_start, page_end = self.get_page_range(start_page)
        
        self.logger.info(f"开始处理页面: {page_start} - {page_end - 1}")
        
        for page_num in range(page_start, page_end):
            try:
                page = self._doc.load_page(page_num)
                yield page_num, page
            except Exception as e:
                self.logger.error(f"加载页面 {page_num} 失败: {e}")
                continue
    
    def get_page(self, page_num: int) -> Optional[fitz.Page]:
        """
        获取指定页面
        
        Args:
            page_num: 页码（0-indexed）
        
        Returns:
            页面对象，失败返回 None
        """
        if self._doc is None:
            self.open()
        
        if 0 <= page_num < self._total_pages:
            try:
                return self._doc.load_page(page_num)
            except Exception as e:
                self.logger.error(f"加载页面 {page_num} 失败: {e}")
        return None
    
    def get_metadata(self) -> dict:
        """
        获取 PDF 元数据
        
        Returns:
            元数据字典
        """
        if self._doc is None:
            self.open()
        
        metadata = self._doc.metadata or {}
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": metadata.get("creationDate", ""),
            "modification_date": metadata.get("modDate", ""),
            "total_pages": self._total_pages,
            "file_size_mb": self.pdf_path.stat().st_size / (1024 * 1024)
        }
    
    def __enter__(self):
        """上下文管理器入口"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False
