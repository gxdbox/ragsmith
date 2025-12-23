#!/usr/bin/env python3
"""
RAGSmith - 主入口

用法:
    python main.py                          # 使用默认配置（balanced 策略）
    python main.py --strategy fast          # 使用快速策略
    python main.py --strategy high_quality  # 使用高质量策略
    python main.py --pdf path/to/file.pdf   # 覆盖 PDF 路径
    python main.py --no-llm                 # 禁用 LLM 校验
    python main.py --no-resume              # 不从断点续传
"""
import argparse
import sys
from pathlib import Path


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="RAGSmith - 产品级 PDF RAG 数据处理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                                    # 使用默认 balanced 策略
  python main.py --strategy fast                    # 快速处理
  python main.py --strategy high_quality            # 高质量处理
  python main.py --pdf data/input/large.pdf --no-llm
  python main.py --list-strategies                  # 列出所有可用策略
        """
    )
    
    parser.add_argument(
        "--strategy", "-s",
        type=str,
        choices=["fast", "balanced", "high_quality", "expert"],
        help="处理策略 (默认: balanced)。fast=快速, balanced=平衡, high_quality=高质量, expert=专家模式"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config/pipeline.yaml",
        help="配置文件路径 (默认: config/pipeline.yaml)。expert 模式下必需"
    )
    
    parser.add_argument(
        "--list-strategies",
        action="store_true",
        help="列出所有可用策略并退出"
    )
    
    parser.add_argument(
        "--pdf", "-p",
        type=str,
        help="PDF 文件路径 (覆盖配置文件中的设置)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="输出目录 (覆盖配置文件中的设置)"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Chunk 大小 (tokens)"
    )
    
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        help="Chunk 重叠大小 (tokens)"
    )
    
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="禁用 LLM 语义校验"
    )
    
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="不从断点续传，重新开始处理"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证配置，不实际处理"
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 确定项目根目录
    script_dir = Path(__file__).parent.resolve()
    
    # 列出策略
    if args.list_strategies:
        from src.core.strategy import get_strategy_engine
        engine = get_strategy_engine()
        strategies = engine.list_strategies()
        
        print("\n可用策略:\n")
        for strategy in strategies:
            status = "✓" if strategy['available'] else "✗"
            print(f"  {status} {strategy['display_name']}")
            print(f"     {strategy['description']}")
            print()
        sys.exit(0)
    
    # 配置文件路径
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = script_dir / config_path
    
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}")
        sys.exit(1)
    
    # 导入流水线（延迟导入以加快启动）
    from src.pipeline import Pipeline
    from src.core.config import Config
    from src.core.strategy import get_strategy_engine
    
    # 使用策略引擎构建配置
    try:
        engine = get_strategy_engine()
        
        # 构建 CLI 覆盖
        cli_overrides = {}
        if args.pdf:
            cli_overrides['pdf'] = {'path': args.pdf}
        if args.output:
            cli_overrides['output'] = {'dir': args.output}
        if args.chunk_size:
            cli_overrides['chunk'] = cli_overrides.get('chunk', {})
            cli_overrides['chunk']['size'] = args.chunk_size
        if args.chunk_overlap:
            cli_overrides['chunk'] = cli_overrides.get('chunk', {})
            cli_overrides['chunk']['overlap'] = args.chunk_overlap
        if args.no_llm:
            cli_overrides['llm'] = {'enabled': False}
        if args.log_level:
            cli_overrides['runtime'] = {'log_level': args.log_level}
        
        # 构建最终配置
        final_config_dict = engine.build_final_config(
            strategy_name=args.strategy,
            user_config_path=config_path if config_path.exists() else None,
            cli_overrides=cli_overrides
        )
        
        # 验证配置
        is_valid, errors = engine.validate_config(final_config_dict)
        if not is_valid:
            print("配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        
        # 从字典创建 Config 对象
        config = Config.from_dict(final_config_dict)
        
    except Exception as e:
        print(f"错误: 配置构建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 验证 PDF 路径
    errors = config.validate(script_dir)
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Dry run 模式
    if args.dry_run:
        strategy_name = final_config_dict.get('metadata', {}).get('strategy', 'unknown')
        strategy_display = final_config_dict.get('metadata', {}).get('strategy_display_name', strategy_name)
        
        print("\n" + "="*60)
        print("配置验证通过!")
        print("="*60)
        print(f"\n策略: {strategy_display}")
        print(f"PDF: {config.pdf.path}")
        print(f"Chunk: {config.chunk.size} tokens, overlap {config.chunk.overlap}")
        print(f"LLM: {'启用' if config.llm.enabled else '禁用'}")
        print(f"输出: {config.output.dir}")
        print("\n" + "="*60 + "\n")
        sys.exit(0)
    
    # 创建并运行流水线（使用构建好的配置）
    pipeline = Pipeline.from_config(config, str(script_dir))
    
    try:
        # 显示处理信息
        strategy_name = final_config_dict.get('metadata', {}).get('strategy', 'unknown')
        strategy_display = final_config_dict.get('metadata', {}).get('strategy_display_name', strategy_name)
        
        print("\n" + "="*60)
        print(f"🔨 RAGSmith v2.0 - {strategy_display}")
        print("="*60 + "\n")
        
        stats = pipeline.run(resume=not args.no_resume)
        
        # 显示完成信息
        print("\n" + "="*60)
        print("✓ 处理完成!")
        print("="*60)
        print(f"\n接受的 chunks: {stats.accepted_chunks}")
        print(f"拒绝的 chunks: {stats.rejected_chunks}")
        print(f"处理时间: {stats.duration_seconds / 60:.1f} 分钟")
        print(f"\n输出目录: {config.output.dir}")
        print("  - rag-ready/    # 通用 RAG 格式")
        print("  - platform/     # 平台特定格式")
        print("  - report/       # HTML 报告")
        print("\n" + "="*60 + "\n")
        
        # 返回码
        if stats.failed_pages > 0:
            sys.exit(2)  # 部分失败
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
