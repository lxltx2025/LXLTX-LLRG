"""
Prompt管理模块（增强版）
支持主题约束和引用规范
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from config import Config


class PromptManager:
    def __init__(self):
        self.prompts_dir = Config.PROMPT_FOLDER
        os.makedirs(self.prompts_dir, exist_ok=True)
        
    def get_analysis_prompt(self, num_papers: int) -> str:
        """生成用于分析综述写作范式的系统提示"""
        return f"""你是一位专业的学术写作分析专家。请仔细分析以下{num_papers}篇综述文献的写作特点，并总结出可复用的写作范式。

请从以下维度进行分析：

1. **整体结构**：文章的章节组织方式、各部分的篇幅比例、逻辑递进关系

2. **写作风格**：语言正式程度、人称使用、术语使用习惯、句式特点

3. **论述逻辑**：如何引出研究问题、如何组织文献回顾、如何进行分析比较、如何得出结论

4. **摘要特点**：摘要的结构、包含的关键要素、字数范围

5. **引言特点**：背景介绍方式、研究意义阐述、文章结构预告

6. **文献综述技巧**：文献组织方式、批判性分析深度、研究空白识别

7. **引用规范**：引用格式、引用频率、引用方式（直接引用/间接引用）

8. **结论特点**：总结方式、未来展望、研究局限性讨论

请基于分析结果，生成一个详细的Prompt模板，用于指导AI生成同类型的综述文章。"""

    def get_generation_system_prompt(self, topic: str, citation_format: str = "gb") -> str:
        """
        生成综述内容的系统提示（包含主题约束和引用规范）
        """
        format_info = Config.CITATION_FORMATS.get(citation_format, Config.CITATION_FORMATS["gb"])
        
        return f"""你是一位专业的学术综述撰写专家。你正在撰写一篇关于「{topic}」的学术综述。

## 核心约束（必须严格遵守）

### 1. 主题约束
- 所有生成内容必须紧密围绕主题「{topic}」展开
- 不得偏离主题，不得引入与主题无关的内容
- 每个段落都应该与主题有明确的逻辑关联

### 2. 引用规范（极其重要）
- **只能引用用户提供的参考文献**，禁止编造或虚构任何文献
- 引用格式采用：{format_info['name']}
- 文内引用格式：{format_info['inline']}
- 参考文献格式：{format_info['template']}
- 每个论点、数据、结论都必须标注来源文献
- 引用时必须注明文献编号，如 [1]、[2] 等

### 3. 引用要求
- 综述中的每个重要观点都需要有文献支持
- 直接引用需使用引号并标注页码（如有）
- 间接引用（改述）也必须标注来源
- 禁止出现无来源的断言性陈述
- 当用户未提供相关文献时，应明确指出"根据现有资料，该方面信息不足"

### 4. 内容质量
- 保持学术写作的严谨性和客观性
- 使用专业术语，但确保表述清晰
- 逻辑结构清晰，论述有理有据
- 避免主观臆断和过度推断

## 引用示例

正确示例：
"研究表明，XXX方法在该领域取得了显著进展[1]。Zhang等人(2023)的研究发现...[2]"

错误示例（禁止）：
"研究表明，XXX方法效果显著。" （无引用来源）
"根据Smith(2024)的研究..." （编造的文献）"""

    def get_literature_constraint_prompt(self, literature_list: List[Dict]) -> str:
        """
        生成文献约束提示，强制只引用提供的文献
        """
        if not literature_list:
            return """
## 参考文献说明
用户未提供参考文献。在生成内容时：
- 使用通用性描述，避免具体数据引用
- 明确标注"该观点需要进一步文献支持"
- 不得编造任何文献信息
"""
        
        lit_list_text = "\n".join([
            f"[{lit['index']}] {lit['authors']} ({lit['year']}). {lit['title']}."
            for lit in literature_list
        ])
        
        return f"""
## 可用参考文献列表（只能引用以下文献）

{lit_list_text}

## 引用规则
1. 生成内容时只能引用上述文献列表中的文献
2. 使用 [编号] 格式进行文内引用，如 [1]、[2]
3. 每个论点都应尽可能关联到具体文献
4. 如果某个观点在上述文献中没有依据，请明确说明"现有文献未涉及该方面"
5. 禁止编造任何不在列表中的文献

## 文献内容摘要
"""

    def get_section_prompts(self, topic: str, literature_list: List[Dict]) -> Dict[str, str]:
        """生成各章节的专用Prompt，包含主题和引用约束"""
        
        lit_refs = self._format_literature_refs(literature_list)
        
        return {
            "abstract": f"""请为主题「{topic}」生成综述的摘要部分。

要求：
- 概括研究背景和目的（紧扣主题）
- 说明综述方法和范围
- 总结主要发现和结论
- 字数控制在250-300字
- 可简要提及引用的主要文献数量

注意：摘要中一般不需要具体引用标注，但内容必须基于提供的文献。""",

            "introduction": f"""请为主题「{topic}」生成综述的引言部分。

要求：
- 介绍「{topic}」的研究背景和重要性
- 概述该领域的发展历程和现状
- 指出现有研究的不足或空白
- 说明本综述的目的和结构
- 字数控制在800-1200字
- 每个重要观点需标注文献来源

{lit_refs}""",

            "methods": f"""请为主题「{topic}」生成综述的方法部分。

要求：
- 说明文献检索策略
- 描述纳入/排除标准
- 介绍文献筛选流程
- 说明质量评估方法（如适用）
- 字数控制在400-600字

当前已纳入的文献数量：{len(literature_list)}篇""",

            "main_body": f"""请为主题「{topic}」生成综述的主体部分。

要求：
- 所有内容必须围绕「{topic}」展开
- 按主题/时间/方法组织文献
- 对每篇引用的文献进行批判性分析和比较
- 识别研究趋势和模式
- 指出矛盾和争议
- 使用小节标题组织内容
- 每个观点、数据都必须标注文献来源 [编号]
- 确保论述逻辑清晰

{lit_refs}

重要：只能引用上述文献，禁止编造文献！""",

            "discussion": f"""请为主题「{topic}」生成综述的讨论部分。

要求：
- 综合分析关于「{topic}」的主要发现
- 讨论研究的理论意义
- 探讨在「{topic}」领域的实践应用价值
- 指出现有研究的局限
- 识别未来研究方向
- 字数控制在1000-1500字
- 讨论内容需有文献支持

{lit_refs}""",

            "conclusion": f"""请为主题「{topic}」生成综述的结论部分。

要求：
- 总结关于「{topic}」的核心发现
- 回应综述目的
- 强调研究贡献
- 提出针对「{topic}」的建议
- 字数控制在300-500字"""
        }
    
    def _format_literature_refs(self, literature_list: List[Dict]) -> str:
        """格式化文献引用列表"""
        if not literature_list:
            return "【注意】用户未提供参考文献，请使用通用性描述，避免具体引用。"
        
        refs = ["可引用的文献列表："]
        for lit in literature_list:
            refs.append(f"[{lit['index']}] {lit['authors']} ({lit['year']}). {lit['title']}")
        
        return "\n".join(refs)
    
    def get_full_generation_prompt(self, topic: str, paradigm: str, 
                                   literature_context: str, 
                                   literature_list: List[Dict],
                                   citation_format: str = "gb") -> str:
        """
        生成完整综述的Prompt
        """
        lit_constraint = self.get_literature_constraint_prompt(literature_list)
        
        return f"""## 综述主题
{topic}

## 写作范式要求
{paradigm}

{lit_constraint}

## 参考文献详细内容
{literature_context}

## 生成任务
请生成一篇完整的学术综述，包括：
1. 摘要（约300字）
2. 引言（约1000字）
3. 主体内容（按主题分章节，约3000-5000字）
4. 讨论（约1000字）
5. 结论（约400字）
6. 参考文献列表

## 重要提醒
- 所有内容必须紧扣主题「{topic}」
- 只能引用提供的参考文献，使用 [编号] 格式
- 禁止编造任何文献
- 每个重要观点都需要文献支持

请开始生成："""

    def save_prompt(self, name: str, content: str, metadata: Dict = None) -> str:
        """保存Prompt到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.json"
        filepath = os.path.join(self.prompts_dir, filename)
        
        data = {
            "name": name,
            "content": content,
            "created_at": timestamp,
            "metadata": metadata or {}
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filename
    
    def load_prompt(self, filename: str) -> Optional[Dict]:
        """加载保存的Prompt"""
        filepath = os.path.join(self.prompts_dir, filename)
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_saved_prompts(self) -> List[Dict]:
        """列出所有保存的Prompt"""
        prompts = []
        
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.json'):
                data = self.load_prompt(filename)
                if data:
                    prompts.append({
                        "filename": filename,
                        "name": data.get("name", ""),
                        "created_at": data.get("created_at", ""),
                    })
        
        return sorted(prompts, key=lambda x: x['created_at'], reverse=True)
    
    def delete_prompt(self, filename: str) -> bool:
        """删除保存的Prompt"""
        filepath = os.path.join(self.prompts_dir, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False


# 全局管理器实例
prompt_manager = PromptManager()