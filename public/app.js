/* ═══════════════════════════════════════════════════
   app.js — Risena Dashboard
   JS dipisah dari index.html (kode lama tidak diubah)
   + Fitur Login / Logout ditambahkan di bawah
═══════════════════════════════════════════════════ */

// ─────────────────────────────────────────────────────
// CONSTANTS & STATE
// ─────────────────────────────────────────────────────
const catColors   = { Tas:'#8b4513', Dompet:'#2d3561', Souvenir:'#3a7d44', Lainnya:'#c9972a' };
const bahanColors = { Kain:'#8b4513', Aksesori:'#2d3561', Benang:'#3a7d44', Kemasan:'#c9972a', Lainnya:'#0d7377' };
const fmt   = n => 'Rp ' + Number(n||0).toLocaleString('id-ID');
const fmtK  = n => n>=1000000 ? 'Rp '+(n/1000000).toFixed(1)+'jt' : n>=1000 ? 'Rp '+(n/1000).toFixed(0)+'rb' : fmt(n);
const today = () => new Date().toISOString().split('T')[0];
const fmtNum = n => Number(n||0).toLocaleString('id-ID', {maximumFractionDigits:2});

let products     = [];
let materials    = [];
let prices       = [];
let orderHistory = [];
let cashflows    = [];
let orderItems   = [];
let orderIdCtr   = 1;
let cfType       = 'in';
let adjType      = 'in';
let charts       = {};
let periods      = { revenue:1, product:1, category:1, cf:3 };

// ─────────────────────────────────────────────────────
// API HELPERS
// ─────────────────────────────────────────────────────
async function api(path, method='GET', body=null) {
  const opts = { method, headers:{'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (!r.ok) { const e = await r.json().catch(()=>({})); throw new Error(e.detail||e.error||'Error'); }
  return r.json();
}

// ─────────────────────────────────────────────────────
// MOBILE SIDEBAR
// ─────────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const ham     = document.getElementById('hamburger-btn');
  const isOpen  = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
    ham.classList.remove('hidden');
  } else {
    sidebar.classList.add('open');
    overlay.classList.add('open');
    ham.classList.add('hidden');
  }
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('open');
  document.getElementById('hamburger-btn').classList.remove('hidden');
}

// ─────────────────────────────────────────────────────
// LOAD DATA
// ─────────────────────────────────────────────────────
async function loadAllData() {
  try {
    const [prods, mats, prcs, ords, cfs] = await Promise.all([
      api('/api/products'),
      api('/api/materials'),
      api('/api/prices'),
      api('/api/orders'),
      api('/api/cashflows'),
    ]);
    products     = prods;
    materials    = mats;
    prices       = prcs;
    orderHistory = ords.map(o => ({ ...o, date: new Date(o.date) }));
    cashflows    = cfs.map(c  => ({ ...c, date: new Date(c.date) }));
    // Set order counter
    const maxOrd = orderHistory.reduce((max, o) => {
      const num = parseInt(o.id.replace('ORD-','')) || 0;
      return num > max ? num : max;
    }, 0);
    orderIdCtr = maxOrd + 1;
  } catch(e) {
    toast('⚠️ Gagal memuat data: ' + e.message);
  }
}

// ─────────────────────────────────────────────────────
// NAVIGASI
// ─────────────────────────────────────────────────────
function navigate(page, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-'+page).classList.add('active');
  if (el) el.classList.add('active');
  closeSidebar();
  if (page==='dashboard')   renderDashboard();
  if (page==='stok')        renderStok();
  if (page==='bahan')       renderBahan();
  if (page==='harga')       renderHarga();
  if (page==='order')       { renderOrderProducts(); renderOrderSummary(); updateOrderTotal(); }
  if (page==='riwayat')     renderRiwayat();
  if (page==='grafik')      renderGrafik();
  if (page==='cashflow')    renderCashflow();
  if (page==='konsinyasi')  loadKonsinyasi();
  if (page==='cetak-log')   loadCetakLog();
}

// ─────────────────────────────────────────────────────
// DASHBOARD
// ─────────────────────────────────────────────────────
function renderDashboard() {
  const now = new Date();
  document.getElementById('dash-date').textContent = now.toLocaleDateString('id-ID',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  const thisMonth = orderHistory.filter(o => o.date.getMonth()===now.getMonth() && o.date.getFullYear()===now.getFullYear());
  const rev = thisMonth.reduce((a,o)=>a+o.total,0);
  const lowStok    = products.filter(p => p.stok <= p.minStok);
  const lowBahan   = materials.filter(m => m.stok <= m.minStok);
  document.getElementById('stat-cards').innerHTML = `
    <div class="stat-card sc-a1"><div class="stat-icon">💰</div><div class="stat-label">Pendapatan Bulan Ini</div><div class="stat-value">${fmtK(rev)}</div><div class="stat-meta">${thisMonth.length} transaksi</div></div>
    <div class="stat-card sc-a2"><div class="stat-icon">📋</div><div class="stat-label">Total Order</div><div class="stat-value">${orderHistory.length}</div><div class="stat-meta">sepanjang waktu</div></div>
    <div class="stat-card sc-a3"><div class="stat-icon">📦</div><div class="stat-label">Produk Jadi</div><div class="stat-value">${products.length}</div><div class="stat-meta">${lowStok.length} stok kritis</div></div>
    <div class="stat-card sc-a5"><div class="stat-icon">🧵</div><div class="stat-label">Bahan Baku</div><div class="stat-value">${materials.length}</div><div class="stat-meta">${lowBahan.length} kritis</div></div>`;
  document.getElementById('kritis-badge').textContent = lowStok.length + ' produk';
  document.getElementById('dash-stok-kritis').innerHTML = lowStok.length
    ? lowStok.map(p => `<tr><td>${p.nama}</td><td><strong style="color:${p.stok===0?'var(--red)':'var(--gold)'}">${p.stok}</strong></td><td>${p.minStok}</td><td><span class="badge ${p.stok===0?'badge-red':'badge-gold'}">${p.stok===0?'Habis':'Kritis'}</span></td></tr>`).join('')
    : `<tr><td colspan="4"><div class="empty-state" style="padding:24px;"><div class="empty-icon">✅</div><div class="empty-text">Semua stok aman</div></div></td></tr>`;
  const recent = orderHistory.slice(0,5);
  document.getElementById('dash-order-recent').innerHTML = recent.length
    ? recent.map(o=>`<div style="padding:12px 22px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;"><div><div style="font-weight:600;font-size:13px;">${o.id}${o.customer?' · '+o.customer:''}</div><div style="font-size:11.5px;color:var(--text3);">${o.dateStr}</div></div><div style="font-weight:700;color:var(--accent);">${fmt(o.total)}</div></div>`).join('')
    : `<div class="empty-state" style="padding:24px;"><div class="empty-icon">📋</div><div class="empty-text">Belum ada order</div></div>`;
  renderDashChart();
}
function renderDashChart() {
  const now=new Date(), lbs=[], rev=[];
  for(let i=29;i>=0;i--) {
    const d=new Date(now); d.setDate(d.getDate()-i);
    lbs.push(i===0?'Hari ini':d.getDate()+'/'+(d.getMonth()+1));
    const dayOrds=orderHistory.filter(o=>o.date.toDateString()===d.toDateString());
    rev.push(dayOrds.reduce((a,o)=>a+o.total,0));
  }
  killChart('chart-dash');
  const ctx=document.getElementById('chart-dash').getContext('2d');
  charts['chart-dash']=new Chart(ctx,{type:'line',data:{labels:lbs,datasets:[{label:'Pendapatan',data:rev,borderColor:'#8b4513',backgroundColor:'rgba(139,69,19,.08)',borderWidth:2.5,pointRadius:2,tension:.4,fill:true}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:i=>fmt(i.raw)}}},scales:{x:{grid:{display:false},ticks:{font:{size:9},maxTicksLimit:10}},y:{grid:{color:'rgba(0,0,0,.04)'},ticks:{callback:v=>fmtK(v),font:{size:10}}}}}});
}

// ─────────────────────────────────────────────────────
// STOK BARANG
// ─────────────────────────────────────────────────────
function renderStok() { renderStokTable(); }
function renderStokTable() {
  const q   = (document.getElementById('stok-search')||{value:''}).value.toLowerCase();
  const cat = (document.getElementById('stok-filter')||{value:''}).value;
  const f   = products.filter(p => (!q||p.nama.toLowerCase().includes(q)||p.kode.toLowerCase().includes(q)) && (!cat||p.kategori===cat));
  document.getElementById('stok-table-body').innerHTML = f.length
    ? f.map(p => {
        const status = p.stok===0 ? '<span class="badge badge-red">Habis</span>' : p.stok<=p.minStok ? '<span class="badge badge-gold">Kritis</span>' : '<span class="badge badge-green">Aman</span>';
        return `<tr><td><code>${p.kode}</code></td><td><strong>${p.nama}</strong><div style="font-size:11.5px;color:var(--text3);margin-top:1px;">${p.deskripsi||''}</div></td><td><span class="cat-dot" style="background:${catColors[p.kategori]||'#999'};"></span>${p.kategori}</td><td><strong style="${p.stok<=p.minStok?'color:var(--red);':''}">${p.stok}</strong> <span style="font-size:11px;color:var(--text3);">${p.satuan}</span></td><td>${p.minStok}</td><td>${status}</td><td style="white-space:nowrap;"><button class="btn btn-secondary btn-sm" onclick="openEditStok(${p.id})">✏️</button> <button class="btn btn-danger btn-sm" onclick="delStok(${p.id})">🗑</button></td></tr>`;
      }).join('')
    : `<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📦</div><div class="empty-text">Tidak ada produk ditemukan</div></div></td></tr>`;
}
function openAddStok() {
  document.getElementById('modal-stok-title').textContent='Tambah Produk';
  document.getElementById('stok-edit-id').value='';
  ['form-kode','form-nama','form-deskripsi'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('form-stok').value=0;
  document.getElementById('form-minstok').value=5;
  document.getElementById('form-kategori').value='Tas';
  document.getElementById('form-satuan').value='pcs';
  openModal('modal-stok');
}
function openEditStok(id) {
  const p=products.find(x=>x.id===id); if(!p) return;
  document.getElementById('modal-stok-title').textContent='Edit Produk';
  document.getElementById('stok-edit-id').value=id;
  document.getElementById('form-kode').value=p.kode;
  document.getElementById('form-nama').value=p.nama;
  document.getElementById('form-kategori').value=p.kategori;
  document.getElementById('form-stok').value=p.stok;
  document.getElementById('form-minstok').value=p.minStok;
  document.getElementById('form-satuan').value=p.satuan;
  document.getElementById('form-deskripsi').value=p.deskripsi||'';
  openModal('modal-stok');
}
async function saveStok() {
  const eid  = document.getElementById('stok-edit-id').value;
  const data = {
    kode:      document.getElementById('form-kode').value.trim(),
    nama:      document.getElementById('form-nama').value.trim(),
    kategori:  document.getElementById('form-kategori').value,
    stok:      parseInt(document.getElementById('form-stok').value)||0,
    minStok:   parseInt(document.getElementById('form-minstok').value)||5,
    satuan:    document.getElementById('form-satuan').value,
    deskripsi: document.getElementById('form-deskripsi').value.trim(),
  };
  if (!data.nama) { toast('Nama produk wajib!'); return; }
  try {
    if (eid) {
      const updated = await api('/api/products/'+eid, 'PUT', data);
      const idx = products.findIndex(p=>p.id==eid);
      products[idx] = updated;
      toast('Diperbarui ✓');
    } else {
      const created = await api('/api/products', 'POST', data);
      products.push(created);
      toast('Ditambahkan ✓');
    }
    closeModal('modal-stok');
    renderStokTable();
  } catch(e) { toast('⚠️ '+e.message); }
}
async function delStok(id) {
  if (!confirm('Hapus produk ini?')) return;
  try {
    await api('/api/products/'+id, 'DELETE');
    products = products.filter(p=>p.id!==id);
    renderStokTable(); toast('Dihapus');
  } catch(e) { toast('⚠️ '+e.message); }
}

// ─────────────────────────────────────────────────────
// STOK BAHAN
// ─────────────────────────────────────────────────────
function renderBahan() { renderBahanStats(); renderBahanTable(); populateRecMaterialSelect(); }
function renderBahanStats() {
  const total = materials.length;
  const kritis = materials.filter(m => m.stok <= m.minStok).length;
  const nilai  = materials.reduce((a,m) => a + m.stok * m.hargaSatuan, 0);
  document.getElementById('bahan-stats').innerHTML = `
    <div class="stat-card sc-a3"><div class="stat-icon">🧵</div><div class="stat-label">Total Jenis Bahan</div><div class="stat-value">${total}</div><div class="stat-meta">item terdaftar</div></div>
    <div class="stat-card sc-a1"><div class="stat-icon">⚠️</div><div class="stat-label">Bahan Kritis</div><div class="stat-value" style="color:${kritis>0?'var(--red)':'inherit'};">${kritis}</div><div class="stat-meta">${kritis>0?'perlu restock':'semua aman'}</div></div>
    <div class="stat-card sc-a2"><div class="stat-icon">💰</div><div class="stat-label">Nilai Inventori Bahan</div><div class="stat-value" style="font-size:18px;">${fmtK(nilai)}</div><div class="stat-meta">stok × harga satuan</div></div>`;
}
function renderBahanTable() {
  const q   = (document.getElementById('bahan-search')||{value:''}).value.toLowerCase();
  const cat = (document.getElementById('bahan-filter')||{value:''}).value;
  const f   = materials.filter(m => (!q||m.nama.toLowerCase().includes(q)||m.kode.toLowerCase().includes(q)) && (!cat||m.kategori===cat));
  document.getElementById('bahan-table-body').innerHTML = f.length
    ? f.map(m => {
        const status = m.stok===0 ? '<span class="badge badge-red">Habis</span>' : m.stok<=m.minStok ? '<span class="badge badge-gold">Kritis</span>' : '<span class="badge badge-green">Aman</span>';
        return `<tr>
          <td><code>${m.kode||'—'}</code></td>
          <td><strong>${m.nama}</strong>${m.catatan?`<div style="font-size:11px;color:var(--text3);">${m.catatan}</div>`:''}</td>
          <td><span class="cat-dot" style="background:${bahanColors[m.kategori]||'#999'}"></span>${m.kategori}</td>
          <td><strong style="${m.stok<=m.minStok?'color:var(--red);':''}">${fmtNum(m.stok)}</strong> <span style="font-size:11px;color:var(--text3);">${m.satuan}</span></td>
          <td>${fmtNum(m.minStok)}</td>
          <td style="white-space:nowrap;">${fmt(m.hargaSatuan)}</td>
          <td style="font-size:12px;color:var(--text3);">${m.supplier||'—'}</td>
          <td>${status}</td>
          <td style="white-space:nowrap;">
            <button class="btn btn-teal btn-sm" onclick="openAdjBahan(${m.id})" title="Update Stok" style="font-size:13px;padding:5px 8px;">±</button>
            <button class="btn btn-secondary btn-sm" onclick="openEditBahan(${m.id})">✏️</button>
            <button class="btn btn-danger btn-sm" onclick="delBahan(${m.id})">🗑</button>
          </td>
        </tr>`;
      }).join('')
    : `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🧵</div><div class="empty-text">Belum ada data bahan baku.<br>Klik <strong>Tambah Bahan</strong> untuk mulai.</div></div></td></tr>`;
}
function openAddBahan() {
  document.getElementById('modal-bahan-title').textContent='Tambah Bahan';
  document.getElementById('bahan-edit-id').value='';
  ['form-bahan-kode','form-bahan-nama','form-bahan-supplier','form-bahan-catatan'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('form-bahan-stok').value=0;
  document.getElementById('form-bahan-minstok').value=5;
  document.getElementById('form-bahan-harga').value=0;
  document.getElementById('form-bahan-kategori').value='Kain';
  document.getElementById('form-bahan-satuan').value='meter';
  openModal('modal-bahan');
}
function openEditBahan(id) {
  const m=materials.find(x=>x.id===id); if(!m) return;
  document.getElementById('modal-bahan-title').textContent='Edit Bahan';
  document.getElementById('bahan-edit-id').value=id;
  document.getElementById('form-bahan-kode').value=m.kode||'';
  document.getElementById('form-bahan-nama').value=m.nama;
  document.getElementById('form-bahan-kategori').value=m.kategori;
  document.getElementById('form-bahan-stok').value=m.stok;
  document.getElementById('form-bahan-minstok').value=m.minStok;
  document.getElementById('form-bahan-satuan').value=m.satuan;
  document.getElementById('form-bahan-harga').value=m.hargaSatuan;
  document.getElementById('form-bahan-supplier').value=m.supplier||'';
  document.getElementById('form-bahan-catatan').value=m.catatan||'';
  openModal('modal-bahan');
}
async function saveBahan() {
  const eid = document.getElementById('bahan-edit-id').value;
  const data = {
    kode:        document.getElementById('form-bahan-kode').value.trim(),
    nama:        document.getElementById('form-bahan-nama').value.trim(),
    kategori:    document.getElementById('form-bahan-kategori').value,
    stok:        parseFloat(document.getElementById('form-bahan-stok').value)||0,
    minStok:     parseFloat(document.getElementById('form-bahan-minstok').value)||0,
    satuan:      document.getElementById('form-bahan-satuan').value,
    hargaSatuan: parseFloat(document.getElementById('form-bahan-harga').value)||0,
    supplier:    document.getElementById('form-bahan-supplier').value.trim(),
    catatan:     document.getElementById('form-bahan-catatan').value.trim(),
  };
  if (!data.nama) { toast('Nama bahan wajib!'); return; }
  try {
    if (eid) {
      const updated = await api('/api/materials/'+eid, 'PUT', data);
      const idx = materials.findIndex(m=>m.id==eid);
      materials[idx] = updated;
      toast('Diperbarui ✓');
    } else {
      const created = await api('/api/materials', 'POST', data);
      materials.push(created);
      toast('Bahan ditambahkan ✓');
    }
    closeModal('modal-bahan');
    renderBahan();
  } catch(e) { toast('⚠️ '+e.message); }
}
async function delBahan(id) {
  if (!confirm('Hapus bahan ini?')) return;
  try {
    await api('/api/materials/'+id, 'DELETE');
    materials = materials.filter(m=>m.id!==id);
    renderBahan(); toast('Dihapus');
  } catch(e) { toast('⚠️ '+e.message); }
}
function openAdjBahan(id) {
  const m=materials.find(x=>x.id===id); if(!m) return;
  document.getElementById('adj-bahan-id').value=id;
  document.getElementById('modal-adj-title').textContent='Update Stok — '+m.nama;
  document.getElementById('adj-bahan-info').innerHTML=`<strong>${m.nama}</strong><div style="margin-top:6px;color:var(--text2);">Stok saat ini: <strong>${fmtNum(m.stok)} ${m.satuan}</strong> · Min: ${fmtNum(m.minStok)}</div>`;
  document.getElementById('adj-jumlah').value='';
  document.getElementById('adj-keterangan').value='';
  setAdjType('in');
  openModal('modal-stok-adj');
}
function setAdjType(t) {
  adjType=t;
  document.getElementById('adj-type').value=t;
  const btnIn  = document.getElementById('adj-btn-in');
  const btnOut = document.getElementById('adj-btn-out');
  btnIn.className  = 'btn '+(t==='in'?'btn-green':'btn-secondary');
  btnOut.className = 'btn '+(t==='out'?'btn-danger':'btn-secondary');
  btnIn.style.cssText  = 'flex:1;justify-content:center;';
  btnOut.style.cssText = 'flex:1;justify-content:center;';
}
async function saveStokAdj() {
  const id     = parseInt(document.getElementById('adj-bahan-id').value);
  const type   = document.getElementById('adj-type').value;
  const jumlah = parseFloat(document.getElementById('adj-jumlah').value)||0;
  const ket    = document.getElementById('adj-keterangan').value.trim();
  if (!jumlah) { toast('Jumlah wajib diisi!'); return; }
  try {
    const result = await api('/api/materials/'+id+'/stok','POST',{type,jumlah,keterangan:ket});
    const idx = materials.findIndex(m=>m.id===id);
    materials[idx] = {...materials[idx], stok: result.stok};
    toast('Stok diperbarui ✓');
    closeModal('modal-stok-adj');
    renderBahan();
  } catch(e) { toast('⚠️ '+e.message); }
}

// ─────────────────────────────────────────────────────
// HARGA & HPP
// ─────────────────────────────────────────────────────
function renderHarga() { popHargaDrop(); renderHargaTable(); loadHppCalc(); }
function popHargaDrop() {
  const sel=document.getElementById('form-harga-produk');
  sel.innerHTML=products.map(p=>`<option value="${p.id}">${p.nama}</option>`).join('');
  const hppSel=document.getElementById('hpp-product-select');
  hppSel.innerHTML='<option value="">— Pilih produk —</option>'+prices.map(pr=>{const prod=products.find(p=>p.id===pr.produkId);return prod?`<option value="${pr.id}">${prod.nama}</option>`:''}).join('');
}
function renderHargaTable() {
  document.getElementById('harga-table-body').innerHTML = prices.length
    ? prices.map(pr => {
        const prod = products.find(p=>p.id===pr.produkId);
        const hpp  = pr.components.reduce((a,c)=>a+c.harga,0) + pr.overhead;
        const margin = pr.hargaJual>0 ? Math.round((pr.hargaJual-hpp)/pr.hargaJual*100) : 0;
        return `<tr><td>${prod?prod.nama:'—'}</td><td>${fmt(hpp)}</td><td><strong>${fmt(pr.hargaJual)}</strong></td><td><span class="badge ${margin>=30?'badge-green':margin>=15?'badge-gold':'badge-red'}">${margin}%</span></td><td style="white-space:nowrap;"><button class="btn btn-secondary btn-sm" onclick="openEditHarga(${pr.id})">✏️</button> <button class="btn btn-danger btn-sm" onclick="delHarga(${pr.id})">🗑</button></td></tr>`;
      }).join('')
    : `<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">🏷</div><div class="empty-text">Belum ada data harga</div></div></td></tr>`;
}
function loadHppCalc() {
  const pid=parseInt(document.getElementById('hpp-product-select').value);
  const pr=prices.find(p=>p.id===pid);
  if(!pr){document.getElementById('hpp-calc-area').innerHTML=`<div class="empty-state"><div class="empty-icon">🧮</div><div class="empty-text">Pilih produk untuk melihat breakdown HPP</div></div>`;return;}
  const prod=products.find(p=>p.id===pr.produkId);
  const hpp=pr.components.reduce((a,c)=>a+c.harga,0)+pr.overhead;
  const profit=pr.hargaJual-hpp;
  document.getElementById('hpp-calc-area').innerHTML=`<div class="hpp-card"><div style="font-size:12px;font-weight:600;color:var(--text2);margin-bottom:10px;">${prod?prod.nama:''}</div>${pr.components.map(c=>`<div class="hpp-row"><span>${c.nama}</span><span>${fmt(c.harga)}</span></div>`).join('')}<div class="hpp-row"><span>Overhead</span><span>${fmt(pr.overhead)}</span></div><div class="hpp-row total"><span>HPP</span><span>${fmt(hpp)}</span></div><div class="hpp-row profit"><span>Keuntungan</span><span>${fmt(profit)}</span></div><div class="hpp-row"><span style="color:var(--text3);">Harga Jual</span><strong>${fmt(pr.hargaJual)}</strong></div></div>`;
}
let hppRows=[];
function addHppRow(nm='',hr=0){const rid='r'+Date.now()+Math.round(Math.random()*9999);hppRows.push(rid);const d=document.createElement('div');d.id='hr-'+rid;d.style.cssText='display:grid;grid-template-columns:2fr 1fr auto;gap:7px;margin-bottom:7px;align-items:center;';d.innerHTML=`<input type="text" placeholder="Nama komponen" value="${nm}" oninput="recalcModal()"><input type="number" placeholder="Harga" value="${hr||''}" min="0" oninput="recalcModal()"><button class="btn btn-danger btn-sm" onclick="rmHppRow('${rid}')">✕</button>`;document.getElementById('hpp-components').appendChild(d);recalcModal();}
function rmHppRow(id){document.getElementById('hr-'+id)?.remove();hppRows=hppRows.filter(r=>r!=id);recalcModal();}
function getHppComps(){return hppRows.map(id=>{const el=document.getElementById('hr-'+id);if(!el)return null;const inp=el.querySelectorAll('input');return{nama:inp[0].value,harga:parseFloat(inp[1].value)||0};}).filter(Boolean);}
function recalcModal(){const c=getHppComps();const tb=c.reduce((a,x)=>a+x.harga,0);const ov=parseFloat(document.getElementById('form-overhead').value)||0;const hj=parseFloat(document.getElementById('form-harga-jual').value)||0;const hpp=tb+ov;const profit=hj-hpp;const m=hj>0?Math.round(profit/hj*100):0;document.getElementById('modal-total-bahan').textContent=fmt(tb);document.getElementById('modal-total-overhead').textContent=fmt(ov);document.getElementById('modal-hpp-total').textContent=fmt(hpp);document.getElementById('modal-profit').textContent=fmt(profit);document.getElementById('modal-margin').textContent=m+'%';}
function openAddHarga(){document.getElementById('modal-harga-title').textContent='Tambah Harga Produk';document.getElementById('harga-edit-id').value='';document.getElementById('hpp-components').innerHTML='';hppRows=[];document.getElementById('form-overhead').value='';document.getElementById('form-harga-jual').value='';popHargaDrop();addHppRow('',0);recalcModal();openModal('modal-harga');}
function openEditHarga(id){const pr=prices.find(p=>p.id===id);if(!pr)return;document.getElementById('modal-harga-title').textContent='Edit Harga';document.getElementById('harga-edit-id').value=id;document.getElementById('hpp-components').innerHTML='';hppRows=[];popHargaDrop();document.getElementById('form-harga-produk').value=pr.produkId;document.getElementById('form-overhead').value=pr.overhead;document.getElementById('form-harga-jual').value=pr.hargaJual;pr.components.forEach(c=>addHppRow(c.nama,c.harga));recalcModal();openModal('modal-harga');}
async function saveHarga() {
  const pid = parseInt(document.getElementById('form-harga-produk').value);
  const ov  = parseFloat(document.getElementById('form-overhead').value)||0;
  const hj  = parseFloat(document.getElementById('form-harga-jual').value)||0;
  const comps = getHppComps();
  if (!pid) { toast('Pilih produk!'); return; }
  if (!hj)  { toast('Harga jual wajib!'); return; }
  const eid  = document.getElementById('harga-edit-id').value;
  const data = { produkId: pid, overhead: ov, hargaJual: hj, components: comps };
  try {
    if (eid) {
      const updated = await api('/api/prices/'+eid, 'PUT', data);
      const idx = prices.findIndex(p=>p.id==eid);
      prices[idx] = updated;
      toast('Diperbarui ✓');
    } else {
      const created = await api('/api/prices', 'POST', data);
      prices.push(created);
      toast('Ditambahkan ✓');
    }
    closeModal('modal-harga'); renderHargaTable();
  } catch(e) { toast('⚠️ '+e.message); }
}
async function delHarga(id) {
  if (!confirm('Hapus data harga ini?')) return;
  try {
    await api('/api/prices/'+id, 'DELETE');
    prices = prices.filter(p=>p.id!==id);
    renderHargaTable(); toast('Dihapus');
  } catch(e) { toast('⚠️ '+e.message); }
}

// ─────────────────────────────────────────────────────
// ORDER
// ─────────────────────────────────────────────────────
function renderOrderProducts(){
  const q=(document.getElementById('order-search')||{value:''}).value.toLowerCase();
  const f=prices.filter(pr=>{const prod=products.find(p=>p.id===pr.produkId);return prod&&(!q||prod.nama.toLowerCase().includes(q));});
  document.getElementById('order-product-list').innerHTML=f.map(pr=>{const prod=products.find(p=>p.id===pr.produkId);const io=orderItems.find(i=>i.priceId===pr.id);return `<div class="order-item"><div class="order-item-info"><div class="order-item-name">${prod.nama}</div><div class="order-item-price">${fmt(pr.hargaJual)} · Stok: ${prod.stok}</div></div><div class="qty-control"><button class="qty-btn" onclick="chgQty(${pr.id},-1)">−</button><div class="qty-val">${io?io.qty:0}</div><button class="qty-btn" onclick="chgQty(${pr.id},1)">+</button></div></div>`;}).join('')||'<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-text">Tidak ada produk</div></div>';
}
function chgQty(pid,delta){const pr=prices.find(p=>p.id===pid);const prod=products.find(p=>p.id===pr.produkId);const idx=orderItems.findIndex(i=>i.priceId===pid);if(idx>=0){orderItems[idx].qty=Math.max(0,orderItems[idx].qty+delta);if(orderItems[idx].qty===0)orderItems.splice(idx,1);}else if(delta>0)orderItems.push({priceId:pid,nama:prod.nama,harga:pr.hargaJual,qty:1});renderOrderProducts();renderOrderSummary();updateOrderTotal();}
function renderOrderSummary(){document.getElementById('order-items-list').innerHTML=orderItems.length?orderItems.map(i=>`<div class="hpp-row"><span>${i.nama}<br><small style="color:var(--text3);">${fmt(i.harga)} × ${i.qty}</small></span><span style="font-weight:700;">${fmt(i.harga*i.qty)}</span></div>`).join(''):`<div class="empty-state"><div class="empty-icon">🛍</div><div class="empty-text">Belum ada produk</div></div>`;}
function updateOrderTotal(){const sub=orderItems.reduce((a,i)=>a+i.harga*i.qty,0);const disc=Math.min(100,Math.max(0,parseFloat(document.getElementById('order-discount').value)||0));const total=sub*(1-disc/100);document.getElementById('order-grand-total').textContent=fmt(Math.round(total));document.getElementById('order-discount-info').textContent=disc>0?`Subtotal ${fmt(sub)} · Diskon ${disc}%`:'';}
function clearOrder(){orderItems=[];renderOrderProducts();renderOrderSummary();updateOrderTotal();}
async function saveOrder() {
  if (!orderItems.length) { toast('Tambahkan produk!'); return; }
  const sub   = orderItems.reduce((a,i)=>a+i.harga*i.qty,0);
  const disc  = Math.min(100,Math.max(0,parseFloat(document.getElementById('order-discount').value)||0));
  const total = Math.round(sub*(1-disc/100));
  const cust  = document.getElementById('order-customer').value||'Umum';
  const note  = document.getElementById('order-note').value;
  const now   = new Date();
  const oid   = 'ORD-' + orderIdCtr++;
  const dateStr = now.toLocaleDateString('id-ID',{day:'2-digit',month:'short',year:'numeric'});
  const items = orderItems.map(i=>({priceId:i.priceId,nama:i.nama,harga:i.harga,qty:i.qty,subtotal:i.harga*i.qty}));
  try {
    await api('/api/orders','POST',{id:oid,customer:cust,date:now.toISOString(),dateStr,subtotal:sub,discount:disc,total,note,items});
    orderHistory.unshift({id:oid,date:now,dateStr,customer:cust,items,subtotal:sub,discount:disc,total,note});
    cashflows.unshift({id:'CF-'+Date.now(),type:'in',date:now,dateStr,desc:'Penjualan - '+cust,category:'Penjualan',amount:total});
    toast('Order '+oid+' disimpan ✓');
    clearOrder();
    ['order-note','order-customer'].forEach(id=>document.getElementById(id).value='');
    document.getElementById('order-discount').value=0;
  } catch(e) { toast('⚠️ '+e.message); }
}

// ─────────────────────────────────────────────────────
// RIWAYAT ORDER
// ─────────────────────────────────────────────────────
function renderRiwayat() {
  const q  = (document.getElementById('riwayat-search')||{value:''}).value.toLowerCase();
  const mf = (document.getElementById('riwayat-filter')||{value:''}).value;
  const months=[...new Set(orderHistory.map(o=>o.date.getFullYear()+'-'+(o.date.getMonth()+1).toString().padStart(2,'0')))];
  const mSel=document.getElementById('riwayat-filter');
  if(mSel&&mSel.options.length<=1){months.forEach(m=>{const d=new Date(m+'-01');const opt=document.createElement('option');opt.value=m;opt.textContent=d.toLocaleDateString('id-ID',{month:'long',year:'numeric'});mSel.appendChild(opt);});}
  const filtered=orderHistory.filter(o=>{const matchQ=!q||o.customer.toLowerCase().includes(q)||o.id.toLowerCase().includes(q)||o.items.some(i=>i.nama.toLowerCase().includes(q));const matchM=!mf||(o.date.getFullYear()+'-'+(o.date.getMonth()+1).toString().padStart(2,'0'))===mf;return matchQ&&matchM;});
  document.getElementById('riwayat-count-badge').textContent=filtered.length+' order';
  document.getElementById('riwayat-list').innerHTML=filtered.length?filtered.map(o=>`<div class="riwayat-row"><div class="riwayat-header"><div><div class="riwayat-id">${o.id}${o.customer?' · '+o.customer:''}</div><div class="riwayat-date">${o.dateStr}</div></div><div style="text-align:right;"><div class="riwayat-total">${fmt(o.total)}</div>${o.discount?`<div style="font-size:11px;color:var(--text3);">Diskon ${o.discount}%</div>`:''}</div></div><div class="riwayat-items">${o.items.map(i=>`${i.nama} ×${i.qty}`).join(' · ')}</div>${o.note?`<div style="font-size:11.5px;color:var(--text3);margin-top:5px;">📝 ${o.note}</div>`:''}<div style="display:flex;justify-content:flex-end;margin-top:8px;"><button class="btn btn-secondary btn-sm" onclick="printNota('${o.id}')" title="Cetak Nota">🖨️ Cetak Nota</button></div></div>`).join(''):`<div class="empty-state"><div class="empty-icon">📋</div><div class="empty-text">Tidak ada order ditemukan</div></div>`;
  const totalRev=filtered.reduce((a,o)=>a+o.total,0);
  const avg=filtered.length?Math.round(totalRev/filtered.length):0;
  const top=getTopProds(filtered);
  document.getElementById('riwayat-summary').innerHTML=`<div class="hpp-row"><span>Total Order</span><strong>${filtered.length}</strong></div><div class="hpp-row"><span>Total Pendapatan</span><strong style="color:var(--accent)">${fmtK(totalRev)}</strong></div><div class="hpp-row"><span>Avg/Order</span><strong>${fmtK(avg)}</strong></div><hr class="divider" style="margin:12px 0;"><div style="font-size:11px;color:var(--text3);margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px;font-weight:600;">Produk Terlaris</div>${top.map(p=>`<div class="hpp-row" style="font-size:12.5px;"><span>${p.nama.split(' ').slice(0,3).join(' ')}</span><span class="badge badge-blue">${p.qty}</span></div>`).join('')||'<div style="font-size:12px;color:var(--text3);">Belum ada data</div>'}`;
}
function getTopProds(orders){const m={};orders.forEach(o=>o.items.forEach(i=>{m[i.nama]=(m[i.nama]||0)+i.qty;}));return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([nama,qty])=>({nama,qty}));}

// ─────────────────────────────────────────────────────
// GRAFIK
// ─────────────────────────────────────────────────────
function setPeriod(key,months,el){periods[key]=months;document.getElementById('pt-'+key)?.querySelectorAll('.period-tab').forEach(t=>t.classList.remove('active'));if(el)el.classList.add('active');if(key==='revenue')renderRevenueChart();if(key==='product')renderProductChart();if(key==='category')renderCategoryChart();if(key==='cf')renderCfChart();}
function getOrdersIn(months){const now=new Date();const cut=new Date(now);cut.setMonth(cut.getMonth()-months);return orderHistory.filter(o=>o.date>=cut);}
function renderGrafik(){renderRevenueChart();renderProductChart();renderCategoryChart();const mo=getOrdersIn(1);const all=orderHistory;const allRev=all.reduce((a,o)=>a+o.total,0);const moRev=mo.reduce((a,o)=>a+o.total,0);const avg=mo.length?Math.round(moRev/mo.length):0;const top=getTopProds(mo);document.getElementById('grafik-stats').innerHTML=`<div class="stat-card sc-a1"><div class="stat-icon">📈</div><div class="stat-label">Total Pendapatan</div><div class="stat-value" style="font-size:17px;">${fmtK(allRev)}</div><div class="stat-meta">sepanjang waktu</div></div><div class="stat-card sc-a2"><div class="stat-icon">📋</div><div class="stat-label">Total Order</div><div class="stat-value">${all.length}</div><div class="stat-meta">semua waktu</div></div><div class="stat-card sc-a3"><div class="stat-icon">💵</div><div class="stat-label">Avg / Order</div><div class="stat-value" style="font-size:17px;">${fmtK(avg)}</div><div class="stat-meta">bulan ini</div></div><div class="stat-card sc-a4"><div class="stat-icon">🏆</div><div class="stat-label">Terlaris Bln Ini</div><div class="stat-value" style="font-size:13px;margin-top:8px;">${top[0]?top[0].nama.split(' ').slice(0,3).join(' '):'—'}</div><div class="stat-meta">${top[0]?top[0].qty+' unit':''}</div></div><div class="stat-card sc-a5"><div class="stat-icon">📦</div><div class="stat-label">Order Bln Ini</div><div class="stat-value">${mo.length}</div><div class="stat-meta">transaksi</div></div>`;}
function renderRevenueChart(){const n=periods.revenue,now=new Date(),lbs=[],rev=[],cnt=[];for(let m=n-1;m>=0;m--){const d=new Date(now.getFullYear(),now.getMonth()-m,1);lbs.push(d.toLocaleDateString('id-ID',{month:'short',year:'2-digit'}));const mo=orderHistory.filter(o=>o.date.getMonth()===d.getMonth()&&o.date.getFullYear()===d.getFullYear());rev.push(mo.reduce((a,o)=>a+o.total,0));cnt.push(mo.length);}killChart('chart-revenue');const ctx=document.getElementById('chart-revenue').getContext('2d');charts['chart-revenue']=new Chart(ctx,{type:'bar',data:{labels:lbs,datasets:[{label:'Pendapatan',data:rev,backgroundColor:'rgba(139,69,19,.75)',borderRadius:6,yAxisID:'y'},{label:'Jumlah Order',data:cnt,type:'line',borderColor:'#c9972a',backgroundColor:'transparent',borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#c9972a',tension:.4,yAxisID:'y2'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{font:{size:11},boxWidth:12}},tooltip:{callbacks:{label:i=>i.datasetIndex===0?fmt(i.raw):i.raw+' order'}}},scales:{x:{grid:{display:false},ticks:{font:{size:10}}},y:{grid:{color:'rgba(0,0,0,.04)'},ticks:{callback:v=>fmtK(v),font:{size:10}}},y2:{position:'right',grid:{display:false},ticks:{font:{size:10}}}}}});}
function renderProductChart(){const orders=getOrdersIn(periods.product);const map={};orders.forEach(o=>o.items.forEach(i=>{map[i.nama]=(map[i.nama]||0)+i.qty;}));const sorted=Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0,6);const pal=['#8b4513','#c9972a','#2d3561','#3a7d44','#c4622d','#0d7377'];killChart('chart-product');const ctx=document.getElementById('chart-product').getContext('2d');charts['chart-product']=new Chart(ctx,{type:'bar',data:{labels:sorted.map(([n])=>n.length>22?n.slice(0,22)+'…':n),datasets:[{data:sorted.map(([,v])=>v),backgroundColor:pal,borderRadius:6}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:i=>i.raw+' pcs'}}},scales:{x:{grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:10}}},y:{grid:{display:false},ticks:{font:{size:10}}}}}});}
function renderCategoryChart(){const orders=getOrdersIn(periods.category);const map={};orders.forEach(o=>o.items.forEach(i=>{const pr=prices.find(p=>p.id===i.priceId);const prod=pr?products.find(p=>p.id===pr.produkId):null;const cat=prod?prod.kategori:'Lainnya';map[cat]=(map[cat]||0)+i.subtotal;}));const entries=Object.entries(map);killChart('chart-category');const ctx=document.getElementById('chart-category').getContext('2d');charts['chart-category']=new Chart(ctx,{type:'doughnut',data:{labels:entries.map(([k])=>k),datasets:[{data:entries.map(([,v])=>v),backgroundColor:['#8b4513','#2d3561','#3a7d44','#c9972a'],borderWidth:2,borderColor:'#fff',hoverOffset:8}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{font:{size:11},boxWidth:12}},tooltip:{callbacks:{label:i=>i.label+': '+fmt(i.raw)}}},cutout:'58%'}});}

// ─────────────────────────────────────────────────────
// CASHFLOW
// ─────────────────────────────────────────────────────
function renderCashflow(){
  const totalIn=cashflows.filter(c=>c.type==='in').reduce((a,c)=>a+c.amount,0);
  const totalOut=cashflows.filter(c=>c.type==='out').reduce((a,c)=>a+c.amount,0);
  const net=totalIn-totalOut;
  document.getElementById('cf-stats').innerHTML=`<div class="stat-card sc-a4"><div class="stat-icon">↑</div><div class="stat-label">Total Pemasukan</div><div class="stat-value" style="font-size:18px;color:var(--green);">${fmtK(totalIn)}</div><div class="stat-meta">semua waktu</div></div><div class="stat-card sc-a1"><div class="stat-icon">↓</div><div class="stat-label">Total Pengeluaran</div><div class="stat-value" style="font-size:18px;color:var(--red);">${fmtK(totalOut)}</div><div class="stat-meta">semua waktu</div></div><div class="stat-card ${net>=0?'sc-a4':'sc-a1'}"><div class="stat-icon">⚖</div><div class="stat-label">Kas Bersih</div><div class="stat-value" style="font-size:18px;color:${net>=0?'var(--green)':'var(--red)'};">${fmtK(Math.abs(net))}</div><div class="stat-meta">${net>=0?'✅ Surplus':'⚠️ Defisit'}</div></div>`;
  renderCfChart();renderCfTable();renderCfCatBreakdown();
  const di=document.getElementById('cf-date');if(di&&!di.value)di.value=today();
}
function renderCfChart(){const n=periods.cf,now=new Date(),lbs=[],inn=[],out=[],net2=[];for(let m=n-1;m>=0;m--){const d=new Date(now.getFullYear(),now.getMonth()-m,1);lbs.push(d.toLocaleDateString('id-ID',{month:'short',year:'2-digit'}));const mo=cashflows.filter(c=>c.date.getMonth()===d.getMonth()&&c.date.getFullYear()===d.getFullYear());const i=mo.filter(c=>c.type==='in').reduce((a,c)=>a+c.amount,0);const o=mo.filter(c=>c.type==='out').reduce((a,c)=>a+c.amount,0);inn.push(i);out.push(o);net2.push(i-o);}killChart('chart-cashflow');const ctx=document.getElementById('chart-cashflow').getContext('2d');charts['chart-cashflow']=new Chart(ctx,{type:'bar',data:{labels:lbs,datasets:[{label:'Pemasukan',data:inn,backgroundColor:'rgba(58,125,68,.75)',borderRadius:5},{label:'Pengeluaran',data:out,backgroundColor:'rgba(192,57,43,.75)',borderRadius:5},{label:'Kas Bersih',data:net2,type:'line',borderColor:'#2d3561',backgroundColor:'transparent',borderWidth:2.5,pointRadius:4,pointBackgroundColor:net2.map(v=>v>=0?'#3a7d44':'#c0392b'),tension:.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{font:{size:11},boxWidth:12}},tooltip:{callbacks:{label:i=>i.dataset.label+': '+fmt(i.raw)}}},scales:{x:{grid:{display:false},ticks:{font:{size:10}}},y:{grid:{color:'rgba(0,0,0,.04)'},ticks:{callback:v=>fmtK(v),font:{size:10}}}}}});}
function renderCfTable(){const tf=(document.getElementById('cf-type-filter')||{value:''}).value;const f=cashflows.filter(c=>!tf||c.type===tf).slice(0,60);document.getElementById('cf-table-body').innerHTML=f.map(c=>`<tr><td style="font-size:11.5px;color:var(--text3);white-space:nowrap;">${c.dateStr}</td><td style="font-size:12.5px;">${c.desc}</td><td><span class="badge badge-${c.type==='in'?'teal':'red'}">${c.category}</span></td><td class="${c.type==='in'?'cf-in':'cf-out'}" style="white-space:nowrap;">${c.type==='in'?'+':'-'}${fmt(c.amount)}</td><td><button class="btn btn-danger btn-sm" onclick="delCf('${c.id}')">🗑</button></td></tr>`).join('')||`<tr><td colspan="5"><div class="empty-state" style="padding:24px;"><div class="empty-icon">💸</div><div class="empty-text">Belum ada transaksi</div></div></td></tr>`;}
function renderCfCatBreakdown(){const out=cashflows.filter(c=>c.type==='out');const map={};out.forEach(c=>{map[c.category]=(map[c.category]||0)+c.amount;});const total=out.reduce((a,c)=>a+c.amount,0);const sorted=Object.entries(map).sort((a,b)=>b[1]-a[1]);const cols=['#c0392b','#8b4513','#c9972a','#2d3561','#3a7d44','#0d7377'];document.getElementById('cf-category-breakdown').innerHTML=sorted.map(([cat,amt],i)=>{const pct=total>0?Math.round(amt/total*100):0;return `<div style="margin-bottom:13px;"><div style="display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:5px;"><span style="font-weight:500;">${cat}</span><span style="color:var(--text3);">${pct}% · ${fmtK(amt)}</span></div><div style="height:7px;border-radius:4px;background:var(--surface2);overflow:hidden;"><div style="height:100%;width:${pct}%;background:${cols[i%cols.length]};border-radius:4px;transition:width .6s;"></div></div></div>`;}).join('')||'<div class="empty-state" style="padding:16px;"><div class="empty-text">Belum ada pengeluaran</div></div>';}
function setCfType(t){cfType=t;document.getElementById('cf-btn-in').className='btn '+(t==='in'?'btn-teal':'btn-secondary');document.getElementById('cf-btn-in').style.cssText='flex:1;justify-content:center;';document.getElementById('cf-btn-out').className='btn '+(t==='out'?'btn-danger':'btn-secondary');document.getElementById('cf-btn-out').style.cssText='flex:1;justify-content:center;';}
async function saveCf() {
  const desc   = document.getElementById('cf-desc').value.trim();
  const amount = parseFloat(document.getElementById('cf-amount').value)||0;
  const dv     = document.getElementById('cf-date').value;
  if (!desc)   { toast('Keterangan wajib!'); return; }
  if (!amount) { toast('Jumlah wajib!'); return; }
  const date    = dv ? new Date(dv) : new Date();
  const dateStr = date.toLocaleDateString('id-ID',{day:'2-digit',month:'short',year:'numeric'});
  const data    = { type: cfType, date: date.toISOString(), dateStr, desc, category: document.getElementById('cf-category').value, amount };
  try {
    const created = await api('/api/cashflows','POST',data);
    cashflows.unshift({ ...created, date, dateStr });
    cashflows.sort((a,b)=>b.date-a.date);
    document.getElementById('cf-desc').value=''; document.getElementById('cf-amount').value='';
    toast('Transaksi dicatat ✓'); renderCashflow();
  } catch(e) { toast('⚠️ '+e.message); }
}
function openAddCf(){document.getElementById('cf-modal-type').value='in';setModalCfType('in');document.getElementById('cf-modal-date').value=today();document.getElementById('cf-modal-desc').value='';document.getElementById('cf-modal-amount').value='';openModal('modal-cf');}
function setModalCfType(t){document.getElementById('cf-modal-type').value=t;document.getElementById('cf-modal-btn-in').className='btn '+(t==='in'?'btn-teal':'btn-secondary');document.getElementById('cf-modal-btn-in').style.cssText='flex:1;justify-content:center;';document.getElementById('cf-modal-btn-out').className='btn '+(t==='out'?'btn-danger':'btn-secondary');document.getElementById('cf-modal-btn-out').style.cssText='flex:1;justify-content:center;';}
async function saveModalCf() {
  const type   = document.getElementById('cf-modal-type').value;
  const desc   = document.getElementById('cf-modal-desc').value.trim();
  const amount = parseFloat(document.getElementById('cf-modal-amount').value)||0;
  const dv     = document.getElementById('cf-modal-date').value;
  if (!desc||!amount) { toast('Lengkapi data!'); return; }
  const date    = dv ? new Date(dv) : new Date();
  const dateStr = date.toLocaleDateString('id-ID',{day:'2-digit',month:'short',year:'numeric'});
  const data    = { type, date: date.toISOString(), dateStr, desc, category: document.getElementById('cf-modal-cat').value, amount };
  try {
    const created = await api('/api/cashflows','POST',data);
    cashflows.unshift({ ...created, date, dateStr });
    cashflows.sort((a,b)=>b.date-a.date);
    toast('Dicatat ✓'); closeModal('modal-cf'); renderCashflow();
  } catch(e) { toast('⚠️ '+e.message); }
}
async function delCf(id) {
  if (!confirm('Hapus transaksi ini?')) return;
  try {
    await api('/api/cashflows/'+id,'DELETE');
    cashflows = cashflows.filter(c=>c.id!==id);
    renderCashflow(); toast('Dihapus');
  } catch(e) { toast('⚠️ '+e.message); }
}

// ─────────────────────────────────────────────────────
// UTILS
// ─────────────────────────────────────────────────────
function openModal(id){document.getElementById(id).classList.add('open');}
function closeModal(id){document.getElementById(id).classList.remove('open');}
document.querySelectorAll('.modal-overlay').forEach(m=>m.addEventListener('click',function(e){if(e.target===this)closeModal(this.id);}));
function killChart(id){if(charts[id]){charts[id].destroy();delete charts[id];}}
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.style.transform='translateY(0)';t.style.opacity='1';setTimeout(()=>{t.style.transform='translateY(60px)';t.style.opacity='0';},2800);}

// ═══════════════════════════════════════════════════
// FITUR LOGIN / LOGOUT (BARU — tidak mengubah kode di atas)
// ═══════════════════════════════════════════════════

const AUTH_KEY = 'risena_auth';

function getAuth() {
  try { return JSON.parse(localStorage.getItem(AUTH_KEY)); } catch { return null; }
}
function setAuth(data) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(data));
}
function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
}

/** Proses klik tombol Masuk */
async function doLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const btn      = document.getElementById('login-btn');
  if (!username || !password) { showLoginError('Username dan password wajib diisi!'); return; }
  btn.disabled = true;
  btn.textContent = 'Memverifikasi...';
  try {
    const result = await api('/api/auth/login', 'POST', { username, password });
    setAuth(result);
    hideLoginScreen();
    updateSidebarUser(result.username);
    await loadAllData();
    renderDashboard();
    toast('Selamat datang, ' + result.username + ' 👋');
  } catch(e) {
    showLoginError(e.message || 'Login gagal, coba lagi.');
    btn.disabled = false;
    btn.textContent = '🔐 Masuk';
  }
}

/** Proses logout */
async function doLogout() {
  if (!confirm('Yakin ingin keluar?')) return;
  const auth = getAuth();
  if (auth?.token) {
    try { await api('/api/auth/logout?token=' + auth.token, 'POST'); } catch {}
  }
  clearAuth();
  showLoginScreen();
}

function showLoginError(msg) {
  const el = document.getElementById('login-error');
  el.textContent = msg;
  el.classList.add('show');
}

function showLoginScreen() {
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('login-username').value = '';
  document.getElementById('login-password').value = '';
  document.getElementById('login-error').classList.remove('show');
  const btn = document.getElementById('login-btn');
  btn.disabled = false;
  btn.textContent = '🔐 Masuk';
}

function hideLoginScreen() {
  document.getElementById('login-screen').classList.add('hidden');
}

function updateSidebarUser(username) {
  const el = document.getElementById('sidebar-user-display');
  if (!el) return;
  el.innerHTML = `
    <div class="user-info-wrap">
      <div class="user-avatar">${username.charAt(0).toUpperCase()}</div>
      <span class="user-name">${username}</span>
    </div>
    <button class="btn-logout" onclick="doLogout()">Keluar</button>`;
}

// ── Keyboard shortcut: Enter di form login ──
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('login-username')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('login-password')?.focus();
  });
  document.getElementById('login-password')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doLogin();
  });
});

// ─────────────────────────────────────────────────────
// STARTUP — cek sesi, lalu load data atau tampilkan login
// ─────────────────────────────────────────────────────
(async () => {
  const auth = getAuth();
  if (!auth?.token) {
    showLoginScreen();
    return;
  }
  try {
    // Verifikasi token masih valid ke server
    await api('/api/auth/check?token=' + auth.token, 'GET');
    hideLoginScreen();
    updateSidebarUser(auth.username);
    await loadAllData();
    renderDashboard();
  } catch {
    // Token expired atau tidak valid → paksa login ulang
    clearAuth();
    showLoginScreen();
  }
})();
// ══════════════════════════════════════════════════════
// KONSINYASI
// ══════════════════════════════════════════════════════

let consignments = [];

async function loadKonsinyasi() {
  try {
    consignments = await api('/api/consignments');
    renderKsStats();
    renderKsTable();
  } catch(e) { toast('⚠️ Gagal muat konsinyasi: ' + e.message); }
}

function renderKsStats() {
  const aktif   = consignments.filter(k => k.status === 'aktif').length;
  const selesai = consignments.filter(k => k.status === 'selesai').length;
  const beredar = consignments.reduce((s,k) => s + Math.max(0, k.qtyTitip - k.qtyTerjual - k.qtyKembali), 0);
  document.getElementById('ks-stats').innerHTML = `
    <div class="stat-card sc-a2"><div class="stat-icon">📦</div><div class="stat-label">Konsinyasi Aktif</div><div class="stat-value">${aktif}</div><div class="stat-meta">sedang berjalan</div></div>
    <div class="stat-card sc-a4"><div class="stat-icon">✅</div><div class="stat-label">Konsinyasi Selesai</div><div class="stat-value">${selesai}</div><div class="stat-meta">sudah ditutup</div></div>
    <div class="stat-card sc-a3"><div class="stat-icon">🏪</div><div class="stat-label">Unit Beredar</div><div class="stat-value">${beredar}</div><div class="stat-meta">masih di toko</div></div>`;
}

function renderKsTable() {
  const q   = (document.getElementById('ks-search')||{value:''}).value.toLowerCase();
  const st  = (document.getElementById('ks-filter-status')||{value:''}).value;
  const tbody = document.getElementById('ks-table-body');
  if (!tbody) return;

  const list = consignments.filter(k => {
    if (st && k.status !== st) return false;
    if (q) {
      const inTempat = k.tempat.toLowerCase().includes(q);
      const inProduk = k.items.some(it => it.namaProduk.toLowerCase().includes(q));
      if (!inTempat && !inProduk) return false;
    }
    return true;
  });

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state"><div class="empty-icon">📦</div><div class="empty-text">Belum ada konsinyasi</div></div></td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(k => {
    const pc     = k.profit > 0 ? 'var(--green)' : k.profit < 0 ? 'var(--red)' : 'var(--text2)';
    const badge  = k.status === 'aktif'
      ? '<span class="badge badge-blue">Aktif</span>'
      : '<span class="badge badge-green">Selesai</span>';
    const produkLabel = k.items.length === 1
      ? k.items[0].namaProduk
      : `${k.items.length} produk`;
    const produkTitle = k.items.map(it => `${it.namaProduk} (${it.qtyTitip} pcs)`).join(', ');
    return `<tr>
      <td><strong>${k.tempat}</strong></td>
      <td title="${produkTitle.replace(/"/g,'&quot;')}">${produkLabel}</td>
      <td style="font-size:12px;color:var(--text3);">${k.tanggalStr}</td>
      <td>${k.durasibulan} bln</td>
      <td>${k.qtyTitip}</td>
      <td>${k.qtyTerjual}</td>
      <td>${k.qtySisa}</td>
      <td style="font-weight:700;color:${pc};">${fmt(k.profit)}</td>
      <td>${badge}</td>
      <td style="white-space:nowrap;">
        <button class="btn btn-secondary btn-sm" onclick="openKsLaporan('${k.id}')" title="Laporan">📊</button>
        <button class="btn btn-secondary btn-sm" onclick="printSuratJalan('${k.id}')" title="Surat Jalan">🖨️</button>
        <button class="btn btn-secondary btn-sm" onclick="openKsUpdate('${k.id}')" title="Update Terjual">✏️</button>
        <button class="btn btn-danger btn-sm" onclick="deleteKs('${k.id}')">🗑</button>
      </td>
    </tr>`;
  }).join('');
}

// ── Baris produk dinamis di modal Tambah Konsinyasi ──────────────
let ksItemSeq = 0;

function addKsItemRow(prefill) {
  ksItemSeq++;
  const rid = ksItemSeq;
  const wrap = document.getElementById('ks-items-wrap');
  const optsHtml = products.map(p => `<option value="${p.id}">${p.nama}</option>`).join('');
  const row = document.createElement('div');
  row.className = 'ks-item-row';
  row.id = `ks-item-${rid}`;
  row.style.cssText = 'display:flex;gap:8px;align-items:flex-end;padding:10px;background:var(--bg2);border-radius:8px;';
  row.innerHTML = `
    <div class="form-group" style="flex:2;margin:0;"><label style="font-size:11px;">Produk</label>
      <select id="ks-item-produk-${rid}" onchange="autoFillKsItemRow(${rid})"><option value="">— Pilih produk —</option>${optsHtml}</select>
    </div>
    <div class="form-group" style="flex:1;margin:0;"><label style="font-size:11px;">Qty</label>
      <input type="number" id="ks-item-qty-${rid}" placeholder="0" min="1" oninput="recalcKsModal()">
    </div>
    <div class="form-group" style="flex:1.3;margin:0;"><label style="font-size:11px;">Harga Jual (Rp)</label>
      <input type="number" id="ks-item-hargajual-${rid}" placeholder="0" min="0" oninput="recalcKsModal()">
    </div>
    <div class="form-group" style="flex:1.3;margin:0;"><label style="font-size:11px;">Modal/HPP (Rp)</label>
      <input type="number" id="ks-item-modal-${rid}" placeholder="0" min="0" oninput="recalcKsModal()">
    </div>
    <button type="button" class="btn btn-danger btn-sm" style="height:36px;" onclick="removeKsItemRow(${rid})" title="Hapus produk ini">🗑</button>`;
  wrap.appendChild(row);

  if (prefill) {
    document.getElementById(`ks-item-produk-${rid}`).value   = prefill.produkId || '';
    document.getElementById(`ks-item-qty-${rid}`).value       = prefill.qtyTitip || '';
    document.getElementById(`ks-item-hargajual-${rid}`).value = prefill.hargaJual || '';
    document.getElementById(`ks-item-modal-${rid}`).value     = prefill.hargaModal || '';
  }
  recalcKsModal();
}

function removeKsItemRow(rid) {
  const el = document.getElementById(`ks-item-${rid}`);
  if (el) el.remove();
  recalcKsModal();
}

function autoFillKsItemRow(rid) {
  const pid = +document.getElementById(`ks-item-produk-${rid}`).value;
  if (!pid) return;
  const pr = prices.find(p => p.produkId === pid);
  if (pr) {
    const hpp = pr.components.reduce((a,c) => a + c.harga, 0) + pr.overhead;
    document.getElementById(`ks-item-modal-${rid}`).value     = Math.round(hpp);
    document.getElementById(`ks-item-hargajual-${rid}`).value = Math.round(pr.hargaJual);
    recalcKsModal();
  }
}

function _collectKsItems() {
  const rows = document.querySelectorAll('#ks-items-wrap .ks-item-row');
  const items = [];
  rows.forEach(row => {
    const rid    = row.id.replace('ks-item-', '');
    const selEl  = document.getElementById(`ks-item-produk-${rid}`);
    const pid    = +selEl.value;
    const nama   = selEl.options[selEl.selectedIndex]?.text || '';
    items.push({
      produkId:   pid,
      namaProduk: nama,
      qtyTitip:   +document.getElementById(`ks-item-qty-${rid}`).value || 0,
      hargaJual:  +document.getElementById(`ks-item-hargajual-${rid}`).value || 0,
      hargaModal: +document.getElementById(`ks-item-modal-${rid}`).value || 0,
    });
  });
  return items;
}

function openAddKonsinyasi() {
  document.getElementById('ks-edit-id').value = '';
  document.getElementById('modal-ks-title').textContent = 'Tambah Konsinyasi';
  document.getElementById('form-ks-tempat').value = '';
  document.getElementById('form-ks-tanggal').value = today();
  document.getElementById('form-ks-durasi').value = '3';
  document.getElementById('form-ks-komisi').value = '0';
  document.getElementById('form-ks-catatan').value = '';
  document.getElementById('ks-items-wrap').innerHTML = '';
  ksItemSeq = 0;
  addKsItemRow(); // mulai dengan 1 baris produk kosong
  recalcKsModal();
  openModal('modal-konsinyasi');
}

function recalcKsModal() {
  const komisi = (+document.getElementById('form-ks-komisi').value || 0) / 100;
  const items  = _collectKsItems();
  let totalModal = 0, pendBersih = 0;
  items.forEach(it => {
    totalModal += it.qtyTitip * it.hargaModal;
    pendBersih += it.qtyTitip * it.hargaJual * (1 - komisi);
  });
  const profit = pendBersih - totalModal;
  document.getElementById('ks-prev-modal').textContent = fmt(totalModal);
  document.getElementById('ks-prev-pend').textContent  = fmt(pendBersih);
  const el = document.getElementById('ks-prev-profit');
  el.textContent = fmt(profit);
  el.style.color = profit >= 0 ? 'var(--green)' : 'var(--red)';
}

async function saveKonsinyasi() {
  const items = _collectKsItems();
  const body  = {
    tempat:       document.getElementById('form-ks-tempat').value.trim(),
    tanggalMulai: document.getElementById('form-ks-tanggal').value,
    durasibulan:  +document.getElementById('form-ks-durasi').value,
    komisiPersen: +document.getElementById('form-ks-komisi').value,
    catatan:      document.getElementById('form-ks-catatan').value,
    items,
  };
  if (!body.tempat) { toast('⚠️ Nama tempat wajib diisi!'); return; }
  if (!items.length) { toast('⚠️ Tambahkan minimal 1 produk!'); return; }
  for (const it of items) {
    if (!it.produkId) { toast('⚠️ Ada baris produk yang belum dipilih!'); return; }
    if (!it.qtyTitip) { toast(`⚠️ Qty titip untuk "${it.namaProduk}" wajib diisi!`); return; }
  }
  try {
    await api('/api/consignments', 'POST', body);
    closeModal('modal-konsinyasi');
    toast('Konsinyasi disimpan ✓');
    loadKonsinyasi();
  } catch(e) { toast('⚠️ ' + e.message); }
}

function openKsUpdate(id) {
  const k = consignments.find(x => x.id === id);
  if (!k) return;
  document.getElementById('ks-update-id').value = id;
  document.getElementById('ks-update-info').innerHTML =
    `<strong>${k.tempat}</strong> &nbsp;|&nbsp; ${k.items.length} produk &nbsp;|&nbsp; Mulai: ${k.tanggalStr}`;

  const wrap = document.getElementById('ks-update-items-wrap');
  wrap.innerHTML = k.items.map(it => `
    <div class="ks-update-item-row" data-item-id="${it.id}" style="padding:10px;background:var(--bg2);border-radius:8px;">
      <div style="font-weight:600;font-size:13px;margin-bottom:6px;">${it.namaProduk}
        <span style="font-weight:400;color:var(--text3);font-size:12px;">— titip ${it.qtyTitip} pcs</span>
      </div>
      <div class="form-row" style="margin:0;">
        <div class="form-group" style="margin:0;"><label style="font-size:11px;">Qty Terjual</label>
          <input type="number" class="ks-upd-terjual" min="0" value="${it.qtyTerjual}"></div>
        <div class="form-group" style="margin:0;"><label style="font-size:11px;">Qty Kembali</label>
          <input type="number" class="ks-upd-kembali" min="0" value="${it.qtyKembali}"></div>
      </div>
    </div>`).join('');

  openModal('modal-ks-update');
}

async function saveKsUpdate() {
  const id = document.getElementById('ks-update-id').value;
  const rows = document.querySelectorAll('#ks-update-items-wrap .ks-update-item-row');
  const items = Array.from(rows).map(row => ({
    itemId:     +row.dataset.itemId,
    qtyTerjual: +row.querySelector('.ks-upd-terjual').value || 0,
    qtyKembali: +row.querySelector('.ks-upd-kembali').value || 0,
  }));
  try {
    const data = await api(`/api/consignments/${id}/update-sold`, 'PUT', { items });
    closeModal('modal-ks-update');
    toast(data.status === 'selesai' ? '✅ Konsinyasi selesai!' : 'Data diperbarui ✓');
    loadKonsinyasi();
  } catch(e) { toast('⚠️ ' + e.message); }
}

async function openKsLaporan(id) {
  try {
    const data = await api(`/api/consignments/${id}/report`);
    const info = data.info;
    const ak   = data.aktual;
    const proj = data.proyeksi;
    const perItem = data.aktualPerItem;

    document.getElementById('modal-ks-lap-title').textContent = `Laporan: ${info.tempat}`;
    document.getElementById('ks-lap-info').innerHTML =
      `<strong>${info.tempat}</strong> — ${info.jumlahProduk} produk<br>
       Mulai: ${info.tanggalStr} &nbsp;|&nbsp; Durasi: ${info.durasibulan} bln &nbsp;|&nbsp;
       Status: <strong>${info.status}</strong> &nbsp;|&nbsp; Komisi toko: ${info.komisiPersen}%`;

    const sc = s => s === 'untung' ? 'var(--green)' : s === 'rugi' ? 'var(--red)' : 'var(--gold)';
    const bc = s => s === 'untung' ? 'badge-green' : s === 'rugi' ? 'badge-red' : 'badge-yellow';

    document.getElementById('ks-lap-per-item').innerHTML = perItem.map(it => `
      <tr>
        <td>${it.namaProduk}</td>
        <td>${it.qtyTitip}</td>
        <td>${it.qtyTerjual}</td>
        <td>${it.qtySisaDitangan}</td>
        <td style="font-weight:700;color:${sc(it.statusProfit)};">${fmt(it.profit)}</td>
      </tr>`).join('');

    document.getElementById('ks-lap-aktual').innerHTML = `
      <div class="hpp-row"><span>Unit Titip</span><span>${ak.qtyTitip}</span></div>
      <div class="hpp-row"><span>Unit Terjual</span><span>${ak.qtyTerjual}</span></div>
      <div class="hpp-row"><span>Unit Kembali</span><span>${ak.qtyKembali}</span></div>
      <div class="hpp-row"><span>Sisa di Tangan</span><span>${ak.qtySisaDitangan} unit (modal ${fmt(ak.nilaiSisaDitangan)} mengendap)</span></div>
      <div class="hpp-row"><span>Pendapatan Kotor</span><span>${fmt(ak.pendapatanKotor)}</span></div>
      <div class="hpp-row"><span>Komisi Toko</span><span style="color:var(--red);">− ${fmt(ak.komisiNominal)}</span></div>
      <div class="hpp-row"><span>Pendapatan Bersih</span><span>${fmt(ak.pendapatanBersih)}</span></div>
      <div class="hpp-row"><span>Modal Terpakai</span><span style="color:var(--red);">− ${fmt(ak.modalTerpakai)}</span></div>
      <div class="hpp-row total"><span>Profit Aktual</span><span style="color:${sc(ak.statusProfit)};">${fmt(ak.profit)} <span class="badge ${bc(ak.statusProfit)}" style="margin-left:6px;">${ak.statusProfit.toUpperCase()}</span></span></div>`;

    document.getElementById('ks-lap-proyeksi').innerHTML = proj.map(p => `
      <tr>
        <td>${p.bulan} Bulan</td>
        <td>~${p.qtyProyeksiTerjual} unit</td>
        <td>${fmt(p.pendapatanBersih)}</td>
        <td>${fmt(p.modalTerpakai)}</td>
        <td style="font-weight:700;color:${sc(p.statusProfit)};">${fmt(p.profit)}</td>
        <td><span class="badge ${bc(p.statusProfit)}">${p.statusProfit}</span></td>
      </tr>`).join('');

    openModal('modal-ks-laporan');
  } catch(e) { toast('⚠️ Gagal muat laporan: ' + e.message); }
}

async function deleteKs(id) {
  if (!confirm('Hapus konsinyasi ini?')) return;
  try {
    await api('/api/consignments/' + id, 'DELETE');
    toast('Dihapus ✓');
    loadKonsinyasi();
  } catch(e) { toast('⚠️ ' + e.message); }
}

// ══════════════════════════════════════════════════════
// REKOMENDASI HARGA
// ══════════════════════════════════════════════════════

function populateRecMaterialSelect() {
  const sel = document.getElementById('rec-material-select');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">— Pilih bahan —</option>';
  materials.forEach(m => {
    sel.innerHTML += `<option value="${m.id}">${m.nama} (${m.satuan}) — ${fmt(m.hargaSatuan)}</option>`;
  });
  if (current) sel.value = current;
}

function loadRecMaterial() {
  const sel = document.getElementById('rec-material-select');
  document.getElementById('rec-info').style.display   = 'none';
  document.getElementById('rec-result').style.display = 'none';
  if (!sel.value) return;
  const mat = materials.find(m => m.id == sel.value);
  if (mat) document.getElementById('rec-harga-baru').value = mat.hargaSatuan;
}

async function hitungRekomendasiHarga() {
  const matId    = +document.getElementById('rec-material-select').value;
  const hargaBaru = +document.getElementById('rec-harga-baru').value;
  const margin   = +document.getElementById('rec-margin').value || 30;
  if (!matId || !hargaBaru) { toast('⚠️ Pilih bahan dan isi harga baru'); return; }

  try {
    const data = await api('/api/price-recommendation', 'POST', {
      materialId: matId, hargaBaruPerSatuan: hargaBaru, targetMargin: margin,
    });
    const mat = data.material;

    // Info kenaikan
    const naik  = mat.naikNominal >= 0;
    const warna = naik ? 'var(--red)' : 'var(--green)';
    document.getElementById('rec-info').style.display = 'block';
    document.getElementById('rec-info-text').innerHTML =
      `<strong>${mat.nama}</strong>: harga lama <strong>${fmt(mat.hargaLama)}</strong> → 
       harga baru <strong>${fmt(mat.hargaBaru)}</strong> / ${mat.satuan} &nbsp;
       <span style="color:${warna};font-weight:700;">
         ${naik ? '▲' : '▼'} ${fmt(Math.abs(mat.naikNominal))} 
         (${mat.naikPersen >= 0 ? '+' : ''}${mat.naikPersen}%)
       </span>`;

    const tbody  = document.getElementById('rec-table-body');
    const resEl  = document.getElementById('rec-result');
    const emptyEl= document.getElementById('rec-empty');
    resEl.style.display = 'block';

    if (!data.rekomendasi.length) {
      tbody.innerHTML = '';
      emptyEl.style.display = 'block';
    } else {
      emptyEl.style.display = 'none';
      tbody.innerHTML = data.rekomendasi.map(rec => {
        const diff = rec.selisihHarga;
        const dc   = diff > 0 ? 'var(--red)' : diff < 0 ? 'var(--green)' : 'var(--text2)';
        return `<tr>
          <td><strong>${rec.namaProduk}</strong></td>
          <td style="font-size:11.5px;color:var(--text3);">${rec.komponenTerdampak}</td>
          <td>${fmt(rec.hppLama)}</td>
          <td style="font-weight:600;">${fmt(rec.hppBaru)}</td>
          <td>${fmt(rec.hargaJualLama)}</td>
          <td style="font-weight:700;color:var(--gold);">${fmt(rec.hargaJualRekomen)}</td>
          <td style="font-weight:600;color:${dc};">${diff > 0 ? '+' : ''}${fmt(diff)}</td>
          <td>${rec.marginLama}%</td>
          <td style="font-weight:600;color:var(--green);">${rec.marginBaru}%</td>
        </tr>`;
      }).join('');
    }
  } catch(e) { toast('⚠️ Gagal hitung rekomendasi: ' + e.message); }
}

// ══════════════════════════════════════════════════════
// CETAK NOTA & SURAT JALAN
// ══════════════════════════════════════════════════════

function printNota(orderId) {
  window.open('/api/print/nota/' + orderId, '_blank');
}

function printSuratJalan(consignmentId) {
  window.open('/api/print/surat-jalan/' + consignmentId, '_blank');
}

// ══════════════════════════════════════════════════════
// RIWAYAT CETAK
// ══════════════════════════════════════════════════════

let cetakLogs = [];

async function loadCetakLog() {
  try {
    cetakLogs = await api('/api/print/logs?limit=200');
    renderCetakLog();
  } catch(e) { toast('⚠️ Gagal muat riwayat cetak: ' + e.message); }
}

function renderCetakLog() {
  const f     = (document.getElementById('cetaklog-filter')||{value:''}).value;
  const list  = f ? cetakLogs.filter(l => l.type === f) : cetakLogs;
  const tbody = document.getElementById('cetaklog-table-body');
  if (!tbody) return;

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">🖨️</div><div class="empty-text">Belum ada riwayat cetak</div></div></td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(l => {
    const typeLabel = l.type === 'nota'
      ? '<span class="badge badge-blue">Nota</span>'
      : '<span class="badge badge-teal">Surat Jalan</span>';
    const printFn = l.type === 'nota'
      ? `printNota('${l.refId}')`
      : `printSuratJalan('${l.refId}')`;
    return `<tr>
      <td>${typeLabel}</td>
      <td><code>${l.refId}</code></td>
      <td style="font-weight:500;">${l.refLabel}</td>
      <td style="font-size:12px;color:var(--text3);white-space:nowrap;">${l.printedStr}</td>
      <td><button class="btn btn-secondary btn-sm" onclick="${printFn}" title="Cetak Ulang">🖨️ Cetak Ulang</button></td>
    </tr>`;
  }).join('');
}
