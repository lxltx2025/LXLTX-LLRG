"""
Ollama API 客户端模块
负责与本地Ollama服务通信，管理模型调用
"""
import requests
import json
from typing import Generator, List, Dict, Optional
from config import Config

class OllamaClient:
    def __init__(self):
        self.base_url = Config.OLLAMA_BASE_URL
        self.current_model = None
        self.model_config = Config.MODEL_CONFIG.copy()
        
    def get_available_models(self) -> List[Dict]:
        """
        扫描并获取本地已下载的所有模型
        返回模型列表，包含名称、大小、参数量等信息
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get('models', []):
                name = model.get('name', '')
                size = model.get('size', 0)
                
                # 估算模型规格
                size_gb = size / (1024**3)
                if size_gb > 20:
                    spec = "14B"
                elif size_gb > 8:
                    spec = "7B"
                else:
                    spec = "1.5B"
                
                models.append({
                    'name': name,
                    'size': size,
                    'size_gb': round(size_gb, 2),
                    'spec': spec,
                    'modified_at': model.get('modified_at', ''),
                    'details': model.get('details', {})
                })
            
            return sorted(models, key=lambda x: x['size'], reverse=True)
            
        except requests.exceptions.RequestException as e:
            print(f"获取模型列表失败: {e}")
            return []
    
    def set_model(self, model_name: str) -> bool:
        """
        设置当前使用的模型
        根据模型规格自动调整显存配置
        """
        models = self.get_available_models()
        model_info = next((m for m in models if m['name'] == model_name), None)
        
        if not model_info:
            return False
        
        self.current_model = model_name
        
        # 根据模型规格调整配置以优化显存使用
        spec = model_info['spec']
        if spec in Config.MEMORY_CONFIG:
            self.model_config.update(Config.MEMORY_CONFIG[spec])
        
        print(f"已切换至模型: {model_name} (规格: {spec})")
        return True
    
    def generate(self, prompt: str, system_prompt: str = "", 
                 stream: bool = True) -> Generator[str, None, None]:
        """
        调用模型生成文本（流式输出）
        """
        if not self.current_model:
            yield "错误: 请先选择一个模型"
            return
        
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.current_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": stream,
            "options": {
                "num_ctx": self.model_config.get("num_ctx", 4096),
                "num_batch": self.model_config.get("num_batch", 256),
                "temperature": self.model_config.get("temperature", 0.7),
                "top_p": self.model_config.get("top_p", 0.9),
                "repeat_penalty": self.model_config.get("repeat_penalty", 1.1),
            }
        }
        
        try:
            with requests.post(url, json=payload, stream=True, timeout=300) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode('utf-8'))
                        if 'response' in data:
                            yield data['response']
                        if data.get('done', False):
                            break
                            
        except requests.exceptions.RequestException as e:
            yield f"生成错误: {str(e)}"
    
    def generate_sync(self, prompt: str, system_prompt: str = "") -> str:
        """
        同步生成文本（非流式）
        """
        result = []
        for chunk in self.generate(prompt, system_prompt, stream=True):
            result.append(chunk)
        return ''.join(result)
    
    def chat(self, messages: List[Dict], stream: bool = True) -> Generator[str, None, None]:
        """
        对话模式生成（支持多轮对话）
        """
        if not self.current_model:
            yield "错误: 请先选择一个模型"
            return
        
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.current_model,
            "messages": messages,
            "stream": stream,
            "options": {
                "num_ctx": self.model_config.get("num_ctx", 4096),
                "temperature": self.model_config.get("temperature", 0.7),
            }
        }
        
        try:
            with requests.post(url, json=payload, stream=True, timeout=300) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode('utf-8'))
                        if 'message' in data and 'content' in data['message']:
                            yield data['message']['content']
                        if data.get('done', False):
                            break
                            
        except requests.exceptions.RequestException as e:
            yield f"对话错误: {str(e)}"
    
    def check_health(self) -> bool:
        """检查Ollama服务是否正常运行"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


# 全局客户端实例
ollama_client = OllamaClient()