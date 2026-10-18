export const usd = (n, decimales = 2) =>
  `$${n.toLocaleString('es-VE', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })}`;

// Para ejes y etiquetas cortas: $12,4k
export const usdCompacto = (n) =>
  n >= 1000 ? `$${(n / 1000).toLocaleString('es-VE', { maximumFractionDigits: 1 })}k` : usd(n, 0);
