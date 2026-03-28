/**
 * 全局初始化 & 工具函数
 */

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function formatDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function truncate(str, len = 100) {
    if (!str) return '';
    const safe = escapeHtml(str);
    return safe.length > len ? safe.substring(0, len) + '...' : safe;
}

$(function () {
    if (typeof components !== 'undefined' && components.renderNav) {
        components.renderNav();
    }
    // 高亮当前导航
    const path = location.pathname.replace(/\/$/, '') || '/';
    $(`nav.sidebar a[href="${path}"]`).addClass('active');

    // 全局快捷键: / 聚焦搜索框
    $(document).on('keydown', function(e) {
        if (e.key === '/' && !$(e.target).is('input,textarea,select')) {
            e.preventDefault();
            const searchInput = $('#search-input, #search-input-compact, #filter-keyword').filter(':visible').first();
            if (searchInput.length) searchInput.focus();
        }
    });
});
