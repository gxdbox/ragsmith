"""
规范化处理层模块
清洗和规范化提取的文本内容
"""
import re
from typing import List, Optional, Set
import logging

from ..core.config import Config, NormalizationConfig
from ..core.models import PageBlock, BlockType


class Normalizer:
    """
    文本规范化处理器
    负责清洗页眉页脚、合并异常换行、规范化标点和空白
    """
    
    def __init__(self, config: Config):
        """
        初始化规范化处理器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.norm_config: NormalizationConfig = config.normalization
        self.logger = logging.getLogger(__name__)
        
        # 页眉页脚模式缓存
        self._header_patterns: Set[str] = set()
        self._footer_patterns: Set[str] = set()
        
        # 预编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """预编译常用正则表达式"""
        # 页码模式
        self.page_number_pattern = re.compile(
            r'^[\s]*[-—]?\s*\d+\s*[-—]?[\s]*$|'  # 纯页码
            r'^[\s]*第\s*\d+\s*页[\s]*$|'         # 中文页码
            r'^[\s]*Page\s*\d+[\s]*$',            # 英文页码
            re.IGNORECASE
        )
        
        # 连续空白
        self.multi_space_pattern = re.compile(r'[ \t]+')
        self.multi_newline_pattern = re.compile(r'\n{3,}')
        
        # 异常换行（中文句子中间的换行）
        self.broken_line_pattern = re.compile(
            r'([\u4e00-\u9fff])\n([\u4e00-\u9fff])'
        )
        
        # 标点规范化映射
        self.punctuation_map = {
            '，': ',', '。': '。', '！': '!', '？': '?',
            '；': ';', '：': ':', '"': '"', '"': '"',
            ''': "'", ''': "'", '【': '[', '】': ']',
            '（': '(', '）': ')', '《': '<', '》': '>',
            '、': ',', '…': '...'
        }
        
        # 噪声字符模式
        self.noise_pattern = re.compile(
            r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|'  # 控制字符
            r'[\ufeff\u200b-\u200f]|'              # 零宽字符
            r'[■□▪▫●○◆◇★☆]+'                      # 装饰符号
        )
    
    def normalize_page_blocks(
        self, 
        blocks: List[PageBlock],
        page_num: int
    ) -> List[PageBlock]:
        """
        规范化页面的所有块
        
        Args:
            blocks: 页面块列表
            page_num: 页码
        
        Returns:
            规范化后的块列表
        """
        normalized_blocks = []
        
        for block in blocks:
            if block.type == BlockType.TEXT:
                normalized = self._normalize_text_block(block, page_num, len(blocks))
                if normalized:
                    normalized_blocks.append(normalized)
            elif block.type == BlockType.TABLE:
                # 表格内容也需要清洗
                normalized = self._normalize_table_block(block)
                if normalized:
                    normalized_blocks.append(normalized)
            else:
                # 图片占位直接保留
                normalized_blocks.append(block)
        
        return normalized_blocks
    
    def _normalize_text_block(
        self, 
        block: PageBlock, 
        page_num: int,
        total_blocks: int
    ) -> Optional[PageBlock]:
        """
        规范化文本块
        
        Args:
            block: 文本块
            page_num: 页码
            total_blocks: 页面总块数
        
        Returns:
            规范化后的块，如果应被过滤则返回 None
        """
        content = block.content
        if not isinstance(content, str):
            return block
        
        # 1. 检查是否为页眉页脚
        if self.norm_config.remove_headers_footers:
            if self._is_header_footer(content, block.bbox, page_num):
                self.logger.debug(f"过滤页眉页脚: {content[:50]}...")
                return None
        
        # 2. 移除噪声字符
        content = self.noise_pattern.sub('', content)
        
        # 3. 合并异常换行
        if self.norm_config.merge_broken_lines:
            content = self._merge_broken_lines(content)
        
        # 4. 规范化空白
        if self.norm_config.normalize_whitespace:
            content = self._normalize_whitespace(content)
        
        # 5. 规范化标点（可选，默认保留原始标点）
        # if self.norm_config.normalize_punctuation:
        #     content = self._normalize_punctuation(content)
        
        # 6. 检查是否为有效内容
        if not self._is_valid_content(content):
            return None
        
        # 更新块内容
        block.content = content
        
        # 如果是 OCR 文本，标记为低可信
        if block.metadata.get("is_ocr", False):
            block.confidence = min(block.confidence, 0.7)
            block.metadata["low_confidence_reason"] = "OCR extracted"
        
        return block
    
    def _normalize_table_block(self, block: PageBlock) -> Optional[PageBlock]:
        """
        规范化表格块
        
        Args:
            block: 表格块
        
        Returns:
            规范化后的块
        """
        if not isinstance(block.content, dict):
            return block
        
        rows = block.content.get("rows", [])
        cleaned_rows = []
        
        for row in rows:
            cleaned_row = []
            for cell in row:
                if isinstance(cell, str):
                    # 清洗单元格内容
                    cell = self.noise_pattern.sub('', cell)
                    cell = self._normalize_whitespace(cell)
                cleaned_row.append(cell)
            cleaned_rows.append(cleaned_row)
        
        block.content["rows"] = cleaned_rows
        return block
    
    def _is_header_footer(
        self, 
        content: str, 
        bbox: Optional[tuple],
        page_num: int
    ) -> bool:
        """
        判断是否为页眉页脚
        
        Args:
            content: 文本内容
            bbox: 边界框
            page_num: 页码
        
        Returns:
            是否为页眉页脚
        """
        content = content.strip()
        
        # 检查是否为页码
        if self.page_number_pattern.match(content):
            return True
        
        # 检查是否为短文本（可能是页眉页脚）
        lines = content.split('\n')
        if len(lines) <= self.norm_config.header_footer_max_lines:
            # 检查是否包含页码
            if re.search(r'\d+', content) and len(content) < 50:
                return True
        
        # 基于位置判断（如果有 bbox）
        if bbox:
            # bbox = (x0, y0, x1, y1)
            # 页面顶部或底部的短文本可能是页眉页脚
            y0, y1 = bbox[1], bbox[3]
            # 假设页面高度约 800，顶部 50 或底部 50 以内
            if y0 < 50 or y1 > 750:
                if len(content) < 100:
                    return True
        
        # 检查是否匹配已知的页眉页脚模式
        if content in self._header_patterns or content in self._footer_patterns:
            return True
        
        return False
    
    def _merge_broken_lines(self, text: str) -> str:
        """
        合并异常换行
        
        处理中文句子中间被错误断开的情况
        
        Args:
            text: 输入文本
        
        Returns:
            合并后的文本
        """
        # 合并中文字符之间的换行
        text = self.broken_line_pattern.sub(r'\1\2', text)
        
        # 合并英文单词中间的换行（带连字符）
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        
        # 合并句子中间的换行（前一行不以句号结尾）
        lines = text.split('\n')
        merged_lines = []
        buffer = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                if buffer:
                    merged_lines.append(buffer)
                    buffer = ""
                continue
            
            if buffer:
                # 检查是否应该合并
                if self._should_merge_lines(buffer, line):
                    buffer += line
                else:
                    merged_lines.append(buffer)
                    buffer = line
            else:
                buffer = line
        
        if buffer:
            merged_lines.append(buffer)
        
        return '\n'.join(merged_lines)
    
    def _should_merge_lines(self, prev_line: str, curr_line: str) -> bool:
        """
        判断两行是否应该合并
        
        Args:
            prev_line: 前一行
            curr_line: 当前行
        
        Returns:
            是否应该合并
        """
        if not prev_line or not curr_line:
            return False
        
        # 前一行以句子结束符结尾，不合并
        if prev_line[-1] in '。！？.!?\n':
            return False
        
        # 前一行以冒号结尾，不合并
        if prev_line[-1] in '：:':
            return False
        
        # 当前行以数字或列表符号开头，不合并
        if re.match(r'^[\d一二三四五六七八九十①②③④⑤•·\-]', curr_line):
            return False
        
        # 前一行太短，可能是标题，不合并
        if len(prev_line) < self.norm_config.min_line_length:
            return False
        
        return True
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        规范化空白字符
        
        Args:
            text: 输入文本
        
        Returns:
            规范化后的文本
        """
        # 将多个空格/制表符合并为单个空格
        text = self.multi_space_pattern.sub(' ', text)
        
        # 将多个换行合并为两个换行（保留段落分隔）
        text = self.multi_newline_pattern.sub('\n\n', text)
        
        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def _normalize_punctuation(self, text: str) -> str:
        """
        规范化标点符号
        
        Args:
            text: 输入文本
        
        Returns:
            规范化后的文本
        """
        for old, new in self.punctuation_map.items():
            text = text.replace(old, new)
        return text
    
    def _is_valid_content(self, content: str) -> bool:
        """
        检查内容是否有效
        
        Args:
            content: 文本内容
        
        Returns:
            是否有效
        """
        if not content or not content.strip():
            return False
        
        # 太短的内容
        if len(content.strip()) < self.norm_config.min_line_length:
            return False
        
        return True
    
    def learn_header_footer_patterns(self, all_blocks: List[List[PageBlock]]) -> None:
        """
        从多页内容中学习页眉页脚模式
        
        通过统计在多页重复出现的短文本来识别页眉页脚
        
        Args:
            all_blocks: 所有页面的块列表
        """
        # 统计每个短文本出现的次数
        text_counts = {}
        
        for page_blocks in all_blocks:
            for block in page_blocks:
                if block.type == BlockType.TEXT and isinstance(block.content, str):
                    content = block.content.strip()
                    # 只统计短文本
                    if len(content) < 100:
                        # 移除页码变化
                        normalized = re.sub(r'\d+', 'N', content)
                        text_counts[normalized] = text_counts.get(normalized, 0) + 1
        
        # 出现次数超过阈值的认为是页眉页脚
        threshold = len(all_blocks) * 0.5  # 超过 50% 页面出现
        
        for text, count in text_counts.items():
            if count >= threshold:
                self._header_patterns.add(text)
                self.logger.debug(f"识别到页眉页脚模式: {text}")
