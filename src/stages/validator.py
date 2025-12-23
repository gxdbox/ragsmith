"""
质量校验与路由层模块
实现规则校验和 LLM 语义校验
"""
import re
import json
import time
from typing import List, Optional, Tuple
import logging
import requests

from ..core.config import Config, QualityConfig, LLMConfig
from ..core.models import Chunk, ValidationResult, QualityLevel
from ..core.utils import (
    is_garbled, 
    calculate_info_density, 
    calculate_noise_ratio,
    calculate_repetition_ratio
)


class Validator:
    """
    质量校验器
    实现双层质量控制：规则校验 + LLM 语义校验
    """
    
    def __init__(self, config: Config):
        """
        初始化校验器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.quality_config: QualityConfig = config.quality
        self.llm_config: LLMConfig = config.llm
        self.logger = logging.getLogger(__name__)
        
        # LLM 调用计数
        self._llm_call_count = 0
        self._max_llm_calls = config.llm.max_calls
    
    def validate_chunk(self, chunk: Chunk) -> Tuple[Chunk, ValidationResult]:
        """
        校验单个 chunk
        
        Args:
            chunk: 待校验的 chunk
        
        Returns:
            (更新后的 chunk, 校验结果)
        """
        # 1. 规则校验（始终执行）
        rule_result = self._rule_validation(chunk)
        chunk.rule_score = rule_result.confidence
        
        # 2. 判断是否需要 LLM 校验
        need_llm = self._should_use_llm(chunk, rule_result)
        
        if need_llm and self._can_call_llm():
            # 3. LLM 语义校验
            llm_result = self._llm_validation(chunk)
            if llm_result:
                chunk.llm_quality = llm_result.quality
                chunk.llm_confidence = llm_result.confidence
                chunk.llm_reason = llm_result.reason
                return chunk, llm_result
        
        return chunk, rule_result
    
    def validate_chunks(self, chunks: List[Chunk]) -> Tuple[List[Chunk], List[Chunk]]:
        """
        批量校验 chunks
        
        Args:
            chunks: chunk 列表
        
        Returns:
            (通过的 chunks, 被拒绝的 chunks)
        """
        accepted = []
        rejected = []
        
        for chunk in chunks:
            chunk, result = self.validate_chunk(chunk)
            
            if result.quality == QualityLevel.REJECT:
                chunk.metadata["reject_reason"] = result.reason
                rejected.append(chunk)
            else:
                accepted.append(chunk)
        
        self.logger.info(
            f"校验完成: 通过 {len(accepted)}, 拒绝 {len(rejected)}, "
            f"LLM 调用 {self._llm_call_count}"
        )
        
        return accepted, rejected
    
    def _rule_validation(self, chunk: Chunk) -> ValidationResult:
        """
        规则校验
        
        Args:
            chunk: 待校验的 chunk
        
        Returns:
            校验结果
        """
        content = chunk.content
        reasons = []
        
        # 1. 长度检查
        length = len(content)
        if length < self.quality_config.min_length:
            reasons.append(f"长度不足: {length} < {self.quality_config.min_length}")
        
        # 2. 信息密度检查
        info_density = calculate_info_density(content)
        if info_density < self.quality_config.min_info_density:
            reasons.append(f"信息密度低: {info_density:.2f} < {self.quality_config.min_info_density}")
        
        # 3. 噪声比例检查
        noise_ratio = calculate_noise_ratio(content)
        if noise_ratio > self.quality_config.max_noise_ratio:
            reasons.append(f"噪声过多: {noise_ratio:.2f} > {self.quality_config.max_noise_ratio}")
        
        # 4. 乱码检测
        garble_ratio = 0.0
        if self.quality_config.garble_detection.enabled:
            is_garble, garble_ratio = is_garbled(
                content, 
                self.quality_config.garble_detection.max_garble_ratio
            )
            if is_garble:
                reasons.append(f"检测到乱码: {garble_ratio:.2f}")
        
        # 5. 重复比例检查
        repetition_ratio = calculate_repetition_ratio(content)
        if repetition_ratio > self.quality_config.max_repetition_ratio:
            reasons.append(f"重复过多: {repetition_ratio:.2f} > {self.quality_config.max_repetition_ratio}")
        
        # 计算综合得分
        score = self._calculate_rule_score(
            length, info_density, noise_ratio, garble_ratio, repetition_ratio
        )
        
        # 确定质量等级
        if reasons:
            if len(reasons) >= 2 or score < 0.3:
                quality = QualityLevel.REJECT
            else:
                quality = QualityLevel.LOW
        else:
            quality = QualityLevel.GOOD
        
        return ValidationResult(
            quality=quality,
            confidence=score,
            reason="; ".join(reasons) if reasons else "规则校验通过",
            length=length,
            noise_ratio=noise_ratio,
            info_density=info_density,
            garble_ratio=garble_ratio,
            repetition_ratio=repetition_ratio,
            source="rule"
        )
    
    def _calculate_rule_score(
        self,
        length: int,
        info_density: float,
        noise_ratio: float,
        garble_ratio: float,
        repetition_ratio: float
    ) -> float:
        """
        计算规则校验综合得分
        
        Args:
            各项指标
        
        Returns:
            综合得分 (0.0-1.0)
        """
        # 长度得分
        length_score = min(length / self.quality_config.min_length, 1.0)
        
        # 信息密度得分
        density_score = min(info_density / self.quality_config.min_info_density, 1.0)
        
        # 噪声得分（越低越好）
        noise_score = max(0, 1 - noise_ratio / self.quality_config.max_noise_ratio)
        
        # 乱码得分（越低越好）
        garble_score = max(0, 1 - garble_ratio / self.quality_config.garble_detection.max_garble_ratio)
        
        # 重复得分（越低越好）
        repetition_score = max(0, 1 - repetition_ratio / self.quality_config.max_repetition_ratio)
        
        # 加权平均
        weights = [0.15, 0.25, 0.25, 0.2, 0.15]
        scores = [length_score, density_score, noise_score, garble_score, repetition_score]
        
        return sum(w * s for w, s in zip(weights, scores))
    
    def _should_use_llm(self, chunk: Chunk, rule_result: ValidationResult) -> bool:
        """
        判断是否需要使用 LLM 校验
        
        Args:
            chunk: chunk 对象
            rule_result: 规则校验结果
        
        Returns:
            是否需要 LLM 校验
        """
        # LLM 未启用
        if not self.llm_config.enabled:
            return False
        
        # LLM 校验未启用
        if not self.quality_config.llm_validation.enabled:
            return False
        
        # 只对边缘 chunk 调用
        if self.quality_config.llm_validation.only_edge_chunks:
            threshold = self.quality_config.llm_validation.edge_threshold
            # 规则得分在边缘区域
            if rule_result.confidence > threshold and rule_result.quality == QualityLevel.GOOD:
                return False  # 明确好的不需要 LLM
            if rule_result.confidence < 0.2:
                return False  # 明确差的也不需要 LLM
        
        return True
    
    def _can_call_llm(self) -> bool:
        """检查是否还能调用 LLM"""
        return self._llm_call_count < self._max_llm_calls
    
    def _llm_validation(self, chunk: Chunk) -> Optional[ValidationResult]:
        """
        LLM 语义校验
        
        Args:
            chunk: 待校验的 chunk
        
        Returns:
            校验结果，失败返回 None
        """
        self._llm_call_count += 1
        
        prompt = self._build_validation_prompt(chunk.content)
        
        try:
            response = self._call_ollama(prompt)
            if response:
                return self._parse_llm_response(response)
        except Exception as e:
            self.logger.warning(f"LLM 校验失败: {e}")
        
        return None
    
    def _build_validation_prompt(self, content: str) -> str:
        """
        构建 LLM 校验提示词
        
        Args:
            content: 待校验内容
        
        Returns:
            提示词
        """
        # 截断过长内容
        max_content_length = 2000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        prompt = f"""你是一个文本质量评估专家。请评估以下文本片段的质量，判断它是否适合用于知识库检索。

评估标准：
1. 内容完整性：文本是否表达了完整的意思
2. 语义连贯性：文本是否通顺、有逻辑
3. 信息价值：文本是否包含有意义的信息
4. 噪声程度：是否包含乱码、无意义符号等

待评估文本：
---
{content}
---

请以 JSON 格式返回评估结果，格式如下：
{{"quality": "good/low/reject", "confidence": 0.0-1.0, "reason": "简要原因"}}

只返回 JSON，不要其他内容。"""
        
        return prompt
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        调用 Ollama API
        
        Args:
            prompt: 提示词
        
        Returns:
            响应文本，失败返回 None
        """
        url = f"{self.llm_config.endpoint}/api/generate"
        
        payload = {
            "model": self.llm_config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.llm_config.temperature
            }
        }
        
        for attempt in range(self.llm_config.retry_times):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.llm_config.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("response", "")
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"Ollama 请求超时 (尝试 {attempt + 1}/{self.llm_config.retry_times})")
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Ollama 请求失败: {e}")
                time.sleep(1)
        
        return None
    
    def _parse_llm_response(self, response: str) -> Optional[ValidationResult]:
        """
        解析 LLM 响应
        
        Args:
            response: LLM 响应文本
        
        Returns:
            校验结果，解析失败返回 None
        """
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                data = json.loads(json_match.group())
                
                quality_str = data.get("quality", "low").lower()
                quality_map = {
                    "good": QualityLevel.GOOD,
                    "low": QualityLevel.LOW,
                    "reject": QualityLevel.REJECT
                }
                quality = quality_map.get(quality_str, QualityLevel.LOW)
                
                return ValidationResult(
                    quality=quality,
                    confidence=float(data.get("confidence", 0.5)),
                    reason=data.get("reason", "LLM 评估"),
                    source="llm"
                )
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"解析 LLM 响应失败: {e}")
        
        return None
    
    @property
    def llm_call_count(self) -> int:
        """获取 LLM 调用次数"""
        return self._llm_call_count
    
    def reset_llm_counter(self) -> None:
        """重置 LLM 调用计数"""
        self._llm_call_count = 0
