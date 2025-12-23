# RAGSmith

**A production-ready, configurable pipeline that transforms large PDFs into high-quality RAG-ready chunks with dual-layer quality control.**

一套产品级、可配置的 PDF RAG 数据处理工具，支持策略化处理、多格式输出和完整的质量追溯。

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0-orange.svg)](https://github.com/gxdbox/ragsmith)

---

## ✨ V2 核心特性

### 🎯 策略化处理（新增）
- **4 种预设策略**：Fast（快速）、Balanced（平衡）、High Quality（高质量）、Expert（专家模式）
- **一键切换**：`--strategy fast` 即可切换处理策略
- **智能配置合并**：策略配置 + 用户配置 + CLI 参数，优先级自动处理

### 📦 产品化输出（新增）
- **多格式导出**：JSONL、CSV、Markdown、Schema JSON
- **平台适配**：Dify、FAISS、Milvus 专用格式
- **可视化报告**：自动生成 HTML 报告，包含统计分析和推荐参数

### 🔍 增强的质量控制
- **双层校验**：规则校验 + 可选 LLM 语义校验
- **失败可解释**：每个被拒绝的 chunk 都有明确原因
- **质量追溯**：完整的元数据和处理链路

### 🚀 核心能力
- **流式处理**：支持 300MB+ 超大 PDF，内存占用可控
- **断点续传**：中断后可从上次位置继续
- **模块化设计**：各处理阶段可插拔、可扩展
- **配置驱动**：修改配置 ≠ 修改代码

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

## 🚀 快速开始

### 1. 安装

```bash
git clone https://github.com/gxdbox/ragsmith.git
cd ragsmith
pip install -r requirements.txt
```

### 2. 准备 PDF

将 PDF 文件放入 `data/input/` 目录。

### 3. 选择策略并运行

```bash
# 使用默认策略（balanced）
python main.py --pdf data/input/your-file.pdf

# 快速处理（适合大批量）
python main.py --pdf data/input/your-file.pdf --strategy fast

# 高质量处理（适合重要文档）
python main.py --pdf data/input/your-file.pdf --strategy high_quality

# 查看所有可用策略
python main.py --list-strategies
```

### 4. 查看结果

处理完成后，在 `data/output/` 目录查看结果：

```
data/output/
├── rag-ready/          # 通用 RAG 格式
│   ├── chunks.jsonl    # JSONL 格式
│   ├── chunks.csv      # CSV 格式（Excel 友好）
│   ├── chunks.md       # Markdown 格式（人工审阅）
│   └── schema.json     # 数据 Schema
├── platform/           # 平台特定格式
│   ├── dify.jsonl      # Dify 知识库格式
│   ├── faiss_data.pkl  # FAISS 格式
│   └── milvus.json     # Milvus 格式
└── report/
    └── report.html     # 可视化报告
```

## 📋 策略说明

### Fast（快速）
- **适用场景**：大批量处理、快速原型验证
- **特点**：大 chunk（1200 tokens）、关闭 LLM、宽松质量标准
- **速度**：⚡⚡⚡ 最快
- **质量**：⭐⭐ 基础
- **成本**：💰 最低

### Balanced（平衡）- 默认推荐
- **适用场景**：80% 的通用场景
- **特点**：中等 chunk（800 tokens）、选择性 LLM、标准质量
- **速度**：⚡⚡ 适中
- **质量**：⭐⭐⭐ 良好
- **成本**：💰💰 适中

### High Quality（高质量）
- **适用场景**：重要文档、精确检索
- **特点**：小 chunk（600 tokens）、全量 LLM、严格质量
- **速度**：⚡ 较慢
- **质量**：⭐⭐⭐⭐ 优秀
- **成本**：💰💰💰 较高

### Expert（专家模式）
- **适用场景**：需要完全自定义的专业用户
- **特点**：不覆盖任何参数，完全由用户配置

---

## ⚙️ 配置说明

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

## 🔌 集成到 RAG 系统

### 方式 1：使用通用格式

```python
import json

# 读取 JSONL 格式
chunks = []
with open('data/output/rag-ready/chunks.jsonl', 'r') as f:
    for line in f:
        chunks.append(json.loads(line))

# 提取文本和元数据
texts = [c['content'] for c in chunks]
metadatas = [{'source': c['source'], 'page': c['page_start']} for c in chunks]
```

### 方式 2：使用平台特定格式

#### Dify 知识库
```bash
# 直接导入 dify.jsonl
cp data/output/platform/dify.jsonl /path/to/dify/knowledge_base/
```

#### FAISS
```python
import pickle
import faiss
from sentence_transformers import SentenceTransformer

# 加载数据
with open('data/output/platform/faiss_data.pkl', 'rb') as f:
    data = pickle.load(f)

# 向量化
model = SentenceTransformer('your-model')
embeddings = model.encode(data['texts'])

# 构建索引
index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings)
```

#### Milvus
```python
import json
from pymilvus import Collection

# 加载数据
with open('data/output/platform/milvus.json', 'r') as f:
    data = json.load(f)

# 批量插入
collection = Collection("rag_chunks")
collection.insert(data['data'])
```

## 📊 性能参考

| PDF 大小 | 页数 | 策略 | 处理时间 | Chunks 数量 |
|---------|------|------|---------|------------|
| 50MB | 200 | Fast | ~5 分钟 | ~800 |
| 50MB | 200 | Balanced | ~15 分钟 | ~1000 |
| 50MB | 200 | High Quality | ~30 分钟 | ~1200 |
| 300MB | 1000 | Fast | ~25 分钟 | ~4000 |
| 300MB | 1000 | Balanced | ~90 分钟 | ~5000 |

*测试环境：MacBook Pro M1, 16GB RAM, Ollama qwen:7b*

---

## ⚠️ 注意事项

### LLM 配置
- 启用 LLM 校验前，确保 Ollama 服务已启动：`ollama serve`
- 首次使用需下载模型：`ollama pull qwen:7b`
- 可通过 `--no-llm` 关闭 LLM 校验以加快处理

### 内存管理
- 流式处理设计，内存占用通常 < 2GB
- 如遇内存问题，可减小 `runtime.batch_size`

### 断点续传
- 处理中断后，再次运行会自动继续
- 使用 `--no-resume` 强制重新开始

---

## 🛠️ 高级用法

### 自定义配置（Expert 模式）

```bash
# 使用自定义配置文件
python main.py --strategy expert --config my-config.yaml
```

### CLI 参数覆盖

```bash
# 覆盖 chunk 大小
python main.py --strategy balanced --chunk-size 1000 --chunk-overlap 200

# 覆盖输出目录
python main.py --pdf input.pdf --output custom-output/
```

### Dry Run（验证配置）

```bash
python main.py --strategy balanced --pdf input.pdf --dry-run
```

---

## 🏗️ 架构设计

RAGSmith 采用模块化、可扩展的架构设计，适合二次开发：

```
src/
├── core/                   # 核心模块
│   ├── config.py          # 配置管理
│   ├── strategy.py        # 策略引擎（V2 新增）
│   ├── config_metadata.py # 配置元数据（V2 新增）
│   ├── models.py          # 数据模型
│   └── utils.py           # 工具函数
├── stages/                # 处理阶段
│   ├── input_loader.py    # 输入层
│   ├── parser.py          # 解析层
│   ├── normalizer.py      # 规范化层
│   ├── chunker.py         # 切片层
│   ├── validator.py       # 校验层
│   ├── output_writer.py   # 输出层
│   ├── output_exporter.py # 多格式导出（V2 新增）
│   └── report_generator.py# 报告生成（V2 新增）
└── pipeline.py            # 流水线编排
```

### 扩展示例

#### 添加新的输出格式

```python
# src/stages/output_exporter.py

def export_custom_format(self, chunks: List[Chunk]):
    """导出自定义格式"""
    output_file = self.platform_dir / "custom.json"
    # 实现你的格式转换逻辑
    ...
```

#### 添加新的处理策略

```yaml
# presets/my_strategy.yaml
strategy:
  name: "my_strategy"
  display_name: "My Custom Strategy"
  description: "我的自定义策略"

chunk:
  size: 900
  overlap: 180
  # ... 其他配置
```

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

---

## 📝 更新日志

### v2.0.0 (2024-12-23)
- ✨ 新增策略化处理机制（Fast/Balanced/High Quality/Expert）
- ✨ 新增多格式输出（CSV、Markdown、平台特定格式）
- ✨ 新增 HTML 可视化报告
- ✨ 新增配置元数据系统（为 UI 化做准备）
- 🔧 增强失败可解释性
- 🔧 优化 CLI 体验
- 📚 更新为产品级文档

### v1.0.0 (2024-12-20)
- 🎉 初始版本发布
- 支持 PDF 流式处理
- 双层质量控制
- 断点续传

---

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF 解析
- [Ollama](https://ollama.ai/) - 本地 LLM 服务
- 所有贡献者和使用者

---

## 📮 联系方式

- GitHub Issues: [https://github.com/gxdbox/ragsmith/issues](https://github.com/gxdbox/ragsmith/issues)
- Email: [your-email@example.com](mailto:your-email@example.com)

---

<div align="center">
  <strong>⭐ 如果这个项目对你有帮助，请给个 Star！</strong>
</div>

## License

MIT
