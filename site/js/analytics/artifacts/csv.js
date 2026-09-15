/* Spreadsheets. CSV by hand, XLSX through SheetJS.
 *
 * Both take the same shape as everything else on this page: a list of column
 * descriptors and a list of rows. The file that comes out is the table that was
 * on screen, in the order it was on screen, with the numbers unrounded — a
 * spreadsheet is the one place where "69.9K" is the wrong answer. */

/* Pinned exactly, from cdnjs, with an integrity hash. Loaded on demand: it is
   880 KB and most sessions never export anything. */
const SHEETJS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
const SHEETJS_SRI = 'sha384-vtjasyidUo0kW94K5MXDXntzOJpQgBKXmE7e2Ga4LG0skTTLeBi97eFAXsqewJjw';

/**
 * The raw value for a cell.
 *
 * `export` uses `c.raw` where a column has one, falling back to the display
 * value. Columns that format for the screen (compact numbers, percentages,
 * dates) give the sheet the underlying number instead, because a spreadsheet is
 * for arithmetic and "6.5%" is a string.
 */
function cellValue(column, row) {
  if (column.raw) return column.raw(row);
  if (column.value) {
    const v = column.value(row);
    return v instanceof Node ? v.textContent : v;
  }
  return row[column.key];
}

function cellText(value) {
  if (value == null) return '';
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

/**
 * RFC 4180: quote anything containing a comma, a quote, or a newline, and
 * double the quotes inside. Instagram captions contain all three.
 */
function escapeCsv(text) {
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * CSV as a string.
 *
 * CRLF line endings and a UTF-8 BOM, both for Excel: without the BOM it opens a
 * Thai caption as mojibake, and it is the export people open in Excel.
 */
export function toCsv(columns, rows, { bom = true } = {}) {
  const lines = [columns.map((c) => escapeCsv(c.name)).join(',')];
  for (const row of rows) {
    lines.push(columns.map((c) => escapeCsv(cellText(cellValue(c, row)))).join(','));
  }
  return (bom ? '﻿' : '') + lines.join('\r\n') + '\r\n';
}

/** Hand the browser a file. The only download path in the dashboard. */
export function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  /* Revoked on the next tick rather than immediately: Safari has not always
     finished reading the object URL when click() returns. */
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadCsv(columns, rows, filename) {
  download(new Blob([toCsv(columns, rows)], { type: 'text/csv;charset=utf-8' }), filename);
}

let sheetjs = null;

/** Load SheetJS once, on demand. Rejects with a sentence, not a stack. */
export function loadSheetJs() {
  if (globalThis.XLSX) return Promise.resolve(globalThis.XLSX);
  if (sheetjs) return sheetjs;
  sheetjs = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SHEETJS_URL;
    script.integrity = SHEETJS_SRI;
    script.crossOrigin = 'anonymous';
    script.referrerPolicy = 'no-referrer';
    script.onload = () => (globalThis.XLSX
      ? resolve(globalThis.XLSX)
      : reject(new Error('The spreadsheet library loaded but did not register itself.')));
    script.onerror = () => {
      sheetjs = null;
      reject(new Error('Could not load the spreadsheet library. '
        + 'CSV still works; XLSX needs the network.'));
    };
    document.head.appendChild(script);
  });
  return sheetjs;
}

/** Excel refuses sheet names over 31 characters or containing : \ / ? * [ ] */
export function sheetName(name) {
  return String(name).replace(/[:\\/?*[\]]/g, ' ').slice(0, 31).trim() || 'Sheet1';
}

/**
 * An XLSX workbook, one sheet per entry.
 *
 * @param {Array<{name: string, columns: Array, rows: Array}>} sheets
 */
export async function downloadXlsx(sheets, filename) {
  const XLSX = await loadSheetJs();
  const book = XLSX.utils.book_new();
  for (const sheet of sheets) {
    const aoa = [sheet.columns.map((c) => c.name)];
    for (const row of sheet.rows) {
      aoa.push(sheet.columns.map((c) => {
        const v = cellValue(c, row);
        /* Numbers stay numbers and dates stay dates. A sheet of strings that
           look like numbers is a sheet nobody can sum. */
        if (v == null) return '';
        if (v instanceof Date) return v;
        return typeof v === 'number' && Number.isFinite(v) ? v : cellText(v);
      }));
    }
    const ws = XLSX.utils.aoa_to_sheet(aoa, { cellDates: true });
    XLSX.utils.book_append_sheet(book, ws, sheetName(sheet.name));
  }
  const out = XLSX.write(book, { bookType: 'xlsx', type: 'array' });
  download(new Blob([out], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  }), filename);
}
