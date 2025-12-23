#!/usr/bin/env python3
"""
PDF RAG 预处理流水线 - 主入口

用法:
    python main.py                          # 使用默认配置
    python main.py --config path/to/config.yaml
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
        description="PDF RAG 预处理流水线 - 将超大 PDF 转换为高质量 RAG 数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py
  python main.py --config config/pipeline.yaml
  python main.py --pdf data/input/large.pdf --no-llm
  python main.py --chunk-size 1000 --chunk-overlap 200
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config/pipeline.yaml",
        help="配置文件路径 (默认: config/pipeline.yaml)"
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
    
    # 加载配置
    try:
        config = Config(str(config_path))
    except Exception as e:
        print(f"错误: 加载配置失败: {e}")
        sys.exit(1)
    
    # 应用命令行覆盖
    if args.pdf:
        config.pdf.path = args.pdf
    
    if args.output:
        config.output.dir = args.output
    
    if args.chunk_size:
        config.chunk.size = args.chunk_size
    
    if args.chunk_overlap:
        config.chunk.overlap = args.chunk_overlap
    
    if args.no_llm:
        config.llm.enabled = False
    
    if args.log_level:
        config.runtime.log_level = args.log_level
    
    # 验证配置
    errors = config.validate(script_dir)
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Dry run 模式
    if args.dry_run:
        print("配置验证通过!")
        print(f"  PDF: {config.pdf.path}")
        print(f"  Chunk: {config.chunk.size} tokens, overlap {config.chunk.overlap}")
        print(f"  LLM: {'启用' if config.llm.enabled else '禁用'}")
        print(f"  输出: {config.output.dir}")
        sys.exit(0)
    
    # 创建并运行流水线
    pipeline = Pipeline(str(config_path), str(script_dir))
    
    # 应用覆盖（需要重新应用，因为 Pipeline 会重新加载配置）
    if args.pdf:
        pipeline.config.pdf.path = args.pdf
    if args.output:
        pipeline.config.output.dir = args.output
    if args.chunk_size:
        pipeline.config.chunk.size = args.chunk_size
    if args.chunk_overlap:
        pipeline.config.chunk.overlap = args.chunk_overlap
    if args.no_llm:
        pipeline.config.llm.enabled = False
    if args.log_level:
        pipeline.config.runtime.log_level = args.log_level
    
    try:
        stats = pipeline.run(resume=not args.no_resume)
        
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
