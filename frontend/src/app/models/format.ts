/** 数字格式化工具。体积较大时用 万m³ / 亿m³ 显示。 */

export function fmtVolume(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '缺失';
  const abs = Math.abs(v);
  if (abs >= 1e8) return (v / 1e8).toFixed(digits) + ' 亿m³';
  if (abs >= 1e4) return (v / 1e4).toFixed(digits) + ' 万m³';
  return v.toFixed(0) + ' m³';
}

export function fmtLevel(v: number | null | undefined): string {
  if (v === null || v === undefined) return '缺失';
  return v.toFixed(2) + ' m';
}

export function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return Math.round(v).toLocaleString('zh-CN');
}

export const PRIORITY_LABELS: Record<string, string> = {
  urban_first: '城市优先',
  agriculture_first: '农业优先',
  equal: '同优先级（按需求比例分摊）',
};
