"""
产品化输出导出器
支持多种格式和平台的输出
"""

import json
import csv
import pickle
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from ..core.models import Chunk


class OutputExporter:
    """
    输出导出器
    支持多种格式：JSONL, CSV, Markdown, 以及平台特定格式
    """
    
    def __init__(self, output_dir: Path):
        """
        初始化导出器
        
        Args:
            output_dir: 输出根目录
        """
        self.output_dir = Path(output_dir)
        self.rag_ready_dir = self.output_dir / "rag-ready"
        self.platform_dir = self.output_dir / "platform"
        self.report_dir = self.output_dir / "report"
        
        # 创建目录结构
        self.rag_ready_dir.mkdir(parents=True, exist_ok=True)
        self.platform_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def export_all(self, chunks: List[Chunk], metadata: Dict[str, Any] = None):
        """
        导出所有格式
        
        Args:
            chunks: chunk 列表
            metadata: 元数据信息
        """
        # RAG-ready 格式
        self.export_jsonl(chunks)
        self.export_csv(chunks)
        self.export_markdown(chunks)
        self.export_schema()
        
        # 平台特定格式
        self.export_dify(chunks)
        self.export_faiss_format(chunks)
        self.export_milvus(chunks)
        
    def export_jsonl(self, chunks: List[Chunk]):
        """导出 JSONL 格式（通用 RAG 格式）"""
        output_file = self.rag_ready_dir / "chunks.jsonl"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + '\n')
    
    def export_csv(self, chunks: List[Chunk]):
        """导出 CSV 格式（便于 Excel 查看）"""
        output_file = self.rag_ready_dir / "chunks.csv"
        
        if not chunks:
            return
        
        fieldnames = [
            'chunk_id', 'content', 'source', 'page_start', 'page_end',
            'token_count', 'char_count', 'rule_score', 'llm_quality', 'llm_confidence'
        ]
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for chunk in chunks:
                row = {
                    'chunk_id': chunk.chunk_id,
                    'content': chunk.content[:200] + '...' if len(chunk.content) > 200 else chunk.content,
                    'source': chunk.source,
                    'page_start': chunk.page_start,
                    'page_end': chunk.page_end,
                    'token_count': chunk.token_count,
                    'char_count': chunk.char_count,
                    'rule_score': f"{chunk.rule_score:.3f}" if chunk.rule_score else '',
                    'llm_quality': chunk.llm_quality.value if chunk.llm_quality else '',
                    'llm_confidence': f"{chunk.llm_confidence:.3f}" if chunk.llm_confidence else ''
                }
                writer.writerow(row)
    
    def export_markdown(self, chunks: List[Chunk]):
        """导出 Markdown 格式（便于人工审阅）"""
        output_file = self.rag_ready_dir / "chunks.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# RAG Chunks Export\n\n")
            f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total chunks: {len(chunks)}\n\n")
            f.write("---\n\n")
            
            for i, chunk in enumerate(chunks, 1):
                f.write(f"## Chunk {i}: {chunk.chunk_id}\n\n")
                f.write(f"**Source:** {chunk.source} (Pages {chunk.page_start}-{chunk.page_end})\n\n")
                f.write(f"**Stats:** {chunk.token_count} tokens, {chunk.char_count} chars\n\n")
                
                if chunk.rule_score:
                    f.write(f"**Rule Score:** {chunk.rule_score:.3f}\n\n")
                
                if chunk.llm_quality:
                    f.write(f"**LLM Quality:** {chunk.llm_quality.value}")
                    if chunk.llm_confidence:
                        f.write(f" (confidence: {chunk.llm_confidence:.3f})")
                    f.write("\n\n")
                
                f.write("**Content:**\n\n")
                f.write(f"{chunk.content}\n\n")
                f.write("---\n\n")
    
    def export_schema(self):
        """导出数据 schema（用于文档和验证）"""
        schema = {
            "version": "2.0",
            "description": "RAGSmith chunk output schema",
            "fields": {
                "chunk_id": {
                    "type": "string",
                    "description": "Unique chunk identifier",
                    "example": "chunk_0001_0003_0001_a1b2c3d4"
                },
                "content": {
                    "type": "string",
                    "description": "Chunk text content"
                },
                "source": {
                    "type": "string",
                    "description": "Source file name"
                },
                "page_start": {
                    "type": "integer",
                    "description": "Starting page number (1-indexed)"
                },
                "page_end": {
                    "type": "integer",
                    "description": "Ending page number (1-indexed)"
                },
                "token_count": {
                    "type": "integer",
                    "description": "Estimated token count"
                },
                "char_count": {
                    "type": "integer",
                    "description": "Character count"
                },
                "rule_score": {
                    "type": "float",
                    "description": "Rule-based quality score (0-1)",
                    "nullable": True
                },
                "llm_quality": {
                    "type": "string",
                    "enum": ["excellent", "good", "acceptable", "poor"],
                    "description": "LLM quality assessment",
                    "nullable": True
                },
                "llm_confidence": {
                    "type": "float",
                    "description": "LLM confidence score (0-1)",
                    "nullable": True
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            }
        }
        
        output_file = self.rag_ready_dir / "schema.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
    
    def export_dify(self, chunks: List[Chunk]):
        """导出 Dify 知识库格式"""
        output_file = self.platform_dir / "dify.jsonl"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                dify_format = {
                    "content": chunk.content,
                    "meta": {
                        "source": chunk.source,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "chunk_id": chunk.chunk_id,
                        "token_count": chunk.token_count
                    }
                }
                f.write(json.dumps(dify_format, ensure_ascii=False) + '\n')
    
    def export_faiss_format(self, chunks: List[Chunk]):
        """导出 FAISS 兼容格式（文本 + 元数据）"""
        output_file = self.platform_dir / "faiss_data.pkl"
        
        data = {
            "texts": [chunk.content for chunk in chunks],
            "metadatas": [
                {
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "token_count": chunk.token_count
                }
                for chunk in chunks
            ]
        }
        
        with open(output_file, 'wb') as f:
            pickle.dump(data, f)
    
    def export_milvus(self, chunks: List[Chunk]):
        """导出 Milvus 兼容格式"""
        output_file = self.platform_dir / "milvus.json"
        
        milvus_data = {
            "collection_name": "rag_chunks",
            "data": [
                {
                    "id": chunk.chunk_id,
                    "text": chunk.content,
                    "source": chunk.source,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "token_count": chunk.token_count,
                    "char_count": chunk.char_count
                }
                for chunk in chunks
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(milvus_data, f, indent=2, ensure_ascii=False)
