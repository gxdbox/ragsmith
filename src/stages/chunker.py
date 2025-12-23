"""
切片与语义增强层模块
将规范化后的文本切分为适合向量化的 chunks
"""
import re
from typing import List, Dict, Any, Optional, Generator
import logging

from ..core.config import Config, ChunkConfig
from ..core.models import PageBlock, Chunk, BlockType
from ..core.utils import count_tokens, split_sentences, generate_chunk_id


class Chunker:
    """
    文本切片器
    基于 token 或字符数切分文本，支持句子边界对齐
    """
    
    def __init__(self, config: Config, source_filename: str):
        """
        初始化切片器
        
        Args:
            config: 配置对象
            source_filename: 源文件名
        """
        self.config = config
        self.chunk_config: ChunkConfig = config.chunk
        self.source_filename = source_filename
        self.logger = logging.getLogger(__name__)
        
        self._chunk_counter = 0
    
    def create_chunks(
        self, 
        page_blocks_map: Dict[int, List[PageBlock]]
    ) -> List[Chunk]:
        """
        从页面块创建 chunks
        
        Args:
            page_blocks_map: {页码: 块列表} 字典
        
        Returns:
            Chunk 列表
        """
        # 1. 合并所有页面的文本内容
        merged_content = self._merge_page_contents(page_blocks_map)
        
        if not merged_content:
            return []
        
        # 2. 切分为 chunks
        chunks = self._split_into_chunks(merged_content)
        
        self.logger.info(f"创建了 {len(chunks)} 个 chunks")
        return chunks
    
    def _merge_page_contents(
        self, 
        page_blocks_map: Dict[int, List[PageBlock]]
    ) -> List[Dict[str, Any]]:
        """
        合并页面内容，保留页码信息
        
        Args:
            page_blocks_map: {页码: 块列表} 字典
        
        Returns:
            合并后的内容列表，每项包含 text 和 page
        """
        merged = []
        
        # 按页码排序
        for page_num in sorted(page_blocks_map.keys()):
            blocks = page_blocks_map[page_num]
            
            for block in blocks:
                if block.type == BlockType.TEXT:
                    if isinstance(block.content, str) and block.content.strip():
                        merged.append({
                            "text": block.content.strip(),
                            "page": page_num,
                            "confidence": block.confidence
                        })
                elif block.type == BlockType.TABLE:
                    # 将表格转换为文本
                    table_text = self._table_to_text(block.content)
                    if table_text:
                        merged.append({
                            "text": table_text,
                            "page": page_num,
                            "confidence": block.confidence,
                            "is_table": True
                        })
        
        return merged
    
    def _table_to_text(self, table_content: Dict[str, Any]) -> str:
        """
        将表格转换为文本
        
        Args:
            table_content: 表格内容
        
        Returns:
            表格的文本表示
        """
        rows = table_content.get("rows", [])
        if not rows:
            return ""
        
        lines = []
        for row in rows:
            # 过滤空单元格
            cells = [str(cell).strip() for cell in row if cell]
            if cells:
                lines.append(" | ".join(cells))
        
        return "\n".join(lines)
    
    def _split_into_chunks(
        self, 
        merged_content: List[Dict[str, Any]]
    ) -> List[Chunk]:
        """
        将合并的内容切分为 chunks
        
        Args:
            merged_content: 合并后的内容列表
        
        Returns:
            Chunk 列表
        """
        chunks = []
        
        # 构建完整文本和页码映射
        full_text = ""
        char_to_page = {}  # 字符位置 -> 页码
        
        for item in merged_content:
            start_pos = len(full_text)
            text = item["text"]
            
            # 添加段落分隔
            if full_text and not full_text.endswith('\n'):
                full_text += '\n\n'
                start_pos = len(full_text)
            
            full_text += text
            
            # 记录字符位置到页码的映射
            for i in range(len(text)):
                char_to_page[start_pos + i] = item["page"]
        
        if not full_text.strip():
            return []
        
        # 根据配置选择切分方式
        if self.chunk_config.split_by == "token":
            chunk_texts = self._split_by_tokens(full_text)
        elif self.chunk_config.split_by == "sentence":
            chunk_texts = self._split_by_sentences(full_text)
        else:
            chunk_texts = self._split_by_chars(full_text)
        
        # 创建 Chunk 对象
        current_pos = 0
        for chunk_text in chunk_texts:
            if not chunk_text.strip():
                continue
            
            # 找到 chunk 在原文中的位置
            chunk_start = full_text.find(chunk_text, current_pos)
            if chunk_start == -1:
                chunk_start = current_pos
            chunk_end = chunk_start + len(chunk_text)
            current_pos = chunk_end - self.chunk_config.overlap
            
            # 确定页码范围
            page_start = char_to_page.get(chunk_start, 0)
            page_end = char_to_page.get(min(chunk_end - 1, len(full_text) - 1), page_start)
            
            self._chunk_counter += 1
            
            chunk = Chunk(
                chunk_id=generate_chunk_id(
                    self.source_filename, 
                    page_start, 
                    page_end, 
                    self._chunk_counter
                ),
                content=chunk_text.strip(),
                source=self.source_filename,
                page_start=page_start,
                page_end=page_end,
                token_count=count_tokens(chunk_text),
                char_count=len(chunk_text)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_by_tokens(self, text: str) -> List[str]:
        """
        基于 token 数量切分文本
        
        Args:
            text: 输入文本
        
        Returns:
            切分后的文本列表
        """
        chunks = []
        
        if self.chunk_config.respect_sentence_boundary:
            # 先按句子分割
            sentences = split_sentences(text)
            
            current_chunk = ""
            current_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = count_tokens(sentence)
                
                # 如果单个句子就超过 chunk 大小
                if sentence_tokens > self.chunk_config.size:
                    # 保存当前 chunk
                    if current_chunk:
                        chunks.append(current_chunk)
                    # 强制切分长句子
                    sub_chunks = self._force_split(sentence)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                    current_tokens = count_tokens(current_chunk)
                    continue
                
                # 检查是否会超过大小
                if current_tokens + sentence_tokens > self.chunk_config.size:
                    # 保存当前 chunk
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # 计算重叠
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + sentence
                    current_tokens = count_tokens(current_chunk)
                else:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
                    current_tokens += sentence_tokens
            
            # 保存最后一个 chunk
            if current_chunk and count_tokens(current_chunk) >= self.chunk_config.min_chunk_size:
                chunks.append(current_chunk)
        else:
            # 简单按 token 数切分
            chunks = self._force_split(text)
        
        return chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """
        基于句子边界切分文本
        
        Args:
            text: 输入文本
        
        Returns:
            切分后的文本列表
        """
        sentences = split_sentences(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.chunk_config.size * 4:  # 假设平均 4 字符/token
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_by_chars(self, text: str) -> List[str]:
        """
        基于字符数切分文本
        
        Args:
            text: 输入文本
        
        Returns:
            切分后的文本列表
        """
        char_size = self.chunk_config.size * 4  # 假设平均 4 字符/token
        char_overlap = self.chunk_config.overlap * 4
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + char_size, len(text))
            
            # 尝试在句子边界切分
            if end < len(text) and self.chunk_config.respect_sentence_boundary:
                # 向前找句子结束符
                for i in range(end, max(start + char_size // 2, start), -1):
                    if text[i] in '。！？.!?\n':
                        end = i + 1
                        break
            
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            
            start = end - char_overlap
            if start <= 0:
                start = end
        
        return chunks
    
    def _force_split(self, text: str) -> List[str]:
        """
        强制切分超长文本
        
        Args:
            text: 输入文本
        
        Returns:
            切分后的文本列表
        """
        chunks = []
        target_tokens = self.chunk_config.size
        overlap_tokens = self.chunk_config.overlap
        
        words = list(text)  # 按字符切分（适合中文）
        current_chunk = []
        current_tokens = 0
        
        for word in words:
            word_tokens = count_tokens(word)
            
            if current_tokens + word_tokens > target_tokens:
                if current_chunk:
                    chunks.append(''.join(current_chunk))
                
                # 计算重叠
                overlap_chars = int(len(current_chunk) * overlap_tokens / target_tokens)
                current_chunk = current_chunk[-overlap_chars:] if overlap_chars > 0 else []
                current_tokens = count_tokens(''.join(current_chunk))
            
            current_chunk.append(word)
            current_tokens += word_tokens
        
        if current_chunk:
            chunks.append(''.join(current_chunk))
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """
        获取用于重叠的文本
        
        Args:
            text: 输入文本
        
        Returns:
            重叠文本
        """
        if not text:
            return ""
        
        target_tokens = self.chunk_config.overlap
        
        # 从末尾开始取
        sentences = split_sentences(text)
        overlap_text = ""
        overlap_tokens = 0
        
        for sentence in reversed(sentences):
            sentence_tokens = count_tokens(sentence)
            if overlap_tokens + sentence_tokens <= target_tokens:
                overlap_text = sentence + " " + overlap_text
                overlap_tokens += sentence_tokens
            else:
                break
        
        return overlap_text.strip()
    
    def create_chunks_streaming(
        self, 
        page_blocks_generator: Generator[tuple[int, List[PageBlock]], None, None],
        buffer_pages: int = 5
    ) -> Generator[Chunk, None, None]:
        """
        流式创建 chunks（用于超大文件）
        
        Args:
            page_blocks_generator: 页面块生成器
            buffer_pages: 缓冲页数
        
        Yields:
            Chunk 对象
        """
        buffer: Dict[int, List[PageBlock]] = {}
        
        for page_num, blocks in page_blocks_generator:
            buffer[page_num] = blocks
            
            # 当缓冲区满时，处理并输出 chunks
            if len(buffer) >= buffer_pages:
                chunks = self.create_chunks(buffer)
                for chunk in chunks[:-1]:  # 保留最后一个用于重叠
                    yield chunk
                
                # 只保留最后一页用于重叠
                last_page = max(buffer.keys())
                buffer = {last_page: buffer[last_page]}
        
        # 处理剩余内容
        if buffer:
            chunks = self.create_chunks(buffer)
            for chunk in chunks:
                yield chunk
    
    def reset_counter(self) -> None:
        """重置 chunk 计数器"""
        self._chunk_counter = 0
