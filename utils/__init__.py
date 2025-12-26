"""
工具模块初始化
"""
from .ollama_client import ollama_client, OllamaClient
from .pdf_processor import doc_processor, DocumentProcessor
from .prompt_manager import prompt_manager, PromptManager
from .export_handler import export_handler, ExportHandler

# 兼容旧代码的别名
pdf_processor = doc_processor
PDFProcessor = DocumentProcessor

__all__ = [
    'ollama_client', 'OllamaClient',
    'doc_processor', 'DocumentProcessor',
    'pdf_processor', 'PDFProcessor',  # 兼容别名
    'prompt_manager', 'PromptManager',
    'export_handler', 'ExportHandler'
]