/**
 * 通用组件 — Redesigned
 */
let _toastCount = 0;

const components = {
    renderNav() {
        const nav = `
        <nav class="sidebar fixed left-0 top-0 h-full w-56 z-40 flex flex-col">
            <div class="p-5 border-b" style="border-color:var(--border)">
                <h1 class="nav-brand text-xl font-bold tracking-tight"><i class="fa fa-bolt mr-2"></i>Knowledge</h1>
                <p class="nav-sub text-xs mt-1">AI 知识库平台</p>
            </div>
            <div class="flex-1 py-4 space-y-1 px-3">
                <a href="/" class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition"><i class="fa fa-dashboard w-5 text-center"></i><span>仪表盘</span></a>
                <a href="/knowledge.html" class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition"><i class="fa fa-book w-5 text-center"></i><span>知识管理</span></a>
                <a href="/search.html" class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition"><i class="fa fa-search w-5 text-center"></i><span>智能搜索</span></a>
                <a href="/skills.html" class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition"><i class="fa fa-magic w-5 text-center"></i><span>Skill 市场</span></a>
                <a href="/metadata.html" class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition"><i class="fa fa-database w-5 text-center"></i><span>元数据</span></a>
                <a href="/teams.html" class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition"><i class="fa fa-users w-5 text-center"></i><span>团队空间</span></a>
            </div>
            <div class="p-4 border-t" style="border-color:var(--border)">
                <div class="flex items-center gap-2 text-xs" style="color:var(--text-muted)">
                    <span class="w-2 h-2 rounded-full bg-green-400 inline-block"></span>
                    <span>系统运行中</span>
                </div>
            </div>
        </nav>`;
        $('body').prepend(nav);
    },

    toast(msg, type = 'info') {
        const colors = { info: 'background:var(--info)', success: 'background:var(--success)', error: 'background:var(--danger)' };
        const idx = _toastCount++;
        const offset = 1 + idx * 3.5;
        const el = $(`<div class="toast-item fixed right-4 px-6 py-3 shadow-lg z-50 animate-fade-in" style="top:${offset}rem;${colors[type]};color:#ffffff;font-weight:600">${escapeHtml(msg)}</div>`);
        $('body').append(el);
        setTimeout(() => { el.remove(); _toastCount = Math.max(0, _toastCount - 1); }, 3000);
    },

    modal(title, content, onConfirm) {
        $('#modal-overlay').remove();
        const html = `
        <div id="modal-overlay" class="fixed inset-0 flex items-center justify-center z-50">
            <div class="modal-inner rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6">
                <h3 class="text-lg font-semibold mb-4">${escapeHtml(title)}</h3>
                <div class="mb-6">${content}</div>
                <div class="flex justify-end gap-3">
                    <button class="btn-cancel px-4 py-2 rounded-lg">取消</button>
                    <button class="btn-confirm px-4 py-2 rounded-lg font-semibold">确认</button>
                </div>
            </div>
        </div>`;
        $('body').append(html);

        const close = () => $('#modal-overlay').remove();
        $('#modal-overlay').on('click', function(e) { if (e.target === this) close(); });
        $(document).on('keydown.modal', function(e) { if (e.key === 'Escape') { close(); $(document).off('keydown.modal'); } });
        $('#modal-overlay .btn-cancel').click(() => { close(); $(document).off('keydown.modal'); });
        $('#modal-overlay .btn-confirm').click(async function() {
            const btn = $(this);
            if (btn.prop('disabled')) return;
            btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-1"></i>处理中...');
            try { await onConfirm(); close(); }
            catch(e) { components.toast(e.message || '操作失败', 'error'); btn.prop('disabled', false).html('确认'); }
            $(document).off('keydown.modal');
        });
    },

    confirm(msg, onOk) {
        this.modal('确认操作', `<p style="color:var(--text-secondary)">${escapeHtml(msg)}</p>`, onOk);
    },

    pagination(total, page, size, onChange) {
        const pages = Math.ceil(total / size);
        if (pages <= 1) return '';
        let html = '<div class="flex items-center gap-2 mt-6 justify-center">';
        for (let i = 1; i <= pages; i++) {
            const cls = i === page ? 'pagination-btn active' : 'pagination-btn';
            html += `<button onclick="${onChange}(${i})" class="${cls}">${i}</button>`;
        }
        html += '</div>';
        return html;
    },

    emptyState(msg = '暂无数据') {
        return `<div class="empty-state text-center py-16"><i class="fa fa-inbox text-4xl mb-3 block"></i><p>${escapeHtml(msg)}</p></div>`;
    },

    loading() {
        return `<div class="text-center py-16"><i class="fa fa-spinner fa-spin text-3xl" style="color:var(--accent)"></i></div>`;
    }
};
