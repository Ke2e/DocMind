"""生成 DocMind W5 验收语料（确定性：同一版本脚本产出同一批文件）。

用法：
    .venv/Scripts/python.exe tools/gen_acceptance_corpus.py

输出目录：fixtures/acceptance/（已在 .gitignore 中，不入版本控制）
覆盖验收点：
    - SC-001 / SC-002  10MB 大文档上传与处理耗时
    - SC-005           损坏文件失败与重试
    - SC-009           四种受支持格式均可达"完成"
    - 边界：0 字节文件、不支持格式、扩展名与内容不符、无文本层扫描件

PDF 全部用底层 canvas 逐页绘制（不用 Platypus 自动分页），
以便确定性地控制页数与体积，并在末尾用 pypdf 自检文本层。
"""

from __future__ import annotations

import io
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "acceptance"

TTF_CANDIDATES = [Path(r"C:\Windows\Fonts\simhei.ttf"), Path(r"C:\Windows\Fonts\Deng.ttf")]
TTF = next((p for p in TTF_CANDIDATES if p.exists()), None)
if TTF is None:
    raise SystemExit("找不到中文字体（需要 simhei.ttf 或 Deng.ttf）")
pdfmetrics.registerFont(TTFont("CN", str(TTF)))

PAGE_W, PAGE_H = A4
MARGIN = 2 * 0.9 * 28.35  # ≈ 2cm
LINE_H = 17.0
CHARS_PER_LINE = 44

# --------------------------------------------------------------------------
# 语料正文：围绕 DocMind 自身的产品规格，含具体数字，
# 便于 W7 的 20-query 评测集直接复用出题
# --------------------------------------------------------------------------

SECTIONS: list[tuple[str, list[str]]] = [
    ("1. 产品概述", [
        "DocMind 是一个基于 Agentic RAG 的企业知识库问答平台。用户上传文档后，系统通过异步解析管线"
        "把文档转成可检索的文本片段；提问时走「查询改写 → 混合检索 → 自我评估 → 重试或生成」的智能体"
        "工作流，并以流式方式输出答案，答案中的每一处引用都能回溯到原文片段。",
        "平台面向单人名下的知识管理场景，第一版不提供团队共享空间。全部内容按用户维度隔离，"
        "文档与检索还必须额外按知识库维度过滤，两个维度同时生效。",
    ]),
    ("2. 术语表", [
        "分块（chunking）：把长文档切成适合检索的文本单元，默认每块 512 token，相邻块重叠 64 token。",
        "混合检索（hybrid retrieval）：同时使用向量召回与关键词召回，再用倒数排名融合算法合并两路结果。",
        "RRF（Reciprocal Rank Fusion）：融合公式为 score = Σ 1/(60 + rank)，其中 60 是平滑常数，rank 从 1 开始。",
        "重排（rerank）：对融合后的候选做交叉编码打分，取分数最高的 8 条进入上下文。",
        "引用对齐（citation alignment）：把答案按句拆分，逐句核对标注的引用片段是否真的支撑该句，"
        "相似度阈值 0.75。",
        "语义缓存：问题向量与缓存集中已有问题相似度超过 0.92 时直接返回历史答案，缓存有效期 24 小时。",
    ]),
    ("3. 文档摄取流程", [
        "摄取分为四个阶段：解析、清洗、分块、入库。文档状态依次经过「已接收、解析中、分块中、完成」，"
        "任一阶段出错则进入「失败」。状态只向终态推进，不允许回退。",
        "解析阶段按文件类型选择对应解析器：PDF 用 pypdf，Word 用 python-docx，Markdown 与纯文本直接读取。"
        "清洗阶段会去掉重复出现的页眉页脚、合并多余空行与空白字符。",
        "分块采用递归降级策略：优先按空行切分，切不动就按换行切分，再不行按中文句末标点切分，"
        "最后兜底按固定长度硬切。这一策略保证既不会出现超长块，也不会把一句话从中间劈开。",
        "单个文件的体积上限是 50MB。支持的类型包括 PDF、DOCX、MD 和 TXT 四种。",
    ]),
    ("4. 检索与生成", [
        "向量召回从向量库取前 50 条，关键词召回从关系库的全文索引取前 50 条，两路结果用 RRF 融合后"
        "交给重排模型精排，最终取前 8 条拼装进上下文。",
        "上下文拼装受 token 预算约束，超出预算时按重排分数从低到高丢弃。",
        "智能体工作流包含五个节点：改写、检索、评估、生成、校验。评估节点给检索结果与问题的相关性打"
        "0 到 1 的分数，低于 0.6 时回到检索节点重试，循环上限 3 次。",
        "校验节点负责引用对齐。若存在引用不达标的句子，会重写一次答案；重写后仍不达标，"
        "则返回固定话术「知识库中未找到充分依据」，而不是编造内容。",
    ]),
    ("5. 失败处理与重试", [
        "解析失败时系统自动重试 2 次，相邻两次重试之间有递进的等待时间。自动重试全部失败后，"
        "文档标记为失败并记录一句可读的原因，用户可以手动重试，手动重试次数上限为 3 次。",
        "损坏的文件通常在提交后 60 秒内被判定为失败。没有任何文本层的扫描件同样判定为失败，"
        "因为第一版不包含图片文字识别能力。",
        "后台执行进程若在处理中途崩溃，文档会停留在中间状态。系统通过定时扫描识别这类长期停留的任务，"
        "把它们重新调度或标记为失败，避免任务永久卡住。",
    ]),
    ("6. 权限与数据隔离", [
        "所有知识库与文档都归属到一个账号。请求身份只从登录凭证推导，不接受请求参数里声明的用户标识。",
        "文档必须归属且只能归属一个知识库。删除仍包含文档的知识库会被拒绝，并提示未清空的文档数量，"
        "以避免与正在执行的后台任务发生竞争。",
        "删除文档会级联清除它产生的全部片段与处理记录。对正在处理中的文档发起删除时，删除立即生效，"
        "后台任务不再向该文档写入数据。",
    ]),
    ("7. 部署与运行环境", [
        "平台以容器方式整体部署，包含应用服务、后台执行服务、定时调度服务、关系数据库、缓存、"
        "反向代理，以及向量检索所需的向量库、协调组件与对象存储，共九个容器。",
        "运行前需要在仓库根目录准备环境变量文件，填写数据库连接、缓存连接、登录凭证签名密钥，"
        "以及模型网关的地址、密钥与模型名称。真实密钥不允许提交到版本库。",
        "向量库的向量维度必须与嵌入模型输出维度一致。当前嵌入模型输出 1024 维，"
        "因此向量集合按 1024 维建立索引，使用余弦距离与 HNSW 索引，索引参数 M 为 16、"
        "efConstruction 为 200。",
    ]),
    ("8. 常见问题", [
        "问：上传一份两百页的文档大概需要多久？答：提交本身在一秒内返回，后台处理通常在五分钟内完成，"
        "具体耗时取决于文档版式与队列负载。",
        "问：能不能上传图片型的扫描件？答：当前版本不支持，会以失败告终并提示无法提取文本。",
        "问：同一个文件上传两次会怎样？答：按两份独立文档处理，不会互相覆盖。",
        "问：知识库删除后文档去哪了？答：知识库只有在清空文档后才能删除，因此不存在文档悬空的情况。",
        "问：为什么答案里会出现「知识库中未找到充分依据」？答：说明检索到的内容不足以支撑回答，"
        "系统选择拒答而不是编造。",
    ]),
]

COURSE_NOTES = """DocMind 学习笔记（原始草稿，未经排版）

一、为什么要自己实现检索管线
- 用现成的链式封装，出问题时只能猜是哪一环坏了
- 自己写的好处：每一环都能打印中间结果，RRF 前后、重排前后都能对比
- 面试时被问到"为什么召回top50而不是top10"，能拿数据回答

二、分块的三个坑
1. 只按固定长度切 -> 一句话被劈成两半，检索到半个句子没法用
2. 重叠太少 -> 关键信息正好落在边界上，两路都召不回来
3. 按标点切但要小心省略号，中文省略号是六个点，切了会碎

三、RRF 为什么要用排名倒数而不是分数
- 两路的分数量纲不一样，向量余弦相似度是 0-1，全文检索的分数没上界
- 直接加权求和会有一路被压死
- 用 1/(60+rank) 只吃排名信息，天然免疫量纲问题

四、状态机设计
uploaded -> parsing -> chunking -> ready
                       \\-> failed -> (手动重试) -> parsing
中间态停留太久 = 进程崩了，靠定时扫描兜底

五、容易忘的点
- 删除中的文档要挡住后台写回，否则出现幽灵片段
- 重试必须幂等，片段表加 (document_id, chunk_index) 唯一约束最省事
- 密钥绝不进 git，.env 从第一天就写进 .gitignore
"""


# --------------------------------------------------------------------------
# 非 PDF 语料
# --------------------------------------------------------------------------

def write_markdown(path: Path) -> None:
    lines = ["# DocMind 产品手册", "", "> 本文档用于知识库问答验收，包含具体参数与流程描述。", ""]
    for title, paras in SECTIONS:
        lines += [f"## {title}", ""]
        lines += [p + "\n" for p in paras]
    lines += ["## 附录：关键参数速查", "", "| 参数 | 取值 |", "| --- | --- |",
              "| 分块粒度 | 512 token |", "| 分块重叠 | 64 token |",
              "| 向量召回条数 | 50 |", "| 关键词召回条数 | 50 |",
              "| RRF 平滑常数 | 60 |", "| 重排保留条数 | 8 |",
              "| 评估重试阈值 | 0.6 |", "| 循环上限 | 3 次 |",
              "| 引用相似度阈值 | 0.75 |", "| 语义缓存阈值 | 0.92 |",
              "| 单文件上限 | 50MB |", "| 手动重试上限 | 3 次 |", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_txt(path: Path) -> None:
    path.write_text(COURSE_NOTES, encoding="utf-8")


def write_docx(path: Path) -> None:
    doc = Document()
    doc.add_heading("DocMind 产品规格说明书", level=0)
    p = doc.add_paragraph("版本 1.0 · 用于知识库问答验收")
    p.runs[0].font.size = Pt(9)
    for title, paras in SECTIONS:
        doc.add_heading(title, level=1)
        for t in paras:
            doc.add_paragraph(t)
    doc.add_heading("附录：关键参数", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    table.rows[0].cells[0].text = "参数"
    table.rows[0].cells[1].text = "取值"
    for k, v in [("分块粒度", "512 token"), ("分块重叠", "64 token"), ("向量召回", "50 条"),
                 ("关键词召回", "50 条"), ("RRF 平滑常数", "60"), ("重排保留", "8 条"),
                 ("评估阈值", "0.6"), ("循环上限", "3 次"), ("引用阈值", "0.75"),
                 ("缓存阈值", "0.92"), ("单文件上限", "50MB")]:
        row = table.add_row()
        row.cells[0].text = k
        row.cells[1].text = v
    doc.save(str(path))


# --------------------------------------------------------------------------
# 图片与 PDF 绘制
# --------------------------------------------------------------------------

def make_chart(rng: random.Random, size=(1400, 900)) -> bytes:
    """生成一张确定性的"链路示意图"，存成 JPEG 以撑起文件体积。"""
    img = Image.new("RGB", size, (248, 249, 252))
    d = ImageDraw.Draw(img)
    for i in range(0, size[1], 30):
        d.rectangle([0, i, size[0], i + 30],
                    fill=(235 + rng.randint(0, 12), 238 + rng.randint(0, 12), 245 + rng.randint(0, 8)))
    font = ImageFont.truetype(str(TTF), 34)
    small = ImageFont.truetype(str(TTF), 26)
    labels = ["用户请求", "查询改写", "混合检索", "RRF 融合", "重排精排", "生成答案", "引用校验"]
    x = 60
    for i, text in enumerate(labels):
        w, y = 170, 120 + (i % 4) * 160
        d.rectangle([x, y, x + w, y + 96], fill=(255, 255, 255), outline=(120, 140, 200), width=3)
        d.text((x + 14, y + 26), text, font=small, fill=(40, 50, 80))
        if i < len(labels) - 1:
            d.line([x + w, y + 48, x + w + 40, y + 48], fill=(150, 160, 190), width=3)
        x += w + 40
        if x > size[0] - 220:
            x = 60
    d.text((60, 40), f"图：检索与生成链路示意（v{rng.randint(1000, 9999)}）", font=font, fill=(30, 40, 70))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _wrap(text: str, width: int = CHARS_PER_LINE) -> list[str]:
    """按字符数折行（中文等宽，够用）。"""
    return [text[i:i + width] for i in range(0, len(text), width)] or [""]


def render_pdf(path: Path, pages: list[list[tuple]], title: str) -> None:
    """pages 中每一页是若干绘制指令：("h1"/"h2"/"p", 文本) 或 ("img", bytes)。"""
    c = rl_canvas.Canvas(str(path), pagesize=A4, pageCompression=0)
    c.setTitle(title)
    for items in pages:
        y = PAGE_H - MARGIN
        for kind, payload in items:
            if kind == "img":
                w = PAGE_W - 2 * MARGIN
                h = w * 0.64
                if y - h < MARGIN:
                    y = MARGIN + h
                c.drawImage(ImageReader(io.BytesIO(payload)), MARGIN, y - h, width=w, height=h)
                y -= h + 12
                continue
            size = {"h1": 18, "h2": 13.5, "p": 10.5}[kind]
            gap = {"h1": 12, "h2": 9, "p": 6}[kind]
            c.setFont("CN", size)
            for line in _wrap(payload, CHARS_PER_LINE if kind == "p" else 30):
                if y < MARGIN + LINE_H:
                    break
                c.drawString(MARGIN, y, line)
                y -= LINE_H if kind == "p" else LINE_H + 3
            y -= gap
        c.showPage()
    c.save()


def intro_pages() -> list[list[tuple]]:
    pages: list[list[tuple]] = [[("h1", "DocMind 产品手册"),
                                 ("p", "本文档由 tools/gen_acceptance_corpus.py 生成，用于摄取管线验收。")]]
    for title, paras in SECTIONS:
        pages.append([("h2", title)] + [("p", t) for t in paras])
    return pages


def appendix_page(i: int, rng: random.Random) -> list[tuple]:
    return [("h2", f"附录 A-{i + 1}　参数与链路图解"),
            ("p", "下图展示一次完整的检索问答链路。每一环的输入输出都会被记录，便于对比优化前后的效果。"
                  "分块粒度、召回条数、融合常数与重排保留条数都可以在检索测试台在线调整。"),
            ("img", make_chart(rng))]


def write_manual(path: Path, target_bytes: int | None = None, seed: int = 20260912) -> None:
    """生成手册 PDF。给 target_bytes 时先探针实测单页体积，再反推页数并收敛。"""
    if not target_bytes:
        rng = random.Random(seed)
        render_pdf(path, intro_pages() + [appendix_page(0, rng)], "DocMind 产品手册")
        return

    probe = 3
    rng = random.Random(seed)
    render_pdf(path, [appendix_page(i, rng) for i in range(probe)], "探针")
    per_page = max(path.stat().st_size / probe, 1)
    blocks = max(1, int(target_bytes / per_page * 1.05) + 1)

    for attempt in range(1, 5):
        rng = random.Random(seed)
        pages = intro_pages() + [appendix_page(i, rng) for i in range(blocks)]
        render_pdf(path, pages, "DocMind 产品手册（大文件版）")
        size = path.stat().st_size
        print(f"  大文件第 {attempt} 轮：{blocks} 张图 → {len(pages)} 页 / {size:,} 字节")
        if size >= target_bytes or attempt == 4:
            break
        blocks = max(blocks + 1, int(blocks * target_bytes / max(size, 1) * 1.05) + 1)


def write_scanned(path: Path) -> None:
    """无文本层 PDF：整页是位图，模拟扫描件。"""
    img = Image.new("RGB", (1240, 1754), (252, 251, 248))
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(str(TTF), 44)
    mid = ImageFont.truetype(str(TTF), 30)
    d.text((90, 110), "DocMind 产品手册（影印件）", font=big, fill=(30, 30, 30))
    y = 220
    for line in ["本页为图像扫描件，不含可选中的文字层。",
                 "用于验证无文本层文档会被判定为失败。",
                 "分块粒度 512 token，重叠 64 token。",
                 "向量召回 50 条，关键词召回 50 条，重排保留 8 条。",
                 "引用对齐相似度阈值 0.75。"]:
        d.text((90, y), line, font=mid, fill=(45, 45, 45))
        y += 70
    d.rectangle([90, y + 40, 1150, y + 500], outline=(120, 120, 120), width=3)
    d.text((110, y + 260), "图 1　检索链路示意（略）", font=mid, fill=(90, 90, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    render_pdf(path, [[("img", buf.getvalue())]], "扫描件样例")


def write_corrupted(src: Path, dst: Path) -> None:
    """把正常 PDF 截断并破坏交叉引用表，模拟损坏文件。"""
    raw = src.read_bytes()
    broken = bytearray(raw[: int(len(raw) * 0.55)])
    marker = broken.rfind(b"startxref")
    if marker > 0:
        broken[marker:] = b"startxref\n0\n%%EOF\n"
    dst.write_bytes(bytes(broken))


def verify() -> list[tuple[str, int, str]]:
    import pypdf

    rows = []
    for f in sorted(OUT.iterdir()):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            r = pypdf.PdfReader(str(f))
            text = "".join((p.extract_text() or "") for p in r.pages[:3])
            note = f"{len(text):,} 字符可抽取 / 共 {len(r.pages)} 页"
        except Exception as e:  # noqa: BLE001
            note = f"无法读取（符合预期）：{type(e).__name__}"
        rows.append((f.name, f.stat().st_size, note))
    return rows


EXPECTS = {
    "docmind_handbook.md": "支持格式，应处理成功",
    "docmind_course_notes.txt": "支持格式，应处理成功",
    "docmind_product_spec.docx": "支持格式，应处理成功",
    "docmind_manual.pdf": "支持格式，应处理成功（SC-009）",
    "docmind_manual_10mb.pdf": "大文件，提交需秒级返回（SC-001/002）",
    "scanned_no_text_layer.pdf": "无文本层，应判定失败",
    "corrupted.pdf": "损坏文件，应自动重试 2 次后失败（SC-005）",
    "mislabeled_image.pdf": "扩展名与内容不符，应判定失败",
    "empty.txt": "0 字节，应在提交阶段拒绝或处理失败",
    "unsupported_sample.csv": "不支持格式，应在提交阶段拒绝",
}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    write_markdown(OUT / "docmind_handbook.md")
    write_txt(OUT / "docmind_course_notes.txt")
    write_docx(OUT / "docmind_product_spec.docx")
    write_manual(OUT / "docmind_manual.pdf")
    write_manual(OUT / "docmind_manual_10mb.pdf", target_bytes=10 * 1024 * 1024)
    write_scanned(OUT / "scanned_no_text_layer.pdf")
    write_corrupted(OUT / "docmind_manual.pdf", OUT / "corrupted.pdf")

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 120, 90)).save(buf, format="PNG")
    (OUT / "mislabeled_image.pdf").write_bytes(buf.getvalue())
    (OUT / "empty.txt").write_bytes(b"")
    (OUT / "unsupported_sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    print(f"\n输出目录：{OUT}\n")
    print(f"{'文件':<32}{'大小':>12}   预期处理结果")
    print("-" * 96)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:<32}{f.stat().st_size:>12,}   {EXPECTS.get(f.name, '')}")

    print("\nPDF 文本层自检（pypdf 抽取前 3 页）：")
    for name, size, note in verify():
        print(f"  {name:<32}{note}")

    big = (OUT / "docmind_manual_10mb.pdf").stat().st_size
    print(f"\n大文件 {big / 1024 / 1024:.2f} MB（目标 ≥ 10 MB）")


if __name__ == "__main__":
    main()
