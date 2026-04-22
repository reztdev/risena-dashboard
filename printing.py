# printing.py — Cetak Nota & Surat Jalan untuk BatikCraft
# ─────────────────────────────────────────────────────────
# Dua jenis dokumen:
#   1. Nota        → pembeli langsung / bayar di tempat
#   2. Surat Jalan → konsinyasi / pengiriman jauh
#
# Setiap cetak otomatis dicatat ke tabel print_logs (riwayat).
# Dokumen di-return sebagai HTML siap print di browser.
# ─────────────────────────────────────────────────────────

import time
from datetime import datetime, date
from calendar import monthrange

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from database import get_conn, fmt_date_id

router = APIRouter(prefix="/api/print", tags=["cetak"])

# ─────────────────────────────────────────────────────────
# KONFIGURASI BRAND — sesuaikan di sini
# ─────────────────────────────────────────────────────────
BRAND_NAME    = "Risena Collection"
BRAND_TAGLINE = "Handmade Asli Pekalongan"
BRAND_ALAMAT  = "Jl. Kimangun Sarkoro No.27, Setono, Pekalongan Timur, Indonesia"
BRAND_TELP    = "082135071834"


# ─────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────

def _rupiah(n: float) -> str:
    """Format angka ke Rupiah: Rp 1.234.567"""
    return "Rp " + "{:,.0f}".format(n).replace(",", ".")


def _add_months(dt: datetime, months: int) -> datetime:
    """Tambah bulan ke datetime tanpa library dateutil."""
    month = dt.month - 1 + months
    year  = dt.year + month // 12
    month = month % 12 + 1
    day   = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _log_print(conn, type_: str, ref_id: str, ref_label: str) -> None:
    """Catat satu baris ke print_logs."""
    pid     = f"PL-{int(time.time() * 1000)}"
    now     = datetime.now()
    now_str = fmt_date_id(now) + f" {now.strftime('%H:%M')}"
    conn.execute(
        "INSERT INTO print_logs (id, type, ref_id, ref_label, printed_at, printed_str) "
        "VALUES (?,?,?,?,?,?)",
        (pid, type_, ref_id, ref_label, now.isoformat(), now_str),
    )


# ─────────────────────────────────────────────────────────
# CSS & TEMPLATE BERSAMA
# ─────────────────────────────────────────────────────────

_CSS = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: Arial, sans-serif;
    font-size: 12px;
    color: #111;
    background: #e8e8e8;
    padding: 20px;
  }

  /* Tombol cetak (disembunyikan saat print) */
  .toolbar {
    text-align: center;
    padding: 12px 0 16px 0;
  }
  .btn {
    display: inline-block;
    padding: 8px 22px;
    font-size: 13px;
    cursor: pointer;
    border: none;
    border-radius: 4px;
    margin: 0 4px;
  }
  .btn-print  { background: #1a1a1a; color: #fff; }
  .btn-close  { background: #888;    color: #fff; }

  /* Kertas */
  .doc {
    max-width: 720px;
    margin: 0 auto;
    background: #fff;
    padding: 28px 32px;
    box-shadow: 0 2px 10px rgba(0,0,0,.15);
  }

  /* Header brand + judul dokumen */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 2px solid #111;
    padding-bottom: 12px;
    margin-bottom: 16px;
  }
  .brand-name { font-size: 22px; font-weight: bold; letter-spacing: 1px; }
  .brand-sub  { font-size: 10px; color: #666; margin-top: 3px; }
  .doc-info   { text-align: right; }
  .doc-title  { font-size: 17px; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; }
  .doc-no     { font-size: 11px; color: #444; margin-top: 3px; }

  /* Blok meta (kepada, durasi, dsb) */
  .meta {
    display: flex;
    gap: 32px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }
  .meta-label { font-size: 9px; text-transform: uppercase; color: #888; margin-bottom: 2px; }
  .meta-value { font-weight: bold; font-size: 12px; }

  /* Tabel item */
  table { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
  thead th {
    background: #1a1a1a;
    color: #fff;
    padding: 7px 9px;
    font-size: 11px;
    font-weight: bold;
    text-align: left;
  }
  tbody td { padding: 6px 9px; border-bottom: 1px solid #ddd; font-size: 11px; }
  tbody tr:nth-child(even) td { background: #f8f8f8; }
  .num { text-align: right; }

  /* Baris total */
  .totals { margin-left: auto; width: 280px; margin-bottom: 18px; }
  .total-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 11px;
    border-bottom: 1px solid #eee;
  }
  .total-row.grand {
    font-weight: bold;
    font-size: 14px;
    border-top: 2px solid #111;
    border-bottom: none;
    padding-top: 7px;
    margin-top: 3px;
  }

  /* Kotak catatan */
  .note-box {
    background: #f5f5f5;
    border-left: 3px solid #bbb;
    padding: 7px 10px;
    font-size: 10px;
    margin-bottom: 20px;
    color: #444;
  }
  .note-label { font-weight: bold; color: #111; margin-bottom: 3px; font-size: 11px; }

  /* Syarat (khusus surat jalan) */
  .syarat {
    font-size: 10px;
    color: #555;
    border: 1px dashed #ccc;
    padding: 7px 10px;
    margin-bottom: 20px;
    border-radius: 3px;
  }

  /* Kolom tanda tangan */
  .signatures {
    display: flex;
    justify-content: space-between;
    margin-top: 30px;
    gap: 20px;
  }
  .sig-block { text-align: center; flex: 1; }
  .sig-title { font-size: 10px; color: #555; margin-bottom: 52px; }
  .sig-line  { border-top: 1px solid #111; padding-top: 4px; font-weight: bold; font-size: 11px; }
  .sig-name  { font-size: 9px; color: #777; margin-top: 2px; }

  /* Footer */
  .footer {
    text-align: center;
    font-size: 9px;
    color: #aaa;
    margin-top: 22px;
    border-top: 1px solid #eee;
    padding-top: 8px;
  }

  /* Override saat print */
  @media print {
    body       { background: white; padding: 0; }
    .toolbar   { display: none; }
    .doc       { box-shadow: none; padding: 0; }
  }
</style>
"""

_TOOLBAR = """
<div class="toolbar no-print">
  <button class="btn btn-print" onclick="window.print()">🖨️ Cetak Dokumen</button>
  <button class="btn btn-close" onclick="window.close()">✕ Tutup</button>
</div>
"""


def _html_wrapper(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  {_CSS}
</head>
<body>
  {_TOOLBAR}
  <div class="doc">
    {body}
  </div>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
# ENDPOINT — NOTA (order / penjualan langsung)
# ════════════════════════════════════════════════════════════

@router.get("/nota/{order_id}", response_class=HTMLResponse)
def print_nota(order_id: str) -> HTMLResponse:
    """
    Generate halaman HTML nota siap cetak untuk satu order.
    Otomatis mencatat riwayat cetak ke print_logs.
    """
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

    # ── Baris item ──
    rows_html = ""
    for i, it in enumerate(items, 1):
        rows_html += f"""
        <tr>
          <td>{i}</td>
          <td>{it['nama']}</td>
          <td class="num">{it['qty']}</td>
          <td class="num">{_rupiah(it['harga'])}</td>
          <td class="num">{_rupiah(it['subtotal'])}</td>
        </tr>"""

    # ── Baris diskon (opsional) ──
    discount_html = ""
    if order["discount"] and order["discount"] > 0:
        discount_html = f"""
        <div class="total-row">
          <span>Diskon</span>
          <span style="color:#c00">- {_rupiah(order['discount'])}</span>
        </div>"""

    # ── Catatan (opsional) ──
    note_html = ""
    if order["note"] and order["note"].strip():
        note_html = f"""
        <div class="note-box">
          <div class="note-label">Catatan</div>
          {order['note']}
        </div>"""

    body = f"""
    <!-- HEADER -->
    <div class="header">
      <div>
        <div class="brand-name">{BRAND_NAME}</div>
        <div class="brand-sub">{BRAND_TAGLINE}</div>
        <div class="brand-sub">{BRAND_ALAMAT}</div>
        <div class="brand-sub">Whatsapp: {BRAND_TELP}</div>
      </div>
      <div class="doc-info">
        <div class="doc-title">Nota</div>
        <div class="doc-no">No.&nbsp;{order['id']}</div>
        <div class="doc-no">Tgl.&nbsp;{order['date_str']}</div>
      </div>
    </div>

    <!-- META -->
    <div class="meta">
      <div>
        <div class="meta-label">Kepada</div>
        <div class="meta-value">{order['customer']}</div>
      </div>
    </div>

    <!-- TABEL ITEM -->
    <table>
      <thead>
        <tr>
          <th style="width:32px">No</th>
          <th>Nama Barang</th>
          <th class="num" style="width:50px">Qty</th>
          <th class="num" style="width:120px">Harga Satuan</th>
          <th class="num" style="width:120px">Subtotal</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <!-- TOTAL -->
    <div class="totals">
      <div class="total-row">
        <span>Subtotal</span>
        <span>{_rupiah(order['subtotal'])}</span>
      </div>
      {discount_html}
      <div class="total-row grand">
        <span>TOTAL</span>
        <span>{_rupiah(order['total'])}</span>
      </div>
    </div>

    {note_html}

    <!-- TANDA TANGAN -->
    <div class="signatures">
      <div class="sig-block">
        <div class="sig-title">Pembeli</div>
        <div class="sig-line">{order['customer']}</div>
        <div class="sig-name">( ________________ )</div>
      </div>
      <div class="sig-block">
        <div class="sig-title">Penjual / Owner</div>
        <div class="sig-line">{BRAND_NAME}</div>
        <div class="sig-name">( ________________ )</div>
      </div>
    </div>

    <!-- FOOTER -->
    <div class="footer">
      Terima kasih atas kepercayaan Anda &bull; {BRAND_NAME}
    </div>
    """

    return HTMLResponse(_html_wrapper(f"Nota {order_id}", body))


# ════════════════════════════════════════════════════════════
# ENDPOINT — SURAT JALAN (konsinyasi / pengiriman jauh)
# ════════════════════════════════════════════════════════════

@router.get("/surat-jalan/{consignment_id}", response_class=HTMLResponse)
def print_surat_jalan(consignment_id: str) -> HTMLResponse:
    """
    Generate halaman HTML surat jalan siap cetak untuk konsinyasi.
    Berisi: info brand, detail barang, nilai titipan, syarat, dan kolom TTD.
    Otomatis mencatat riwayat cetak ke print_logs.
    """
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM consignments WHERE id=?", (consignment_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "Konsinyasi tidak ditemukan")

        _log_print(conn, "surat_jalan", consignment_id, r["tempat"])
        conn.commit()

    # ── Tanggal jatuh tempo ──
    try:
        mulai_dt  = datetime.fromisoformat(r["tanggal_mulai"])
        jatuh_dt  = _add_months(mulai_dt, r["durasi_bulan"])
        jatuh_str = fmt_date_id(jatuh_dt)
    except Exception:
        jatuh_str = "-"

    # ── Nilai finansial ──
    nilai_total = r["qty_titip"] * r["harga_jual"]
    nilai_modal = r["qty_titip"] * r["harga_modal"]
    komisi_nom  = nilai_total * (r["komisi_persen"] / 100)

    # ── Catatan (opsional) ──
    note_html = ""
    if r["catatan"] and r["catatan"].strip():
        note_html = f"""
        <div class="note-box">
          <div class="note-label">Catatan</div>
          {r['catatan']}
        </div>"""

    body = f"""
    <!-- HEADER -->
    <div class="header">
      <div>
        <div class="brand-name">{BRAND_NAME}</div>
        <div class="brand-sub">{BRAND_TAGLINE}</div>
        <div class="brand-sub">{BRAND_ALAMAT}</div>
        <div class="brand-sub">Telp: {BRAND_TELP}</div>
      </div>
      <div class="doc-info">
        <div class="doc-title">Surat Jalan</div>
        <div class="doc-no">No.&nbsp;{r['id']}</div>
        <div class="doc-no">Tgl.&nbsp;{r['tanggal_str']}</div>
      </div>
    </div>

    <!-- META -->
    <div class="meta">
      <div>
        <div class="meta-label">Dikirim / Dititipkan Ke</div>
        <div class="meta-value">{r['tempat']}</div>
      </div>
      <div>
        <div class="meta-label">Durasi Konsinyasi</div>
        <div class="meta-value">{r['durasi_bulan']} Bulan &mdash; s/d {jatuh_str}</div>
      </div>
      <div>
        <div class="meta-label">Komisi Toko</div>
        <div class="meta-value">{r['komisi_persen']}% ({_rupiah(komisi_nom)})</div>
      </div>
    </div>

    <!-- TABEL BARANG -->
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
      <tbody>
        <tr>
          <td>1</td>
          <td>{r['nama_produk']}</td>
          <td class="num">{r['qty_titip']} pcs</td>
          <td class="num">{_rupiah(r['harga_jual'])}</td>
          <td class="num">{_rupiah(nilai_total)}</td>
        </tr>
      </tbody>
    </table>

    <!-- TOTAL -->
    <div class="totals">
      <div class="total-row">
        <span>Total Nilai Titipan</span>
        <span>{_rupiah(nilai_total)}</span>
      </div>
      <div class="total-row">
        <span>Nilai Modal (HPP)</span>
        <span>{_rupiah(nilai_modal)}</span>
      </div>
      <div class="total-row">
        <span>Estimasi Komisi Toko</span>
        <span>{_rupiah(komisi_nom)}</span>
      </div>
    </div>

    {note_html}

    <!-- SYARAT KONSINYASI -->
    <div class="syarat">
      <strong>Syarat &amp; Ketentuan Konsinyasi:</strong><br>
      1. Barang yang tidak terjual wajib dikembalikan dalam kondisi baik sebelum <strong>{jatuh_str}</strong>.<br>
      2. Toko/konsinyee bertanggung jawab atas barang yang hilang atau rusak selama masa titipan.<br>
      3. Pembayaran hasil penjualan dilakukan selambatnya 7 hari setelah barang terjual.<br>
      4. Dokumen ini sah sebagai bukti serah terima barang.
    </div>

    <!-- TANDA TANGAN -->
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

    <!-- FOOTER -->
    <div class="footer">
      Dokumen ini sah sebagai bukti serah terima barang konsinyasi &bull; {BRAND_NAME}
    </div>
    """

    return HTMLResponse(_html_wrapper(f"Surat Jalan {consignment_id}", body))


# ════════════════════════════════════════════════════════════
# ENDPOINT — RIWAYAT CETAK
# ════════════════════════════════════════════════════════════

@router.get("/logs")
def get_print_logs(limit: int = 100) -> list[dict]:
    """
    Riwayat semua dokumen yang pernah dicetak.
    Setiap kali /nota atau /surat-jalan diakses, otomatis masuk ke sini.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM print_logs ORDER BY printed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id":         r["id"],
            "type":       r["type"],          # "nota" atau "surat_jalan"
            "refId":      r["ref_id"],         # order_id / consignment_id
            "refLabel":   r["ref_label"],      # nama customer / nama toko
            "printedAt":  r["printed_at"],
            "printedStr": r["printed_str"],    # format Bahasa Indonesia
        }
        for r in rows
    ]