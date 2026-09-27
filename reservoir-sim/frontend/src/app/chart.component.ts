import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface ChartSeries {
  label: string;
  values: (number | null)[];
  color: string;
  dashed?: boolean;
}

export interface ChartHLine {
  value: number;
  label: string;
  color: string;
}

/** 轻量 SVG 折线图：null 值（缺测）显示为断线，不补零。 */
@Component({
  selector: 'app-chart',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="chart-scroll">
      <svg [attr.width]="width" [attr.height]="height" role="img">
        <!-- 水平参考线（如库容上下限） -->
        <g *ngFor="let h of hlines">
          <line [attr.x1]="padL" [attr.x2]="width - padR"
                [attr.y1]="y(h.value)" [attr.y2]="y(h.value)"
                [attr.stroke]="h.color" stroke-dasharray="5,4" stroke-width="1.2" />
          <text [attr.x]="width - padR + 2" [attr.y]="y(h.value) + 3"
                font-size="9" [attr.fill]="h.color">{{ h.label }}</text>
        </g>
        <!-- 坐标轴 -->
        <line [attr.x1]="padL" [attr.y1]="height - padB" [attr.x2]="width - padR"
              [attr.y2]="height - padB" stroke="#90a4ae" stroke-width="1" />
        <line [attr.x1]="padL" [attr.y1]="padT" [attr.x2]="padL"
              [attr.y2]="height - padB" stroke="#90a4ae" stroke-width="1" />
        <text *ngFor="let t of yTicks" [attr.x]="padL - 4" [attr.y]="y(t) + 3"
              font-size="9" text-anchor="end" fill="#78909c">{{ fmt(t) }}</text>
        <text *ngFor="let t of xTicks" [attr.x]="x(t)" [attr.y]="height - padB + 12"
              font-size="9" text-anchor="middle" fill="#78909c">{{ t }}</text>
        <text [attr.x]="padL" [attr.y]="padT - 4" font-size="10" fill="#546e7a">{{ ylabel }}</text>
        <!-- 数据线 -->
        <path *ngFor="let s of series" [attr.d]="path(s.values)" fill="none"
              [attr.stroke]="s.color" stroke-width="1.6"
              [attr.stroke-dasharray]="s.dashed ? '4,3' : null" />
        <!-- 缺测点标记 -->
        <g *ngFor="let s of series">
          <circle *ngFor="let i of missingIdx(s.values)" [attr.cx]="x(i)"
                  [attr.cy]="height - padB" r="2.5" fill="#ef6c00">
            <title>时段 {{ i }}：缺测</title>
          </circle>
        </g>
      </svg>
      <div class="legend">
        <span *ngFor="let s of series"><i [style.background]="s.color"></i>{{ s.label }}</span>
        <span *ngFor="let h of hlines"><i [style.background]="h.color"></i>{{ h.label }}</span>
      </div>
    </div>
  `,
})
export class ChartComponent {
  @Input() series: ChartSeries[] = [];
  @Input() hlines: ChartHLine[] = [];
  @Input() ylabel = '';
  @Input() width = 640;
  @Input() height = 240;

  padL = 56; padR = 46; padT = 16; padB = 22;

  get allValues(): number[] {
    const vs: number[] = [];
    for (const s of this.series) {
      for (const v of s.values) if (v !== null) vs.push(v);
    }
    for (const h of this.hlines) vs.push(h.value);
    return vs;
  }

  get yMin(): number { const v = this.allValues; return v.length ? Math.min(...v) : 0; }
  get yMax(): number { const v = this.allValues; return v.length ? Math.max(...v) : 1; }
  get n(): number { return this.series.length ? this.series[0].values.length : 0; }

  x(i: number): number {
    const span = Math.max(this.n - 1, 1);
    return this.padL + (i / span) * (this.width - this.padL - this.padR);
  }

  y(v: number): number {
    const lo = this.yMin, hi = this.yMax;
    const pad = (hi - lo) * 0.08 || 1;
    const t = (v - (lo - pad)) / ((hi + pad) - (lo - pad));
    return this.padT + (1 - t) * (this.height - this.padT - this.padB);
  }

  get yTicks(): number[] {
    const lo = this.yMin, hi = this.yMax;
    const out: number[] = [];
    for (let k = 0; k <= 4; k++) out.push(lo + (k / 4) * (hi - lo));
    return out;
  }

  get xTicks(): number[] {
    const n = this.n;
    if (n <= 1) return [0];
    const step = Math.max(1, Math.round((n - 1) / 4));
    const out: number[] = [];
    for (let i = 0; i < n; i += step) out.push(i);
    if (out[out.length - 1] !== n - 1) out.push(n - 1);
    return out;
  }

  /** 生成折线路径；遇 null（缺测）断开，绝不用 0 代替。 */
  path(values: (number | null)[]): string {
    let d = '';
    let pen = false;
    values.forEach((v, i) => {
      if (v === null) { pen = false; return; }
      d += (pen ? 'L' : 'M') + this.x(i).toFixed(1) + ',' + this.y(v).toFixed(1);
      pen = true;
    });
    return d;
  }

  missingIdx(values: (number | null)[]): number[] {
    const out: number[] = [];
    values.forEach((v, i) => { if (v === null) out.push(i); });
    return out;
  }

  fmt(v: number): string {
    const a = Math.abs(v);
    if (a >= 1e8) return (v / 1e8).toFixed(2) + '亿';
    if (a >= 1e4) return (v / 1e4).toFixed(1) + '万';
    if (a >= 100) return v.toFixed(0);
    if (a >= 1) return v.toFixed(1);
    return v.toPrecision(2);
  }
}
