# RAGSmith

A configurable, production-ready pipeline that transforms large PDFs into high-quality RAG-ready chunks with dual-layer quality control.

一套可配置、可扩展的自动化预处理流水线，用于将超大 PDF（~300MB）转换为高质量、可控、可追溯的 RAG 数据原料。

## 特性

- **流式处理**：逐页读取，不一次性加载全文件，支持超大 PDF
- **可配置**：通过 YAML 配置文件控制所有行为，修改配置 ≠ 修改代码
- **可扩展**：模块化设计，各处理阶段可插拔
- **断点续传**：支持中断后从上次位置继续处理
- **双层质量控制**：规则校验 + LLM 语义校验
- **完整追溯**：保留原始页码、块 ID 等元数据

## 目录结构

```
ragsmith/
├── config/
│   └── pipeline.yaml      # 配置文件
├── data/
│   ├── input/             # 输入 PDF 文件
│   └── output/            # 输出结果
│       ├── pages.jsonl    # 逐页解析结果
│       ├── chunks.jsonl   # 可向量化的 chunks
│       ├── rejected.jsonl # 被过滤的内容
│       └── stats.json     # 处理统计
├── src/
│   ├── core/              # 核心模块
│   │   ├── config.py      # 配置管理
│   │   ├── models.py      # 数据模型
│   │   └── utils.py       # 工具函数
│   ├── stages/            # 处理阶段
│   │   ├── input_loader.py    # 输入层
│   │   ├── parser.py          # 解析层
│   │   ├── normalizer.py      # 规范化层
│   │   ├── chunker.py         # 切片层
│   │   ├── validator.py       # 校验层
│   │   └── output_writer.py   # 输出层
│   └── pipeline.py        # 流水线编排
├── main.py                # 主入口
├── requirements.txt       # 依赖
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd ragsmith
pip install -r requirements.txt
```

### 2. 准备 PDF 文件

将 PDF 文件放入 `data/input/` 目录，并修改 `config/pipeline.yaml` 中的路径：

```yaml
pdf:
  path: "data/input/your-file.pdf"
```

### 3. 运行流水线

```bash
# 使用默认配置
python main.py

# 指定 PDF 文件
python main.py --pdf data/input/large.pdf

# 禁用 LLM 校验（更快）
python main.py --no-llm

# 查看帮助
python main.py --help
```

## 配置说明

### 主要配置项

```yaml
# PDF 输入
pdf:
  path: "data/input/sample.pdf"
  start_page: 0      # 起始页（用于断点续传）
  end_page: null     # 结束页，null 表示处理到最后

# 切片配置
chunk:
  size: 800          # chunk 大小（tokens）
  overlap: 150       # 重叠大小（tokens）
  min_chunk_size: 100

# 质量校验
quality:
  min_length: 200    # 最小长度
  max_noise_ratio: 0.3
  llm_validation:
    enabled: true    # 是否启用 LLM 校验
    only_edge_chunks: true  # 只对边缘 chunk 调用

# LLM 配置
llm:
  enabled: true
  provider: "ollama"
  model: "qwen:7b"
  endpoint: "http://localhost:11434"
  max_calls: 500     # 最大调用次数
```

### 关闭 LLM 校验

如果不需要 LLM 校验，或 Ollama 未运行，可以关闭：

```yaml
llm:
  enabled: false
```

或使用命令行参数：

```bash
python main.py --no-llm
```

## 输出格式

### chunks.jsonl

每行一个 JSON 对象，可直接用于向量化：

```json
{
  "chunk_id": "chunk_0001_0003_0001_a1b2c3d4",
  "content": "文本内容...",
  "source": "sample.pdf",
  "page_start": 1,
  "page_end": 3,
  "token_count": 756,
  "char_count": 1200,
  "rule_score": 0.85,
  "llm_quality": "good",
  "llm_confidence": 0.92,
  "metadata": {}
}
```

### pages.jsonl

逐页解析结果，用于回放和调试：

```json
{
  "page": 1,
  "type": "text",
  "content": "页面文本...",
  "confidence": 1.0,
  "bbox": [0, 0, 595, 842],
  "block_id": "block_0001_0001"
}
```

### stats.json

处理统计信息：

```json
{
  "source_file": "sample.pdf",
  "total_pages": 500,
  "processed_pages": 500,
  "total_chunks": 1200,
  "accepted_chunks": 1150,
  "rejected_chunks": 50,
  "llm_calls": 120,
  "duration_seconds": 1800
}
```

## 流水线架构

```
┌─────────────┐
│  Input      │  流式读取 PDF
│  Loader     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Parser     │  提取文本、表格、图片
│             │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Normalizer  │  清洗、规范化
│             │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Chunker    │  切分为 chunks
│             │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Validator   │  规则校验 + LLM 校验
│             │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Output     │  写入 JSONL 文件
│  Writer     │
└─────────────┘
```

## 断点续传

流水线支持断点续传。如果处理中断：

1. 检查点会自动保存到 `data/output/checkpoint.json`
2. 再次运行时会自动从上次位置继续
3. 使用 `--no-resume` 强制重新开始

## 后续使用

生成的 `chunks.jsonl` 可用于：

1. **Dify 知识库**：直接导入
2. **FAISS**：加载后向量化
3. **Milvus**：批量插入
4. **PGVector**：导入 PostgreSQL

## 注意事项

- 超大 PDF（300MB+）可能需要 30-90 分钟处理
- 建议先用小文件测试配置
- LLM 校验会增加处理时间，可按需关闭
- 确保 Ollama 服务已启动（如启用 LLM）

## License

MIT
