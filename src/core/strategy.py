"""
Strategy Engine - 策略加载、合并、校验模块
负责处理预设策略与用户配置的合并逻辑
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from copy import deepcopy


class StrategyEngine:
    """
    策略引擎
    负责加载预设策略、合并用户配置、生成最终运行配置
    """
    
    AVAILABLE_STRATEGIES = ["fast", "balanced", "high_quality", "expert"]
    DEFAULT_STRATEGY = "balanced"
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        初始化策略引擎
        
        Args:
            project_root: 项目根目录，如果为 None 则自动推断
        """
        if project_root is None:
            # 自动推断项目根目录（从当前文件向上查找）
            current_file = Path(__file__).resolve()
            self.project_root = current_file.parent.parent.parent
        else:
            self.project_root = Path(project_root)
        
        self.presets_dir = self.project_root / "presets"
        self.config_dir = self.project_root / "config"
        
    def load_strategy(self, strategy_name: Optional[str] = None) -> Dict[str, Any]:
        """
        加载指定策略的配置
        
        Args:
            strategy_name: 策略名称，如果为 None 则使用默认策略
            
        Returns:
            策略配置字典
            
        Raises:
            ValueError: 策略名称不合法
            FileNotFoundError: 策略文件不存在
        """
        if strategy_name is None:
            strategy_name = self.DEFAULT_STRATEGY
        
        if strategy_name not in self.AVAILABLE_STRATEGIES:
            raise ValueError(
                f"Invalid strategy: {strategy_name}. "
                f"Available strategies: {', '.join(self.AVAILABLE_STRATEGIES)}"
            )
        
        preset_file = self.presets_dir / f"{strategy_name}.yaml"
        
        if not preset_file.exists():
            raise FileNotFoundError(f"Strategy file not found: {preset_file}")
        
        with open(preset_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config if config else {}
    
    def load_user_config(self, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        加载用户自定义配置
        
        Args:
            config_path: 配置文件路径，如果为 None 则使用默认路径
            
        Returns:
            用户配置字典
        """
        if config_path is None:
            config_path = self.config_dir / "pipeline.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config if config else {}
    
    def merge_configs(
        self,
        strategy_config: Dict[str, Any],
        user_config: Dict[str, Any],
        strategy_name: str
    ) -> Dict[str, Any]:
        """
        合并策略配置和用户配置
        
        优先级：用户配置 > 策略配置
        特殊处理：expert 策略不覆盖任何用户配置
        
        Args:
            strategy_config: 策略配置
            user_config: 用户配置
            strategy_name: 策略名称
            
        Returns:
            合并后的配置
        """
        if strategy_name == "expert":
            # expert 模式：完全使用用户配置
            return deepcopy(user_config)
        
        # 深拷贝策略配置作为基础
        merged = deepcopy(strategy_config)
        
        # 递归合并用户配置
        self._deep_merge(merged, user_config)
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """
        深度合并两个字典（原地修改 base）
        
        Args:
            base: 基础字典（会被修改）
            override: 覆盖字典
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                # 递归合并嵌套字典
                self._deep_merge(base[key], value)
            else:
                # 直接覆盖
                base[key] = deepcopy(value)
    
    def build_final_config(
        self,
        strategy_name: Optional[str] = None,
        user_config_path: Optional[Path] = None,
        cli_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        构建最终运行配置
        
        优先级：CLI 参数 > 用户配置 > 策略配置
        
        Args:
            strategy_name: 策略名称
            user_config_path: 用户配置文件路径
            cli_overrides: 命令行参数覆盖
            
        Returns:
            最终配置字典
        """
        # 1. 加载策略配置
        strategy_name = strategy_name or self.DEFAULT_STRATEGY
        strategy_config = self.load_strategy(strategy_name)
        
        # 2. 加载用户配置
        user_config = self.load_user_config(user_config_path)
        
        # 3. 合并策略和用户配置
        final_config = self.merge_configs(strategy_config, user_config, strategy_name)
        
        # 4. 应用 CLI 覆盖
        if cli_overrides:
            self._deep_merge(final_config, cli_overrides)
        
        # 5. 添加元信息
        if 'metadata' not in final_config:
            final_config['metadata'] = {}
        
        final_config['metadata']['strategy'] = strategy_name
        final_config['metadata']['strategy_display_name'] = strategy_config.get(
            'strategy', {}
        ).get('display_name', strategy_name)
        
        return final_config
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        校验配置的合法性
        
        Args:
            config: 待校验的配置
            
        Returns:
            (是否合法, 错误信息列表)
        """
        errors = []
        
        # 检查必需的顶层键
        required_keys = ['pdf', 'chunk', 'quality', 'output']
        for key in required_keys:
            if key not in config:
                errors.append(f"Missing required config section: {key}")
        
        # 检查 chunk 配置
        if 'chunk' in config:
            chunk = config['chunk']
            if chunk.get('size', 0) <= 0:
                errors.append("chunk.size must be positive")
            if chunk.get('overlap', 0) < 0:
                errors.append("chunk.overlap must be non-negative")
            if chunk.get('overlap', 0) >= chunk.get('size', 1):
                errors.append("chunk.overlap must be less than chunk.size")
        
        # 检查 quality 配置
        if 'quality' in config:
            quality = config['quality']
            if quality.get('min_length', 0) < 0:
                errors.append("quality.min_length must be non-negative")
            if not 0 <= quality.get('max_noise_ratio', 0.5) <= 1:
                errors.append("quality.max_noise_ratio must be between 0 and 1")
        
        # 检查 LLM 配置
        if 'llm' in config and config['llm'].get('enabled'):
            llm = config['llm']
            if not llm.get('endpoint'):
                errors.append("llm.endpoint is required when LLM is enabled")
            if not llm.get('model'):
                errors.append("llm.model is required when LLM is enabled")
        
        return len(errors) == 0, errors
    
    def get_strategy_info(self, strategy_name: str) -> Dict[str, Any]:
        """
        获取策略的详细信息（用于 UI 展示）
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            策略信息字典
        """
        try:
            config = self.load_strategy(strategy_name)
            strategy_info = config.get('strategy', {})
            
            return {
                'name': strategy_name,
                'display_name': strategy_info.get('display_name', strategy_name),
                'description': strategy_info.get('description', ''),
                'available': True
            }
        except Exception as e:
            return {
                'name': strategy_name,
                'display_name': strategy_name,
                'description': '',
                'available': False,
                'error': str(e)
            }
    
    def list_strategies(self) -> list[Dict[str, Any]]:
        """
        列出所有可用策略
        
        Returns:
            策略信息列表
        """
        return [self.get_strategy_info(name) for name in self.AVAILABLE_STRATEGIES]


def get_strategy_engine() -> StrategyEngine:
    """
    获取策略引擎单例
    
    Returns:
        StrategyEngine 实例
    """
    return StrategyEngine()
