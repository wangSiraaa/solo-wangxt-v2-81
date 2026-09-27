import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChartComponent, ChartSeries, ChartHLine } from './chart.component';
import { ScenarioIn, SimResult } from './models';
import { fmtNum, fmtVol } from './format';

/** 模拟结果：摘要、冲突时段、图表与逐时段水量平衡表。 */
@Component({
  selector: 'app-result-view',
  standalone: true,
  imports: [CommonModule, ChartComponent],
  template: `
    <ng-container *ngIf="result">
      <div class="card">
        <h2>结果摘要 —— {{ scenario?.name }}</h2>
        <div class="summary-cards">
          <div class="item"><div class="v">{{ fv(s.total_inflow_volume) }}</div><div class="k">总来水</div></div>
          <div class="item"><div class="v">{{ fv(s.total_evaporation_volume) }}</div><div class="k">总蒸发</div></div>
          <div class="item"><div class="v">{{ fv(s.total_eco_release_volume) }}</div><div class="k">生态下泄总量</div></div>
          <div class="item" *ngFor="let u of uses">
            <div class="v">{{ fv(s.total_deficit_volume[u]) }}</div>
            <div class="k">{{ u }} 总缺口</div>
          </div>
          <div class="item"><div class="v">{{ fv(s.total_spill_volume) }}</div><div class="k">总弃水</div></div>
          <div class="item"><div class="v">{{ s.missing_steps.length }}</div><div class="k">缺测时段数</div></div>
          <div class="item"><div class="v">{{ s.max_abs_balance_error.toExponential(2) }}</div>
            <div class="k">最大守恒残差 m³</div></div>
        </div>
      </div>

      <div class="card" *ngIf="s.conflict_steps.length; else noConflict">
        <h2>⚠ 不可行：硬条件冲突时段（{{ s.conflict_steps.length }} 个）</h2>
        <span class="badge" *ngFor="let c of s.conflict_steps">
          时段 {{ c.step }}：{{ c.message }}
        </span>
        <p class="hint">冲突表示该时段无法同时满足全部硬条件（最小生态流量 / 库容上下限），
          请调整需求、优先级或初始库容后重试。</p>
      </div>
      <ng-template #noConflict>
        <div class="card"><h2>✔ 硬条件全程满足，方案可行</h2></div>
      </ng-template>

      <div class="card">
        <h2>库容与水位</h2>
        <app-chart [series]="storageSeries" [hlines]="limitLines" ylabel="库容 m³"></app-chart>
        <app-chart [series]="levelSeries" ylabel="水位 m"></app-chart>
      </div>

      <div class="card">
        <h2>取水与需求</h2>
        <app-chart [series]="withdrawSeries" ylabel="流量 m³/s"></app-chart>
        <h2 style="margin-top:1rem">需求缺口</h2>
        <app-chart [series]="deficitSeries" ylabel="缺口 m³/s"></app-chart>
      </div>

      <div class="card">
        <h2>弃水与生态下泄</h2>
        <app-chart [series]="spillSeries" ylabel="流量 m³/s"></app-chart>
      </div>

      <div class="card">
        <h2>逐时段水量平衡表</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时段</th><th>入流 m³/s</th><th>蒸发 m³</th><th>生态 m³/s</th>
                <th *ngFor="let u of uses">{{ u }}取水</th>
                <th>弃水 m³/s</th><th>末库容 m³</th><th>水位 m</th>
                <th *ngFor="let u of uses">{{ u }}缺口</th>
                <th>守恒残差</th><th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let t of steps"
                  [class.conflict]="result.conflicts[t] !== null"
                  [class.missing]="result.missing_inflow[t]">
                <td>{{ t }}</td>
                <td>{{ fn(result.inflow[t]) }}</td>
                <td>{{ fn(result.evaporation_volume[t], 0) }}</td>
                <td>{{ fn(result.eco_release[t]) }}</td>
                <td *ngFor="let u of uses">{{ fn(result.withdrawals[u][t]) }}</td>
                <td>{{ fn(result.spill[t]) }}</td>
                <td>{{ fn(result.storage[t], 0) }}</td>
                <td>{{ fn(result.level[t], 2) }}</td>
                <td *ngFor="let u of uses">{{ fn(result.deficits[u][t]) }}</td>
                <td>{{ result.balance_error[t] === null ? '缺失' : result.balance_error[t]!.toExponential(1) }}</td>
                <td>
                  {{ result.missing_inflow[t] ? '入流缺测' : '' }}
                  {{ result.estimated_start[t] ? '起始库容为估计值' : '' }}
                  {{ result.conflicts[t] ? '冲突' : '' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </ng-container>
  `,
})
export class ResultViewComponent {
  @Input() result: SimResult | null = null;
  @Input() scenario: ScenarioIn | null = null;

  fv = fmtVol;
  fn = fmtNum;

  get s() { return this.result!.summary; }

  get uses(): string[] {
    return this.result ? this.result.priority : [];
  }

  get steps(): number[] {
    return this.result ? Array.from({ length: this.result.n_steps }, (_, i) => i) : [];
  }

  get storageSeries(): ChartSeries[] {
    return [{ label: '末库容', values: this.result!.storage, color: '#1565c0' }];
  }

  get limitLines(): ChartHLine[] {
    const r = this.result!;
    return [
      { value: r.storage_min, label: '下限', color: '#c62828' },
      { value: r.storage_max, label: '上限', color: '#2e7d32' },
    ];
  }

  get levelSeries(): ChartSeries[] {
    return [{ label: '水位', values: this.result!.level, color: '#00838f' }];
  }

  get withdrawSeries(): ChartSeries[] {
    const r = this.result!;
    const out: ChartSeries[] = [];
    const colors = ['#2e7d32', '#ef6c00'];
    const dashColors = ['#81c784', '#ffcc80'];
    this.uses.forEach((u, i) => {
      out.push({ label: `${u}取水`, values: r.withdrawals[u], color: colors[i % 2] });
      out.push({
        label: `${u}需求`, values: r.demands[u],
        color: dashColors[i % 2], dashed: true,
      });
    });
    return out;
  }

  get deficitSeries(): ChartSeries[] {
    const r = this.result!;
    const colors = ['#2e7d32', '#ef6c00'];
    return this.uses.map((u, i) => ({
      label: `${u}缺口`, values: r.deficits[u], color: colors[i % 2],
    }));
  }

  get spillSeries(): ChartSeries[] {
    const r = this.result!;
    return [
      { label: '弃水', values: r.spill, color: '#6a1b9a' },
      { label: '生态下泄', values: r.eco_release, color: '#00838f' },
    ];
  }
}
