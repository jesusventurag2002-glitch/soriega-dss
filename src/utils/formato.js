export const usd = (n, decimales = 2) =>
  `$${n.toLocaleString('es-VE', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })}`;

// Para ejes y etiquetas cortas: $12,4k
export const usdCompacto = (n) =>
  n >= 1000 ? `$${(n / 1000).toLocaleString('es-VE', { maximumFractionDigits: 1 })}k` : usd(n, 0);

// "2026-10-16" -> Date local (new Date('2026-10-16') sería medianoche UTC y en Venezuela caería el día anterior)
export const fechaLocal = (iso) => {
  const [a, m, d] = iso.split('-').map(Number);
  return new Date(a, m - 1, d);
};

export const nombreMes = (mes, ano) => {
  const texto = new Date(ano, mes - 1, 1).toLocaleDateString('es-VE', { month: 'long', year: 'numeric' });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
};

// "BROTCARSERVICE" -> "Brotcarservice"
export const capitalizar = (s) => s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
