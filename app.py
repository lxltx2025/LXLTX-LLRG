"""
主程序入口（v2.2 修复版）
修复按钮显示逻辑和参考文献限制
"""
import os
import uuid
import hashlib
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from config import Config
from utils.ollama_client import ollama_client
from utils.pdf_processor import doc_processor
from utils.prompt_manager import prompt_manager
from utils.export_handler import export_handler

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# 初始化SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 初始化目录
Config.init_folders()


class LiteraturePool:
    """
    用户上传文献池管理
    严格控制参考文献来源
    """
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.files = {}  # {file_id: file_info}
        self.processed = {}  # {file_id: processed_data}
        self.citation_list = []  # 引用列表
        self.content_hashes = set()  # 内容哈希，用于去重验证
        self.is_processing = False
        self.is_processed = False
        self.processing_error = None
    
    def add_file(self, file_id: str, file_info: dict, content_hash: str = None):
        """添加文件到文献池"""
        self.files[file_id] = file_info
        if content_hash:
            self.content_hashes.add(content_hash)
        # 添加新文件后重置处理状态
        self.is_processed = False
        self.processing_error = None
    
    def remove_file(self, file_id: str):
        """从文献池移除文件"""
        if file_id in self.files:
            del self.files[file_id]
        if file_id in self.processed:
            del self.processed[file_id]
        # 重建引用列表
        self._rebuild_citation_list()
        # 移除文件后重置处理状态
        if len(self.files) == 0:
            self.is_processed = False
    
    def _rebuild_citation_list(self):
        """重建引用列表"""
        self.citation_list = []
        for i, (file_id, data) in enumerate(self.processed.items(), 1):
            citation_info = data.get('citation_info', {})
            self.citation_list.append({
                "index": i,
                "id": file_id,
                "title": citation_info.get('title', data.get('filename', '')),
                "authors": citation_info.get('authors', '未知作者'),
                "year": citation_info.get('year', 'n.d.'),
                "filename": data.get('filename', ''),
                "abstract": citation_info.get('abstract', '')[:300],
                "content_hash": data.get('content_hash', ''),
            })
    
    def set_processed(self, file_id: str, data: dict):
        """设置文件的处理结果"""
        self.processed[file_id] = data
        self._rebuild_citation_list()
    
    def validate_citation(self, citation_index: int) -> bool:
        """验证引用索引是否在合法范围内"""
        return 1 <= citation_index <= len(self.citation_list)
    
    def get_valid_citation_range(self) -> tuple:
        """获取有效的引用范围"""
        return (1, len(self.citation_list))
    
    def get_citation_by_index(self, index: int) -> dict:
        """根据索引获取引用信息"""
        if self.validate_citation(index):
            return self.citation_list[index - 1]
        return None
    
    def get_all_file_ids(self) -> set:
        """获取所有文件ID"""
        return set(self.files.keys())
    
    def get_status(self) -> dict:
        """获取文献池状态"""
        return {
            "file_count": len(self.files),
            "processed_count": len(self.processed),
            "citation_count": len(self.citation_list),
            "is_processing": self.is_processing,
            "is_processed": self.is_processed,
            "has_error": self.processing_error is not None,
            "error_message": self.processing_error,
            "can_generate": len(self.citation_list) > 0 and self.is_processed and not self.is_processing,
        }


class AppState:
    """应用全局状态"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.current_step = 1
        self.completed_steps = set()
        self.current_paradigm = ""
        self.current_framework = {}
        self.review_content = {}
        self.review_files = {}  # 综述分析用的文件
        self.conversation_history = []
        self.review_topic = ""
        self.citation_format = "gb"
        # 使用专用的文献池管理参考文献
        self.literature_pool = LiteraturePool()

state = AppState()


# ==================== 页面路由 ====================

@app.route('/')
def index():
    return render_template('index.html')


# ==================== 文献池状态API ====================

@app.route('/api/literature-pool/status', methods=['GET'])
def get_literature_pool_status():
    """获取文献池状态（用于前端按钮状态控制）"""
    status = state.literature_pool.get_status()
    return jsonify({
        'success': True,
        **status,
        'literature_list': state.literature_pool.citation_list
    })


# ==================== 配置API ====================

@app.route('/api/citation-formats', methods=['GET'])
def get_citation_formats():
    """获取可用的引用格式列表"""
    formats = []
    for key, value in Config.CITATION_FORMATS.items():
        formats.append({
            "id": key,
            "name": value["name"],
            "description": value["description"]
        })
    return jsonify({'success': True, 'formats': formats})


@app.route('/api/review-topic', methods=['POST'])
def set_review_topic():
    """设置综述主题"""
    data = request.get_json()
    topic = data.get('topic', '').strip()
    citation_format = data.get('citation_format', 'gb')
    
    if not topic:
        return jsonify({'success': False, 'error': '综述主题不能为空'})
    
    if len(topic) < 5:
        return jsonify({'success': False, 'error': '综述主题至少需要5个字符'})
    
    if len(topic) > 200:
        return jsonify({'success': False, 'error': '综述主题不能超过200个字符'})
    
    state.review_topic = topic
    state.citation_format = citation_format
    
    return jsonify({
        'success': True, 
        'message': f'综述主题已设置：{topic}',
        'topic': topic,
        'citation_format': citation_format
    })


@app.route('/api/review-topic', methods=['GET'])
def get_review_topic():
    """获取当前综述主题"""
    return jsonify({
        'success': True,
        'topic': state.review_topic,
        'citation_format': state.citation_format
    })


# ==================== 文件管理API ====================

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """通用文件上传接口"""
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': '未选择文件'})
    
    file_type = request.form.get('type', 'review')
    files = request.files.getlist('files')
    
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': '未选择文件'})
    
    max_files = Config.BATCH_CONFIG.get("max_files", 20)
    if len(files) > max_files:
        return jsonify({'success': False, 'error': f'最多支持{max_files}个文件'})
    
    uploaded_files = []
    errors = []
    
    for file in files:
        if not file or file.filename == '':
            continue
            
        if not Config.allowed_file(file.filename):
            errors.append(f"{file.filename}: 不支持的格式")
            continue
        
        file_id = str(uuid.uuid4())[:8]
        filename = secure_filename(file.filename)
        
        prefix = "review_" if file_type == "review" else "lit_"
        filepath = os.path.join(Config.UPLOAD_FOLDER, f"{prefix}{file_id}_{filename}")
        file.save(filepath)
        
        # 计算内容哈希
        with open(filepath, 'rb') as f:
            content_hash = hashlib.md5(f.read()).hexdigest()
        
        file_info = {
            "id": file_id,
            "filename": filename,
            "path": filepath,
            "size": os.path.getsize(filepath),
            "format": filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown',
            "content_hash": content_hash
        }
        
        if file_type == "review":
            state.review_files[file_id] = file_info
        else:
            # 添加到文献池
            state.literature_pool.add_file(file_id, file_info, content_hash)
        
        uploaded_files.append(file_info)
    
    # 返回文献池状态
    pool_status = state.literature_pool.get_status()
    
    return jsonify({
        'success': True,
        'message': f'成功上传 {len(uploaded_files)} 个文件',
        'files': uploaded_files,
        'errors': errors if errors else None,
        'pool_status': pool_status
    })


@app.route('/api/files/<file_type>', methods=['GET'])
def get_files(file_type):
    """获取已上传的文件列表"""
    if file_type == 'review':
        files = list(state.review_files.values())
    else:
        files = list(state.literature_pool.files.values())
    
    pool_status = state.literature_pool.get_status()
    
    return jsonify({
        'success': True, 
        'files': files,
        'pool_status': pool_status
    })


@app.route('/api/files/<file_type>/<file_id>', methods=['DELETE'])
def delete_file(file_type, file_id):
    """删除指定文件"""
    if file_type == 'review':
        if file_id not in state.review_files:
            return jsonify({'success': False, 'error': '文件不存在'})
        
        file_info = state.review_files[file_id]
        if os.path.exists(file_info['path']):
            os.remove(file_info['path'])
        del state.review_files[file_id]
    else:
        if file_id not in state.literature_pool.files:
            return jsonify({'success': False, 'error': '文件不存在'})
        
        file_info = state.literature_pool.files[file_id]
        if os.path.exists(file_info['path']):
            os.remove(file_info['path'])
        state.literature_pool.remove_file(file_id)
    
    pool_status = state.literature_pool.get_status()
    
    return jsonify({
        'success': True, 
        'message': '文件已删除',
        'pool_status': pool_status
    })


@app.route('/api/files/<file_type>/clear', methods=['DELETE'])
def clear_files(file_type):
    """清空指定类型的所有文件"""
    if file_type == 'review':
        for file_info in state.review_files.values():
            if os.path.exists(file_info['path']):
                os.remove(file_info['path'])
        state.review_files.clear()
    else:
        for file_info in state.literature_pool.files.values():
            if os.path.exists(file_info['path']):
                os.remove(file_info['path'])
        state.literature_pool.reset()
    
    pool_status = state.literature_pool.get_status()
    
    return jsonify({
        'success': True, 
        'message': '已清空所有文件',
        'pool_status': pool_status
    })


# ==================== 文献处理API ====================

@app.route('/api/literature/process', methods=['POST'])
def process_literature():
    """处理上传的参考文献"""
    pool = state.literature_pool
    
    if len(pool.files) == 0:
        return jsonify({
            'success': False, 
            'error': '请先上传至少1篇参考文献',
            'pool_status': pool.get_status()
        })
    
    # 设置处理状态
    pool.is_processing = True
    pool.processing_error = None
    
    try:
        for file_id, file_info in pool.files.items():
            # 跳过已处理的文件
            if file_id in pool.processed:
                continue
            
            result = doc_processor.process_single_file(file_info['path'], file_id)
            result['content_hash'] = file_info.get('content_hash', '')
            pool.set_processed(file_id, result)
        
        pool.is_processing = False
        pool.is_processed = True
        
        return jsonify({
            'success': True,
            'message': f'成功处理 {len(pool.processed)} 篇文献',
            'literature_list': pool.citation_list,
            'pool_status': pool.get_status()
        })
        
    except Exception as e:
        pool.is_processing = False
        pool.processing_error = str(e)
        
        return jsonify({
            'success': False, 
            'error': f'文献处理失败: {str(e)}',
            'pool_status': pool.get_status()
        })


@app.route('/api/literature/list', methods=['GET'])
def get_literature_list():
    """获取已处理的文献引用列表"""
    pool = state.literature_pool
    return jsonify({
        'success': True,
        'literature_list': pool.citation_list,
        'pool_status': pool.get_status()
    })


# ==================== 模型管理API ====================

@app.route('/api/models', methods=['GET'])
def get_models():
    models = ollama_client.get_available_models()
    current = ollama_client.current_model
    return jsonify({
        'success': True,
        'models': models,
        'current': current
    })


@app.route('/api/models/select', methods=['POST'])
def select_model():
    data = request.get_json()
    model_name = data.get('model')
    
    if not model_name:
        return jsonify({'success': False, 'error': '未指定模型'})
    
    success = ollama_client.set_model(model_name)
    
    if success:
        return jsonify({'success': True, 'message': f'已切换至模型: {model_name}'})
    else:
        return jsonify({'success': False, 'error': '模型切换失败'})


@app.route('/api/health', methods=['GET'])
def health_check():
    healthy = ollama_client.check_health()
    return jsonify({
        'success': True,
        'ollama_status': 'running' if healthy else 'offline'
    })


# ==================== 步骤管理API ====================

@app.route('/api/steps/current', methods=['GET'])
def get_current_step():
    return jsonify({
        'success': True,
        'current_step': state.current_step,
        'completed_steps': list(state.completed_steps)
    })


@app.route('/api/steps/complete', methods=['POST'])
def complete_step():
    data = request.get_json()
    step = data.get('step')
    
    if step:
        state.completed_steps.add(step)
        if step < 4:
            state.current_step = step + 1
    
    return jsonify({
        'success': True,
        'current_step': state.current_step,
        'completed_steps': list(state.completed_steps)
    })


@app.route('/api/steps/reset', methods=['POST'])
def reset_steps():
    state.reset()
    return jsonify({'success': True, 'message': '已重置'})


# ==================== Prompt管理API ====================

@app.route('/api/prompts', methods=['GET'])
def list_prompts():
    prompts = prompt_manager.list_saved_prompts()
    return jsonify({'success': True, 'prompts': prompts})


@app.route('/api/prompts/<filename>', methods=['GET'])
def get_prompt(filename):
    data = prompt_manager.load_prompt(filename)
    if data:
        return jsonify({'success': True, 'data': data})
    return jsonify({'success': False, 'error': 'Prompt不存在'})


@app.route('/api/prompts', methods=['POST'])
def save_prompt():
    data = request.get_json()
    name = data.get('name', '自定义Prompt')
    content = data.get('content', '')
    
    if not content:
        return jsonify({'success': False, 'error': 'Prompt内容不能为空'})
    
    filename = prompt_manager.save_prompt(name, content)
    return jsonify({'success': True, 'filename': filename})


@app.route('/api/prompts/<filename>', methods=['DELETE'])
def delete_prompt(filename):
    success = prompt_manager.delete_prompt(filename)
    return jsonify({'success': success})


# ==================== 导出API ====================

@app.route('/api/exports', methods=['GET'])
def list_exports():
    exports = export_handler.list_exports()
    return jsonify({'success': True, 'exports': exports})


@app.route('/api/exports/<filename>', methods=['GET'])
def download_export(filename):
    filepath = export_handler.get_export_path(filename)
    if filepath:
        return send_file(filepath, as_attachment=True)
    return jsonify({'success': False, 'error': '文件不存在'})


@app.route('/api/export', methods=['POST'])
def export_review():
    data = request.get_json()
    content = data.get('content', '')
    title = data.get('title', state.review_topic or '综述')
    format_type = data.get('format', 'docx')
    
    if not content:
        return jsonify({'success': False, 'error': '没有可导出的内容'})
    
    # 添加参考文献列表（仅使用用户上传的文献）
    pool = state.literature_pool
    if pool.citation_list:
        refs_section = "\n\n## 参考文献\n\n"
        refs_section += f"（以下{len(pool.citation_list)}篇参考文献均来自用户上传）\n\n"
        for lit in pool.citation_list:
            refs_section += f"[{lit['index']}] {lit['authors']} ({lit['year']}). {lit['title']}.\n"
        content += refs_section
    
    try:
        if format_type == 'markdown':
            filepath = export_handler.export_to_markdown(content, title)
        elif format_type == 'docx':
            filepath = export_handler.export_to_docx(content, title)
        elif format_type == 'html':
            filepath = export_handler.export_to_html(content, title)
        elif format_type == 'pdf':
            filepath = export_handler.export_to_pdf(content, title)
            if not filepath:
                return jsonify({'success': False, 'error': 'PDF导出失败'})
        else:
            return jsonify({'success': False, 'error': '不支持的格式'})
        
        filename = os.path.basename(filepath)
        return jsonify({
            'success': True,
            'filename': filename,
            'message': f'文件已导出: {filename}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== WebSocket事件处理 ====================

@socketio.on('connect')
def handle_connect():
    emit('status', {'message': '已连接到服务器'})
    emit('step_update', {
        'current_step': state.current_step,
        'completed_steps': list(state.completed_steps)
    })
    # 发送文献池状态
    emit('pool_status_update', state.literature_pool.get_status())


def emit_progress(current, total, message, status="processing"):
    """发送进度更新"""
    percentage = int((current / max(total, 1)) * 100)
    emit('progress_update', {
        'current': current,
        'total': total,
        'percentage': percentage,
        'message': message,
        'status': status
    })


def emit_pool_status():
    """发送文献池状态更新"""
    emit('pool_status_update', state.literature_pool.get_status())


def validate_and_filter_citations(content: str, pool: LiteraturePool) -> tuple:
    """
    验证并过滤内容中的引用
    返回: (过滤后的内容, 无效引用列表)
    """
    import re
    
    valid_range = pool.get_valid_citation_range()
    max_valid = valid_range[1]
    
    invalid_citations = []
    
    def replace_invalid(match):
        citation_num = int(match.group(1))
        if citation_num > max_valid or citation_num < 1:
            invalid_citations.append(citation_num)
            # 用最接近的有效引用替换，或移除
            if max_valid > 0:
                return f"[{min(citation_num, max_valid)}]"
            else:
                return ""
        return match.group(0)
    
    # 替换无效引用
    filtered_content = re.sub(r'\[(\d+)\]', replace_invalid, content)
    
    return filtered_content, invalid_citations


@socketio.on('analyze_paradigm')
def handle_analyze_paradigm(data):
    """分析综述写作范式"""
    if not state.review_files:
        emit('error', {'message': '请先上传综述文献'})
        return
    
    if not ollama_client.current_model:
        emit('error', {'message': '请先选择一个模型'})
        return
    
    file_paths = [f['path'] for f in state.review_files.values()]
    total_files = len(file_paths)
    
    emit_progress(0, total_files + 2, "开始处理文献...", "processing")
    
    processed_files = []
    for i, path in enumerate(file_paths):
        filename = os.path.basename(path)
        emit_progress(i, total_files + 2, f"正在解析文献 {i+1}/{total_files}: {filename}", "processing")
        
        result = doc_processor.process_single_file(path)
        processed_files.append(result)
        socketio.sleep(0.1)
    
    emit_progress(total_files, total_files + 2, "正在准备分析内容...", "processing")
    combined_text = doc_processor.prepare_for_analysis(processed_files)
    
    emit_progress(total_files + 1, total_files + 2, "正在分析写作范式...", "analyzing")
    
    system_prompt = prompt_manager.get_analysis_prompt(len(processed_files))
    
    result_parts = []
    for chunk in ollama_client.generate(combined_text, system_prompt):
        result_parts.append(chunk)
        emit('paradigm_chunk', {'chunk': chunk})
        socketio.sleep(0)
    
    full_result = ''.join(result_parts)
    state.current_paradigm = full_result
    state.completed_steps.add(2)
    state.current_step = 3
    
    emit_progress(total_files + 2, total_files + 2, "分析完成！", "completed")
    
    emit('paradigm_complete', {
        'paradigm': full_result,
        'message': '写作范式分析完成',
        'summary': doc_processor.get_summary(processed_files)
    })
    
    emit('step_update', {
        'current_step': state.current_step,
        'completed_steps': list(state.completed_steps)
    })


@socketio.on('process_literature')
def handle_process_literature(data):
    """处理参考文献（WebSocket版本，支持进度更新）"""
    pool = state.literature_pool
    
    if len(pool.files) == 0:
        emit('error', {'message': '请先上传至少1篇参考文献'})
        emit_pool_status()
        return
    
    pool.is_processing = True
    pool.processing_error = None
    emit_pool_status()
    
    try:
        total = len(pool.files)
        processed_count = 0
        
        for file_id, file_info in pool.files.items():
            if file_id in pool.processed:
                processed_count += 1
                continue
            
            emit_progress(processed_count, total, f"正在分析: {file_info['filename']}", "processing")
            
            result = doc_processor.process_single_file(file_info['path'], file_id)
            result['content_hash'] = file_info.get('content_hash', '')
            pool.set_processed(file_id, result)
            
            processed_count += 1
            socketio.sleep(0.1)
        
        pool.is_processing = False
        pool.is_processed = True
        
        emit_progress(total, total, "文献分析完成！", "completed")
        
        emit('literature_processed', {
            'success': True,
            'message': f'成功分析 {len(pool.processed)} 篇文献',
            'literature_list': pool.citation_list,
            'pool_status': pool.get_status()
        })
        
    except Exception as e:
        pool.is_processing = False
        pool.processing_error = str(e)
        
        emit('error', {'message': f'文献分析失败: {str(e)}'})
        emit_pool_status()


@socketio.on('generate_framework')
def handle_generate_framework(data):
    """生成综述框架"""
    pool = state.literature_pool
    topic = data.get('topic', state.review_topic)
    paradigm = data.get('paradigm', state.current_paradigm)
    
    if not topic:
        emit('error', {'message': '请先设置综述主题'})
        return
    
    if not paradigm:
        emit('error', {'message': '请先分析写作范式或输入Prompt'})
        return
    
    if not ollama_client.current_model:
        emit('error', {'message': '请先选择一个模型'})
        return
    
    # 检查文献池状态
    if len(pool.files) > 0 and not pool.is_processed:
        emit('error', {'message': '请先等待参考文献分析完成'})
        return
    
    state.review_topic = topic
    
    emit_progress(0, 3, "正在准备...", "processing")
    
    # 准备文献上下文（仅使用用户上传的文献）
    lit_context = ""
    if pool.processed:
        emit_progress(1, 3, "正在整合参考文献...", "processing")
        processed_list = list(pool.processed.values())
        lit_context, _ = doc_processor.prepare_literature_context(
            processed_list, 
            state.citation_format
        )
    
    emit_progress(2, 3, "正在生成框架...", "analyzing")
    
    # 构建框架生成Prompt，明确限制只使用用户上传的文献
    lit_count = len(pool.citation_list)
    lit_list_text = ""
    if pool.citation_list:
        lit_list_text = f"\n\n## 可用参考文献（共{lit_count}篇，均来自用户上传）\n\n"
        lit_list_text += "【重要】以下是您唯一可以引用的文献，禁止引用任何不在此列表中的文献：\n\n"
        for lit in pool.citation_list:
            lit_list_text += f"[{lit['index']}] {lit['authors']} ({lit['year']}). {lit['title']}\n"
    else:
        lit_list_text = "\n\n【注意】用户未上传参考文献，请勿在内容中添加任何文献引用。\n"
    
    framework_prompt = f"""请为以下综述主题生成详细的框架结构：

## 综述主题
{topic}

## 写作范式参考
{paradigm[:3000] if len(paradigm) > 3000 else paradigm}

{lit_list_text}

## 参考文献内容摘要
{lit_context[:5000] if len(lit_context) > 5000 else lit_context if lit_context else "（用户未上传参考文献）"}

## 框架要求
请生成包含以下部分的框架：
1. **摘要** - 简要说明应包含的内容要点
2. **引言** - 列出需要涵盖的要点
3. **研究方法**（如适用）
4. **主体部分** - 详细的章节划分，每章需关联可引用的文献编号
5. **讨论** - 讨论重点
6. **结论** - 总结要点

## 引用规则
- 仅可引用上述列表中的文献，使用[编号]格式
- 最大引用编号为[{lit_count}]
- 禁止编造或引用任何未在列表中的文献"""
    
    result_parts = []
    for chunk in ollama_client.generate(framework_prompt):
        result_parts.append(chunk)
        emit('framework_chunk', {'chunk': chunk})
        socketio.sleep(0)
    
    full_result = ''.join(result_parts)
    
    # 验证并过滤引用
    if pool.citation_list:
        full_result, invalid = validate_and_filter_citations(full_result, pool)
        if invalid:
            emit('status', {'message': f'已自动修正{len(invalid)}处无效引用'})
    
    state.current_framework = {'content': full_result}
    
    emit_progress(3, 3, "框架生成完成！", "completed")
    
    emit('framework_complete', {
        'framework': full_result,
        'message': '综述框架生成完成',
        'literature_list': pool.citation_list,
        'pool_status': pool.get_status()
    })


@socketio.on('generate_section')
def handle_generate_section(data):
    """生成指定章节"""
    pool = state.literature_pool
    section = data.get('section', 'full')
    topic = data.get('topic', state.review_topic)
    paradigm = data.get('paradigm', state.current_paradigm)
    framework = data.get('framework', state.current_framework.get('content', ''))
    
    if not topic:
        emit('error', {'message': '请先设置综述主题'})
        return
    
    if not ollama_client.current_model:
        emit('error', {'message': '请先选择一个模型'})
        return
    
    # 检查文献池状态
    pool_status = pool.get_status()
    if len(pool.files) > 0 and not pool_status['can_generate']:
        if pool.is_processing:
            emit('error', {'message': '正在分析参考文献，请稍候...'})
        elif pool.processing_error:
            emit('error', {'message': f'分析失败: {pool.processing_error}，请重新上传文献'})
        else:
            emit('error', {'message': '请先完成参考文献分析'})
        return
    
    section_names = {
        'full': '完整综述',
        'abstract': '摘要',
        'introduction': '引言',
        'methods': '方法',
        'main_body': '主体内容',
        'discussion': '讨论',
        'conclusion': '结论'
    }
    
    section_name = section_names.get(section, section)
    emit_progress(0, 3, f"正在准备生成{section_name}...", "processing")
    
    # 准备文献上下文（严格限制来源）
    lit_context = ""
    lit_count = len(pool.citation_list)
    
    if pool.processed:
        emit_progress(1, 3, "正在整合参考文献...", "processing")
        processed_list = list(pool.processed.values())
        lit_context, _ = doc_processor.prepare_literature_context(
            processed_list,
            state.citation_format
        )
    
    emit_progress(2, 3, f"正在生成{section_name}...", "analyzing")
    
    # 构建严格的引用约束
    citation_constraint = ""
    if lit_count > 0:
        citation_constraint = f"""
## 引用约束（必须严格遵守）

### 可引用文献列表（共{lit_count}篇，均来自用户上传）
"""
        for lit in pool.citation_list:
            citation_constraint += f"[{lit['index']}] {lit['authors']} ({lit['year']}). {lit['title']}\n"
        
        citation_constraint += f"""
### 引用规则
1. 只能引用上述{lit_count}篇文献，引用格式为[编号]
2. 有效引用范围：[1]到[{lit_count}]
3. 禁止使用超出范围的编号，如[{lit_count + 1}]及以上
4. 禁止编造任何不在列表中的文献
5. 如某观点无对应文献支持，请明确说明"现有文献未涉及"
"""
    else:
        citation_constraint = """
## 引用约束
用户未上传参考文献，请勿在内容中添加任何文献引用标注如[1]、[2]等。
所有观点请使用通用性描述。
"""
    
    # 获取系统提示
    system_prompt = prompt_manager.get_generation_system_prompt(topic, state.citation_format)
    
    # 获取章节专用Prompt
    section_prompts = prompt_manager.get_section_prompts(topic, pool.citation_list)
    
    if section == 'full':
        generation_prompt = f"""## 综述主题
{topic}

## 写作范式要求
{paradigm[:2000] if len(paradigm) > 2000 else paradigm}

## 综述框架
{framework[:2000] if len(framework) > 2000 else framework}

{citation_constraint}

## 参考文献详细内容
{lit_context if lit_context else "（用户未上传参考文献）"}

## 生成任务
请生成一篇完整的学术综述，包括：
1. 摘要（约300字）
2. 引言（约1000字）
3. 主体内容（按主题分章节，约3000-5000字）
4. 讨论（约1000字）
5. 结论（约400字）

请开始生成："""
    else:
        section_instruction = section_prompts.get(section, "请生成该部分内容。")
        
        generation_prompt = f"""## 综述主题
{topic}

## 写作范式要求
{paradigm[:2000] if len(paradigm) > 2000 else paradigm}

## 综述框架
{framework[:2000] if len(framework) > 2000 else framework}

{citation_constraint}

## 参考文献详细内容
{lit_context if lit_context else "（用户未上传参考文献）"}

## 当前任务
{section_instruction}

请开始生成："""
    
    result_parts = []
    for chunk in ollama_client.generate(generation_prompt, system_prompt):
        result_parts.append(chunk)
        emit('section_chunk', {'section': section, 'chunk': chunk})
        socketio.sleep(0)
    
    full_result = ''.join(result_parts)
    
    # 验证并过滤引用（二次校验）
    if pool.citation_list:
        full_result, invalid = validate_and_filter_citations(full_result, pool)
        if invalid:
            emit('status', {'message': f'已自动修正{len(set(invalid))}处超出范围的引用'})
    
    state.review_content[section] = full_result
    state.completed_steps.add(3)
    state.current_step = 4
    
    emit_progress(3, 3, f"{section_name}生成完成！", "completed")
    
    emit('section_complete', {
        'section': section,
        'content': full_result,
        'message': f'{section_name}生成完成',
        'literature_list': pool.citation_list,
        'pool_status': pool.get_status(),
        'citation_info': {
            'total_available': lit_count,
            'source': '用户上传文献'
        }
    })
    
    emit('step_update', {
        'current_step': state.current_step,
        'completed_steps': list(state.completed_steps)
    })


@socketio.on('refine_content')
def handle_refine_content(data):
    """优化内容"""
    pool = state.literature_pool
    feedback = data.get('feedback', '')
    current_content = data.get('content', '')
    topic = state.review_topic
    
    if not feedback:
        emit('error', {'message': '请输入修改意见'})
        return
    
    if not current_content:
        emit('error', {'message': '没有可优化的内容'})
        return
    
    if not ollama_client.current_model:
        emit('error', {'message': '请先选择一个模型'})
        return
    
    emit_progress(0, 2, "正在分析修改意见...", "processing")
    
    # 构建引用约束
    lit_count = len(pool.citation_list)
    lit_list_text = ""
    if pool.citation_list:
        lit_list_text = f"\n## 可引用文献（共{lit_count}篇，来自用户上传）\n"
        for lit in pool.citation_list:
            lit_list_text += f"[{lit['index']}] {lit['authors']} ({lit['year']}). {lit['title']}\n"
        lit_list_text += f"\n【重要】只能引用[1]到[{lit_count}]，禁止使用其他编号\n"
    
    refine_prompt = f"""## 综述主题
{topic}

## 当前内容
{current_content}

## 用户修改意见
{feedback}

{lit_list_text}

## 修改要求
请根据用户的修改意见对内容进行优化，同时必须遵守以下规则：
1. 所有内容必须围绕主题「{topic}」
2. {"只能引用上述" + str(lit_count) + "篇文献，使用[编号]格式" if lit_count > 0 else "不要添加任何文献引用"}
3. {"有效引用范围：[1]到[" + str(lit_count) + "]" if lit_count > 0 else ""}
4. 禁止编造任何不存在的文献
5. 保持学术写作风格

请输出修改后的完整内容："""
    
    system_prompt = prompt_manager.get_generation_system_prompt(topic, state.citation_format)
    
    emit_progress(1, 2, "正在优化内容...", "analyzing")
    
    result_parts = []
    for chunk in ollama_client.generate(refine_prompt, system_prompt):
        result_parts.append(chunk)
        emit('refine_chunk', {'chunk': chunk})
        socketio.sleep(0)
    
    full_result = ''.join(result_parts)
    
    # 验证并过滤引用
    if pool.citation_list:
        full_result, invalid = validate_and_filter_citations(full_result, pool)
        if invalid:
            emit('status', {'message': f'已自动修正{len(set(invalid))}处超出范围的引用'})
    
    state.conversation_history.append({'role': 'user', 'content': feedback})
    state.conversation_history.append({'role': 'assistant', 'content': full_result})
    
    emit_progress(2, 2, "优化完成！", "completed")
    
    emit('refine_complete', {
        'content': full_result,
        'message': '内容优化完成'
    })


@socketio.on('clear_history')
def handle_clear_history():
    state.conversation_history = []
    state.review_content = {}
    emit('status', {'message': '已清除历史记录'})


# ==================== 启动应用 ====================

def open_browser():
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    print("=" * 50)
    print("    综述生成系统 v2.2 启动中...")
    print("=" * 50)
    
    if ollama_client.check_health():
        print("✓ Ollama服务运行正常")
        models = ollama_client.get_available_models()
        print(f"✓ 发现 {len(models)} 个可用模型")
        for m in models:
            print(f"  - {m['name']} ({m['spec']}, {m['size_gb']}GB)")
    else:
        print("✗ 警告: Ollama服务未运行")
    
    print("\n正在启动Web服务...")
    print("访问地址: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    Timer(1, open_browser).start()
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)