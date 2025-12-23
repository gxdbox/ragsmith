"""
工具函数模块
提供通用的工具函数
"""
import re
import logging
from typing import List, Optional
import unicodedata


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(getattr(logging, level.upper()))
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def count_tokens(text: str, method: str = "simple") -> int:
    """
    估算文本的 token 数量
    
    Args:
        text: 输入文本
        method: 计算方法 (simple, tiktoken)
    
    Returns:
        估算的 token 数量
    """
    if method == "simple":
        # 简单估算：中文按字符计，英文按空格分词
        # 中文约 1 字符 = 1-2 tokens，英文约 4 字符 = 1 token
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 4)
    else:
        # 可扩展：使用 tiktoken 等库精确计算
        return len(text) // 3


def is_chinese_char(char: str) -> bool:
    """判断是否为中文字符"""
    return '\u4e00' <= char <= '\u9fff'


def is_garbled(text: str, threshold: float = 0.1) -> tuple[bool, float]:
    """
    检测文本是否为乱码
    
    Args:
        text: 输入文本
        threshold: 乱码比例阈值
    
    Returns:
        (是否乱码, 乱码比例)
    """
    if not text:
        return False, 0.0
    
    # 统计不可打印字符和异常字符
    garble_count = 0
    total_count = len(text)
    
    for char in text:
        # 检查是否为控制字符（除了常见的空白字符）
        if unicodedata.category(char).startswith('C') and char not in '\n\r\t ':
            garble_count += 1
        # 检查是否为私用区字符
        elif unicodedata.category(char) == 'Co':
            garble_count += 1
        # 检查是否为替换字符
        elif char == '\ufffd':
            garble_count += 1
    
    ratio = garble_count / total_count if total_count > 0 else 0
    return ratio > threshold, ratio


def calculate_info_density(text: str) -> float:
    """
    计算文本信息密度
    
    信息密度 = 有意义字符数 / 总字符数
    有意义字符：中文、英文字母、数字
    
    Args:
        text: 输入文本
    
    Returns:
        信息密度 (0.0-1.0)
    """
    if not text:
        return 0.0
    
    # 统计有意义字符
    meaningful = 0
    for char in text:
        if is_chinese_char(char):
            meaningful += 1
        elif char.isalnum():
            meaningful += 1
    
    return meaningful / len(text)


def calculate_noise_ratio(text: str) -> float:
    """
    计算噪声比例
    
    噪声：连续特殊符号、过多空白、无意义重复
    
    Args:
        text: 输入文本
    
    Returns:
        噪声比例 (0.0-1.0)
    """
    if not text:
        return 0.0
    
    noise_count = 0
    total = len(text)
    
    # 检测连续特殊符号
    special_pattern = re.compile(r'[^\w\s\u4e00-\u9fff]{3,}')
    for match in special_pattern.finditer(text):
        noise_count += len(match.group())
    
    # 检测过多连续空白
    whitespace_pattern = re.compile(r'\s{4,}')
    for match in whitespace_pattern.finditer(text):
        noise_count += len(match.group()) - 1  # 保留一个空白
    
    return min(noise_count / total, 1.0) if total > 0 else 0.0


def calculate_repetition_ratio(text: str, min_repeat_len: int = 5) -> float:
    """
    计算重复比例
    
    检测文本中重复出现的片段
    
    Args:
        text: 输入文本
        min_repeat_len: 最小重复片段长度
    
    Returns:
        重复比例 (0.0-1.0)
    """
    if len(text) < min_repeat_len * 2:
        return 0.0
    
    # 使用滑动窗口检测重复
    seen = set()
    repeat_chars = 0
    
    for i in range(len(text) - min_repeat_len + 1):
        segment = text[i:i + min_repeat_len]
        if segment in seen:
            repeat_chars += 1
        else:
            seen.add(segment)
    
    return repeat_chars / (len(text) - min_repeat_len + 1)


def split_sentences(text: str) -> List[str]:
    """
    将文本分割为句子
    
    支持中英文标点
    
    Args:
        text: 输入文本
    
    Returns:
        句子列表
    """
    # 中英文句子结束符
    sentence_endings = re.compile(r'([。！？.!?]+)')
    
    parts = sentence_endings.split(text)
    sentences = []
    
    i = 0
    while i < len(parts):
        sentence = parts[i]
        # 如果下一个是标点，合并
        if i + 1 < len(parts) and sentence_endings.match(parts[i + 1]):
            sentence += parts[i + 1]
            i += 2
        else:
            i += 1
        
        sentence = sentence.strip()
        if sentence:
            sentences.append(sentence)
    
    return sentences


def clean_text(text: str) -> str:
    """
    基础文本清洗
    
    Args:
        text: 输入文本
    
    Returns:
        清洗后的文本
    """
    if not text:
        return ""
    
    # 移除零宽字符
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f\u205f-\u206f]', '', text)
    
    # 规范化 Unicode
    text = unicodedata.normalize('NFKC', text)
    
    # 移除控制字符（保留换行和制表符）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    return text


def generate_chunk_id(source: str, page_start: int, page_end: int, index: int) -> str:
    """
    生成 chunk ID
    
    Args:
        source: 来源文件名
        page_start: 起始页
        page_end: 结束页
        index: 序号
    
    Returns:
        唯一的 chunk ID
    """
    import hashlib
    
    # 使用文件名、页码范围和序号生成 ID
    base = f"{source}_{page_start}_{page_end}_{index}"
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:8]
    
    return f"chunk_{page_start:04d}_{page_end:04d}_{index:04d}_{hash_suffix}"
