/** 水量/流量的人性化格式化（教学展示用：万、亿） */
export function fmtVol(v: number | null | undefined): string {
  if (v === null || v === undefined) return '缺失';
  const a = Math.abs(v);
  if (a >= 1e8) return (v / 1e8).toFixed(3) + ' 亿m³';
  if (a >= 1e4) return (v / 1e4).toFixed(2) + ' 万m³';
  if (a >= 1) return v.toFixed(1) + ' m³';
  return v.toExponential(2) + ' m³';
}

export function fmtNum(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined) return '缺失';
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e6 || a < 1e-3)) return v.toExponential(2);
  return v.toFixed(digits);
}
