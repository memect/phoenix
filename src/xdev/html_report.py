"""
xdev HTML 报告生成
"""

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .evaluation_result import EvaluationResult


def _load_pdf_links(base_url: str, set_id: str) -> dict[str, str]:
    try:
        from evaluator.standards.dataset_app import DatasetApp
        app = DatasetApp(base_url=base_url)
        data = app.fetch_documents_info(set_id)
        return {item['id']: item['pdf_link'] for item in data.get('data', [])
                if item.get('id') and item.get('pdf_link')}
    except Exception as e:
        print(f"无法加载 PDF 链接: {e}")
        return {}


def _escape(value: Any) -> str:
    if value is None:
        return '<span class="null">null</span>'
    return html.escape(str(value))


def _format_value(value: Any) -> str:
    if value is None:
        return '<span class="null">null</span>'
    if isinstance(value, (dict, list)):
        try:
            return f'<pre class="json">{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre>'
        except Exception:
            return f'<pre>{html.escape(str(value))}</pre>'
    return html.escape(str(value))


def _percent(value: float) -> str:
    return f"{value:.1%}"


def _accuracy_class(accuracy: float) -> str:
    if accuracy >= 0.9:
        return "accuracy-high"
    elif accuracy >= 0.7:
        return "accuracy-medium"
    return "accuracy-low"


CSS_STYLES = """
:root {
    --bg-color: #f8fafc;
    --card-bg: #ffffff;
    --text-color: #1e293b;
    --text-muted: #64748b;
    --border-color: #e2e8f0;
    --success-color: #10b981;
    --error-color: #ef4444;
    --warning-color: #f59e0b;
    --info-color: #3b82f6;
}
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: var(--bg-color); color: var(--text-color); line-height: 1.6; margin: 0; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
h1, h2, h3 { margin-top: 0; font-weight: 600; }
h1 { font-size: 1.75rem; margin-bottom: 1.5rem; padding-bottom: 0.75rem; border-bottom: 2px solid var(--border-color); }
h2 { font-size: 1.25rem; margin-bottom: 1rem; }
.card { background: var(--card-bg); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1.5rem; margin-bottom: 1.5rem; }
.meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
.meta-item { display: flex; flex-direction: column; }
.meta-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.25rem; }
.meta-value { font-size: 1rem; font-weight: 500; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.stat-card { background: var(--card-bg); border-radius: 8px; padding: 1.25rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.stat-value { font-size: 2rem; font-weight: 700; line-height: 1.2; }
.stat-value.accuracy-high { color: var(--success-color); }
.stat-value.accuracy-medium { color: var(--warning-color); }
.stat-value.accuracy-low { color: var(--error-color); }
.stat-label { font-size: 0.875rem; color: var(--text-muted); margin-top: 0.25rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border-color); }
th { background: var(--bg-color); font-weight: 600; color: var(--text-muted); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }
tr:hover { background: var(--bg-color); }
.text-right { text-align: right; }
.detail-card { background: var(--card-bg); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1rem; overflow: hidden; }
.detail-header { padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); cursor: pointer; }
.detail-header:hover { background: var(--bg-color); }
.detail-id { font-weight: 600; font-family: monospace; font-size: 0.875rem; }
.detail-badge { padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.badge-correct { background: #d1fae5; color: #065f46; }
.badge-incorrect { background: #fee2e2; color: #991b1b; }
.badge-error { background: #fef3c7; color: #92400e; }
.detail-body { padding: 1.5rem; display: none; }
.detail-body.expanded { display: block; }
.detail-section { margin-bottom: 1.5rem; }
.detail-section:last-child { margin-bottom: 0; }
.detail-section h3 { font-size: 0.875rem; color: var(--text-muted); margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.field-comparison { border: 1px solid var(--border-color); border-radius: 6px; overflow: hidden; }
.field-row { display: grid; grid-template-columns: 150px 1fr 1fr; border-bottom: 1px solid var(--border-color); }
.field-row:last-child { border-bottom: none; }
.field-name { background: var(--bg-color); padding: 0.75rem; font-weight: 500; font-size: 0.875rem; display: flex; align-items: center; gap: 0.5rem; }
.field-value { padding: 0.75rem; font-size: 0.875rem; word-break: break-word; }
.field-standard { border-right: 1px solid var(--border-color); }
.field-status { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.status-correct { background: var(--success-color); }
.status-incorrect { background: var(--error-color); }
.status-missing { background: var(--warning-color); }
.status-extra { background: var(--info-color); }
.null { color: var(--text-muted); font-style: italic; }
pre.json { background: var(--bg-color); padding: 0.75rem; border-radius: 4px; margin: 0; font-size: 0.8rem; overflow-x: auto; }
.error-box { background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 1rem; }
.error-box pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 0.8rem; color: #991b1b; }
.match-list { display: flex; flex-direction: column; gap: 1rem; }
.match-item { border: 1px solid var(--border-color); border-radius: 6px; padding: 1rem; }
.match-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; font-size: 0.875rem; }
.match-fields { display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 0.75rem; }
.match-field { padding: 0.25rem 0.5rem; border-radius: 4px; }
.match-field.correct { background: #d1fae5; color: #065f46; }
.match-field.incorrect { background: #fee2e2; color: #991b1b; }
.match-field.missing { background: #fef3c7; color: #92400e; }
.match-field.extra { background: #dbeafe; color: #1e40af; }
.toggle-btn { background: none; border: none; cursor: pointer; font-size: 1.25rem; color: var(--text-muted); transition: transform 0.2s; }
.toggle-btn.expanded { transform: rotate(90deg); }
.filters { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.filter-btn { padding: 0.5rem 1rem; border: 1px solid var(--border-color); border-radius: 6px; background: var(--card-bg); cursor: pointer; font-size: 0.875rem; }
.filter-btn.active { background: var(--text-color); color: white; border-color: var(--text-color); }
.split-layout { display: flex; gap: 1rem; height: 75vh; min-height: 500px; }
.left-panel { flex: 1; overflow-y: auto; padding-right: 0.5rem; }
.left-panel.expanded { flex: 1 1 100%; }
.right-panel { flex: 1; display: flex; flex-direction: column; border: 1px solid var(--border-color); border-radius: 8px; background: var(--card-bg); overflow: hidden; }
.right-panel.collapsed { flex: 0 0 40px; min-width: 40px; }
.right-panel.collapsed .pdf-container, .right-panel.collapsed .pdf-title, .right-panel.collapsed .pdf-link { display: none; }
.right-panel.collapsed .pdf-header { writing-mode: vertical-rl; padding: 1rem 0.5rem; justify-content: center; height: 100%; cursor: pointer; }
.pdf-header { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; background: var(--bg-color); gap: 0.5rem; }
.collapse-btn { background: none; border: 1px solid var(--border-color); border-radius: 4px; padding: 0.25rem 0.5rem; cursor: pointer; font-size: 0.75rem; color: var(--text-muted); }
.pdf-title { font-size: 0.875rem; font-weight: 500; }
.pdf-link { font-size: 0.75rem; color: var(--info-color); text-decoration: none; }
.pdf-container { flex: 1; padding: 0.5rem; }
.pdf-iframe { width: 100%; height: 100%; border: none; border-radius: 4px; }
.detail-card.selected { box-shadow: 0 0 0 2px var(--info-color); }
.generated-at { text-align: center; color: var(--text-muted); font-size: 0.75rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border-color); }
"""

JS_SCRIPT = """
let pdfPanelCollapsed = false;
function showPdf(url, title) {
    if (!url) return;
    const viewerUrl = 'https://mozilla.github.io/pdf.js/web/viewer.html?file=' + encodeURIComponent(url);
    document.getElementById('pdf-iframe').src = viewerUrl;
    document.getElementById('pdf-title').textContent = '📄 ' + (title || 'PDF 原文');
    const link = document.getElementById('pdf-link');
    link.href = url; link.style.display = 'inline';
}
function togglePdfPanel() {
    const rp = document.querySelector('.right-panel');
    const lp = document.querySelector('.left-panel');
    const btn = document.getElementById('collapse-btn');
    pdfPanelCollapsed = !pdfPanelCollapsed;
    rp.classList.toggle('collapsed', pdfPanelCollapsed);
    lp.classList.toggle('expanded', pdfPanelCollapsed);
    btn.textContent = pdfPanelCollapsed ? '展开' : '折叠';
}
function selectCard(card) {
    document.querySelectorAll('.detail-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    const pdfUrl = card.dataset.pdf;
    if (pdfUrl) showPdf(pdfUrl, card.dataset.docId);
}
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.detail-header').forEach(header => {
        header.addEventListener('click', function() {
            const card = this.closest('.detail-card');
            this.nextElementSibling.classList.toggle('expanded');
            this.querySelector('.toggle-btn').classList.toggle('expanded');
            selectCard(card);
        });
    });
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const filter = this.dataset.filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.detail-card').forEach(card => {
                card.style.display = (filter === 'all' || card.dataset.type === filter) ? 'block' : 'none';
            });
        });
    });
    const first = document.querySelector('.detail-card[data-type="incorrect"]') || document.querySelector('.detail-card');
    if (first) {
        const body = first.querySelector('.detail-body');
        const btn = first.querySelector('.toggle-btn');
        if (body && btn) { body.classList.add('expanded'); btn.classList.add('expanded'); }
        selectCard(first);
    }
});
"""


def generate_html_report(result_with_meta: 'EvaluationResult', base_url: Optional[str] = None) -> str:
    from evaluator.evaluators.object.models import ObjectEvaluationResult
    from evaluator.evaluators.list_of_objects.models import ListOfObjectsEvaluationResult
    from evaluator.core.models import RecordDetailType, FieldDetailType

    result = result_with_meta.result
    is_object_type = isinstance(result, ObjectEvaluationResult)

    actual_base_url = base_url or result_with_meta.base_url
    pdf_links: dict[str, str] = {}
    if actual_base_url and result_with_meta.set_id:
        pdf_links = _load_pdf_links(actual_base_url, result_with_meta.set_id)

    parts = []
    title = _escape(result_with_meta.set_id or 'xdev')
    parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>评估报告 - {title}</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
<div class="container">
    <h1>📊 评估报告</h1>
""")

    # 元数据
    parts.append('<div class="card"><div class="meta-grid">')
    meta_items = [("结果类型", "单对象评估" if is_object_type else "列表评估")]
    if result_with_meta.set_id:
        meta_items.append(("标准集 ID", result_with_meta.set_id))
    if result_with_meta.base_url:
        meta_items.append(("API URL", result_with_meta.base_url))
    for label, value in meta_items:
        parts.append(f'<div class="meta-item"><span class="meta-label">{label}</span>'
                     f'<span class="meta-value">{_escape(value)}</span></div>')
    parts.append('</div></div>')

    # 统计
    acc_class = _accuracy_class(result.overall_accuracy)
    parts.append(f"""<div class="stats-grid">
    <div class="stat-card"><div class="stat-value {acc_class}">{_percent(result.overall_accuracy)}</div><div class="stat-label">总体准确率</div></div>
    <div class="stat-card"><div class="stat-value">{result.total_records}</div><div class="stat-label">总记录数</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--success-color)">{result.total_correct}</div><div class="stat-label">正确</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--error-color)">{result.total_records - result.total_correct}</div><div class="stat-label">错误</div></div>
</div>""")

    # 字段统计
    parts.append('<div class="card"><h2>📈 字段级统计</h2><table><thead><tr>'
                 '<th>字段</th><th class="text-right">准确率</th><th class="text-right">精确率</th>'
                 '<th class="text-right">召回率</th><th class="text-right">F1</th></tr></thead><tbody>')
    for field_name, stats in result.field_stats.items():
        fc = _accuracy_class(stats.accuracy)
        parts.append(f'<tr><td><strong>{_escape(field_name)}</strong></td>'
                     f'<td class="text-right {fc}">{_percent(stats.accuracy)}</td>'
                     f'<td class="text-right">{_percent(stats.precision)}</td>'
                     f'<td class="text-right">{_percent(stats.recall)}</td>'
                     f'<td class="text-right">{_percent(stats.f1)}</td></tr>')
    parts.append('</tbody></table></div>')

    # 详细结果
    correct_count = result.total_correct
    incorrect_count = result.total_records - result.total_correct
    parts.append(f"""<h2>📋 详细结果</h2>
<div class="filters">
    <button class="filter-btn active" data-filter="all">全部 ({result.total_records})</button>
    <button class="filter-btn" data-filter="correct">正确 ({correct_count})</button>
    <button class="filter-btn" data-filter="incorrect">错误 ({incorrect_count})</button>
</div>
<div class="split-layout">
<div class="left-panel">""")

    for detail in result.details:
        detail_type = detail.type.value
        doc_id = detail.standared_info.id
        pdf_url = pdf_links.get(doc_id, '')

        has_error = False
        error_info = None
        if hasattr(detail.extracted_info, 'runtime_info') and detail.extracted_info.runtime_info:
            ri = detail.extracted_info.runtime_info
            if ri.exception_info:
                has_error = True
                error_info = ri.exception_info

        if has_error:
            badge_class, badge_text = "badge-error", "异常"
        elif detail.type == RecordDetailType.CORRECT:
            badge_class, badge_text = "badge-correct", "正确"
        else:
            badge_class, badge_text = "badge-incorrect", "错误"

        parts.append(f"""<div class="detail-card" data-type="{detail_type}" data-pdf="{_escape(pdf_url)}" data-doc-id="{_escape(doc_id)}">
    <div class="detail-header">
        <span class="detail-id">{_escape(doc_id)}</span>
        <div style="display:flex;align-items:center;gap:0.5rem;">
            <span class="detail-badge {badge_class}">{badge_text}</span>
            <button class="toggle-btn">▶</button>
        </div>
    </div>
    <div class="detail-body">""")

        if has_error and error_info:
            parts.append(f"""<div class="detail-section"><h3>❌ 运行错误</h3>
<div class="error-box"><pre>{_escape(error_info.error_message)}</pre>
<details style="margin-top:0.5rem;"><summary style="cursor:pointer;color:#991b1b;">查看堆栈</summary>
<pre style="margin-top:0.5rem;">{_escape(error_info.error_traceback or '')}</pre></details></div></div>""")

        if is_object_type:
            _render_object_detail(parts, detail, FieldDetailType)
        else:
            _render_list_detail(parts, detail)

        parts.append('</div></div>')

    parts.append('</div>')  # left-panel

    parts.append("""<div class="right-panel">
    <div class="pdf-header" onclick="if(pdfPanelCollapsed) togglePdfPanel();">
        <span class="pdf-title" id="pdf-title">📄 点击左侧记录查看 PDF 原文</span>
        <div style="display:flex;align-items:center;gap:0.5rem;">
            <a id="pdf-link" href="#" target="_blank" class="pdf-link" style="display:none;">新窗口打开</a>
            <button id="collapse-btn" class="collapse-btn" onclick="event.stopPropagation();togglePdfPanel();">折叠</button>
        </div>
    </div>
    <div class="pdf-container"><iframe id="pdf-iframe" class="pdf-iframe"></iframe></div>
</div>""")

    parts.append('</div>')  # split-layout

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts.append(f"""<div class="generated-at">报告生成时间: {generated_at}</div>
</div>
<script>{JS_SCRIPT}</script>
</body>
</html>""")

    return ''.join(parts)


def _render_object_detail(parts: list, detail, FieldDetailType) -> None:
    parts.append('<div class="detail-section"><h3>字段对比</h3><div class="field-comparison">')
    parts.append('<div class="field-row" style="font-weight:600;background:var(--bg-color);">'
                 '<div class="field-name">字段</div>'
                 '<div class="field-value field-standard">标准值</div>'
                 '<div class="field-value">提取值</div></div>')
    for f in detail.related_field_details:
        parts.append(f'<div class="field-row">'
                     f'<div class="field-name"><span class="field-status status-{f.type.value}"></span>{_escape(f.name)}</div>'
                     f'<div class="field-value field-standard">{_format_value(f.standard_value)}</div>'
                     f'<div class="field-value">{_format_value(f.extracted_value)}</div></div>')
    parts.append('</div></div>')


def _render_list_detail(parts: list, detail) -> None:
    if detail.matched:
        parts.append(f'<div class="detail-section"><h3>匹配的对象 ({len(detail.matched)})</h3><div class="match-list">')
        for m in detail.matched:
            score_color = ("var(--success-color)" if m.similarity_score >= 0.9
                           else "var(--warning-color)" if m.similarity_score >= 0.7 else "var(--error-color)")
            parts.append(f'<div class="match-item"><div class="match-header">'
                         f'<span>标准[{m.std_list_idx}] ↔ 提取[{m.ext_list_idx}]</span>'
                         f'<span class="match-score" style="color:{score_color}">相似度: {_percent(m.similarity_score)}</span>'
                         f'</div><div class="match-fields">')
            for f in m.correct_fields:
                parts.append(f'<span class="match-field correct">✓ {_escape(f)}</span>')
            for f in m.incorrect_fields:
                parts.append(f'<span class="match-field incorrect">✗ {_escape(f)}</span>')
            for f in m.missing_fields:
                parts.append(f'<span class="match-field missing">- {_escape(f)}</span>')
            for f in m.extra_fields:
                parts.append(f'<span class="match-field extra">+ {_escape(f)}</span>')
            parts.append('</div>')
            if m.similarity_score < 1.0:
                parts.append(f'<details style="margin-top:0.75rem;"><summary style="cursor:pointer;font-size:0.875rem;">查看详情</summary>'
                              f'<div style="margin-top:0.5rem;display:grid;grid-template-columns:1fr 1fr;gap:1rem;">'
                              f'<div><strong>标准值:</strong>{_format_value(m.standard_value)}</div>'
                              f'<div><strong>提取值:</strong>{_format_value(m.extracted_value)}</div></div></details>')
            parts.append('</div>')
        parts.append('</div></div>')

    if detail.missing:
        parts.append(f'<div class="detail-section"><h3>漏提的对象 ({len(detail.missing)})</h3>')
        for obj in detail.missing:
            parts.append(f'<div style="margin-bottom:0.5rem;">{_format_value(obj)}</div>')
        parts.append('</div>')

    if detail.extra:
        parts.append(f'<div class="detail-section"><h3>多提的对象 ({len(detail.extra)})</h3>')
        for obj in detail.extra:
            parts.append(f'<div style="margin-bottom:0.5rem;">{_format_value(obj)}</div>')
        parts.append('</div>')


def save_html_report(result_with_meta: 'EvaluationResult', path: str | Path, base_url: Optional[str] = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_html_report(result_with_meta, base_url=base_url), encoding='utf-8')
