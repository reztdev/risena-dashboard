# printing.py — Cetak Nota & Surat Jalan untuk BatikCraft
# ─────────────────────────────────────────────────────────
# Dua jenis dokumen dengan ukuran kertas berbeda:
#   1. Nota        → Thermal printer (80mm default, 58mm via ?lebar=58)
#   2. Surat Jalan → A4 full (konsinyasi / pengiriman jauh)
#
# Setiap cetak otomatis dicatat ke tabel print_logs (riwayat).
# Dokumen di-return sebagai HTML siap print di browser.
# ─────────────────────────────────────────────────────────

import time
from datetime import datetime
from calendar import monthrange

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from database import get_conn, fmt_date_id

router = APIRouter(prefix="/api/print", tags=["cetak"])

# ─────────────────────────────────────────────────────────
# KONFIGURASI BRAND — sesuaikan di sini
# ─────────────────────────────────────────────────────────
BRAND_NAME    = "Risena Collection"
BRAND_TAGLINE = "Handmade Asli Pekalongan"
BRAND_ALAMAT  = "Jl. Kimangun Sarkoro No.27, Setono, Pekalongan Timur"
BRAND_TELP    = "082135071834"


# ─────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────

def _rupiah(n: float) -> str:
    return "Rp " + "{:,.0f}".format(n).replace(",", ".")


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year  = dt.year + month // 12
    month = month % 12 + 1
    day   = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _log_print(conn, type_: str, ref_id: str, ref_label: str) -> None:
    pid     = f"PL-{int(time.time() * 1000)}"
    now     = datetime.now()
    now_str = fmt_date_id(now) + f" {now.strftime('%H:%M')}"
    conn.execute(
        "INSERT INTO print_logs (id, type, ref_id, ref_label, printed_at, printed_str) "
        "VALUES (?,?,?,?,?,?)",
        (pid, type_, ref_id, ref_label, now.isoformat(), now_str),
    )


# ═════════════════════════════════════════════════════════
# CSS THERMAL — Nota pembeli langsung (58mm / 80mm)
# ═════════════════════════════════════════════════════════

def _css_thermal(lebar_mm: int) -> str:
    """CSS untuk printer thermal. Lebar 58mm atau 80mm."""
    doc_w    = f"{lebar_mm}mm"
    fs_base  = "10px" if lebar_mm == 58 else "11px"
    fs_brand = "13px" if lebar_mm == 58 else "15px"
    fs_total = "12px" if lebar_mm == 58 else "13px"

    return f"""<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}

  body {{
    font-family: 'Courier New', Courier, monospace;
    font-size: {fs_base};
    color: #000;
    background: #c8c8c8;
    padding: 16px;
  }}

  .toolbar {{ text-align:center; padding:10px 0 14px; }}
  .btn {{
    display:inline-block; padding:7px 18px; font-size:12px;
    cursor:pointer; border:none; border-radius:4px; margin:0 3px;
    font-family: Arial, sans-serif;
  }}
  .btn-print {{ background:#1a1a1a; color:#fff; }}
  .btn-close {{ background:#888;    color:#fff; }}

  /* Kertas thermal — lebar fixed, tinggi mengikuti konten */
  .doc {{
    width: {doc_w};
    margin: 0 auto;
    background: #fff;
    padding: 8px 8px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25);
  }}

  /* Header brand — terpusat */
  .th-brand {{
    text-align: center;
    border-bottom: 1px dashed #000;
    padding-bottom: 7px;
    margin-bottom: 7px;
  }}
  .th-brand-name {{ font-size:{fs_brand}; font-weight:bold; letter-spacing:.5px; }}
  .th-brand-sub  {{ font-size:9px; margin-top:2px; line-height:1.45; }}

  /* Info dokumen */
  .th-doc-info {{
    border-bottom: 1px dashed #000;
    padding-bottom: 6px;
    margin-bottom: 6px;
  }}
  .th-doc-row {{
    display:flex; justify-content:space-between; margin-bottom:2px; font-size:{fs_base};
  }}
  .th-doc-row span:first-child {{ color:#444; }}
  .th-doc-row span:last-child  {{ font-weight:bold; }}

  /* Item list */
  .th-items {{ width:100%; margin-bottom:4px; }}
  .th-items-head {{
    border-top:1px dashed #000; border-bottom:1px dashed #000;
    padding:3px 0; display:flex; justify-content:space-between;
    font-size:9px; font-weight:bold;
  }}
  .th-item-row {{
    padding:4px 0;
    border-bottom:1px dotted #bbb;
  }}
  .th-item-name   {{ font-size:{fs_base}; font-weight:bold; }}
  .th-item-detail {{
    display:flex; justify-content:space-between;
    font-size:{fs_base}; margin-top:1px; color:#333;
  }}

  /* Total */
  .th-totals {{
    border-top:1px dashed #000;
    padding-top:5px; margin-bottom:7px;
  }}
  .th-total-row {{
    display:flex; justify-content:space-between;
    font-size:{fs_base}; margin-bottom:3px;
  }}
  .th-total-grand {{
    display:flex; justify-content:space-between;
    font-size:{fs_total}; font-weight:bold;
    border-top:1px dashed #000;
    padding-top:4px; margin-top:4px;
  }}
  .th-diskon {{ color:#c00; }}

  /* Catatan */
  .th-note {{
    font-size:9px; border-top:1px dashed #000;
    padding-top:5px; margin-bottom:7px;
    color:#333; line-height:1.5;
  }}

  /* Footer */
  .th-footer {{
    border-top:1px dashed #000; padding-top:6px;
    text-align:center; font-size:9px; color:#444; line-height:1.6;
  }}

  /* === PRINT === */
  @media print {{
    body     {{ background:white; padding:0; }}
    .toolbar {{ display:none; }}
    .doc     {{ box-shadow:none; padding:4px 6px 10px; width:{doc_w}; }}
    @page    {{ size:{doc_w} auto; margin:2mm; }}
  }}
</style>"""


# ═════════════════════════════════════════════════════════
# CSS A4 — Surat Jalan konsinyasi / pengiriman jauh
# ═════════════════════════════════════════════════════════

_CSS_A4 = """<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: Arial, sans-serif;
    font-size: 12px; color:#111;
    background: #ddd; padding:24px;
  }

  .toolbar { text-align:center; padding:10px 0 14px; }
  .btn {
    display:inline-block; padding:8px 22px; font-size:13px;
    cursor:pointer; border:none; border-radius:4px; margin:0 4px;
  }
  .btn-print { background:#1a1a1a; color:#fff; }
  .btn-close { background:#888;    color:#fff; }

  /* Kertas A4 */
  .doc {
    width:210mm; min-height:297mm; margin:0 auto;
    background:#fff; padding:18mm 16mm;
    box-shadow:0 2px 14px rgba(0,0,0,.18);
  }

  /* Header */
  .header {
    display:flex; justify-content:space-between; align-items:flex-start;
    border-bottom:2px solid #111; padding-bottom:13px; margin-bottom:17px;
  }
  .brand-name { font-size:22px; font-weight:bold; letter-spacing:1px; }
  .brand-sub  { font-size:10px; color:#555; margin-top:3px; }
  .doc-info   { text-align:right; }
  .doc-title  { font-size:18px; font-weight:bold; text-transform:uppercase; letter-spacing:2px; }
  .doc-no     { font-size:11px; color:#444; margin-top:4px; }

  /* Meta */
  .meta { display:flex; gap:28px; margin-bottom:16px; flex-wrap:wrap; }
  .meta-label { font-size:9px; text-transform:uppercase; color:#888; margin-bottom:3px; }
  .meta-value { font-weight:bold; font-size:12px; }

  /* Tabel */
  table { width:100%; border-collapse:collapse; margin-bottom:14px; }
  thead th {
    background:#1a1a1a; color:#fff;
    padding:8px 10px; font-size:11px; text-align:left;
  }
  tbody td { padding:7px 10px; border-bottom:1px solid #ddd; font-size:11px; }
  tbody tr:nth-child(even) td { background:#f7f7f7; }
  .num { text-align:right; }

  /* Ringkasan nilai */
  .totals { margin-left:auto; width:290px; margin-bottom:20px; }
  .total-row {
    display:flex; justify-content:space-between;
    padding:5px 0; font-size:11px; border-bottom:1px solid #eee;
  }

  /* Note */
  .note-box {
    background:#f5f5f5; border-left:3px solid #bbb;
    padding:8px 11px; font-size:10px; margin-bottom:18px; color:#444;
  }
  .note-label { font-weight:bold; color:#111; margin-bottom:3px; font-size:11px; }

  /* Syarat */
  .syarat {
    font-size:10px; color:#555; border:1px dashed #ccc;
    padding:8px 11px; margin-bottom:20px; border-radius:3px; line-height:1.7;
  }

  /* TTD */
  .signatures { display:flex; justify-content:space-between; margin-top:32px; gap:24px; }
  .sig-block  { text-align:center; flex:1; }
  .sig-title  { font-size:10px; color:#555; margin-bottom:56px; }
  .sig-line   { border-top:1px solid #111; padding-top:4px; font-weight:bold; font-size:11px; }
  .sig-name   { font-size:9px; color:#777; margin-top:2px; }

  /* Footer */
  .footer {
    text-align:center; font-size:9px; color:#aaa;
    margin-top:22px; border-top:1px solid #eee; padding-top:8px;
  }

  /* === PRINT === */
  @media print {
    body     { background:white; padding:0; }
    .toolbar { display:none; }
    .doc     { box-shadow:none; padding:12mm 14mm; width:210mm; min-height:auto; }
    @page    { size:A4; margin:0; }
  }
</style>"""


# ─────────────────────────────────────────────────────────
# WRAPPER HTML
# ─────────────────────────────────────────────────────────

_TOOLBAR = """<div class="toolbar">
  <button class="btn btn-print" onclick="window.print()">🖨️ Cetak</button>
  <button class="btn btn-close" onclick="window.close()">✕ Tutup</button>
</div>"""


def _wrap(title: str, css: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  {css}
</head>
<body>
  {_TOOLBAR}
  <div class="doc">
    {body}
  </div>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
# ENDPOINT — NOTA THERMAL (order / penjualan langsung)
# ════════════════════════════════════════════════════════════

@router.get("/nota/{order_id}", response_class=HTMLResponse)
def print_nota(
    order_id: str,
    lebar: int = Query(default=80, description="Lebar kertas thermal mm (58 atau 80)")
) -> HTMLResponse:
    """
    Nota thermal untuk pembeli langsung.
    - Default 80mm. Printer 58mm: /api/print/nota/{id}?lebar=58
    - Layout vertikal satu kolom, font monospace, tanpa background warna.
    - @page size otomatis menyesuaikan lebar.
    """
    if lebar not in (58, 80):
        lebar = 80

    with get_conn() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        ).fetchone()
        if not order:
            raise HTTPException(404, "Order tidak ditemukan")

        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY id",
            (order_id,),
        ).fetchall()

        _log_print(conn, "nota", order_id, order["customer"])
        conn.commit()

    # ── Item rows ──
    rows_html = ""
    for it in items:
        rows_html += f"""
        <div class="th-item-row">
          <div class="th-item-name">{it['nama']}</div>
          <div class="th-item-detail">
            <span>{it['qty']} x {_rupiah(it['harga'])}</span>
            <span><b>{_rupiah(it['subtotal'])}</b></span>
          </div>
        </div>"""

    # ── Diskon ──
    disc_html = ""
    if order["discount"] and order["discount"] > 0:
        disc_html = f"""
        <div class="th-total-row">
          <span>Diskon {int(order['discount'])}%</span>
          <span class="th-diskon">- {_rupiah(order['subtotal'] * order['discount'] / 100)}</span>
        </div>"""

    # ── Catatan ──
    note_html = ""
    if order["note"] and order["note"].strip():
        note_html = f'<div class="th-note">Catatan: {order["note"]}</div>'

    body = f"""
    <div class="th-brand">
      <div class="th-brand-name">{BRAND_NAME}</div>
      <div class="th-brand-sub">{BRAND_TAGLINE}</div>
      <div class="th-brand-sub">{BRAND_ALAMAT}</div>
      <div class="th-brand-sub">WA: {BRAND_TELP}</div>
    </div>

    <div class="th-doc-info">
      <div class="th-doc-row"><span>No</span><span>{order['id']}</span></div>
      <div class="th-doc-row"><span>Tgl</span><span>{order['date_str']}</span></div>
      <div class="th-doc-row"><span>Kepada</span><span>{order['customer']}</span></div>
    </div>

    <div class="th-items">
      <div class="th-items-head">
        <span>Barang</span><span>Subtotal</span>
      </div>
      {rows_html}
    </div>

    <div class="th-totals">
      <div class="th-total-row">
        <span>Subtotal</span><span>{_rupiah(order['subtotal'])}</span>
      </div>
      {disc_html}
      <div class="th-total-grand">
        <span>TOTAL</span><span>{_rupiah(order['total'])}</span>
      </div>
    </div>

    {note_html}

    <div class="th-footer">
      *** Terima kasih ***<br>
      Barang yang sudah dibeli tidak dapat dikembalikan.<br>
      {BRAND_NAME}
    </div>"""

    return HTMLResponse(_wrap(f"Nota {order_id}", _css_thermal(lebar), body))


# ════════════════════════════════════════════════════════════
# ENDPOINT — SURAT JALAN A4 (konsinyasi / pengiriman jauh)
# ════════════════════════════════════════════════════════════

@router.get("/surat-jalan/{batch_id}", response_class=HTMLResponse)
def print_surat_jalan(batch_id: str) -> HTMLResponse:
    """
    Surat jalan A4 untuk konsinyasi / pengiriman jauh.
    1 batch bisa berisi banyak produk (multi-item) — semuanya ditampilkan
    sebagai baris terpisah dalam 1 tabel barang.
    Berisi: info brand, detail barang, nilai titipan, syarat, kolom TTD.
    @page size: A4.
    """
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM consignment_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "Konsinyasi tidak ditemukan")
        items = conn.execute(
            "SELECT * FROM consignment_items WHERE batch_id=? ORDER BY id",
            (batch_id,)
        ).fetchall()
        if not items:
            raise HTTPException(404, "Konsinyasi ini belum punya produk")

        _log_print(conn, "surat_jalan", batch_id, r["tempat"])
        conn.commit()

    # ── Tanggal jatuh tempo (dipakai di syarat & ketentuan) ──
    try:
        mulai_dt  = datetime.fromisoformat(r["tanggal_mulai"])
        jatuh_dt  = _add_months(mulai_dt, r["durasi_bulan"])
        jatuh_str = fmt_date_id(jatuh_dt)
    except Exception:
        jatuh_str = "-"

    rows_html   = ""
    nilai_total = 0.0
    for idx, it in enumerate(items, start=1):
        subtotal    = it["qty_titip"] * it["harga_jual"]
        nilai_total += subtotal
        rows_html += f"""
        <tr>
          <td>{idx}</td>
          <td>{it['nama_produk']}</td>
          <td class="num">{it['qty_titip']} pcs</td>
          <td class="num">{_rupiah(it['harga_jual'])}</td>
          <td class="num">{_rupiah(subtotal)}</td>
        </tr>"""

    komisi_nom = nilai_total * (r["komisi_persen"] / 100)

    note_html = ""
    if r["catatan"] and r["catatan"].strip():
        note_html = f"""
        <div class="note-box">
          <div class="note-label">Catatan</div>
          {r['catatan']}
        </div>"""

    body = f"""
    <div class="header">
      <div>
        <div class="brand-name">{BRAND_NAME}</div>
        <div class="brand-sub">{BRAND_TAGLINE}</div>
        <div class="brand-sub">{BRAND_ALAMAT}</div>
        <div class="brand-sub">WA: {BRAND_TELP}</div>
      </div>
      <div class="doc-info">
        <div class="doc-title">Surat Jalan</div>
        <div class="doc-no">No.&nbsp;{r['id']}</div>
        <div class="doc-no">Tgl.&nbsp;{r['tanggal_str']}</div>
      </div>
    </div>

    <div class="meta">
      <div>
        <div class="meta-label">Dikirim / Dititipkan Ke</div>
        <div class="meta-value">{r['tempat']}</div>
      </div>
      <div>
        <div class="meta-label">Komisi Toko</div>
        <div class="meta-value">{r['komisi_persen']}% ({_rupiah(komisi_nom)})</div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width:32px">No</th>
          <th>Nama Barang</th>
          <th class="num" style="width:80px">Qty</th>
          <th class="num" style="width:120px">Harga Jual</th>
          <th class="num" style="width:130px">Total Nilai</th>
        </tr>
      </thead>
      <tbody>{rows_html}
      </tbody>
    </table>

    <div class="totals">
      <div class="total-row"><span>Total Nilai Titipan</span><span>{_rupiah(nilai_total)}</span></div>
      <div class="total-row"><span>Estimasi Komisi Toko</span><span>{_rupiah(komisi_nom)}</span></div>
    </div>

    {note_html}

    <div class="syarat">
      <strong>Syarat &amp; Ketentuan Konsinyasi:</strong><br>
      1. Barang yang tidak terjual wajib dikembalikan dalam kondisi baik sebelum <strong>{jatuh_str}</strong>.<br>
      2. Toko/konsinyee bertanggung jawab atas barang yang hilang atau rusak selama masa titipan.<br>
      3. Pembayaran hasil penjualan dilakukan selambatnya 7 hari setelah barang terjual.<br>
      4. Dokumen ini sah sebagai bukti serah terima barang.
    </div>

    <div class="signatures">
      <div class="sig-block">
        <div class="sig-title">Penerima / Konsinyee</div>
        <div class="sig-line">{r['tempat']}</div>
        <div class="sig-name">( ________________ )</div>
      </div>
      <div class="sig-block">
        <div class="sig-title">Pengirim / Owner</div>
        <div class="sig-line">{BRAND_NAME}</div>
        <div class="sig-name">( ________________ )</div>
      </div>
    </div>

    <div class="footer">
      Dokumen ini sah sebagai bukti serah terima barang konsinyasi &bull; {BRAND_NAME}
    </div>"""

    return HTMLResponse(_wrap(f"Surat Jalan {batch_id}", _CSS_A4, body))


# ════════════════════════════════════════════════════════════
# ENDPOINT — RIWAYAT CETAK
# ════════════════════════════════════════════════════════════

@router.get("/logs")
def get_print_logs(limit: int = 100) -> list[dict]:
    """Riwayat semua dokumen yang pernah dicetak."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM print_logs ORDER BY printed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id":         r["id"],
            "type":       r["type"],
            "refId":      r["ref_id"],
            "refLabel":   r["ref_label"],
            "printedAt":  r["printed_at"],
            "printedStr": r["printed_str"],
        }
        for r in rows
    ]
    
