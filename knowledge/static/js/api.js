/**
 * Knowledge API 接口封装
 */
const API_BASE = '/api/v1';

const api = {
    async request(method, path, data) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (data && method !== 'GET') opts.body = JSON.stringify(data);
        try {
            const resp = await fetch(API_BASE + path, opts);
            if (!resp.ok) {
                const errBody = await resp.json().catch(() => ({}));
                throw new Error(errBody.detail || errBody.message || `请求失败 (${resp.status})`);
            }
            return resp.json();
        } catch(e) {
            if (typeof components !== 'undefined') components.toast(e.message || '网络请求失败', 'error');
            throw e;
        }
    },
    // Knowledge
    getKnowledgeList: (page = 1, category) => api.request('GET', `/knowledge?page=${page}${category ? '&category=' + category : ''}`),
    createKnowledge: (data) => api.request('POST', '/knowledge', data),
    getKnowledge: (id) => api.request('GET', `/knowledge/${id}`),
    updateKnowledge: (id, data) => api.request('PUT', `/knowledge/${id}`, data),
    deleteKnowledge: (id) => api.request('DELETE', `/knowledge/${id}`),
    // Search
    search: (query, category) => api.request('POST', '/search', { query, category }),
    // Skills
    getSkillList: (page = 1, category) => api.request('GET', `/skills?page=${page}${category ? '&category=' + category : ''}`),
    createSkill: (data) => api.request('POST', '/skills', data),
    getSkill: (id) => api.request('GET', `/skills/${id}`),
    updateSkill: (id, data) => api.request('PUT', `/skills/${id}`, data),
    deleteSkill: (id) => api.request('DELETE', `/skills/${id}`),
    toggleFavorite: (id) => api.request('POST', `/skills/${id}/favorite`),
    // Metadata
    getTableList: () => api.request('GET', '/metadata/tables'),
    getTable: (name) => api.request('GET', `/metadata/tables/${name}`),
    importMetadata: (dbName) => api.request('POST', '/metadata/import', { db_name: dbName }),
    // Teams
    getTeamList: () => api.request('GET', '/teams'),
    createTeam: (data) => api.request('POST', '/teams', data),
    getTeamMembers: (id) => api.request('GET', `/teams/${id}/members`),
    addTeamMember: (id, data) => api.request('POST', `/teams/${id}/members`, data),
    // Dashboard
    getStats: () => api.request('GET', '/dashboard/stats'),
};
