# fixtures/ —— 测试与验收数据

## acceptance/（由脚本生成，不入版本控制）

`fixtures/acceptance/` 下全部文件由 `tools/gen_acceptance_corpus.py` 确定性地生成，
**不提交到 git**（含 10MB 级二进制）。缺失或想重建时执行：

```bash
.venv/Scripts/python.exe tools/gen_acceptance_corpus.py
```

首次使用需先准备依赖（已随仓库 `.gitignore` 排除 `.venv/`）：

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install reportlab python-docx pillow pypdf
```

### 文件清单与预期结果

| 文件 | 用途 | 预期处理结果 |
| --- | --- | --- |
| `docmind_handbook.md` | 支持格式样例（含表格） | 成功，片段可还原 |
| `docmind_course_notes.txt` | 支持格式样例（纯文本） | 成功 |
| `docmind_product_spec.docx` | 支持格式样例（标题层级 + 表格） | 成功 |
| `docmind_manual.pdf` | 支持格式样例（多页文本） | 成功 |
| `docmind_manual_10mb.pdf` | 大文件，验收提交不阻塞（SC-001/002） | 成功；提交 ≤ 2s 返回受理 |
| `scanned_no_text_layer.pdf` | 无文本层扫描件 | 失败，原因说明无法提取文本 |
| `corrupted.pdf` | 截断并破坏交叉引用表 | 自动重试 2 次后失败，附可读原因（SC-005） |
| `mislabeled_image.pdf` | 内容是 PNG 但扩展名为 .pdf | 失败 |
| `empty.txt` | 0 字节 | 提交阶段拒绝或处理失败 |
| `unsupported_sample.csv` | 不在支持列表内的格式 | 提交阶段拒绝，不产生文档记录 |

### 语料正文说明

正文内容围绕 DocMind 自身的产品规格撰写（分块 512/64、召回 50、RRF 常数 60、重排保留 8、
评估阈值 0.6、引用阈值 0.75、缓存阈值 0.92、单文件上限 50MB 等具体数字），
目的是让 W7 的 20-query 评测集可以直接基于这批语料出题，且答案可客观核对。

`docmind_manual.pdf` 是五个 PDF 的截断源：`corrupted.pdf` 由它截取前 55% 并改写 `startxref` 生成。
因此脚本内两个文件的生成有先后依赖，不要单独重排顺序。
