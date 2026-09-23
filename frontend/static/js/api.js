/* ============================================================
   ERP LEIVA — API helper
   Wrapper de fetch con manejo de errores, JSON, multipart y sesión
   ============================================================ */

const API = {
  base: '',

  async request(method, path, body = null, opts = {}) {
    const init = {
      method,
      credentials: 'include',
      headers: { 'Accept': 'application/json' },
    };
    if (body !== null && !(body instanceof FormData)) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    } else if (body instanceof FormData) {
      init.body = body;
    }
    const resp = await fetch(this.base + path, init);
    if (resp.status === 401 && !path.startsWith('/api/auth/')) {
      App.showLogin();
      throw new Error('No autenticado');
    }
    if (resp.status === 402) {
      alert('Suscripción vencida. Renueva el plan.');
      throw new Error('Suscripción vencida');
    }
    if (resp.status === 403) {
      const data = await resp.json().catch(() => ({detail: 'Sin permisos'}));
      throw new Error(data.detail || 'Sin permisos');
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({detail: resp.statusText}));
      throw new Error(data.detail || ('Error ' + resp.status));
    }
    if (resp.status === 204) return null;
    return resp.json();
  },

  get(path, params) {
    const q = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request('GET', path + q);
  },
  post(path, body) { return this.request('POST', path, body); },
  patch(path, body) { return this.request('PATCH', path, body); },
  put(path, body) { return this.request('PUT', path, body); },
  del(path) { return this.request('DELETE', path); },
  upload(path, file, fields = {}) {
    const fd = new FormData();
    fd.append('file', file);
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    return this.request('POST', path, fd);
  },
};