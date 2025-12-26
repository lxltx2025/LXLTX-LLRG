"""
文献处理模块（增强版）
支持PDF和TXT格式的批量处理，增强文献元数据提取
"""
import fitz  # PyMuPDF
import os
import re
import hashlib
from typing import List, Dict, Tuple, Callable, Optional
from config import Config


class DocumentProcessor:
    def __init__(self):
        self.max_chars_per_doc = Config.BATCH_CONFIG.get("max_chars_per_file", 50000)
        self.max_total_chars = Config.BATCH_CONFIG.get("max_total_chars", 150000)
        
    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, Dict]:
        """
        从PDF文件中提取文本内容和元数据
        """
        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            
            # 提取元数据
            metadata = {
                "page_count": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "keywords": doc.metadata.get("keywords", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
            }
            
            for page_num, page in enumerate(doc):
                text = page.get_text("text")
                text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
            
            doc.close()
            full_text = "\n".join(text_parts)
            
            # 尝试从文本中提取更多信息
            if not metadata["title"]:
                metadata["title"] = self._extract_title_from_text(full_text)
            if not metadata["author"]:
                metadata["author"] = self._extract_authors_from_text(full_text)
            
            # 提取年份
            metadata["year"] = self._extract_year_from_text(full_text)
            
            # 限制文本长度
            if len(full_text) > self.max_chars_per_doc:
                full_text = full_text[:self.max_chars_per_doc] + "\n\n[文本已截断...]"
            
            return full_text, metadata
            
        except Exception as e:
            return f"PDF解析错误: {str(e)}", {"error": str(e)}
    
    def extract_text_from_txt(self, txt_path: str) -> Tuple[str, Dict]:
        """
        从TXT文件中提取文本内容
        """
        try:
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            text = None
            
            for encoding in encodings:
                try:
                    with open(txt_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                return "无法解析文件编码", {"error": "encoding error"}
            
            # 从文本提取元数据
            metadata = {
                "char_count": len(text),
                "line_count": text.count('\n') + 1,
                "title": self._extract_title_from_text(text),
                "author": self._extract_authors_from_text(text),
                "year": self._extract_year_from_text(text),
            }
            
            if len(text) > self.max_chars_per_doc:
                text = text[:self.max_chars_per_doc] + "\n\n[文本已截断...]"
            
            return text, metadata
            
        except Exception as e:
            return f"TXT解析错误: {str(e)}", {"error": str(e)}
    
    def _extract_title_from_text(self, text: str) -> str:
        """从文本开头提取可能的标题"""
        lines = text.split('\n')
        for line in lines[:15]:
            line = line.strip()
            # 标题通常在10-200字符之间，不以数字开头
            if 10 < len(line) < 200 and not line[0].isdigit():
                # 排除常见的非标题行
                skip_patterns = ['abstract', 'introduction', 'keywords', '摘要', '引言', '关键词']
                if not any(p in line.lower() for p in skip_patterns):
                    return line
        return ""
    
    def _extract_authors_from_text(self, text: str) -> str:
        """从文本提取作者信息"""
        lines = text.split('\n')
        for i, line in enumerate(lines[:20]):
            line = line.strip()
            # 寻找作者行的特征
            if any(keyword in line.lower() for keyword in ['author', '作者', 'by']):
                # 返回下一行或当前行的作者信息
                author_line = line.split(':')[-1].strip() if ':' in line else line
                if author_line:
                    return author_line
            # 检测姓名模式（如 "Zhang Wei, Li Ming"）
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+(\s*,\s*[A-Z][a-z]+\s+[A-Z][a-z]+)*$', line):
                return line
        return ""
    
    def _extract_year_from_text(self, text: str) -> str:
        """从文本提取发表年份"""
        # 匹配4位年份（1900-2099）
        years = re.findall(r'\b(19|20)\d{2}\b', text[:5000])
        if years:
            # 返回最常见的年份，通常是发表年
            from collections import Counter
            year_counts = Counter(years)
            return year_counts.most_common(1)[0][0]
        return ""
    
    def extract_text(self, file_path: str) -> Tuple[str, Dict]:
        """根据文件类型自动选择解析方法"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif ext == '.txt':
            return self.extract_text_from_txt(file_path)
        else:
            return f"不支持的文件格式: {ext}", {"error": "unsupported format"}
    
    def extract_structure(self, text: str) -> Dict:
        """分析文本结构"""
        structure = {
            "title": "",
            "abstract": "",
            "sections": [],
            "references_count": 0,
            "key_findings": []
        }
        
        lines = text.split('\n')
        
        # 提取标题
        for line in lines[:10]:
            line = line.strip()
            if 10 < len(line) < 200:
                structure["title"] = line
                break
        
        # 提取摘要
        abstract_patterns = [r'abstract', r'摘\s*要', r'summary']
        in_abstract = False
        abstract_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            if any(re.search(p, line_lower) for p in abstract_patterns):
                in_abstract = True
                continue
            if in_abstract:
                if re.match(r'^(introduction|引言|1\.|keywords|关键词)', line_lower):
                    break
                abstract_lines.append(line)
        
        structure["abstract"] = ' '.join(abstract_lines)[:1000]
        
        # 提取关键发现/结论
        conclusion_patterns = [r'conclusion', r'结论', r'findings', r'结果']
        in_conclusion = False
        conclusion_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            if any(re.search(p, line_lower) for p in conclusion_patterns):
                in_conclusion = True
                continue
            if in_conclusion:
                if len(conclusion_lines) >= 10:
                    break
                if line.strip():
                    conclusion_lines.append(line.strip())
        
        structure["key_findings"] = conclusion_lines[:5]
        
        # 识别章节
        section_patterns = [
            r'^(\d+\.?\s+)(.+)$',
            r'^(第[一二三四五六七八九十]+[章节])\s*(.+)$',
            r'^(Introduction|Methods?|Results?|Discussion|Conclusion)s?\s*$',
        ]
        
        for line in lines:
            line = line.strip()
            for pattern in section_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match and len(line) < 100:
                    structure["sections"].append(line)
                    break
        
        # 统计参考文献数量
        ref_count = len(re.findall(r'\[\d+\]', text))
        structure["references_count"] = ref_count
        
        return structure
    
    def process_single_file(self, file_path: str, file_id: str = None) -> Dict:
        """处理单个文件，生成完整的文献信息"""
        filename = os.path.basename(file_path)
        text, metadata = self.extract_text(file_path)
        structure = self.extract_structure(text)
        
        # 生成唯一ID（如果没有提供）
        if not file_id:
            file_id = hashlib.md5(file_path.encode()).hexdigest()[:8]
        
        return {
            "id": file_id,
            "filename": filename,
            "path": file_path,
            "text": text,
            "structure": structure,
            "metadata": metadata,
            "char_count": len(text),
            "format": os.path.splitext(filename)[1].lower()[1:],
            # 用于引用的标准化信息
            "citation_info": {
                "id": file_id,
                "title": metadata.get("title") or structure.get("title") or filename,
                "authors": metadata.get("author", "未知作者"),
                "year": metadata.get("year", "n.d."),
                "abstract": structure.get("abstract", ""),
                "key_findings": structure.get("key_findings", []),
            }
        }
    
    def process_multiple_files(self, file_paths: List[str], 
                                progress_callback: Optional[Callable] = None) -> List[Dict]:
        """批量处理多个文件"""
        results = []
        total = len(file_paths)
        
        for i, path in enumerate(file_paths):
            filename = os.path.basename(path)
            
            if progress_callback:
                progress_callback(i, total, filename, "processing")
            
            result = self.process_single_file(path)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total, filename, "completed")
        
        return results
    
    def prepare_for_analysis(self, file_data_list: List[Dict], 
                             max_total_chars: Optional[int] = None) -> str:
        """准备用于大模型分析的文本内容"""
        if max_total_chars is None:
            max_total_chars = self.max_total_chars
            
        combined_parts = []
        chars_per_doc = max_total_chars // max(len(file_data_list), 1)
        
        for i, file_data in enumerate(file_data_list, 1):
            text = file_data["text"]
            if len(text) > chars_per_doc:
                text = text[:chars_per_doc] + "\n[...内容已截断...]"
            
            combined_parts.append(f"""
========== 文献 {i}: {file_data['filename']} ==========
{text}
""")
        
        return "\n".join(combined_parts)
    
    def prepare_literature_context(self, file_data_list: List[Dict], 
                                   citation_format: str = "gb") -> Tuple[str, List[Dict]]:
        """
        准备文献上下文，用于生成时强制引用
        返回：(上下文文本, 引用列表)
        """
        context_parts = []
        citation_list = []
        
        for i, file_data in enumerate(file_data_list, 1):
            citation_info = file_data.get("citation_info", {})
            
            # 构建引用条目
            citation_entry = {
                "index": i,
                "id": citation_info.get("id", f"ref{i}"),
                "title": citation_info.get("title", file_data["filename"]),
                "authors": citation_info.get("authors", "未知作者"),
                "year": citation_info.get("year", "n.d."),
                "filename": file_data["filename"],
                "abstract": citation_info.get("abstract", "")[:500],
                "key_findings": citation_info.get("key_findings", []),
            }
            citation_list.append(citation_entry)
            
            # 构建上下文
            text = file_data["text"]
            if len(text) > 8000:
                text = text[:8000] + "\n[...内容已截断...]"
            
            context_parts.append(f"""
【文献{i}】
- 标题: {citation_entry['title']}
- 作者: {citation_entry['authors']}
- 年份: {citation_entry['year']}
- 摘要: {citation_entry['abstract']}
- 主要发现: {'; '.join(citation_entry['key_findings'][:3]) if citation_entry['key_findings'] else '无'}

正文内容:
{text}
""")
        
        return "\n".join(context_parts), citation_list
    
    def get_summary(self, file_data_list: List[Dict]) -> Dict:
        """获取批量处理结果的摘要信息"""
        total_chars = sum(f["char_count"] for f in file_data_list)
        formats = {}
        for f in file_data_list:
            fmt = f.get("format", "unknown")
            formats[fmt] = formats.get(fmt, 0) + 1
        
        return {
            "file_count": len(file_data_list),
            "total_chars": total_chars,
            "formats": formats,
            "files": [{"name": f["filename"], "chars": f["char_count"]} for f in file_data_list]
        }


# 全局实例
doc_processor = DocumentProcessor()
pdf_processor = doc_processor
PDFProcessor = DocumentProcessor