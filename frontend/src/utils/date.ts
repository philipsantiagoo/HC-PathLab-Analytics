/**
 * Converte uma data vinda da API em Date.
 *
 * O banco guarda `timestamp without time zone` em UTC e o backend serializa
 * sem sufixo, ex. `2026-07-28T22:17:22`. O JavaScript interpreta string ISO
 * sem offset como horário LOCAL — num fuso UTC-3 isso joga a data 3 horas no
 * futuro e faz "assumido agora" virar `-1d`. Marcamos como UTC quando o
 * backend não informou offset; se um dia ele passar a informar, respeitamos.
 */
export function parseDataApi(valor: Date | string | null | undefined): Date | null {
  if (valor === null || valor === undefined) return null;
  if (valor instanceof Date) return Number.isNaN(valor.getTime()) ? null : valor;

  const texto = valor.trim();
  if (!texto) return null;
  const temOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(texto);
  // Só data (YYYY-MM-DD) já é tratada como UTC pelo próprio JS.
  const somenteData = /^\d{4}-\d{2}-\d{2}$/.test(texto);
  const d = new Date(temOffset || somenteData ? texto : `${texto}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Aceita Date ou string ISO — a API devolve datas como string. */
export function formatDateShort(data: Date | string | null | undefined = new Date()): string {
  const d = parseDataApi(data);
  if (!d) return '—';
  const dia = String(d.getDate()).padStart(2, '0');
  const mes = String(d.getMonth() + 1).padStart(2, '0');
  const ano = String(d.getFullYear()).slice(-2);
  return `${dia}/${mes}/${ano}`;
}
