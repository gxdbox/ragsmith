#!/usr/bin/env python3
"""
将 chunks.jsonl 导出为 rag-streamlit-cn 可用的格式

用法:
    python scripts/export_for_streamlit.py
    python scripts/export_for_streamlit.py --output ../rag-streamlit-cn/imported_chunks.json
"""
import json
import argparse
from pathlib import Path


def export_chunks(input_path: str, output_path: str):
    """
    将 chunks.jsonl 转换为纯文本列表 JSON
    
    Args:
        input_path: chunks.jsonl 路径
        output_path: 输出 JSON 路径
    """
    chunks = []
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                # 提取文本内容，可选择添加元数据
                content = data.get('content', '')
                
                # 可选：添加来源信息作为前缀
                # source = data.get('source', '')
                # page_start = data.get('page_start', 0)
                # page_end = data.get('page_end', 0)
                # content = f"[来源: {source}, 页码: {page_start}-{page_end}]\n{content}"
                
                if content:
                    chunks.append(content)
    
    # 保存为 JSON 列表
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    print(f"导出完成: {len(chunks)} 个 chunks")
    print(f"输出文件: {output_path}")
    
    return chunks


def main():
    parser = argparse.ArgumentParser(description="导出 chunks 为 Streamlit RAG 格式")
    parser.add_argument(
        "--input", "-i",
        default="data/output/chunks.jsonl",
        help="输入文件路径"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/output/chunks_for_streamlit.json",
        help="输出文件路径"
    )
    
    args = parser.parse_args()
    
    # 处理相对路径
    script_dir = Path(__file__).parent.parent
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.is_absolute():
        input_path = script_dir / input_path
    if not output_path.is_absolute():
        output_path = script_dir / output_path
    
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}")
        return
    
    export_chunks(str(input_path), str(output_path))


if __name__ == "__main__":
    main()
