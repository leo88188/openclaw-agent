/**
 * 通用组件 — v2.0 (对齐 ui-design.md)
 */
let _toastCount = 0;

const components = {
    renderNav() {
        const nav = `
        <nav class="sidebar fixed left-0 top-0 h-full w-60 z-40 flex flex-col">
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

    /* Toast — ui-design.md 4.4 规范 */
    toast(msg, type = 'info') {
        const cfg = {
            success: { icon: 'fa-check-circle', bg: 'var(--success-light,#ecfdf5)', border: 'var(--success,#2e7d32)', color: 'var(--success,#2e7d32)', dur: 3000 },
            error:   { icon: 'fa-times-circle', bg: 'var(--error-light,#fef2f2)', border: 'var(--danger,#d32f2f)', color: 'var(--danger,#d32f2f)', dur: 5000 },
            warning: { icon: 'fa-exclamation-triangle', bg: '#fffbeb', border: '#d97706', color: '#d97706', dur: 4000 },
            info:    { icon: 'fa-info-circle', bg: '#e6f2ff', border: 'var(--accent,#0066cc)', color: 'var(--accent,#0066cc)', dur: 3000 }
        };
        const c = cfg[type] || cfg.info;
        const idx = _toastCount++;
        const top = 24 + idx * 64;
        const el = $(`<div class="toast-item fixed z-50 flex items-center gap-3 px-5 py-3 shadow-lg" style="top:${top}px;right:24px;width:360px;background:${c.bg};border-left:3px solid ${c.border};border-radius:var(--radius-md,6px);transform:translateX(100%);transition:transform 0.2s ease-out">
            <i class="fa ${c.icon}" style="color:${c.color};font-size:16px"></i>
            <span style="color:var(--text-primary,#1a1a1a);font-size:14px;font-weight:500">${escapeHtml(msg)}</span>
        </div>`);
        $('body').append(el);
        requestAnimationFrame(() => el.css('transform', 'translateX(0)'));
        setTimeout(() => {
            el.css({ opacity: 0, transition: 'opacity 0.15s ease-in' });
            setTimeout(() => { el.remove(); _toastCount = Math.max(0, _toastCount - 1); }, 150);
        }, c.dur);
    },

    /* Modal — 支持自定义宽度 */
    modal(title, content, onConfirm, opts = {}) {
        $('#modal-overlay').remove();
        const w = opts.width || 'max-w-lg';
        const confirmText = opts.confirmText || '确认';
        const html = `
        <div id="modal-overlay" class="fixed inset-0 flex items-center justify-center z-50" style="opacity:0;transition:opacity 0.2s ease-out">
            <div class="modal-inner rounded-xl shadow-2xl w-full ${w} mx-4 p-6" style="transform:translateY(20px);transition:transform 0.2s ease-out">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-semibold" style="color:var(--text-primary)">${escapeHtml(title)}</h3>
                    <button class="modal-close" style="color:var(--text-muted);cursor:pointer;padding:4px"><i class="fa fa-times"></i></button>
                </div>
                <div class="modal-body mb-6">${content}</div>
                <div class="flex justify-end gap-3">
                    <button class="btn-cancel px-4 py-2 rounded-lg">取消</button>
                    <button class="btn-confirm px-4 py-2 rounded-lg font-semibold">${escapeHtml(confirmText)}</button>
                </div>
            </div>
        </div>`;
        $('body').append(html);
        requestAnimationFrame(() => {
            $('#modal-overlay').css('opacity', 1);
            $('#modal-overlay .modal-inner').css('transform', 'translateY(0)');
        });

        const close = () => {
            $('#modal-overlay').css('opacity', 0);
            $('#modal-overlay .modal-inner').css('transform', 'translateY(10px)');
            setTimeout(() => $('#modal-overlay').remove(), 150);
            $(document).off('keydown.modal');
        };
        $('#modal-overlay').on('click', function(e) { if (e.target === this) close(); });
        $('#modal-overlay .modal-close').click(close);
        $(document).on('keydown.modal', function(e) { if (e.key === 'Escape') close(); });
        $('#modal-overlay .btn-cancel').click(close);
        if (onConfirm) {
            $('#modal-overlay .btn-confirm').click(async function() {
                const btn = $(this);
                if (btn.prop('disabled')) return;
                btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-1"></i>处理中...');
                try { await onConfirm(); close(); }
                catch(e) { components.toast(e.message || '操作失败', 'error'); btn.prop('disabled', false).html(confirmText); }
            });
        } else {
            $('#modal-overlay .btn-confirm').hide();
            $('#modal-overlay .btn-cancel').text('关闭');
        }
    },

    confirm(msg, onOk) {
        this.modal('确认操作', `<p style="color:var(--text-secondary)">${escapeHtml(msg)}</p>`, onOk);
    },

    pagination(total, page, size, onChange) {
        const pages = Math.ceil(total / size);
        if (pages <= 1) return '';
        let html = '<div class="flex items-center gap-2 mt-6 justify-center">';
        if (page > 1) html += `<button onclick="${onChange}(${page-1})" class="pagination-btn"><i class="fa fa-chevron-left"></i></button>`;
        for (let i = 1; i <= pages; i++) {
            if (pages > 7 && i > 3 && i < pages - 2 && Math.abs(i - page) > 1) {
                if (i === 4 || i === pages - 3) html += '<span class="px-1" style="color:var(--text-muted)">...</span>';
                continue;
            }
            html += `<button onclick="${onChange}(${i})" class="pagination-btn${i===page?' active':''}">${i}</button>`;
        }
        if (page < pages) html += `<button onclick="${onChange}(${page+1})" class="pagination-btn"><i class="fa fa-chevron-right"></i></button>`;
        html += '</div>';
        return html;
    },

    emptyState(msg = '暂无数据', ctaText, ctaAction) {
        let html = `<div class="empty-state text-center py-16"><i class="fa fa-inbox text-4xl mb-3 block"></i><p>${escapeHtml(msg)}</p>`;
        if (ctaText && ctaAction) {
            html += `<button onclick="${ctaAction}" class="btn-accent mt-4 text-sm"><i class="fa fa-plus mr-1"></i>${escapeHtml(ctaText)}</button>`;
        }
        html += '</div>';
        return html;
    },

    loading() {
        return `<div class="text-center py-16"><i class="fa fa-spinner fa-spin text-3xl" style="color:var(--accent)"></i></div>`;
    },

    skeleton(type = 'card', count = 6) {
        if (type === 'card') {
            let html = '';
            for (let i = 0; i < count; i++) {
                html += `<div class="card p-5"><div class="skeleton-line h-5 w-3/4 mb-3"></div><div class="skeleton-line h-3 w-full mb-2"></div><div class="skeleton-line h-3 w-2/3"></div></div>`;
            }
            return html;
        }
        if (type === 'table') {
            let html = '';
            for (let i = 0; i < count; i++) {
                html += `<div class="skeleton-line h-4 w-full mb-3"></div>`;
            }
            return html;
        }
        return components.loading();
    }
};
