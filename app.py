#!/usr/bin/env python3
"""
RAGSmith Streamlit UI
简单易用的 Web 界面
"""

import streamlit as st
import sys
import os
from pathlib import Path
import json
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.strategy import get_strategy_engine
from src.core.config import Config
from src.core.config_metadata import get_all_metadata, ImpactType
from src.pipeline import Pipeline

# 页面配置
st.set_page_config(
    page_title="RAGSmith - PDF RAG 数据处理",
    page_icon="🔨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .strategy-card {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 2px solid #e0e0e0;
        margin: 0.5rem 0;
    }
    .strategy-card:hover {
        border-color: #667eea;
        box-shadow: 0 4px 6px rgba(102, 126, 234, 0.1);
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# 标题
st.markdown('<h1 class="main-header">🔨 RAGSmith</h1>', unsafe_allow_html=True)
st.markdown("**产品级 PDF RAG 数据处理工具** - 策略化处理 · 多格式输出 · 质量追溯")

# 侧边栏 - 策略选择
st.sidebar.header("⚙️ 配置")

# 获取策略引擎
engine = get_strategy_engine()
strategies = engine.list_strategies()

# 策略选择
strategy_options = {s['display_name']: s['name'] for s in strategies if s['available']}
selected_strategy_display = st.sidebar.selectbox(
    "选择处理策略",
    options=list(strategy_options.keys()),
    index=1,  # 默认 Balanced
    help="选择适合你场景的处理策略"
)
selected_strategy = strategy_options[selected_strategy_display]

# 显示策略信息
strategy_info = next(s for s in strategies if s['name'] == selected_strategy)
with st.sidebar.expander("📋 策略说明", expanded=True):
    st.markdown(f"**{strategy_info['display_name']}**")
    st.write(strategy_info['description'])

# 主界面 - 分栏
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📄 PDF 文件")
    
    # 文件上传
    uploaded_file = st.file_uploader(
        "上传 PDF 文件",
        type=['pdf'],
        help="支持最大 300MB 的 PDF 文件"
    )
    
    # 或者选择已有文件
    input_dir = Path("data/input")
    if input_dir.exists():
        existing_files = list(input_dir.glob("*.pdf"))
        if existing_files:
            st.markdown("**或选择已有文件：**")
            selected_file = st.selectbox(
                "已有 PDF 文件",
                options=[""] + [f.name for f in existing_files],
                format_func=lambda x: "（选择文件）" if x == "" else x
            )
            if selected_file:
                uploaded_file = selected_file

with col2:
    st.header("🎛️ 高级选项")
    
    # LLM 开关
    enable_llm = st.checkbox(
        "启用 LLM 校验",
        value=True,
        help="使用 LLM 进行语义质量校验（需要 Ollama 服务）"
    )
    
    # Chunk 大小
    chunk_size = st.slider(
        "Chunk 大小",
        min_value=200,
        max_value=2000,
        value=800,
        step=50,
        help="每个文本块的大小（tokens）"
    )
    
    # Chunk 重叠
    chunk_overlap = st.slider(
        "Chunk 重叠",
        min_value=0,
        max_value=500,
        value=150,
        step=25,
        help="相邻 chunk 之间的重叠大小（tokens）"
    )

# 处理按钮
st.markdown("---")
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])

with col_btn1:
    process_button = st.button("🚀 开始处理", type="primary", use_container_width=True)

with col_btn2:
    dry_run_button = st.button("🔍 验证配置", use_container_width=True)

# 处理逻辑
if dry_run_button or process_button:
    if not uploaded_file:
        st.error("❌ 请先上传或选择 PDF 文件")
    else:
        # 确定文件路径
        if isinstance(uploaded_file, str):
            pdf_path = f"data/input/{uploaded_file}"
        else:
            # 保存上传的文件
            pdf_path = f"data/input/{uploaded_file.name}"
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✓ 文件已保存到 {pdf_path}")
        
        # 构建配置
        try:
            cli_overrides = {
                'pdf': {'path': pdf_path},
                'chunk': {
                    'size': chunk_size,
                    'overlap': chunk_overlap
                },
                'llm': {'enabled': enable_llm}
            }
            
            final_config_dict = engine.build_final_config(
                strategy_name=selected_strategy,
                user_config_path=Path("config/pipeline.yaml"),
                cli_overrides=cli_overrides
            )
            
            # 验证配置
            is_valid, errors = engine.validate_config(final_config_dict)
            
            if not is_valid:
                st.error("❌ 配置验证失败：")
                for error in errors:
                    st.error(f"  - {error}")
            else:
                if dry_run_button:
                    # Dry run 模式
                    st.success("✅ 配置验证通过！")
                    
                    with st.expander("📋 配置详情", expanded=True):
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("策略", strategy_info['display_name'])
                        with col_b:
                            st.metric("Chunk 大小", f"{chunk_size} tokens")
                        with col_c:
                            st.metric("LLM", "启用" if enable_llm else "禁用")
                        
                        st.json({
                            "pdf_path": pdf_path,
                            "strategy": selected_strategy,
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                            "llm_enabled": enable_llm
                        })
                
                else:
                    # 实际处理
                    st.info(f"🔨 使用 **{strategy_info['display_name']}** 策略处理中...")
                    
                    # 创建进度显示
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        # 创建配置和流水线
                        config = Config.from_dict(final_config_dict)
                        pipeline = Pipeline.from_config(config, str(Path.cwd()))
                        
                        # 运行处理
                        status_text.text("正在处理 PDF...")
                        start_time = time.time()
                        
                        stats = pipeline.run(resume=False)
                        
                        end_time = time.time()
                        duration = end_time - start_time
                        
                        progress_bar.progress(100)
                        status_text.empty()
                        
                        # 显示结果
                        st.success(f"✅ 处理完成！耗时 {duration/60:.1f} 分钟")
                        
                        # 统计信息
                        st.markdown("### 📊 处理统计")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("总页数", stats.total_pages)
                        with col2:
                            st.metric("接受的 Chunks", stats.accepted_chunks)
                        with col3:
                            st.metric("拒绝的 Chunks", stats.rejected_chunks)
                        with col4:
                            acceptance_rate = (stats.accepted_chunks / max(stats.total_chunks, 1)) * 100
                            st.metric("接受率", f"{acceptance_rate:.1f}%")
                        
                        # 输出文件（带下载按钮）
                        st.markdown("### 📁 输出文件")
                        output_dir = Path(config.output.dir)
                        
                        col_out1, col_out2 = st.columns(2)
                        
                        with col_out1:
                            st.markdown("**通用格式：**")
                            rag_ready_dir = output_dir / "rag-ready"
                            if rag_ready_dir.exists():
                                for file in sorted(rag_ready_dir.glob("*")):
                                    col_file, col_btn = st.columns([3, 1])
                                    with col_file:
                                        st.markdown(f"📄 `{file.name}` ({file.stat().st_size / 1024:.1f} KB)")
                                    with col_btn:
                                        with open(file, 'rb') as f:
                                            st.download_button(
                                                label="⬇️",
                                                data=f.read(),
                                                file_name=file.name,
                                                mime="application/octet-stream",
                                                key=f"download_rag_{file.name}"
                                            )
                        
                        with col_out2:
                            st.markdown("**平台格式：**")
                            platform_dir = output_dir / "platform"
                            if platform_dir.exists():
                                for file in sorted(platform_dir.glob("*")):
                                    col_file, col_btn = st.columns([3, 1])
                                    with col_file:
                                        st.markdown(f"📄 `{file.name}` ({file.stat().st_size / 1024:.1f} KB)")
                                    with col_btn:
                                        with open(file, 'rb') as f:
                                            st.download_button(
                                                label="⬇️",
                                                data=f.read(),
                                                file_name=file.name,
                                                mime="application/octet-stream",
                                                key=f"download_platform_{file.name}"
                                            )
                        
                        # HTML 报告（带下载和预览）
                        report_file = output_dir / "report" / "report.html"
                        if report_file.exists():
                            st.markdown("### 📈 可视化报告")
                            
                            col_report1, col_report2 = st.columns([3, 1])
                            with col_report1:
                                st.markdown(f"📊 `report.html` ({report_file.stat().st_size / 1024:.1f} KB)")
                            with col_report2:
                                with open(report_file, 'rb') as f:
                                    st.download_button(
                                        label="⬇️ 下载报告",
                                        data=f.read(),
                                        file_name="ragsmith_report.html",
                                        mime="text/html",
                                        key="download_report"
                                    )
                            
                            # 提供在线预览选项
                            if st.checkbox("📺 在线预览报告", key="preview_report"):
                                with open(report_file, 'r', encoding='utf-8') as f:
                                    st.components.v1.html(f.read(), height=800, scrolling=True)
                        
                    except Exception as e:
                        st.error(f"❌ 处理失败：{str(e)}")
                        import traceback
                        with st.expander("查看错误详情"):
                            st.code(traceback.format_exc())
        
        except Exception as e:
            st.error(f"❌ 配置构建失败：{str(e)}")
            import traceback
            with st.expander("查看错误详情"):
                st.code(traceback.format_exc())

# 底部信息
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns(3)

with col_footer1:
    st.markdown("**📚 文档**")
    st.markdown("[GitHub](https://github.com/gxdbox/ragsmith) · [README](README.md)")

with col_footer2:
    st.markdown("**⚡ 快捷命令**")
    st.code("python3 main.py --list-strategies", language="bash")

with col_footer3:
    st.markdown("**🔧 版本**")
    st.markdown("RAGSmith v2.0")

# 侧边栏底部 - 帮助信息
with st.sidebar:
    st.markdown("---")
    st.markdown("### 💡 使用提示")
    st.markdown("""
    1. **选择策略**：根据场景选择合适的处理策略
    2. **上传 PDF**：支持拖拽上传或选择已有文件
    3. **调整参数**：可选调整 chunk 大小等参数
    4. **开始处理**：点击按钮开始处理
    5. **查看报告**：处理完成后查看 HTML 报告
    """)
    
    st.markdown("### ⚠️ 注意事项")
    st.markdown("""
    - 启用 LLM 需要 Ollama 服务运行
    - 大文件处理可能需要较长时间
    - 建议先用小文件测试
    """)
