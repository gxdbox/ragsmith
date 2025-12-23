#!/usr/bin/env python3
"""
知识图谱抽取工具
从 chunks.jsonl 中抽取实体和关系，构建知识图谱

用法:
    python scripts/extract_knowledge_graph.py
    python scripts/extract_knowledge_graph.py --input data/output/chunks.jsonl --output data/output/knowledge_graph.json
"""
import json
import argparse
import time
import os
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

# 绕过代理访问本地服务
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'


# 抽取 Prompt 模板
EXTRACTION_PROMPT = '''从以下教材文本中抽取软件架构领域的实体和关系。

实体类型: Method, Model, ArchitectureView, DesignStage, QualityAttribute, Concept
关系类型: includes, consists_of, applies_to, affects, defines, compares_with, belongs_to, supports

规则:
1. 只抽取架构相关的核心知识
2. 不确定就不要输出
3. 如果没有可抽取内容，返回空数组

直接输出JSON，不要任何解释:
{"entities":[{"name":"名称","type":"类型","description":"描述"}],"relations":[{"source":"源","relation":"关系","target":"目标","confidence":0.9}]}

文本:
{{CHUNK_TEXT}}

JSON:'''


class KnowledgeGraphExtractor:
    """知识图谱抽取器"""
    
    def __init__(
        self,
        llm_endpoint: str = "http://localhost:11434",
        llm_model: str = "qwen:7b",
        use_ollama: bool = True
    ):
        self.llm_endpoint = llm_endpoint
        self.llm_model = llm_model
        self.use_ollama = use_ollama
        
        # 存储抽取结果
        self.all_entities: Dict[str, Dict] = {}  # name -> entity
        self.all_relations: List[Dict] = []
        
    def extract_from_chunk(self, chunk_text: str, chunk_id: str = "", debug: bool = False) -> Optional[Dict]:
        """从单个 chunk 抽取实体和关系"""
        prompt = EXTRACTION_PROMPT.replace("{{CHUNK_TEXT}}", chunk_text)
        
        try:
            if self.use_ollama:
                response = self._call_ollama(prompt)
            else:
                response = self._call_openai_compatible(prompt)
            
            if debug:
                print(f"  [DEBUG] LLM 响应: {response[:500] if response else 'None'}...")
            
            if response:
                # 解析 JSON
                result = self._parse_json_response(response)
                if result:
                    result['source_chunk'] = chunk_id
                    return result
                elif debug:
                    print(f"  [DEBUG] JSON 解析失败")
        except Exception as e:
            print(f"  抽取失败 [{chunk_id}]: {e}")
        
        return None
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """调用 Ollama API"""
        url = f"{self.llm_endpoint}/api/generate"
        payload = {
            "model": self.llm_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2000
            }
        }
        
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json().get("response", "")
        return None
    
    def _call_openai_compatible(self, prompt: str) -> Optional[str]:
        """调用 OpenAI 兼容 API"""
        url = f"{self.llm_endpoint}/v1/chat/completions"
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return None
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON"""
        # 尝试直接解析
        try:
            return json.loads(response)
        except:
            pass
        
        # 尝试提取 JSON 块
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        return None
    
    def merge_results(self, result: Dict):
        """合并抽取结果，去重"""
        if not result:
            return
        
        # 合并实体
        for entity in result.get("entities", []):
            name = entity.get("name", "").strip()
            if name and name not in self.all_entities:
                self.all_entities[name] = entity
        
        # 合并关系（简单去重）
        for relation in result.get("relations", []):
            # 检查是否已存在相同关系
            exists = any(
                r["source"] == relation.get("source") and
                r["relation"] == relation.get("relation") and
                r["target"] == relation.get("target")
                for r in self.all_relations
            )
            if not exists and relation.get("source") and relation.get("target"):
                self.all_relations.append(relation)
    
    def get_merged_graph(self) -> Dict:
        """获取合并后的知识图谱"""
        return {
            "entities": list(self.all_entities.values()),
            "relations": self.all_relations,
            "statistics": {
                "entity_count": len(self.all_entities),
                "relation_count": len(self.all_relations),
                "entity_types": self._count_by_type(self.all_entities.values(), "type"),
                "relation_types": self._count_by_type(self.all_relations, "relation")
            }
        }
    
    def _count_by_type(self, items, key: str) -> Dict[str, int]:
        """按类型统计"""
        counts = {}
        for item in items:
            t = item.get(key, "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts


def load_chunks(input_path: str) -> List[Dict]:
    """加载 chunks"""
    chunks = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def main():
    parser = argparse.ArgumentParser(description="从 chunks 中抽取知识图谱")
    parser.add_argument("--input", "-i", default="data/output/chunks.jsonl", help="输入文件")
    parser.add_argument("--output", "-o", default="data/output/knowledge_graph.json", help="输出文件")
    parser.add_argument("--endpoint", default="http://localhost:11434", help="LLM API 端点")
    parser.add_argument("--model", default="qwen:7b", help="LLM 模型")
    parser.add_argument("--limit", type=int, default=0, help="限制处理数量（0=全部）")
    parser.add_argument("--skip", type=int, default=0, help="跳过前 N 个")
    
    args = parser.parse_args()
    
    # 处理路径
    script_dir = Path(__file__).parent.parent
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.is_absolute():
        input_path = script_dir / input_path
    if not output_path.is_absolute():
        output_path = script_dir / output_path
    
    # 加载 chunks
    print(f"加载 chunks: {input_path}")
    chunks = load_chunks(str(input_path))
    print(f"共 {len(chunks)} 个 chunks")
    
    # 应用 skip 和 limit
    if args.skip > 0:
        chunks = chunks[args.skip:]
    if args.limit > 0:
        chunks = chunks[:args.limit]
    
    print(f"将处理 {len(chunks)} 个 chunks")
    
    # 初始化抽取器
    extractor = KnowledgeGraphExtractor(
        llm_endpoint=args.endpoint,
        llm_model=args.model
    )
    
    # 逐个抽取
    for i, chunk in enumerate(chunks):
        chunk_id = chunk.get("chunk_id", f"chunk_{i}")
        content = chunk.get("content", "")
        
        if len(content) < 100:  # 跳过太短的
            continue
        
        print(f"[{i+1}/{len(chunks)}] 处理 {chunk_id}...")
        
        result = extractor.extract_from_chunk(content, chunk_id, debug=(i < 2))
        if result:
            entities = result.get("entities", [])
            relations = result.get("relations", [])
            print(f"  → 抽取到 {len(entities)} 个实体, {len(relations)} 个关系")
            extractor.merge_results(result)
        
        # 避免请求过快
        time.sleep(0.5)
    
    # 保存结果
    graph = extractor.get_merged_graph()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"知识图谱抽取完成!")
    print(f"{'='*50}")
    print(f"实体数量: {graph['statistics']['entity_count']}")
    print(f"关系数量: {graph['statistics']['relation_count']}")
    print(f"实体类型分布: {graph['statistics']['entity_types']}")
    print(f"关系类型分布: {graph['statistics']['relation_types']}")
    print(f"输出文件: {output_path}")


if __name__ == "__main__":
    main()
