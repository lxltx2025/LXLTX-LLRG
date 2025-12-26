# LXLTX-LLRG: Local Literature Review Generator

A local Large Language Model (LLM) powered academic literature review generation system. Built on Ollama local deployment, LXLTX-LLRG provides researchers with an efficient, privacy-preserving solution for generating standardized academic reviews.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technical Architecture](#technical-architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Features](#advanced-features)
- [Changelog](#changelog)
- [Contributing](#contributing)

---

## Overview

LXLTX-LLRG employs a **four-stage progressive generation workflow** to ensure logical coherence and academic rigor:

1. **Paradigm Analysis** — Analyze writing patterns and academic standards from exemplary reviews
2. **Literature Processing** — Batch process references and extract structured metadata
3. **Framework Generation** — Generate hierarchical review outlines based on topic and literature
4. **Content Generation** — Generate section-by-section or full-document reviews meeting academic standards

---

## Features

### 📖 Writing Paradigm Analysis
- Upload exemplary review papers (PDF/TXT) as reference samples
- Automatically parse academic structure, argumentation logic, and writing style
- Extract reusable academic writing templates

> Implementation: `app.py:639-694`

### 📚 Reference Management
- Batch upload references (PDF/TXT) for large-scale processing
- Automatic metadata extraction (title, author, year, abstract, keywords, etc.)
- Build standardized literature pools with traceable citation sources
- Integrated deduplication and hash verification for uniqueness

> Implementation: `app.py:31-120`

### 🏗️ Intelligent Framework Generation
- Generate academically compliant review frameworks based on research topic and writing paradigm
- Smart citation distribution planning with optimized argumentation chains
- Support for multiple citation formats (GB/T 7714, APA, MLA, Harvard)

> Implementation: `app.py:748-850`

### ✍️ Review Content Generation
| Mode | Description |
|------|-------------|
| **Section-by-Section** | Generate and optimize individual sections (Abstract, Introduction, Methods, Results, Discussion, Conclusion) |
| **Full Document** | One-click complete review generation with cross-section logical coherence |
| **Real-time Streaming** | WebSocket-based visualization with instant adjustment support |
| **Citation Verification** | Automatic detection and correction of invalid citations |

> Implementation: `app.py:852-1000`

### 📤 Multi-format Export
- Export to Markdown, Word (.docx), HTML, PDF
- Automatic standardized reference list attachment
- Metadata and timestamp for version management

> Implementation: `app.py:536-578`

---

## Technical Architecture

### Backend Stack

| Component | Technology |
|-----------|------------|
| Web Framework | Flask + Flask-SocketIO |
| LLM Service | Ollama (local deployment) |
| PDF Processing | PyMuPDF |
| Word Export | python-docx |
| PDF Export | WeasyPrint (optional) |

> Configuration: `app.py:5-17`

### Core Modules

| Module | File | Description |
|--------|------|-------------|
| **Ollama Client** | `utils/ollama_client.py:10-75` | LLM communication, model scanning, VRAM optimization, streaming/sync generation |
| **Document Processor** | `utils/pdf_processor.py:13-96` | PDF/TXT text extraction, metadata parsing, hierarchical structure analysis |
| **Prompt Manager** | `utils/prompt_manager.py:12-85` | Academic system prompts, topic constraints, section-specific prompts, template management |
| **Export Handler** | `utils/export_handler.py:14-72` | Multi-format export, academic formatting, metadata embedding |

---

## Requirements

### System Requirements
- **OS**: Linux / macOS / Windows (Linux/macOS recommended for optimal performance)
- **Python**: 3.8+
- **VRAM**: ≥ 8GB (14B models require ≥ 16GB)

### Required Dependencies

**1. Ollama Service**
- Purpose: Local LLM deployment and inference
- Download: https://ollama.ai
- Prerequisite: At least one open-source LLM (recommended: qwen2, llama3, mistral)

**2. Python Packages**
```
Flask
Flask-SocketIO
eventlet
requests
PyMuPDF (fitz)
python-docx
markdown
weasyprint  # Optional, for PDF export
```

---

## Installation

### Step 1: Install Ollama

```bash
# Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download installer from: https://ollama.ai/download
```

### Step 2: Download LLM Model

Choose based on your VRAM capacity:

```bash
# Recommended (7B, balanced performance)
ollama pull qwen2:7b

# High-performance (14B, requires ≥16GB VRAM)
ollama pull qwen2:14b

# Alternatives
ollama pull llama3:8b
```

### Step 3: Start Ollama Service

```bash
ollama serve
```

Default endpoint: `http://localhost:11434`

### Step 4: Clone Repository

```bash
git clone https://github.com/lxltx2025/LXLTX-LLRG.git
cd LXLTX-LLRG
```

### Step 5: Create Virtual Environment (Recommended)

```bash
# Create
python3 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### Step 6: Install Dependencies

```bash
# Core dependencies
pip install flask flask-socketio eventlet requests pymupdf python-docx markdown

# Optional: PDF export
pip install weasyprint
```

### Step 7: Configure System

Edit `config.py` in the project root:
- Ollama service address (default: `http://localhost:11434`): `config.py:20-22`
- See [Configuration](#configuration) for additional options

### Step 8: Launch System

```bash
# Linux/macOS
chmod +x start.sh
./start.sh

# Windows
python app.py
```

Access the web interface at: `http://127.0.0.1:5000`

> Startup script: `start.sh:1-39`

---

## Usage

### Step 1: Topic & Citation Format Setup

1. Enter your research topic (e.g., "Advances in Deep Learning for Medical Image Segmentation")
2. Select target citation format (GB/T 7714, APA, MLA, Harvard)
3. Click **Confirm Topic**

> Implementation: `app.py:178-203` | Citation config: `config.py:47-73`

### Step 2: Writing Paradigm Analysis

1. Upload 1-5 exemplary review papers (PDF/TXT) from your field
2. Click **Analyze Writing Paradigm**
3. System generates reusable academic writing templates

**Constraints:**
- Max 100 files per upload, 50,000 characters per file
- Supported formats: PDF (non-scanned), TXT (UTF-8)

> Config: `config.py:40-45`

### Step 3: Reference Upload & Processing

1. Navigate to **References** tab
2. Upload literature files (PDF/TXT)
3. Click **Analyze References** — System automatically:
   - Extracts metadata (title, author, year, abstract)
   - Identifies key findings
   - Generates citation indices

> ⚠️ **Academic Integrity**: Only user-uploaded literature is cited. No fabricated citations.
> Implementation: `app.py:356-400`

### Step 4: Framework Generation

1. Complete Steps 1-3
2. Click **Generate Review Framework**
3. Review the hierarchical structure with chapter outlines and citation distribution

### Step 5: Content Generation

**Option A: Section-by-Section (Recommended)**
1. Select target section (Abstract, Introduction, Methods, Body, Discussion, Conclusion)
2. Click **Generate** for that section
3. Edit and optimize before proceeding

**Option B: Full Document**
1. Click **Generate Complete Review**
2. System generates all sections sequentially

> Implementation: `app.py:880-963`

### Step 6: Export

1. Review generated content
2. Select export format (Markdown/Word/HTML/PDF)
3. Click **Export** — Files saved to `outputs/` directory

> Implementation: `app.py:546-553`

---

## Project Structure

```
LXLTX-LLRG/
├── app.py                  # Main application (core logic)
├── config.py               # System configuration
├── start.sh / start.bat    # Cross-platform startup scripts
├── utils/                  # Core utility modules
│   ├── ollama_client.py    # Ollama service communication
│   ├── pdf_processor.py    # Document parsing & metadata extraction
│   ├── prompt_manager.py   # Academic prompt generation & management
│   └── export_handler.py   # Multi-format export handling
├── templates/              # Frontend templates
│   └── index.html          # Main interface
├── static/                 # Static assets
│   ├── css/                # Stylesheets
│   └── js/                 # JavaScript
├── uploads/                # Uploaded files (auto-created)
├── outputs/                # Exported files (auto-created)
└── prompts/                # Custom prompt templates (auto-created)
```

---

## Configuration

### Model Inference Settings

Located in `config.py:23-38`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `context_length` | 4096 | Context window size |
| `temperature` | 0.3 | Generation randomness (0.2-0.4 recommended for academic writing) |
| `max_tokens` | 2048 | Maximum tokens per generation |

### Batch Processing Limits

Located in `config.py:40-45`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_UPLOAD_FILES` | 100 | Max files per upload |
| `MAX_FILE_SIZE` | 50000 | Max characters per file |
| `SUPPORTED_FORMATS` | `{'pdf', 'txt'}` | Allowed file formats |

### Citation Format Settings

Located in `config.py:47-73`:
- Citation annotation format (e.g., `[1]`, `(Author, Year)`)
- Reference list sorting rules
- Metadata display fields (DOI, journal name, etc.)

---

## Troubleshooting

### Q1: Ollama Connection Failed
- Verify Ollama is running: `ollama serve`
- Check `config.py` service address (default: `http://localhost:11434`)
- Ensure firewall allows port 11434

### Q2: PDF Parsing Failed
- Confirm PDF is text-based (not scanned; use OCR for scanned documents)
- Check for file corruption
- Convert complex PDFs to TXT format

### Q3: Poor Generation Quality
- Use larger models (e.g., qwen2:14b instead of qwen2:7b)
- Add more high-quality paradigm documents
- Include more topic-relevant references
- Lower `temperature` for increased rigor

---

## Advanced Features

### Custom Prompt Templates

Create, save, and reuse personalized prompts for discipline-specific writing styles.

> Implementation: `prompt_manager.py:246-262`

- Edit custom prompts in **Advanced Settings**
- Assign prompts to specific sections
- Select saved prompts during generation

### Conversational Generation Mode

Multi-turn dialogue with the LLM for deep content optimization.

> Implementation: `ollama_client.py:125-158`

- Provide real-time modification requests during generation
- System maintains conversation history for coherent revisions
- Export dialogue logs for review

---

## System Highlights

| Feature | Description |
|---------|-------------|
| 🔒 **Fully Local** | All processing runs locally — no data leakage |
| 📖 **Academic Rigor** | Traceable citations, no fabrication |
| ⚡ **Real-time Feedback** | WebSocket streaming with instant adjustments |
| 🔧 **Highly Configurable** | Multi-model, multi-format, custom prompts |
| 📦 **Batch Processing** | Large-scale literature upload and parsing |
| 📄 **Universal Export** | All major academic document formats |

---

## Changelog

### v2.2 (Current - Bugfix Release)

- Fixed frontend button display logic issues
- Enhanced reference citation restriction mechanism
- Optimized literature pool management (reduced memory usage)
- Improved LLM inference memory efficiency

> Implementation: `app.py:1-4`

---

## Team Introduction

The LXLTX-Lab is a research team composed mainly of masters and doctors from China and abroad, covering mainstream Medical AI research fields such as radiomics, pathomics, and genomics.

Explore our query system for over 980 public medical image datasets and replay recordings of the latest medical-engineering cross-disciplinary frontier forums!

Our mission is to bring together top talents worldwide, build a Medical AI ecosystem, and promote the translation of Medical AI from the laboratory to clinical practice. We look forward to your joining!

For more information, visit our official website: https://www.lxltx.site/