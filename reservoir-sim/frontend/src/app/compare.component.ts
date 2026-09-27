import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from './api.service';
import { ChartComponent, ChartSeries, ChartHLine } from './chart.component';
import { CompareResponse, ScenarioMeta } from './models';
import { fmtVol } from './format';

/** 方案对比：选择两个已保存场景，分别模拟并叠加比较。 */
@Component({
  selector: 'app-compare',
  standalone: true,
  imports: [CommonModule, FormsModule, ChartComponent],
  template: `
    <div class="card">
      <h2>选择两个方案</h2>
      <div class="grid">
        <div>
          <label>方案 A</label>
          <select [(ngModel)]="aId">
            <option *ngFor="let s of scenarios" [ngValue]="s.id">{{ s.name }}（#{{ s.id }}）</option>
          </select>
        </div>
        <div>
          <label>方案 B</label>
          <select [(ngModel)]="bId">
            <option *ngFor="let s of scenarios" [ngValue]="s.id">{{ s.name }}（#{{ s.id }}）</option>
          </select>
        </div>
      </div>
      <div class="actions">
        <button class="primary" (click)="run()" [disabled]="!aId || !bId || loading">
          {{ loading ? '计算中…' : '对比' }}
        </button>
        <button class="ghost" (click)="reload()">刷新场景列表</button>
      </div>
      <p class="hint" *ngIf="!scenarios.length">
        暂无已保存场景：请先在“场景设置”页保存至少两个方案（场景保存于 PostgreSQL）。
      </p>
      <p class="error" *ngIf="error">{{ error }}</p>
    </div>

    <ng-container *ngIf="cmp">
      <div class="card">
        <h2>指标差异（B − A）</h2>
        <table>
          <thead>
            <tr><th>指标</th><th>{{ cmp.a.name }}</th><th>{{ cmp.b.name }}</th><th>差值 B−A</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let u of uses">
              <td>{{ u }} 总缺口</td>
              <td>{{ fv(sa().total_deficit_volume[u]) }}</td>
              <td>{{ fv(sb().total_deficit_volume[u]) }}</td>
              <td>{{ fv(cmp.diff.total_deficit_volume[u]) }}</td>
            </tr>
            <tr>
              <td>总弃水</td>
              <td>{{ fv(sa().total_spill_volume) }}</td>
              <td>{{ fv(sb().total_spill_volume) }}</td>
              <td>{{ fv(cmp.diff.total_spill_volume) }}</td>
            </tr>
            <tr>
              <td>生态下泄总量</td>
              <td>{{ fv(sa().total_eco_release_volume) }}</td>
              <td>{{ fv(sb().total_eco_release_volume) }}</td>
              <td>{{ fv(cmp.diff.total_eco_release_volume) }}</td>
            </tr>
            <tr>
              <td>硬条件冲突时段数</td>
              <td>{{ cmp.diff.n_conflict_steps.a }}</td>
              <td>{{ cmp.diff.n_conflict_steps.b }}</td>
              <td>{{ cmp.diff.n_conflict_steps.b - cmp.diff.n_conflict_steps.a }}</td>
            </tr>
            <tr>
              <td>最低库容</td>
              <td>{{ fv(cmp.diff.min_storage.a) }}</td>
              <td>{{ fv(cmp.diff.min_storage.b) }}</td>
              <td>—</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h2>库容过程对比</h2>
        <app-chart [series]="storageCmp" [hlines]="limitLines" ylabel="库容 m³"></app-chart>
      </div>

      <div class="card" *ngFor="let u of uses">
        <h2>{{ u }} 缺口对比</h2>
        <app-chart [series]="deficitCmp(u)" ylabel="缺口 m³/s"></app-chart>
      </div>
    </ng-container>
  `,
})
export class CompareComponent implements OnInit {
  scenarios: ScenarioMeta[] = [];
  aId: number | null = null;
  bId: number | null = null;
  cmp: CompareResponse | null = null;
  loading = false;
  error = '';
  fv = fmtVol;

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.api.listScenarios().subscribe({
      next: (list) => {
        this.scenarios = list;
        if (list.length >= 2) {
          this.aId = this.aId ?? list[0].id;
          this.bId = this.bId ?? list[1].id;
        }
      },
      error: () => { this.error = '无法获取场景列表：请确认后端与数据库已启动。'; },
    });
  }

  run(): void {
    if (!this.aId || !this.bId) return;
    this.loading = true;
    this.error = '';
    this.api.compare(this.aId, this.bId).subscribe({
      next: (r) => { this.cmp = r; this.loading = false; },
      error: (e) => {
        this.error = e?.error?.detail ? JSON.stringify(e.error.detail) : '对比失败';
        this.loading = false;
      },
    });
  }

  sa() { return this.cmp!.a.result.summary; }
  sb() { return this.cmp!.b.result.summary; }

  get uses(): string[] {
    return this.cmp ? Object.keys(this.cmp.diff.total_deficit_volume) : [];
  }

  get storageCmp(): ChartSeries[] {
    return [
      { label: `A：${this.cmp!.a.name}`, values: this.cmp!.a.result.storage, color: '#1565c0' },
      { label: `B：${this.cmp!.b.name}`, values: this.cmp!.b.result.storage, color: '#2e7d32' },
    ];
  }

  get limitLines(): ChartHLine[] {
    const r = this.cmp!.a.result;
    return [
      { value: r.storage_min, label: '下限', color: '#c62828' },
      { value: r.storage_max, label: '上限', color: '#2e7d32' },
    ];
  }

  deficitCmp(u: string): ChartSeries[] {
    return [
      { label: `A：${this.cmp!.a.name}`, values: this.cmp!.a.result.deficits[u], color: '#1565c0' },
      { label: `B：${this.cmp!.b.name}`, values: this.cmp!.b.result.deficits[u], color: '#2e7d32' },
    ];
  }
}
