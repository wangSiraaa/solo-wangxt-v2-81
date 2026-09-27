import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SchemeResult } from '../models/api.model';
import { PRIORITY_LABELS, fmtVolume } from '../models/format';

@Component({
  selector: 'app-scheme-compare',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="card" *ngIf="schemes.length === 2">
      <h2>④ 两个供水方案比较</h2>
      <table>
        <thead>
          <tr>
            <th>指标</th>
            <th>{{ schemes[0].summary.name }}</th>
            <th>{{ schemes[1].summary.name }}</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>优先级设置</td>
            <td>{{ PRIORITY_LABELS[schemes[0].summary.priority] }}</td>
            <td>{{ PRIORITY_LABELS[schemes[1].summary.priority] }}</td>
          </tr>
          <tr *ngFor="let r of rows">
            <td>{{ r.label }}</td>
            <td [class.win]="r.better === 0">{{ fmt(r.a) }}</td>
            <td [class.win]="r.better === 1">{{ fmt(r.b) }}</td>
          </tr>
          <tr>
            <td>不可行（冲突）时段</td>
            <td [class.bad]="schemes[0].summary.infeasible_periods.length">
              {{ schemes[0].summary.infeasible_periods.length ? indexList(schemes[0].summary.infeasible_periods) : '无' }}
            </td>
            <td [class.bad]="schemes[1].summary.infeasible_periods.length">
              {{ schemes[1].summary.infeasible_periods.length ? indexList(schemes[1].summary.infeasible_periods) : '无' }}
            </td>
          </tr>
          <tr>
            <td>缺测时段</td>
            <td>{{ schemes[0].summary.missing_periods.length ? indexList(schemes[0].summary.missing_periods) : '无' }}</td>
            <td>{{ schemes[1].summary.missing_periods.length ? indexList(schemes[1].summary.missing_periods) : '无' }}</td>
          </tr>
        </tbody>
      </table>

      <p class="muted" style="margin-top:8px">
        教学提示：在总水量相同的时段，优先级只改变“缺口由谁承担”，不改变总供水量；
        若提前供水会导致后续时段触及死库容，则系统会在逐时段表中标注。
      </p>
    </div>
  `,
  styles: [
    `td.win { background: #f0fdf4; font-weight: 600; } td.bad { color: var(--red); }`,
  ],
})
export class SchemeCompareComponent {
  @Input() schemes: SchemeResult[] = [];

  PRIORITY_LABELS = PRIORITY_LABELS;
  fmt = (v: number | null) => fmtVolume(v);

  get rows(): { label: string; a: number | null; b: number | null; better?: 0 | 1 }[] {
    const a = this.schemes[0].summary;
    const b = this.schemes[1].summary;
    const cmp = (x: number | null, y: number | null, higher: boolean): 0 | 1 | undefined => {
      if (x === null || y === null || Math.abs(x - y) < 1e-6) return undefined;
      return (x > y) === higher ? 0 : 1;
    };
    return [
      { label: '城市供水合计', a: a.total_urban_supply_m3, b: b.total_urban_supply_m3, better: cmp(a.total_urban_supply_m3, b.total_urban_supply_m3, true) },
      { label: '农业供水合计', a: a.total_ag_supply_m3, b: b.total_ag_supply_m3, better: cmp(a.total_ag_supply_m3, b.total_ag_supply_m3, true) },
      { label: '总需求缺口（越少越好）', a: a.total_shortage_m3, b: b.total_shortage_m3, better: cmp(a.total_shortage_m3, b.total_shortage_m3, false) },
      { label: '总弃水', a: a.total_spill_m3, b: b.total_spill_m3 },
      { label: '生态泄放合计', a: a.total_env_release_m3, b: b.total_env_release_m3 },
      { label: '期末库容', a: a.final_storage_m3, b: b.final_storage_m3 },
    ];
  }

  indexList(idxs: number[]): string {
    return idxs.map((i) => `第${i + 1}时段`).join('、');
  }
}
