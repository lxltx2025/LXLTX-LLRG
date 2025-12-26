"""
配置文件 - 系统参数设置（修复版）
"""
import os

class Config:
    # 基础路径配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    PROMPT_FOLDER = os.path.join(BASE_DIR, 'prompts')
    
    # Flask配置
    SECRET_KEY = 'your-secret-key-here-2024'
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024
    
    # 支持的文件格式
    ALLOWED_EXTENSIONS = {'pdf', 'txt'}
    
    # Ollama配置
    OLLAMA_BASE_URL = "http://172.16.25.135:11434"
    
    # 模型推理配置
    MODEL_CONFIG = {
        "context_length": 8192,
        "num_gpu": 1,
        "num_thread": 8,
        "temperature": 0.7,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }
    
    # 显存优化配置
    MEMORY_CONFIG = {
        "14B": {"num_ctx": 4096, "num_batch": 256},
        "7B": {"num_ctx": 8192, "num_batch": 512},
        "1.5B": {"num_ctx": 16384, "num_batch": 1024},
    }
    
    # 批量处理配置
    BATCH_CONFIG = {
        "max_files": 100,
        "max_chars_per_file": 50000,
        "max_total_chars": 150000,
    }
    
    # 引用格式配置
    CITATION_FORMATS = {
        "apa": {
            "name": "APA格式",
            "description": "美国心理学会格式",
            "template": "{authors} ({year}). {title}. {journal}, {volume}({issue}), {pages}.",
            "inline": "({author}, {year})"
        },
        "gb": {
            "name": "GB/T 7714",
            "description": "中国国家标准",
            "template": "[{index}] {authors}. {title}[J]. {journal}, {year}, {volume}({issue}): {pages}.",
            "inline": "[{index}]"
        },
        "mla": {
            "name": "MLA格式",
            "description": "现代语言协会格式",
            "template": "{authors}. \"{title}.\" {journal} {volume}.{issue} ({year}): {pages}.",
            "inline": "({author} {page})"
        },
        "harvard": {
            "name": "Harvard格式",
            "description": "哈佛引用格式",
            "template": "{authors} ({year}) '{title}', {journal}, {volume}({issue}), pp. {pages}.",
            "inline": "({author}, {year})"
        }
    }
    
    @classmethod
    def init_folders(cls):
        for folder in [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER, cls.PROMPT_FOLDER]:
            os.makedirs(folder, exist_ok=True)
    
    @classmethod
    def allowed_file(cls, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in cls.ALLOWED_EXTENSIONS