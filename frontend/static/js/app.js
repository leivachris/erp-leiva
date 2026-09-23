/* ============================================================
   ERP LEIVA — App principal
   SPA con hash router, atajos teclado estilo BigTech
   ============================================================ */

// Alias globales para usar desde event listeners fuera del objeto App
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const App = {
  me: null,
  empresa: null,
  currentView: null,
  selectedId: null,
  searchTimer: null,

  /* ============ UTILIDADES ============ */
  fmt: {
    money(n) {
      return new Intl.NumberFormat('es-ES', {style:'currency', currency:'EUR'}).format(n || 0);
    },
    num(n, d = 2) {
      return new Intl.NumberFormat('es-ES', {minimumFractionDigits:d, maximumFractionDigits:d}).format(n || 0);
    },
    date(d) {
      if (!d) return '';
      return new Date(d).toLocaleDateString('es-ES');
    },
    datetime(d) {
      if (!d) return '';
      return new Date(d).toLocaleString('es-ES');
    },
    pct(n) {
      return (n || 0).toFixed(1) + ' %';
    },
  },

  el(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstChild;
  },

  $(s) { return document.querySelector(s); },
  $$(s) { return Array.from(document.querySelectorAll(s)); },

  status(msg) {
    const el = $('#status-msg');
    if (el) el.textContent = msg;
  },

  /* ============ MODAL ============ */
  modal(title, htmlContent) {
    return new Promise(resolve => {
      const m = $('#modal');
      $('#modal-title').textContent = title;
      const body = $('#modal-body');
      body.innerHTML = '';
      if (typeof htmlContent === 'string') {
        body.innerHTML = htmlContent;
      } else if (htmlContent instanceof Node) {
        body.appendChild(htmlContent);
      }
      m.hidden = false;
      const close = (val) => { m.hidden = true; resolve(val); };
      window.addEventListener('keydown', escClose = (e) => {
        if (e.key === 'Escape') { window.removeEventListener('keydown', escClose); close(null); }
      });
      body._closeModal = close;
    });
  },

  confirm(msg) {
    return new Promise(resolve => {
      const box = App.el(`<div><p>${msg}</p>
        <div class="form-actions">
          <button class="btn" data-act="no">Cancelar (Esc)</button>
          <button class="btn-primary" data-act="si">Sí, continuar</button>
        </div></div>`);
      box.querySelector('[data-act=no]').onclick = () => { $('#modal').hidden = true; resolve(false); };
      box.querySelector('[data-act=si]').onclick = () => { $('#modal').hidden = true; resolve(true); };
      $('#modal-title').textContent = 'Confirmar';
      $('#modal-body').innerHTML = '';
      $('#modal-body').appendChild(box);
      $('#modal').hidden = false;
    });
  },

  /* ============ ARRANQUE ============ */
  async init() {
    console.log('[ERP] init');
    // Mostrar reloj en statusbar
    setInterval(() => {
      const f = $('#status-fecha');
      if (f) f.textContent = new Date().toLocaleString('es-ES');
    }, 1000);

    try {
      const estado = await API.get('/api/instalacion/estado');
      console.log('[ERP] estado:', estado);
      if (!estado.instalado) {
        this.showSetup();
        this.loadPlanes();
      } else {
        this.showLogin(estado.empresa_nombre || '');
      }
    } catch (e) {
      console.error('[ERP] init error', e);
      // Si falla, asumimos instalado y mostramos login
      this.showLogin();
    }
  },

  async loadPlanes() {
    try {
      const planes = await API.get('/api/planes');
      const cont = $('#planes-list');
      cont.innerHTML = '';
      planes.forEach(p => {
        const card = App.el(`
          <div class="plan-card ${p.codigo === 'pro' ? 'destacado' : ''}" data-cod="${p.codigo}">
            <div class="plan-nombre">${p.nombre}</div>
            <div class="plan-precio">${p.precio_mensual} €<span class="small muted">/mes</span></div>
            <div class="plan-desc">${p.descripcion || ''}</div>
            <ul>${Object.entries(p.features || {}).map(([k,v]) =>
              `<li class="${v?'':'disabled'}">${v?'✓':'✗'} ${this.featName(k)}</li>`
            ).join('')}</ul>
          </div>
        `);
        card.onclick = () => {
          cont.querySelectorAll('.plan-card').forEach(c => c.classList.remove('selected'));
          card.classList.add('selected');
          $('input[name=plan_codigo]').value = p.codigo;
        };
        cont.appendChild(card);
      });
      // seleccionar pro por defecto
      const pro = cont.querySelector('[data-cod=pro]');
      if (pro) pro.click();
    } catch (e) {
      console.error('No se pudieron cargar planes:', e);
    }
  },

  featName(k) {
    const names = {
      inventario: 'Inventario y ubicaciones',
      ventas: 'Ventas y albaranes',
      compras: 'Compras y proveedores',
      facturacion: 'Facturación',
      tesoreria: 'Tesorería',
      obras: 'Gestión de obras',
      multi_almacen: 'Multi-almacén',
      multi_usuario_avanzado: 'Roles avanzados',
      tarifas_avanzadas: 'Tarifas avanzadas',
      reportes_avanzados: 'Reportes avanzados',
      api_externa: 'API externa',
      soporte_prioritario: 'Soporte prioritario',
      marca_blanca: 'Marca blanca',
      punto_venta: 'TPV / Caja',
    };
    return names[k] || k;
  },

  /* ============ SETUP ============ */
  showSetup() {
    $('#screen-setup').hidden = false;
    $('#screen-login').hidden = true;
    $('#app').hidden = true;
  },

  async doSetup(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const data = {
      empresa: {
        nombre: fd.get('nombre'),
        nombre_comercial: fd.get('nombre_comercial'),
        cif: fd.get('cif'),
        direccion: fd.get('direccion'),
        cp: fd.get('cp'),
        poblacion: fd.get('poblacion'),
        telefono: fd.get('telefono'),
        email: fd.get('email'),
      },
      admin: {
        username: fd.get('admin_username'),
        nombre: fd.get('admin_nombre') || fd.get('admin_username'),
        email: fd.get('admin_email'),
        password: fd.get('admin_password'),
      },
      plan_codigo: fd.get('plan_codigo'),
    };
    try {
      const res = await API.post('/api/instalacion/setup', data);
      $('#setup-error').hidden = true;
      alert('Instalación completada.\nUsuario: ' + res.admin_username + '\nPlan: ' + res.plan);
      this.showLogin(data.empresa.nombre);
    } catch (e) {
      const err = $('#setup-error');
      err.textContent = e.message; err.hidden = false;
    }
  },

  /* ============ LOGIN ============ */
  showLogin(empresaNombre = '') {
    $('#screen-setup').hidden = true;
    $('#screen-login').hidden = false;
    $('#app').hidden = true;
    if (empresaNombre) {
      $('#empresa-nombre-login').textContent = empresaNombre;
    }
  },

  async doLogin(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const me = await API.post('/api/auth/login', {
        username: fd.get('username'),
        password: fd.get('password'),
      });
      console.log('[ERP] login OK:', me.username);
      this.me = me;
      this.empresa = { id: me.empresa_id, nombre: me.empresa_nombre, slug: me.empresa_slug };
      $('#login-error').hidden = true;
      // Ocultar TODAS las pantallas de auth y mostrar app
      $('#screen-setup').hidden = true;
      $('#screen-login').hidden = true;
      $('#app').hidden = false;
      // Llenar UI
      $('#brand-nombre').textContent = me.empresa_nombre;
      $('#status-empresa').textContent = me.empresa_nombre + ' (' + me.plan + ')';
      $('#user-info').textContent = me.nombre + ' (' + me.rol + ')';
      // Badge: root tiene prioridad sobre el plan
      if (me.rol === 'root') {
        $('#plan-info').textContent = 'ROOT';
        $('#plan-info').style.background = '#7f1d1d';
      } else {
        $('#plan-info').textContent = me.plan || '';
        $('#plan-info').style.background = '';
      }
      // Cargar dashboard
      this.go(location.hash.slice(1) || 'dashboard');
    } catch (e) {
      console.error('[ERP] login error', e);
      const err = $('#login-error');
      err.textContent = e.message; err.hidden = false;
    }
  },

  async logout() {
    try { await API.post('/api/auth/logout'); } catch {}
    this.me = null; this.empresa = null;
    this.showLogin();
  },

  /* ============ ROUTER ============ */
  go(view) {
    if (!view) view = 'dashboard';
    location.hash = '#' + view;
  },

  async router() {
    const view = location.hash.slice(1) || 'dashboard';
    if (!this.me) return;
    if (!this.featuresPermitidas(view)) {
      this.main(`<div class="warn">Tu plan actual (${this.me.plan}) no incluye esta funcionalidad. Mejora el plan desde Configuración.</div>`);
      return;
    }
    this.$$('.sidebar nav a').forEach(a => {
      a.classList.toggle('active', a.dataset.view === view);
    });
    this.currentView = view;
    try {
      const fn = this['view_' + view] || this.viewNotFound;
      await fn.call(this);
    } catch (e) {
      console.error(e);
      this.main(`<div class="error">Error: ${e.message}</div>`);
    }
  },

  featuresPermitidas(view) {
    // root bypassa tot
    if (this.me.rol === 'root') return true;
    // admin bypassa tot (ja té tots els permisos del backend)
    if (this.me.rol === 'admin') return true;
    const map = {
      compras: 'compras',
      facturacion: 'facturacion',
      tesoreria: 'tesoreria',
      tpv: 'punto_venta',
      obras: 'obras',
    };
    const feat = map[view];
    if (!feat) return true;
    return this.me.features && this.me.features[feat];
  },

  viewNotFound() {
    this.main('<div class="error">Vista no encontrada</div>');
  },

  main(html) {
    const m = $('#main');
    if (typeof html === 'string') m.innerHTML = html;
    else if (html instanceof Node) { m.innerHTML = ''; m.appendChild(html); }
  },

  viewHeader(title, toolbar = '') {
    return `<div class="view-header">
      <h2>${title}</h2>
      <div class="grow"></div>
      <div class="view-toolbar">${toolbar}</div>
    </div>`;
  },

  /* ============ DASHBOARD ============ */
  async view_dashboard() {
    const [kpis, alertas] = await Promise.all([
      API.get('/api/dashboard/kpis'),
      API.get('/api/dashboard/alertas'),
    ]);

    const k = kpis;
    this.main(`
      <div class="view-header">
        <h2>Dashboard</h2>
        <div class="grow"></div>
        <span class="muted small">Bienvenido, ${this.me.nombre}</span>
      </div>
      <div class="kpis">
        <div class="kpi"><div class="kpi-label">Productos</div><div class="kpi-value">${k.productos_total}</div></div>
        <div class="kpi ${k.productos_bajo_minimo > 0 ? 'danger' : ''}"><div class="kpi-label">Bajo mínimo</div><div class="kpi-value">${k.productos_bajo_minimo}</div></div>
        <div class="kpi"><div class="kpi-label">Valor stock</div><div class="kpi-value">${this.fmt.money(k.stock_valor_compra)}</div></div>
        <div class="kpi"><div class="kpi-label">Proveedores</div><div class="kpi-value">${k.proveedores_total}</div></div>
        <div class="kpi"><div class="kpi-label">Clientes</div><div class="kpi-value">${k.clientes_total}</div></div>
        <div class="kpi"><div class="kpi-label">Obras activas</div><div class="kpi-value">${k.obras_activas}</div></div>
        <div class="kpi warn"><div class="kpi-label">Albaranes sin facturar</div><div class="kpi-value">${k.albaranes_pendientes_facturar}</div></div>
        <div class="kpi warn"><div class="kpi-label">Por cobrar</div><div class="kpi-value">${this.fmt.money(k.facturas_cliente_pendientes)}</div></div>
        <div class="kpi"><div class="kpi-label">Por pagar</div><div class="kpi-value">${this.fmt.money(k.facturas_proveedor_pendientes)}</div></div>
        <div class="kpi success"><div class="kpi-label">Ventas mes</div><div class="kpi-value">${this.fmt.money(k.ventas_mes)}</div></div>
        <div class="kpi"><div class="kpi-label">Compras mes</div><div class="kpi-value">${this.fmt.money(k.compras_mes)}</div></div>
      </div>

      <div class="panel">
        <div class="panel-title">⚠️ Productos bajo mínimo (${alertas.bajo_stock.length})</div>
        <table class="grid">
          <thead><tr><th>SKU</th><th>Producto</th><th class="num">Stock</th><th class="num">Mínimo</th><th class="num">Diferencia</th></tr></thead>
          <tbody>
          ${alertas.bajo_stock.map(p => `
            <tr data-go="productos" data-id="${p.id}">
              <td>${p.sku}</td><td>${p.nombre}</td>
              <td class="num">${this.fmt.num(p.stock_actual)}</td>
              <td class="num">${this.fmt.num(p.stock_minimo)}</td>
              <td class="num">${this.fmt.num(p.stock_actual - p.stock_minimo)}</td>
            </tr>`).join('') || '<tr><td colspan="5" class="center muted">Todo en orden ✓</td></tr>'}
          </tbody>
        </table>
      </div>

      <div class="panel mt-2">
        <div class="panel-title">📄 Albaranes sin facturar > 15 días (${alertas.albaranes_sin_facturar.length})</div>
        <table class="grid">
          <thead><tr><th>Número</th><th>Fecha</th><th>Cliente</th><th class="num">Total</th></tr></thead>
          <tbody>
          ${alertas.albaranes_sin_facturar.map(a => `
            <tr>
              <td>${a.numero}</td>
              <td>${this.fmt.date(a.fecha)}</td>
              <td>${a.cliente_nombre}</td>
              <td class="num">${this.fmt.money(a.total)}</td>
            </tr>`).join('') || '<tr><td colspan="4" class="center muted">Nada pendiente</td></tr>'}
          </tbody>
        </table>
      </div>
    `);

    this.$$('tr[data-go]').forEach(tr => {
      tr.onclick = () => this.go(tr.dataset.go);
    });
  },

  /* ============ PRODUCTOS ============ */
  async view_productos() {
    const filtroFam = this.cache('productos.familia', '');
    const filtroActivos = this.cache('productos.activos', '1');
    const q = this.cache('productos.q', '');
    const bajoMin = this.cache('productos.bajoMin', '0');

    const params = {};
    if (q) params.q = q;
    if (filtroFam) params.familia_id = filtroFam;
    if (filtroActivos === '1') params.solo_activos = 'true';
    if (bajoMin === '1') params.bajo_minimo = 'true';

    const [prods, familias] = await Promise.all([
      API.get('/api/productos', params),
      API.get('/api/productos/familias'),
    ]);

    this.main(`
      <div class="view-header">
        <h2>Productos (${prods.length})</h2>
        <div class="grow"></div>
        <input id="prod-q" placeholder="Buscar por SKU, nombre o código barras..." value="${q}" style="width:280px">
        <select id="prod-fam">
          <option value="">Todas las familias</option>
          ${familias.map(f => `<option value="${f.id}" ${filtroFam==f.id?'selected':''}>${f.nombre}</option>`).join('')}
        </select>
        <label class="muted small" style="display:flex;align-items:center;gap:4px">
          <input type="checkbox" id="prod-activos" ${filtroActivos==='1'?'checked':''}> Activos
        </label>
        <label class="muted small" style="display:flex;align-items:center;gap:4px">
          <input type="checkbox" id="prod-bajo" ${bajoMin==='1'?'checked':''}> Bajo mínimo
        </label>
        <button id="prod-nuevo" class="btn-primary">+ Nuevo (F4)</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead>
            <tr>
              <th>SKU</th><th>Nombre</th><th>Familia</th>
              <th class="num">Stock</th><th class="num">Mín</th>
              <th class="num">Compra</th><th class="num">Venta</th>
              <th class="center">IVA</th><th class="center">U.</th>
              <th>Marca</th><th>Estado</th>
            </tr>
          </thead>
          <tbody>
            ${prods.map(p => `
              <tr data-id="${p.id}">
                <td><strong>${p.sku}</strong></td>
                <td>${p.nombre}</td>
                <td>${p.familia_nombre || '-'}</td>
                <td class="num ${p.stock_actual <= p.stock_minimo && p.stock_minimo > 0 ? 'danger' : ''}">${this.fmt.num(p.stock_actual)}</td>
                <td class="num">${this.fmt.num(p.stock_minimo)}</td>
                <td class="num">${this.fmt.money(p.precio_compra)}</td>
                <td class="num">${this.fmt.money(p.precio_venta)}</td>
                <td class="center">${p.iva}%</td>
                <td class="center">${p.unidad_stock}</td>
                <td>${p.marca || '-'}</td>
                <td>${p.activo ? '<span class="badge-cell ok">Activo</span>' : '<span class="badge-cell warn">Inactivo</span>'}</td>
              </tr>`).join('')}
            ${prods.length === 0 ? '<tr><td colspan="11" class="loading">Sin productos. Pulsa F4 o el botón + Nuevo.</td></tr>' : ''}
          </tbody>
        </table>
      </div>
    `);

    // handlers
    $('#prod-q').oninput = (e) => { this.cache('productos.q', e.target.value); this.debounceReload(); };
    $('#prod-fam').onchange = (e) => { this.cache('productos.familia', e.target.value); this.router(); };
    $('#prod-activos').onchange = (e) => { this.cache('productos.activos', e.target.checked ? '1' : '0'); this.router(); };
    $('#prod-bajo').onchange = (e) => { this.cache('productos.bajoMin', e.target.checked ? '1' : '0'); this.router(); };
    $('#prod-nuevo').onclick = () => this.productoEdit(null);

    this.$$('tr[data-id]').forEach(tr => {
      tr.onclick = () => this.productoEdit(parseInt(tr.dataset.id));
    });
  },

  async productoEdit(id) {
    const isNew = !id;
    let p = id ? await API.get(`/api/productos/${id}`) : {
      sku: '', nombre: '', familia_id: null,
      unidad_stock: 'ud', unidad_compra: 'ud', unidad_venta: 'ud',
      factor_compra: 1, factor_venta: 1,
      precio_compra: 0, precio_venta: 0, iva: '21',
      stock_minimo: 0, stock_maximo: 0,
      peso_kg: 0, volumen_m3: 0,
      codigo_barras: '', codigo_proveedor: '', marca: '', modelo: '',
      notas: '',
    };
    const fams = await API.get('/api/productos/familias');
    const ivas = ['21','10','4','0'];
    const unidades = ['ud','kg','g','l','m','m2','m3','palet','bigbag','saco','bolsa','rollo','caja','t'];

    const html = `
      <form id="form-prod">
        <div class="form-grid">
          <label>SKU *<input name="sku" value="${p.sku || ''}" required ${isNew?'':'readonly'}></label>
          <label>Código barras<input name="codigo_barras" value="${p.codigo_barras || ''}"></label>
          <label class="full">Nombre *<input name="nombre" value="${p.nombre || ''}" required></label>
          <label>Familia
            <select name="familia_id">
              <option value="">-- sin familia --</option>
              ${fams.map(f => `<option value="${f.id}" ${p.familia_id===f.id?'selected':''}>${f.nombre}</option>`).join('')}
            </select>
          </label>
          <label>Marca<input name="marca" value="${p.marca || ''}"></label>
          <label>Modelo<input name="modelo" value="${p.modelo || ''}"></label>
          <label>Ref. proveedor<input name="codigo_proveedor" value="${p.codigo_proveedor || ''}"></label>

          <label>Unidad stock
            <select name="unidad_stock">
              ${unidades.map(u => `<option value="${u}" ${p.unidad_stock===u?'selected':''}>${u}</option>`).join('')}
            </select>
          </label>
          <label>Unidad compra
            <select name="unidad_compra">
              ${unidades.map(u => `<option value="${u}" ${p.unidad_compra===u?'selected':''}>${u}</option>`).join('')}
            </select>
          </label>
          <label>Unidad venta
            <select name="unidad_venta">
              ${unidades.map(u => `<option value="${u}" ${p.unidad_venta===u?'selected':''}>${u}</option>`).join('')}
            </select>
          </label>
          <label>Factor compra<input name="factor_compra" type="number" step="0.001" value="${p.factor_compra||1}"></label>

          <label>Precio compra<input name="precio_compra" type="number" step="0.0001" value="${p.precio_compra||0}"></label>
          <label>Precio venta<input name="precio_venta" type="number" step="0.0001" value="${p.precio_venta||0}"></label>
          <label>IVA
            <select name="iva">
              ${ivas.map(v => `<option value="${v}" ${p.iva===v?'selected':''}>${v}%</option>`).join('')}
            </select>
          </label>

          <label>Stock mínimo<input name="stock_minimo" type="number" step="0.001" value="${p.stock_minimo||0}"></label>
          <label>Stock máximo<input name="stock_maximo" type="number" step="0.001" value="${p.stock_maximo||0}"></label>
          <label>Peso (kg)<input name="peso_kg" type="number" step="0.001" value="${p.peso_kg||0}"></label>
          <label>Volumen (m³)<input name="volumen_m3" type="number" step="0.001" value="${p.volumen_m3||0}"></label>

          <label class="full">Notas<textarea name="notas" rows="2">${p.notas||''}</textarea></label>
        </div>
        <div class="form-actions">
          <button type="button" class="btn" data-act="cancel">Cancelar (Esc)</button>
          ${isNew ? '' : '<button type="button" class="btn-danger" data-act="del">Eliminar</button>'}
          <button type="submit" class="btn-primary">Guardar (F9)</button>
        </div>
      </form>
    `;
    await this.modal(isNew ? 'Nuevo producto' : `Editar ${p.sku}`, html);

    const form = $('#form-prod');
    form.querySelector('[data-act=cancel]').onclick = () => { $('#modal').hidden = true; };
    const delBtn = form.querySelector('[data-act=del]');
    if (delBtn) delBtn.onclick = async () => {
      if (await this.confirm('¿Eliminar este producto? Solo si no tiene stock.')) {
        try { await API.del('/api/productos/' + id); $('#modal').hidden = true; this.router(); }
        catch (e) { alert(e.message); }
      }
    };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = Object.fromEntries(fd);
      // casts
      ['factor_compra','factor_venta','precio_compra','precio_venta',
       'stock_minimo','stock_maximo','peso_kg','volumen_m3'].forEach(k => {
        body[k] = parseFloat(body[k]) || 0;
      });
      ['familia_id'].forEach(k => { body[k] = body[k] ? parseInt(body[k]) : null; });
      try {
        if (isNew) await API.post('/api/productos', body);
        else await API.patch('/api/productos/' + id, body);
        $('#modal').hidden = true;
        this.status('Producto guardado ✓');
        this.router();
      } catch (e) {
        alert(e.message);
      }
    };
  },

  /* ============ PROVEEDORES / CLIENTES ============ */
  async view_proveedores() { return this.viewTerceros('proveedor', 'Proveedores'); },
  async view_clientes() { return this.viewTerceros('cliente', 'Clientes'); },

  async viewTerceros(tipo, titulo) {
    const q = this.cache(`terceros.${tipo}.q`, '');
    const data = await API.get('/api/terceros', {tipo, q});

    this.main(`
      <div class="view-header">
        <h2>${titulo} (${data.length})</h2>
        <div class="grow"></div>
        <input id="ter-q" placeholder="Buscar por código, nombre o CIF..." value="${q}" style="width:280px">
        <button id="ter-nuevo" class="btn-primary">+ Nuevo (F4)</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead>
            <tr>
              <th>Código</th><th>Nombre</th><th>CIF/NIF</th>
              <th>Dirección</th><th>Contacto</th>
              <th>Forma pago</th>
              <th class="num">Días</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(t => `
              <tr data-id="${t.id}">
                <td><strong>${t.codigo}</strong></td>
                <td>${t.nombre}</td>
                <td>${t.cif_nif || '-'}</td>
                <td>${(t.direccion||'') + (t.poblacion ? ', ' + t.poblacion : '')}</td>
                <td>${t.contacto || '-'}<br><small class="muted">${t.telefono||''}</small></td>
                <td>${t.forma_pago || '-'}</td>
                <td class="num">${t.dias_pago || '-'}</td>
              </tr>`).join('')}
            ${data.length === 0 ? `<tr><td colspan="7" class="loading">Sin ${titulo.toLowerCase()}. Pulsa F4.</td></tr>` : ''}
          </tbody>
        </table>
      </div>
    `);

    $('#ter-q').oninput = (e) => { this.cache(`terceros.${tipo}.q`, e.target.value); this.debounceReload(); };
    $('#ter-nuevo').onclick = () => this.terceroEdit(null, tipo);
    this.$$('tr[data-id]').forEach(tr => {
      tr.onclick = () => this.terceroEdit(parseInt(tr.dataset.id), tipo);
    });
  },

  async terceroEdit(id, tipo) {
    const isNew = !id;
    let t = id ? await API.get('/api/terceros/' + id) : {
      tipo, codigo: '', nombre: '', cif_nif: '', direccion: '',
      cp: '', poblacion: '', provincia: '', pais: 'España',
      telefono: '', email: '', contacto: '', web: '',
      iban: '', banco: '', forma_pago: '', dias_pago: 30,
      dia_pago_1: null, dia_pago_2: null,
      limite_credito: 0,
      regimen_iva: 'general', aplica_irpf: false, irpf_porcentaje: 0,
      recargo_equivalencia: false, notas: '',
    };
    const html = `
      <form id="form-ter">
        <div class="form-grid">
          <label>Código *<input name="codigo" value="${t.codigo||''}" required ${isNew?'':'readonly'}></label>
          <label>Tipo
            <select name="tipo">
              <option value="cliente" ${t.tipo==='cliente'?'selected':''}>Cliente</option>
              <option value="proveedor" ${t.tipo==='proveedor'?'selected':''}>Proveedor</option>
              <option value="ambos" ${t.tipo==='ambos'?'selected':''}>Ambos</option>
            </select>
          </label>
          <label class="full">Nombre *<input name="nombre" value="${t.nombre||''}" required></label>
          <label>Nombre comercial<input name="nombre_comercial" value="${t.nombre_comercial||''}"></label>
          <label>CIF/NIF<input name="cif_nif" value="${t.cif_nif||''}"></label>
          <label class="full">Dirección<input name="direccion" value="${t.direccion||''}"></label>
          <label>CP<input name="cp" value="${t.cp||''}"></label>
          <label>Población<input name="poblacion" value="${t.poblacion||''}"></label>
          <label>Provincia<input name="provincia" value="${t.provincia||''}"></label>
          <label>País<input name="pais" value="${t.pais||'España'}"></label>
          <label>Teléfono<input name="telefono" value="${t.telefono||''}"></label>
          <label>Email<input name="email" type="email" value="${t.email||''}"></label>
          <label>Contacto<input name="contacto" value="${t.contacto||''}"></label>
          <label>Web<input name="web" value="${t.web||''}"></label>
          <label>Banco<input name="banco" value="${t.banco||''}"></label>
          <label>IBAN<input name="iban" value="${t.iban||''}" placeholder="ES00 0000 0000 0000 0000 0000"></label>
          <label>Forma de pago<input name="forma_pago" value="${t.forma_pago||''}" placeholder="transferencia, contado, talón..."></label>
          <label>Días pago<input name="dias_pago" type="number" value="${t.dias_pago||30}"></label>
          <label>Día pago 1<input name="dia_pago_1" type="number" min="1" max="31" value="${t.dia_pago_1||''}"></label>
          <label>Día pago 2<input name="dia_pago_2" type="number" min="1" max="31" value="${t.dia_pago_2||''}"></label>
          <label>Límite crédito<input name="limite_credito" type="number" step="0.01" value="${t.limite_credito||0}"></label>

          <fieldset style="grid-column: 1/-1; padding:8px; margin:6px 0">
            <legend>Fiscal</legend>
            <label>Régimen IVA
              <select name="regimen_iva">
                <option value="general" ${t.regimen_iva==='general'?'selected':''}>General</option>
                <option value="recargo_equivalencia" ${t.regimen_iva==='recargo_equivalencia'?'selected':''}>Recargo equivalencia</option>
                <option value="simplificado" ${t.regimen_iva==='simplificado'?'selected':''}>Simplificado</option>
                <option value="exento" ${t.regimen_iva==='exento'?'selected':''}>Exento</option>
              </select>
            </label>
            <label><input type="checkbox" name="recargo_equivalencia" ${t.recargo_equivalencia?'checked':''}> Aplicar recargo equivalencia</label>
            <label><input type="checkbox" name="aplica_irpf" ${t.aplica_irpf?'checked':''}> Aplica IRPF (retención)</label>
            <label>% IRPF<input name="irpf_porcentaje" type="number" step="0.1" value="${t.irpf_porcentaje||0}"></label>
          </fieldset>

          <label class="full">Notas<textarea name="notas" rows="2">${t.notas||''}</textarea></label>
        </div>
        <div class="form-actions">
          <button type="button" class="btn" data-act="cancel">Cancelar (Esc)</button>
          <button type="submit" class="btn-primary">Guardar (F9)</button>
        </div>
      </form>
    `;
    await this.modal(isNew ? `Nuevo ${tipo}` : `Editar ${t.codigo}`, html);

    const form = $('#form-ter');
    form.querySelector('[data-act=cancel]').onclick = () => { $('#modal').hidden = true; };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(form));
      ['dias_pago','dia_pago_1','dia_pago_2','limite_credito'].forEach(k => {
        if (body[k] !== '' && body[k] != null) body[k] = parseFloat(body[k]) || 0;
      });
      ['aplica_irpf','recargo_equivalencia'].forEach(k => { body[k] = form.querySelector(`[name=${k}]`).checked; });
      body.irpf_porcentaje = parseFloat(body.irpf_porcentaje) || 0;
      try {
        if (isNew) await API.post('/api/terceros', body);
        else await API.patch('/api/terceros/' + id, body);
        $('#modal').hidden = true;
        this.status('Guardado ✓');
        this.router();
      } catch (e) { alert(e.message); }
    };
  },

  /* ============ OBRAS ============ */
  async view_obras() {
    const data = await API.get('/api/terceros/obras/all');
    this.main(`
      <div class="view-header">
        <h2>Obras (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nueva</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead><tr><th>Código</th><th>Nombre</th><th>Cliente</th><th>Estado</th><th>Inicio</th><th>Fin prevista</th><th class="num">Presupuesto</th></tr></thead>
          <tbody>
            ${data.map(o => `
              <tr>
                <td><strong>${o.codigo}</strong></td>
                <td>${o.nombre}</td>
                <td>${o.cliente_nombre || '-'}</td>
                <td><span class="badge-cell ${o.estado==='activa'?'ok':o.estado==='finalizada'?'warn':''}">${o.estado}</span></td>
                <td>${this.fmt.date(o.fecha_inicio)}</td>
                <td>${this.fmt.date(o.fecha_fin_prevista)}</td>
                <td class="num">${this.fmt.money(o.presupuesto)}</td>
              </tr>`).join('') || '<tr><td colspan="7" class="loading">Sin obras</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  /* ============ UBICACIONES ============ */
  async view_ubicaciones() {
    const data = await API.get('/api/ubicaciones');
    this.main(`
      <div class="view-header">
        <h2>Ubicaciones (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nueva</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead><tr><th>Código</th><th>Pasillo</th><th>Estantería</th><th>Hueco</th><th>Nivel</th><th class="num">Cap. kg</th><th class="num">Cap. m³</th></tr></thead>
          <tbody>
            ${data.map(u => `
              <tr><td><strong>${u.codigo}</strong></td><td>${u.pasillo}</td><td>${u.estanteria}</td><td>${u.hueco}</td><td>${u.nivel}</td><td class="num">${u.capacidad_kg||0}</td><td class="num">${u.capacidad_m3||0}</td></tr>`).join('') || '<tr><td colspan="7" class="loading">Sin ubicaciones</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  async view_familias() {
    const data = await API.get('/api/productos/familias');
    this.main(`
      <div class="view-header">
        <h2>Familias (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nueva</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead><tr><th>Código</th><th>Nombre</th><th>Descripción</th></tr></thead>
          <tbody>
            ${data.map(f => `<tr><td><strong>${f.codigo}</strong></td><td>${f.nombre}</td><td>${f.descripcion||'-'}</td></tr>`).join('') || '<tr><td colspan="3" class="loading">Sin familias</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  /* ============ COMPRAS / VENTAS (albaranes) ============ */
  async view_compras() {
    const data = await API.get('/api/albaranes/entrada', {limit: 200});
    this.main(this.albaranListHTML('Compras / Albaranes de entrada', data, 'entrada'));
  },
  async view_ventas() {
    const data = await API.get('/api/albaranes/salida', {limit: 200});
    this.main(this.albaranListHTML('Ventas / Albaranes de salida', data, 'salida'));
  },

  albaranListHTML(titulo, data, tipo) {
    return `
      <div class="view-header">
        <h2>${titulo} (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nuevo ${tipo === 'entrada' ? 'albarán' : ''}</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead><tr><th>Número</th><th>Fecha</th><th>${tipo==='entrada'?'Proveedor':'Cliente'}</th>${tipo==='salida'?'<th>Obra</th>':''}<th>Estado</th><th class="num">Total</th></tr></thead>
          <tbody>
            ${data.map(a => `
              <tr>
                <td><strong>${a.numero}</strong></td>
                <td>${this.fmt.date(a.fecha)}</td>
                <td>${a[tipo==='entrada'?'proveedor_nombre':'cliente_nombre']}</td>
                ${tipo==='salida'?'<td>'+(a.obra_nombre||'-')+'</td>':''}
                <td><span class="badge-cell ${a.estado==='confirmado'?'ok':''}">${a.estado}</span></td>
                <td class="num">${this.fmt.money(a.total)}</td>
              </tr>`).join('') || `<tr><td colspan="6" class="loading">Sin albaranes</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  },

  /* ============ FACTURACION ============ */
  async view_facturacion() {
    const [cli, prov] = await Promise.all([
      API.get('/api/facturacion/cliente', {limit: 100}),
      API.get('/api/facturacion/proveedor', {limit: 100}),
    ]);
    this.main(`
      <div class="view-header"><h2>Facturación</h2></div>

      <div class="panel">
        <div class="panel-title">📤 Facturas emitidas (${cli.length})</div>
        <table class="grid">
          <thead><tr><th>Número</th><th>Fecha</th><th>Vencimiento</th><th>Cliente</th><th>Estado</th><th class="num">Total</th><th class="num">IRPF</th><th class="num">Cobrado</th><th class="num">Pendiente</th></tr></thead>
          <tbody>
            ${cli.map(f => `
              <tr>
                <td><strong>${f.numero}</strong></td>
                <td>${this.fmt.date(f.fecha)}</td>
                <td>${this.fmt.date(f.fecha_vencimiento)}</td>
                <td>${f.cliente_nombre}</td>
                <td><span class="badge-cell ${f.estado==='pagada'?'ok':f.estado==='vencida'?'danger':'warn'}">${f.estado}</span></td>
                <td class="num">${this.fmt.money(f.total)}</td>
                <td class="num">${f.irpf_porcentaje?this.fmt.money(f.importe_irpf):'-'}</td>
                <td class="num">${this.fmt.money(f.cobrado)}</td>
                <td class="num"><strong>${this.fmt.money(f.pendiente)}</strong></td>
              </tr>`).join('') || '<tr><td colspan="9" class="loading">Sin facturas</td></tr>'}
          </tbody>
        </table>
      </div>

      <div class="panel mt-2">
        <div class="panel-title">📥 Facturas recibidas (${prov.length})</div>
        <table class="grid">
          <thead><tr><th>Número</th><th>Fecha</th><th>Vencimiento</th><th>Proveedor</th><th>Nº prov.</th><th>Estado</th><th class="num">Total</th><th class="num">IRPF</th><th class="num">Pagado</th><th class="num">Pendiente</th></tr></thead>
          <tbody>
            ${prov.map(f => `
              <tr>
                <td><strong>${f.numero}</strong></td>
                <td>${this.fmt.date(f.fecha)}</td>
                <td>${this.fmt.date(f.fecha_vencimiento)}</td>
                <td>${f.proveedor_nombre}</td>
                <td>${f.numero_proveedor||'-'}</td>
                <td><span class="badge-cell ${f.estado==='pagada'?'ok':f.estado==='vencida'?'danger':'warn'}">${f.estado}</span></td>
                <td class="num">${this.fmt.money(f.total)}</td>
                <td class="num">${f.irpf_porcentaje?this.fmt.money(f.importe_irpf):'-'}</td>
                <td class="num">${this.fmt.money(f.pagado)}</td>
                <td class="num"><strong>${this.fmt.money(f.pendiente)}</strong></td>
              </tr>`).join('') || '<tr><td colspan="10" class="loading">Sin facturas</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  /* ============ TESORERIA / VENCIMIENTOS ============ */
  async view_tesoreria() {
    const [ctas, movs] = await Promise.all([
      API.get('/api/tesoreria/cuentas'),
      API.get('/api/tesoreria/movimientos', {limit: 200}),
    ]);
    const saldo_total = ctas.reduce((s,c) => s + (c.saldo_actual||0), 0);
    this.main(`
      <div class="view-header"><h2>Tesorería</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nueva cuenta</button>
      </div>

      <div class="kpis">
        ${ctas.map(c => `<div class="kpi">
          <div class="kpi-label">${c.nombre}</div>
          <div class="kpi-value">${this.fmt.money(c.saldo_actual)}</div>
        </div>`).join('')}
        <div class="kpi success"><div class="kpi-label">TOTAL</div><div class="kpi-value">${this.fmt.money(saldo_total)}</div></div>
      </div>

      <div class="panel">
        <div class="panel-title">Movimientos recientes (${movs.length})</div>
        <table class="grid">
          <thead><tr><th>Fecha</th><th>Tipo</th><th>Cuenta</th><th>Concepto</th><th class="num">Importe</th><th class="center">Conciliado</th></tr></thead>
          <tbody>
            ${movs.map(m => `
              <tr>
                <td>${this.fmt.date(m.fecha)}</td>
                <td><span class="badge-cell ${m.tipo==='cobro'?'ok':m.tipo==='pago'?'danger':''}">${m.tipo}</span></td>
                <td>${m.cuenta_nombre}</td>
                <td>${m.concepto||''}</td>
                <td class="num ${m.importe<0?'danger':''}">${this.fmt.money(m.importe)}</td>
                <td class="center">${m.conciliado?'✓':''}</td>
              </tr>`).join('') || '<tr><td colspan="6" class="loading">Sin movimientos</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  async view_vencimientos() {
    const data = await API.get('/api/tesoreria/vencimientos', {dias: 30});
    this.main(`
      <div class="view-header"><h2>Vencimientos (próximos 30 días)</h2></div>
      <div class="panel">
        <div class="panel-title">📥 A pagar (${data.pagos.length})</div>
        <table class="grid">
          <thead><tr><th>Número</th><th>Vencimiento</th><th>Proveedor</th><th class="num">Importe</th></tr></thead>
          <tbody>
            ${data.pagos.map(p => `<tr><td>${p.numero}</td><td class="${p.vencida?'danger':''}">${this.fmt.date(p.vencimiento)} ${p.vencida?'⚠️':''}</td><td>${p.tercero_nombre}</td><td class="num">${this.fmt.money(p.importe)}</td></tr>`).join('') || '<tr><td colspan="4" class="loading">Nada pendiente</td></tr>'}
          </tbody>
        </table>
      </div>
      <div class="panel mt-2">
        <div class="panel-title">📤 A cobrar (${data.cobros.length})</div>
        <table class="grid">
          <thead><tr><th>Número</th><th>Vencimiento</th><th>Cliente</th><th class="num">Importe</th></tr></thead>
          <tbody>
            ${data.cobros.map(p => `<tr><td>${p.numero}</td><td class="${p.vencida?'danger':''}">${this.fmt.date(p.vencimiento)} ${p.vencida?'⚠️':''}</td><td>${p.tercero_nombre}</td><td class="num">${this.fmt.money(p.importe)}</td></tr>`).join('') || '<tr><td colspan="4" class="loading">Nada pendiente</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  /* ============ TPV ============ */
  async view_tpv() {
    const ses = await API.get('/api/tpv/sesion/actual');
    this.main(`
      <div class="view-header"><h2>💵 Punto de venta (TPV)</h2></div>
      <div class="panel">
        <div class="panel-title">Sesión de caja</div>
        <div style="padding:14px">
          ${ses.abierta ? `
            <p><strong>Sesión abierta #${ses.id}</strong></p>
            <p>Saldo inicial: ${this.fmt.money(ses.saldo_inicial)}</p>
            <p>Saldo teórico: ${this.fmt.money(ses.saldo_teorico)}</p>
            <p>Tickets emitidos: ${ses.tickets_count}</p>
            <button class="btn-danger" id="tpv-cerrar">Cerrar caja</button>
          ` : `
            <p>No tienes sesión abierta.</p>
            <label>Saldo inicial <input id="tpv-saldo" type="number" step="0.01" value="0"></label>
            <button class="btn-primary" id="tpv-abrir">Abrir caja</button>
          `}
        </div>
      </div>
      <p class="muted small mt-2">Módulo de venta rápida (en desarrollo completo).</p>
    `);
    const abrir = $('#tpv-abrir');
    if (abrir) abrir.onclick = async () => {
      try {
        await API.post('/api/tpv/sesion/abrir', {saldo_inicial: parseFloat($('#tpv-saldo').value) || 0});
        this.router();
      } catch (e) { alert(e.message); }
    };
    const cerrar = $('#tpv-cerrar');
    if (cerrar) cerrar.onclick = async () => {
      const real = parseFloat(prompt('Saldo real en caja:', ses.saldo_teorico));
      if (isNaN(real)) return;
      try {
        const r = await API.post(`/api/tpv/sesion/${ses.id}/cerrar`,
          {saldo_final_real: real});
        alert(`Caja cerrada.\nTeórico: ${this.fmt.money(r.saldo_teorico)}\nReal: ${this.fmt.money(r.saldo_real)}\nDiferencia: ${this.fmt.money(r.diferencia)}`);
        this.router();
      } catch (e) { alert(e.message); }
    };
  },

  /* ============ TRASPASOS / INVENTARIO ============ */
  async view_traspasos() {
    const data = await API.get('/api/traspasos');
    this.main(`
      <div class="view-header"><h2>Traspasos entre ubicaciones (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nuevo traspaso</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead><tr><th>Número</th><th>Fecha</th><th>Motivo</th><th class="num">Líneas</th></tr></thead>
          <tbody>
            ${data.map(t => `<tr><td><strong>${t.numero}</strong></td><td>${this.fmt.datetime(t.fecha)}</td><td>${t.motivo||'-'}</td><td class="num">${t.lineas_count}</td></tr>`).join('') || '<tr><td colspan="4" class="loading">Sin traspasos</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  async view_inventario() {
    const data = await API.get('/api/inventario');
    this.main(`
      <div class="view-header"><h2>Inventario físico / recuentos (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary">+ Nuevo recuento</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead><tr><th>Nombre</th><th>Fecha</th><th>Estado</th><th class="num">Líneas</th></tr></thead>
          <tbody>
            ${data.map(i => `<tr><td>${i.nombre}</td><td>${this.fmt.date(i.fecha)}</td><td><span class="badge-cell ${i.estado==='cerrado'?'ok':'warn'}">${i.estado}</span></td><td class="num">${i.lineas}</td></tr>`).join('') || '<tr><td colspan="4" class="loading">Sin recuentos</td></tr>'}
          </tbody>
        </table>
      </div>
    `);
  },

  /* ============ ALMACENES ============ */
  async view_almacenes() {
    const data = await API.get('/api/almacenes');
    this.main(`
      <div class="view-header">
        <h2>🏢 Almacenes (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary" id="alm-nuevo">+ Nuevo almacén (F4)</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead>
            <tr>
              <th>Código</th><th>Nombre</th><th>Dirección</th><th>Población</th>
              <th>Teléfono</th><th class="num">Ubicaciones</th>
              <th class="num">Valor stock</th><th>Principal</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(a => `
              <tr data-id="${a.id}">
                <td><strong>${a.codigo}</strong></td>
                <td>${a.nombre}</td>
                <td>${a.direccion || '-'}</td>
                <td>${a.poblacion || '-'}</td>
                <td>${a.telefono || '-'}</td>
                <td class="num">${a.ubicaciones_count}</td>
                <td class="num">${this.fmt.money(a.stock_valor)}</td>
                <td>${a.es_principal ? '<span class="badge-cell ok">Principal</span>' : ''}</td>
              </tr>`).join('')}
            ${data.length === 0 ? '<tr><td colspan="8" class="loading">Sin almacenes. Pulsa F4.</td></tr>' : ''}
          </tbody>
        </table>
      </div>
    `);
    $('#alm-nuevo').onclick = () => this.almacenEdit(null);
    this.$$('tr[data-id]').forEach(tr => {
      tr.onclick = () => this.almacenEdit(parseInt(tr.dataset.id));
    });
  },

  async almacenEdit(id) {
    const isNew = !id;
    let a = isNew ? {
      codigo: '', nombre: '', direccion: '', cp: '', poblacion: '', provincia: '',
      telefono: '', email: '', contacto: '', es_principal: false, notas: '',
    } : await API.get('/api/almacenes').then(arr => arr.find(x => x.id === id));

    const html = `
      <form id="form-alm">
        <div class="form-grid">
          <label>Código *<input name="codigo" value="${a.codigo||''}" required ${isNew?'':'readonly'}></label>
          <label class="full">Nombre *<input name="nombre" value="${a.nombre||''}" required></label>
          <label class="full">Dirección<input name="direccion" value="${a.direccion||''}"></label>
          <label>CP<input name="cp" value="${a.cp||''}"></label>
          <label>Población<input name="poblacion" value="${a.poblacion||''}"></label>
          <label>Provincia<input name="provincia" value="${a.provincia||''}"></label>
          <label>Teléfono<input name="telefono" value="${a.telefono||''}"></label>
          <label>Email<input name="email" value="${a.email||''}"></label>
          <label>Contacto<input name="contacto" value="${a.contacto||''}"></label>
          <label class="full"><input type="checkbox" name="es_principal" ${a.es_principal?'checked':''}> Almacén principal (entradas por defecto)</label>
          <label class="full">Notas<textarea name="notas" rows="2">${a.notas||''}</textarea></label>
        </div>
        <div class="form-actions">
          <button type="button" class="btn" data-act="cancel">Cancelar (Esc)</button>
          ${isNew ? '' : '<button type="button" class="btn-danger" data-act="del">Eliminar</button>'}
          <button type="submit" class="btn-primary">Guardar (F9)</button>
        </div>
      </form>
    `;
    await this.modal(isNew ? 'Nuevo almacén' : `Editar ${a.codigo}`, html);
    const form = $('#form-alm');
    form.querySelector('[data-act=cancel]').onclick = () => { $('#modal').hidden = true; };
    const delBtn = form.querySelector('[data-act=del]');
    if (delBtn) delBtn.onclick = async () => {
      if (await this.confirm('¿Eliminar este almacén? Solo si no tiene stock.')) {
        try { await API.del('/api/almacenes/' + id); $('#modal').hidden = true; this.router(); }
        catch (e) { alert(e.message); }
      }
    };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = Object.fromEntries(fd);
      body.es_principal = form.querySelector('[name=es_principal]').checked;
      try {
        if (isNew) await API.post('/api/almacenes', body);
        else await API.patch('/api/almacenes/' + id, body);
        $('#modal').hidden = true;
        this.status('Almacén guardado ✓');
        this.router();
      } catch (e) { alert(e.message); }
    };
  },

  /* ============ TRANSITOS ============ */
  async view_transitos() {
    const data = await API.get('/api/transitos');
    this.main(`
      <div class="view-header">
        <h2>🚚 Tránsitos entre almacenes (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary" id="trn-nuevo">+ Nuevo tránsito (F4)</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead>
            <tr>
              <th>Número</th><th>Fecha envío</th><th>Origen</th><th>Destino</th>
              <th>Transportista</th><th class="num">Líneas</th>
              <th class="num">Bultos</th><th class="num">Kg</th><th>Estado</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(t => `
              <tr data-id="${t.id}">
                <td><strong>${t.numero}</strong></td>
                <td>${this.fmt.date(t.fecha_envio)}</td>
                <td>${t.almacen_origen}</td>
                <td>${t.almacen_destino}</td>
                <td>${t.transportista||'-'}</td>
                <td class="num">${t.lineas_count}</td>
                <td class="num">${t.bultos}</td>
                <td class="num">${this.fmt.num(t.peso_kg)}</td>
                <td><span class="badge-cell ${t.estado==='recibido'?'ok':t.estado==='en_transito'?'warn':t.estado==='cancelado'?'danger':''}">${t.estado}</span></td>
              </tr>`).join('')}
            ${data.length === 0 ? '<tr><td colspan="9" class="loading">Sin tránsitos. Pulsa F4 para crear uno.</td></tr>' : ''}
          </tbody>
        </table>
      </div>
    `);
    $('#trn-nuevo').onclick = () => this.transitoEdit(null);
    this.$$('tr[data-id]').forEach(tr => {
      tr.onclick = () => this.transitoDetalle(parseInt(tr.dataset.id));
    });
  },

  async transitoEdit(id) {
    const almacenes = await API.get('/api/almacenes');
    if (almacenes.length < 2) {
      alert('Necesitas al menos 2 almacenes para crear un tránsito.');
      return;
    }
    const html = `
      <form id="form-trn">
        <div class="form-grid">
          <label>Almacén origen *
            <select name="almacen_origen_id" required>
                <option value="">-- elige --</option>
                ${almacenes.map(a => `<option value="${a.id}">${a.codigo} - ${a.nombre}</option>`).join('')}
            </select>
          </label>
          <label>Almacén destino *
            <select name="almacen_destino_id" required>
                <option value="">-- elige --</option>
                ${almacenes.map(a => `<option value="${a.id}">${a.codigo} - ${a.nombre}</option>`).join('')}
            </select>
          </label>
          <label>Transportista<input name="transportista"></label>
          <label>Matrícula<input name="matricula"></label>
          <label class="num">Bultos<input name="bultos" type="number" value="0"></label>
          <label class="num">Peso (kg)<input name="peso_kg" type="number" step="0.1" value="0"></label>
          <label class="full">Motivo<input name="motivo"></label>
          <label class="full">Notas<textarea name="notas" rows="2"></textarea></label>
          <label class="full">Productos (líneas):
            <textarea name="lineas_texto" rows="6" placeholder="SKU,cantidad&#10;CEM001,10&#10;LAD001,100"></textarea>
            <small class="muted">Una línea por producto. Formato: SKU,cantidad</small>
          </label>
        </div>
        <div class="form-actions">
          <button type="button" class="btn" data-act="cancel">Cancelar (Esc)</button>
          <button type="submit" class="btn-primary">Crear tránsito (F9)</button>
        </div>
      </form>
    `;
    await this.modal('Nuevo tránsito entre almacenes', html);
    const form = $('#form-trn');
    form.querySelector('[data-act=cancel]').onclick = () => { $('#modal').hidden = true; };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = {
        almacen_origen_id: parseInt(fd.get('almacen_origen_id')),
        almacen_destino_id: parseInt(fd.get('almacen_destino_id')),
        transportista: fd.get('transportista'),
        matricula: fd.get('matricula'),
        bultos: parseInt(fd.get('bultos')) || 0,
        peso_kg: parseFloat(fd.get('peso_kg')) || 0,
        motivo: fd.get('motivo'),
        notas: fd.get('notas'),
        lineas: [],
      };
      // parsear lineas_texto
      const texto = (fd.get('lineas_texto') || '').toString().trim();
      if (!texto) { alert('Añade al menos una línea de productos'); return; }
      // buscar productos por SKU
      const prods = await API.get('/api/productos?limit=5000');
      const skuMap = {};
      prods.forEach(p => skuMap[p.sku.toUpperCase()] = p);
      for (const ln of texto.split('\n')) {
        const [sku, cant] = ln.split(',').map(s => s.trim());
        if (!sku || !cant) continue;
        const p = skuMap[sku.toUpperCase()];
        if (!p) { alert('SKU no encontrado: ' + sku); return; }
        body.lineas.push({ producto_id: p.id, cantidad: parseFloat(cant) });
      }
      if (body.lineas.length === 0) { alert('Sin líneas válidas'); return; }
      try {
        const r = await API.post('/api/transitos', body);
        alert('Tránsito creado: ' + r.numero);
        $('#modal').hidden = true;
        this.router();
      } catch (e) { alert(e.message); }
    };
  },

  async transitoDetalle(id) {
    // list + alert (podria ser un modal mejor)
    const data = await API.get('/api/transitos');
    const t = data.find(x => x.id === id);
    if (!t) return;
    const txt = `Tránsito ${t.numero}\n` +
      `Origen: ${t.almacen_origen}\n` +
      `Destino: ${t.almacen_destino}\n` +
      `Estado: ${t.estado}\n` +
      `Líneas: ${t.lineas_count}\n` +
      `\nSi quieres recibir o cancelar, pulsa el botón correspondiente.`;
    alert(txt);
    // botones rapidos
    if (confirm('¿Recibir tránsito completo ahora?')) {
      try { await API.post(`/api/transitos/${id}/recibir`, {}); this.router(); }
      catch (e) { alert(e.message); }
    } else if (confirm('¿Cancelar tránsito?')) {
      try { await API.post(`/api/transitos/${id}/cancelar`); this.router(); }
      catch (e) { alert(e.message); }
    }
  },

  /* ============ HOJAS DE CARGA ============ */
  async view_hojas_carga() {
    const data = await API.get('/api/expediciones/hojas');
    this.main(`
      <div class="view-header">
        <h2>📋 Hojas de carga (${data.length})</h2>
        <div class="grow"></div>
        <button class="btn-primary" id="hc-nueva">+ Nueva hoja (F4)</button>
      </div>
      <div class="panel">
        <table class="grid">
          <thead>
            <tr>
              <th>Número</th><th>Fecha</th><th>Transportista</th><th>Matrícula</th>
              <th>Conductor</th><th>Ruta</th>
              <th class="num">Expediciones</th>
              <th class="num">Bultos</th>
              <th class="num">Kg</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(h => `
              <tr data-id="${h.id}">
                <td><strong>${h.numero}</strong></td>
                <td>${this.fmt.date(h.fecha)}</td>
                <td>${h.transportista||'-'}</td>
                <td>${h.matricula||'-'}</td>
                <td>${h.conductor||'-'}</td>
                <td>${h.ruta||'-'}</td>
                <td class="num">${h.expediciones_count}</td>
                <td class="num">${h.bultos_total}</td>
                <td class="num">${this.fmt.num(h.peso_kg_total)}</td>
                <td><span class="badge-cell ${h.estado==='completada'?'ok':h.estado==='en_curso'?'warn':''}">${h.estado}</span></td>
              </tr>`).join('')}
            ${data.length === 0 ? '<tr><td colspan="10" class="loading">Sin hojas de carga. Crea una desde "+ Nueva" o desde Pendientes de expedir.</td></tr>' : ''}
          </tbody>
        </table>
      </div>
    `);
    $('#hc-nueva').onclick = () => this.hojaCargaEdit(null);
    this.$$('tr[data-id]').forEach(tr => {
      tr.onclick = () => this.hojaCargaDetalle(parseInt(tr.dataset.id));
    });
  },

  async hojaCargaEdit(id) {
    const almacenes = await API.get('/api/almacenes');
    const html = `
      <form id="form-hc">
        <div class="form-grid">
          <label>Fecha<input name="fecha" type="date" value="${new Date().toISOString().slice(0,10)}"></label>
          <label>Almacén origen
            <select name="almacen_origen_id">
              <option value="">-- sin asignar --</option>
              ${almacenes.map(a => `<option value="${a.id}">${a.codigo} - ${a.nombre}</option>`).join('')}
            </select>
          </label>
          <label>Transportista<input name="transportista"></label>
          <label>Matrícula<input name="matricula"></label>
          <label class="full">Conductor<input name="conductor"></label>
          <label class="full">Ruta / descripción<input name="ruta" placeholder="Polígono Sur → Centro → Polígono Norte"></label>
          <label class="full">Notas<textarea name="notas" rows="2"></textarea></label>
          <label class="full">Expediciones (líneas):
            <textarea name="expediciones_texto" rows="6" placeholder="cliente_id|obra_id|direccion|poblacion|cp|bultos|peso|ventana"></textarea>
            <small class="muted">Una línea por entrega. Campos separados por |.</small>
          </label>
        </div>
        <div class="form-actions">
          <button type="button" class="btn" data-act="cancel">Cancelar (Esc)</button>
          <button type="submit" class="btn-primary">Crear hoja (F9)</button>
        </div>
      </form>
    `;
    await this.modal('Nueva hoja de carga', html);
    const form = $('#form-hc');
    form.querySelector('[data-act=cancel]').onclick = () => { $('#modal').hidden = true; };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = {
        fecha: fd.get('fecha'),
        almacen_origen_id: fd.get('almacen_origen_id') ? parseInt(fd.get('almacen_origen_id')) : null,
        transportista: fd.get('transportista'),
        matricula: fd.get('matricula'),
        conductor: fd.get('conductor'),
        ruta: fd.get('ruta'),
        notas: fd.get('notas'),
        expediciones: [],
      };
      // parsear expediciones
      const texto = (fd.get('expediciones_texto') || '').toString().trim();
      if (texto) {
        const lineas = texto.split('\n');
        for (let i = 0; i < lineas.length; i++) {
          const parts = lineas[i].split('|').map(s => s.trim());
          body.expediciones.push({
            orden: i,
            cliente_id: parts[0] ? parseInt(parts[0]) : null,
            obra_id: parts[1] ? parseInt(parts[1]) : null,
            direccion_entrega: parts[2] || null,
            poblacion_entrega: parts[3] || null,
            cp_entrega: parts[4] || null,
            bultos: parts[5] ? parseInt(parts[5]) : 0,
            peso_kg: parts[6] ? parseFloat(parts[6]) : 0,
            ventana_horaria: parts[7] || null,
          });
        }
      }
      try {
        const r = await API.post('/api/expediciones/hojas', body);
        alert('Hoja creada: ' + r.numero);
        $('#modal').hidden = true;
        this.router();
      } catch (e) { alert(e.message); }
    };
  },

  async hojaCargaDetalle(id) {
    const h = await API.get(`/api/expediciones/hojas/${id}`);
    const html = `
      <div style="padding:14px">
        <h3>Hoja ${h.numero}</h3>
        <p class="muted">${h.fecha} · ${h.transportista||'-'} · ${h.matricula||'-'} · ${h.conductor||'-'}</p>
        <p><strong>Ruta:</strong> ${h.ruta || '(sin ruta)'}</p>
        <p><strong>Estado:</strong> ${h.estado}</p>
        <p><strong>Totales:</strong> ${h.bultos_total} bultos, ${this.fmt.num(h.peso_kg_total)} kg</p>
        ${h.notas ? `<p><strong>Notas:</strong> ${h.notas}</p>` : ''}

        <h4>Expediciones (${h.expediciones.length})</h4>
        <table class="grid">
          <thead>
            <tr>
              <th>#</th><th>Cliente</th><th>Obra</th>
              <th>Dirección</th><th>Población</th>
              <th>Ventana</th><th class="num">Bultos</th>
              <th class="num">Kg</th><th>Estado</th>
            </tr>
          </thead>
          <tbody>
            ${h.expediciones.map(e => `
              <tr>
                <td>${e.orden+1}</td>
                <td>${e.cliente_nombre||'-'}</td>
                <td>${e.obra_nombre||'-'}</td>
                <td>${e.direccion_entrega||'-'}</td>
                <td>${e.poblacion_entrega||'-'}</td>
                <td>${e.ventana_horaria||'-'}</td>
                <td class="num">${e.bultos}</td>
                <td class="num">${this.fmt.num(e.peso_kg)}</td>
                <td>
                  <select data-eid="${e.id}" class="exp-estado">
                    ${['pendiente','entregado','parcial','incidencia','devuelto'].map(s =>
                      `<option value="${s}" ${s===e.estado?'selected':''}>${s}</option>`
                    ).join('')}
                  </select>
                </td>
              </tr>`).join('') || '<tr><td colspan="9" class="loading">Sin expediciones</td></tr>'}
          </tbody>
        </table>
        <div class="form-actions">
          <button class="btn" data-act="cancel">Cerrar</button>
          ${h.estado !== 'completada' ? '<button class="btn-success" data-act="completar">Marcar completada</button>' : ''}
        </div>
      </div>
    `;
    await this.modal(`Hoja ${h.numero}`, html);
    $('#modal-body').querySelector('[data-act=cancel]').onclick = () => { $('#modal').hidden = true; };
    const compl = $('#modal-body').querySelector('[data-act=completar]');
    if (compl) compl.onclick = async () => {
      try { await API.post(`/api/expediciones/hojas/${id}/completar`); $('#modal').hidden = true; this.router(); }
      catch (e) { alert(e.message); }
    };
    // cambios de estado
    this.$$('#modal-body .exp-estado').forEach(sel => {
      sel.onchange = async () => {
        const eid = parseInt(sel.dataset.eid);
        try { await API.post(`/api/expediciones/hojas/${id}/expediciones/${eid}/estado`, {estado: sel.value}); }
        catch (e) { alert(e.message); }
      };
    });
  },

  /* ============ PENDIENTES EXPEDIR ============ */
  async view_pendientes_expedir() {
    const data = await API.get('/api/expediciones/pendientes');
    this.main(`
      <div class="view-header">
        <h2>📤 Albaranes pendientes de expedir (${data.length})</h2>
        <div class="grow"></div>
        <a href="#hojas_carga" class="btn-primary">Crear hoja de carga</a>
      </div>
      <div class="panel">
        <table class="grid">
          <thead>
            <tr>
              <th>Número</th><th>Fecha</th><th>Cliente</th><th>Obra</th>
              <th>Dirección</th><th>Población</th><th class="num">Total</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(a => `
              <tr>
                <td><strong>${a.numero}</strong></td>
                <td>${this.fmt.date(a.fecha)}</td>
                <td>${a.cliente_nombre}</td>
                <td>${a.obra_nombre||'-'}</td>
                <td>${a.direccion||'-'}</td>
                <td>${a.poblacion||'-'}</td>
                <td class="num">${this.fmt.money(a.total)}</td>
              </tr>`).join('') || '<tr><td colspan="7" class="loading">No hay albaranes pendientes</td></tr>'}
          </tbody>
        </table>
      </div>
      <p class="muted mt-2">💡 Estos albaranes de salida ya están confirmados pero no están asignados a ninguna hoja de carga. Crea una hoja y agrúpalos para una ruta de transporte.</p>
    `);
  },

  /* ============ IMPORTAR ============ */
  async view_importar() {
    this.main(`
      <div class="view-header"><h2>Importar desde CSV</h2></div>
      <div class="panel">
        <div class="panel-title">Importar productos</div>
        <div style="padding:14px">
          <p>Sube un CSV con columnas: <code>sku,nombre,familia,unidad_stock,precio_compra,precio_venta,iva,stock_minimo,stock_actual,codigo_barras,marca,modelo,peso_kg</code></p>
          <p class="muted small">Separador recomendado: <code>;</code></p>
          <input type="file" id="imp-prod" accept=".csv,.txt">
          <button id="imp-prod-go" class="btn-primary">Importar productos</button>
          <div id="imp-prod-res" class="mt-2"></div>
        </div>
      </div>
      <div class="panel mt-2">
        <div class="panel-title">Importar clientes / proveedores</div>
        <div style="padding:14px">
          <p>Columnas: <code>codigo,nombre,cif_nif,direccion,cp,poblacion,provincia,telefono,email,forma_pago,dias_pago,iban</code></p>
          <select id="imp-ter-tipo">
            <option value="cliente">Clientes</option>
            <option value="proveedor">Proveedores</option>
          </select>
          <input type="file" id="imp-ter" accept=".csv,.txt">
          <button id="imp-ter-go" class="btn-primary">Importar</button>
          <div id="imp-ter-res" class="mt-2"></div>
        </div>
      </div>
    `);

    $('#imp-prod-go').onclick = async () => {
      const f = $('#imp-prod').files[0];
      if (!f) return alert('Selecciona un fichero');
      try {
        const r = await API.upload('/api/importar/productos', f);
        $('#imp-prod-res').innerHTML = `<div class="success">
          Importados: ${r.creados} creados, ${r.actualizados} actualizados, ${r.total} total.
          ${r.errores.length ? '<br>Errores: <pre>' + r.errores.join('\n') + '</pre>' : ''}
        </div>`;
      } catch (e) { alert(e.message); }
    };
    $('#imp-ter-go').onclick = async () => {
      const f = $('#imp-ter').files[0];
      if (!f) return alert('Selecciona un fichero');
      const tipo = $('#imp-ter-tipo').value;
      try {
        const r = await API.upload(`/api/importar/terceros?tipo=${tipo}`, f);
        $('#imp-ter-res').innerHTML = `<div class="success">
          Importados: ${r.creados} creados, ${r.actualizados} actualizados, ${r.total} total.
          ${r.errores.length ? '<br>Errores: <pre>' + r.errores.join('\n') + '</pre>' : ''}
        </div>`;
      } catch (e) { alert(e.message); }
    };
  },

  /* ============ CONFIGURACION ============ */
  async view_config() {
    const [emp, plan, planes] = await Promise.all([
      API.get('/api/empresa'),
      API.get('/api/empresa/suscripcion'),
      API.get('/api/planes'),
    ]);
    this.main(`
      <div class="view-header"><h2>Configuración</h2></div>
      <div class="panel">
        <div class="panel-title">Datos de la empresa</div>
        <div style="padding:14px">
          <form id="form-emp">
            <div class="form-grid">
              <label>Nombre <input name="nombre" value="${emp.nombre}"></label>
              <label>Nombre comercial <input name="nombre_comercial" value="${emp.nombre_comercial||''}"></label>
              <label>CIF <input name="cif" value="${emp.cif||''}"></label>
              <label>Dirección <input name="direccion" value="${emp.direccion||''}"></label>
              <label>CP <input name="cp" value="${emp.cp||''}"></label>
              <label>Población <input name="poblacion" value="${emp.poblacion||''}"></label>
              <label>Teléfono <input name="telefono" value="${emp.telefono||''}"></label>
              <label>Email <input name="email" value="${emp.email||''}"></label>
              <label>Web <input name="web" value="${emp.web||''}"></label>
              <label>Color primario <input name="color_primario" value="${emp.color_primario||'#2563eb'}" type="color"></label>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn-primary">Guardar</button>
            </div>
          </form>
        </div>
      </div>

      <div class="panel mt-2">
        <div class="panel-title">Plan actual: ${plan.plan_nombre || 'Sin plan'} (${plan.estado})</div>
        <div style="padding:14px">
          ${plan.fecha_fin ? `<p>Fecha fin: ${this.fmt.date(plan.fecha_fin)}</p>` : ''}
          ${plan.fecha_proxima_renovacion ? `<p>Próxima renovación: ${this.fmt.date(plan.fecha_proxima_renovacion)}</p>` : ''}
        </div>
      </div>

      <div class="panel mt-2">
        <div class="panel-title">Planes disponibles</div>
        <div style="padding:14px">
          ${planes.map(p => `<div style="padding:8px;border:1px solid var(--border);margin-bottom:6px">
            <strong>${p.nombre}</strong> — ${p.precio_mensual} €/mes o ${p.precio_anual} €/año
            <p class="small muted">${p.descripcion || ''}</p>
            <ul class="small">
              ${Object.entries(p.features || {}).filter(([_,v]) => v).map(([k]) =>
                `<li>✓ ${this.featName(k)}</li>`).join('')}
            </ul>
            <button class="btn">Mejorar a ${p.nombre}</button>
          </div>`).join('')}
        </div>
      </div>
    `);

    $('#form-emp').onsubmit = async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target));
      try {
        await API.patch('/api/empresa', body);
        this.status('Empresa actualizada ✓');
      } catch (e) { alert(e.message); }
    };
  },

  /* ============ CACHE & UTIL ============ */
  cache: {},
  cacheGet(k, def) { return this.cache[k] !== undefined ? this.cache[k] : def; },
  cacheSet(k, v) { this.cache[k] = v; },
  cache(k, v) { if (v !== undefined) this.cache[k] = v; return this.cache[k]; },

  debounceReload() {
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.router(), 300);
  },

  /* ============ BUSQUEDA GLOBAL ============ */
  async doSearch(q) {
    if (!q || q.length < 2) { $('#search-results').hidden = true; return; }
    try {
      const r = await API.get('/api/dashboard/buscar', {q});
      const cont = $('#search-results');
      let html = '';
      if (r.productos.length) {
        html += '<div class="sr-cat">Productos</div>';
        r.productos.forEach(p => {
          html += `<div class="sr-item" data-go="productos" data-id="${p.id}">
            <strong>${p.sku}</strong> — ${p.nombre} <small class="muted">(stock: ${this.fmt.num(p.stock)})</small>
          </div>`;
        });
      }
      if (r.terceros.length) {
        html += '<div class="sr-cat">Terceros</div>';
        r.terceros.forEach(t => {
          html += `<div class="sr-item" data-go="${t.tipo==='cliente'?'clientes':'proveedores'}" data-id="${t.id}">
            <strong>${t.codigo}</strong> — ${t.nombre} <small class="muted">(${t.tipo})</small>
          </div>`;
        });
      }
      if (r.obras.length) {
        html += '<div class="sr-cat">Obras</div>';
        r.obras.forEach(o => {
          html += `<div class="sr-item" data-go="obras" data-id="${o.id}">
            <strong>${o.codigo}</strong> — ${o.nombre}
          </div>`;
        });
      }
      if (!html) html = '<div class="sr-empty">Sin resultados</div>';
      cont.innerHTML = html;
      cont.hidden = false;
      cont.querySelectorAll('.sr-item[data-go]').forEach(it => {
        it.onclick = () => { cont.hidden = true; this.go(it.dataset.go); };
      });
    } catch (e) {}
  },
};

/* ============ EVENTOS GLOBALES ============ */
window.addEventListener('hashchange', () => App.me && App.router());

document.addEventListener('DOMContentLoaded', () => {
  $('#form-setup').addEventListener('submit', (e) => App.doSetup(e));
  $('#form-login').addEventListener('submit', (e) => App.doLogin(e));
  $('#btn-logout').addEventListener('click', () => App.logout());

  // busqueda global
  $('#search-global').addEventListener('input', (e) => App.doSearch(e.target.value));
  $('#search-global').addEventListener('blur', () => setTimeout(() => $('#search-results').hidden = true, 200));
  $('#search-global').addEventListener('focus', (e) => { if (e.target.value) App.doSearch(e.target.value); });

  // atajos de teclado estilo BigTech
  document.addEventListener('keydown', (e) => {
    // Ctrl+B = buscar
    if (e.ctrlKey && e.key === 'b') { e.preventDefault(); $('#search-global').focus(); return; }
    if (!$('#app').hidden === false) return;
    if ($('#modal').hidden === false) return; // modal captura sus propios atajos
    // F4 = nuevo
    if (e.key === 'F4') {
      e.preventDefault();
      if (App.currentView === 'productos') App.productoEdit(null);
      else if (App.currentView === 'proveedores') App.terceroEdit(null, 'proveedor');
      else if (App.currentView === 'clientes') App.terceroEdit(null, 'cliente');
    }
    // F5 = recargar vista
    if (e.key === 'F5') { e.preventDefault(); App.router(); }
  });

  App.init();
});