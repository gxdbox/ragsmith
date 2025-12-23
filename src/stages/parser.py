"""
文档解析层模块
使用 PyMuPDF 提取 PDF 页面内容
"""
import fitz
import re
from typing import List, Dict, Any, Optional
import logging

from ..core.config import Config, ParsingConfig
from ..core.models import PageBlock, BlockType


class PDFParser:
    """
    PDF 解析器
    从 PDF 页面提取文本、表格和图片信息
    """
    
    def __init__(self, config: Config):
        """
        初始化解析器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.parsing_config: ParsingConfig = config.parsing
        self.logger = logging.getLogger(__name__)
        
        self._block_counter = 0
    
    def parse_page(self, page_num: int, page: fitz.Page) -> List[PageBlock]:
        """
        解析单个页面
        
        Args:
            page_num: 页码
            page: PyMuPDF 页面对象
        
        Returns:
            PageBlock 列表
        """
        blocks = []
        
        # 提取文本块
        text_blocks = self._extract_text_blocks(page_num, page)
        blocks.extend(text_blocks)
        
        # 提取表格（如果启用）
        if self.parsing_config.extract_tables:
            table_blocks = self._extract_tables(page_num, page)
            blocks.extend(table_blocks)
        
        # 记录图片占位（如果启用）
        if self.parsing_config.extract_images:
            image_blocks = self._extract_image_placeholders(page_num, page)
            blocks.extend(image_blocks)
        
        return blocks
    
    def _extract_text_blocks(self, page_num: int, page: fitz.Page) -> List[PageBlock]:
        """
        提取页面文本块
        
        Args:
            page_num: 页码
            page: 页面对象
        
        Returns:
            文本 PageBlock 列表
        """
        blocks = []
        
        # 使用 dict 模式获取结构化文本
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # 文本块
                text_content = self._extract_block_text(block)
                
                if text_content.strip():
                    self._block_counter += 1
                    bbox = block.get("bbox", (0, 0, 0, 0))
                    
                    page_block = PageBlock(
                        page=page_num,
                        type=BlockType.TEXT,
                        content=text_content,
                        confidence=1.0,
                        bbox=tuple(bbox),
                        block_id=f"block_{page_num:04d}_{self._block_counter:04d}",
                        metadata={
                            "font_info": self._get_font_info(block),
                            "line_count": len(block.get("lines", []))
                        }
                    )
                    blocks.append(page_block)
        
        return blocks
    
    def _extract_block_text(self, block: Dict[str, Any]) -> str:
        """
        从块中提取文本
        
        Args:
            block: PyMuPDF 块字典
        
        Returns:
            提取的文本
        """
        lines = []
        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
            lines.append(line_text)
        
        return "\n".join(lines)
    
    def _get_font_info(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取块的字体信息
        
        Args:
            block: PyMuPDF 块字典
        
        Returns:
            字体信息字典
        """
        fonts = set()
        sizes = []
        
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                fonts.add(span.get("font", "unknown"))
                sizes.append(span.get("size", 0))
        
        return {
            "fonts": list(fonts),
            "avg_size": sum(sizes) / len(sizes) if sizes else 0,
            "max_size": max(sizes) if sizes else 0
        }
    
    def _extract_tables(self, page_num: int, page: fitz.Page) -> List[PageBlock]:
        """
        提取页面表格
        
        Args:
            page_num: 页码
            page: 页面对象
        
        Returns:
            表格 PageBlock 列表
        """
        blocks = []
        
        try:
            # 使用 PyMuPDF 的表格检测功能
            tables = page.find_tables(strategy=self.parsing_config.table_strategy)
            
            for idx, table in enumerate(tables):
                self._block_counter += 1
                
                # 提取表格数据
                table_data = []
                for row in table.extract():
                    cleaned_row = [cell if cell else "" for cell in row]
                    table_data.append(cleaned_row)
                
                if table_data:
                    page_block = PageBlock(
                        page=page_num,
                        type=BlockType.TABLE,
                        content={
                            "rows": table_data,
                            "row_count": len(table_data),
                            "col_count": len(table_data[0]) if table_data else 0
                        },
                        confidence=0.8,  # 表格识别置信度略低
                        bbox=table.bbox if hasattr(table, 'bbox') else None,
                        block_id=f"table_{page_num:04d}_{self._block_counter:04d}",
                        metadata={
                            "table_index": idx
                        }
                    )
                    blocks.append(page_block)
        
        except Exception as e:
            self.logger.warning(f"页面 {page_num} 表格提取失败: {e}")
        
        return blocks
    
    def _extract_image_placeholders(self, page_num: int, page: fitz.Page) -> List[PageBlock]:
        """
        提取图片占位信息（不进行 OCR）
        
        Args:
            page_num: 页码
            page: 页面对象
        
        Returns:
            图片占位 PageBlock 列表
        """
        blocks = []
        
        try:
            image_list = page.get_images(full=True)
            
            for idx, img_info in enumerate(image_list):
                self._block_counter += 1
                
                xref = img_info[0]
                
                # 获取图片在页面上的位置
                img_rects = page.get_image_rects(xref)
                bbox = img_rects[0] if img_rects else None
                
                page_block = PageBlock(
                    page=page_num,
                    type=BlockType.IMAGE,
                    content=f"[IMAGE: xref={xref}, index={idx}]",
                    confidence=0.0,  # 图片占位，无文本置信度
                    bbox=tuple(bbox) if bbox else None,
                    block_id=f"image_{page_num:04d}_{self._block_counter:04d}",
                    metadata={
                        "xref": xref,
                        "image_index": idx,
                        "width": img_info[2] if len(img_info) > 2 else 0,
                        "height": img_info[3] if len(img_info) > 3 else 0
                    }
                )
                blocks.append(page_block)
        
        except Exception as e:
            self.logger.warning(f"页面 {page_num} 图片提取失败: {e}")
        
        return blocks
    
    def parse_pages_batch(
        self, 
        pages: List[tuple[int, fitz.Page]]
    ) -> Dict[int, List[PageBlock]]:
        """
        批量解析多个页面
        
        Args:
            pages: (页码, 页面对象) 元组列表
        
        Returns:
            {页码: PageBlock列表} 字典
        """
        results = {}
        
        for page_num, page in pages:
            try:
                blocks = self.parse_page(page_num, page)
                results[page_num] = blocks
            except Exception as e:
                self.logger.error(f"解析页面 {page_num} 失败: {e}")
                results[page_num] = []
        
        return results
    
    def table_to_text(self, table_content: Dict[str, Any]) -> str:
        """
        将表格内容转换为文本格式
        
        Args:
            table_content: 表格内容字典
        
        Returns:
            表格的文本表示
        """
        rows = table_content.get("rows", [])
        if not rows:
            return ""
        
        # 简单的表格文本化
        lines = []
        for row in rows:
            line = " | ".join(str(cell) for cell in row)
            lines.append(line)
        
        return "\n".join(lines)
    
    def reset_counter(self) -> None:
        """重置块计数器"""
        self._block_counter = 0
