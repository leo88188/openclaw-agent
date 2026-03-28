/**
 * Knowledge API 接口封装 — v2.0
 */
const API_BASE = '/api/v1';

const api = {
    async request(method, path, data) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (data && method !== 'GET') opts.body = JSON.stringify(data);
        try {
            const resp = await fetch(API_BASE + path, opts);
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || err.message || `请求失败 (${resp.status})`);
            }
            return resp.json();
        } catch(e) {
            if (typeof components !== 'undefined') components.toast(e.message || '网络请求失败', 'error');
            throw e;
        }
    },
    // Knowledge
    getKnowledgeList(page=1, opts={}) {
        let q = `/knowledge?page=${page}&page_size=${opts.page_size||20}`;
        if (opts.category) q += `&category=${encodeURIComponent(opts.category)}`;
        if (opts.keyword) q += `&keyword=${encodeURIComponent(opts.keyword)}`;
        if (opts.tags) q += `&tags=${encodeURIComponent(opts.tags)}`;
        return api.request('GET', q);
    },
    createKnowledge: (data) => api.request('POST', '/knowledge', data),
    getKnowledge: (id) => api.request('GET', `/knowledge/${id}`),
    updateKnowledge: (id, data) => api.request('PUT', `/knowledge/${id}`, data),
    deleteKnowledge: (id) => api.request('DELETE', `/knowledge/${id}`),
    // Search
    search(query, opts={}) {
        return api.request('POST', '/search', {
            query, limit: opts.limit || 20,
            category: opts.category || null,
            source_type: opts.source_type || null,
            time_range: opts.time_range || null
        });
    },
    // Skills
    getSkillList(page=1, opts={}) {
        let q = `/skills?page=${page}&page_size=${opts.page_size||20}`;
        if (opts.category) q += `&category=${encodeURIComponent(opts.category)}`;
        return api.request('GET', q);
    },
    createSkill: (data) => api.request('POST', '/skills', data),
    getSkill: (id) => api.request('GET', `/skills/${id}`),
    updateSkill: (id, data) => api.request('PUT', `/skills/${id}`, data),
    deleteSkill: (id) => api.request('DELETE', `/skills/${id}`),
    toggleFavorite: (id) => api.request('POST', `/skills/${id}/favorite`),
    recordUse: (id) => api.request('POST', `/skills/${id}/use`),
    // Metadata
    getTableList: () => api.request('GET', '/metadata/tables'),
    getTable: (name) => api.request('GET', `/metadata/tables/${encodeURIComponent(name)}`),
    importMetadata: (dbName) => api.request('POST', '/metadata/import', { db_name: dbName }),
    // Teams
    getTeamList: () => api.request('GET', '/teams'),
    createTeam: (data) => api.request('POST', '/teams', data),
    getTeamMembers: (id) => api.request('GET', `/teams/${id}/members`),
    addTeamMember: (id, data) => api.request('POST', `/teams/${id}/members`, data),
    updateMemberRole: (id, uid, role) => api.request('PUT', `/teams/${id}/members/${encodeURIComponent(uid)}`, { role }),
    removeMember: (id, uid) => api.request('DELETE', `/teams/${id}/members/${encodeURIComponent(uid)}`),
    // Dashboard
    getStats: () => api.request('GET', '/dashboard/stats'),
    healthCheck: () => api.request('GET', '/health'),
};
