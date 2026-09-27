import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from './services/api.service';
import {
  ScenarioInput,
  ScenarioMeta,
  SimulationResponse,
} from './models/api.model';
import { ScenarioFormComponent } from './pages/scenario-form.component';
import { PeriodQuizComponent } from './pages/period-quiz.component';
import { PeriodTableComponent } from './pages/period-table.component';
import { SchemeCompareComponent } from './pages/scheme-compare.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ScenarioFormComponent,
    PeriodQuizComponent,
    PeriodTableComponent,
    SchemeCompareComponent,
  ],
  template: `
    <div class="layout">
      <h1>水库水量平衡教学模拟系统</h1>
      <p class="muted">
        FastAPI + SciPy 固定时间步演算 ｜ Angular 展示库容、取水与需求缺口 ｜ PostgreSQL 保存场景
      </p>
      <div class="disclaimer">
        ⚠️ 本系统仅用于教学模拟：不连接真实闸门，演算结果不替代现实供水调度决策。
      </div>

      <div class="card">
        <div class="row" style="align-items:flex-end">
          <div style="flex:2">
            <label>已保存场景（PostgreSQL）</label>
            <select [(ngModel)]="selectedSavedId">
              <option [ngValue]="null">— 选择已保存场景 —</option>
              <option *ngFor="let s of saved" [ngValue]="s.id">
                #{{ s.id }} {{ s.name }}（{{ s.created_at.slice(0, 16) }}）
              </option>
            </select>
          </div>
          <div>
            <button class="secondary" [disabled]="selectedSavedId === null" (click)="loadSelected()">载入并模拟</button>
            <button class="secondary" [disabled]="selectedSavedId === null" (click)="deleteSelected()">删除</button>
            <button class="secondary" (click)="refreshSaved()">刷新列表</button>
          </div>
        </div>
        <div *ngIf="saveMsg" class="muted" style="margin-top:8px">{{ saveMsg }}</div>
      </div>

      <app-scenario-form (runScenario)="onRun($event)" (saveScenario)="onSave($event)"></app-scenario-form>

      <div *ngIf="error" class="error-box">{{ error }}</div>

      <ng-container *ngIf="result">
        <div class="card" *ngIf="result.conflicts.length">
          <h2 style="color:var(--red)">⚠ 找不到可行方案：以下时段存在硬条件冲突</h2>
          <p class="muted">
            “可行”要求同时满足：期末库容 ≥ 死库容、≤ 正常蓄水位库容，且下泄不低于生态基流。
            下列时段即使两类用水<b>完全不取水</b>也无法满足，说明需要调整来水预报、
            生态基流指标、库容参数或前期调度。
          </p>
          <table>
            <thead><tr><th>冲突时段</th><th>原因</th><th>所需净入流(m³)</th><th>实际净入流(m³)</th></tr></thead>
            <tbody>
              <tr *ngFor="let c of result.conflicts" class="conflict">
                <td>{{ c.label ?? ('第' + (c.index + 1) + '时段') }}</td>
                <td style="text-align:left">{{ c.reason }}</td>
                <td>{{ c.required_m3 === null ? '—' : c.required_m3.toLocaleString() }}</td>
                <td>{{ c.available_m3 === null ? '—' : c.available_m3.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card" *ngIf="result.schemes.length > 1">
          <h2>选择查看的方案</h2>
          <div class="tabs">
            <button *ngFor="let s of result.schemes; let i = index"
                    [class.active]="schemeIndex === i"
                    (click)="schemeIndex = i">
              {{ s.summary.name }}
              <span *ngIf="s.summary.infeasible_periods.length" class="badge red">
                {{ s.summary.infeasible_periods.length }} 个冲突时段
              </span>
            </button>
          </div>
        </div>

        <ng-container *ngIf="activeScheme as sch">
          <app-period-quiz [periods]="sch.periods"></app-period-quiz>
          <app-period-table [scheme]="sch"></app-period-table>
        </ng-container>

        <app-scheme-compare [schemes]="result.schemes"></app-scheme-compare>
      </ng-container>
    </div>
  `,
})
export class AppComponent implements OnInit {
  result: SimulationResponse | null = null;
  error = '';
  saved: ScenarioMeta[] = [];
  selectedSavedId: number | null = null;
  saveMsg = '';
  schemeIndex = 0;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.refreshSaved();
  }

  get activeScheme() {
    return this.result?.schemes[this.schemeIndex];
  }

  onRun(scenario: ScenarioInput): void {
    this.error = '';
    this.result = null;
    this.api.simulate(scenario).subscribe({
      next: (r) => {
        this.result = r;
        this.schemeIndex = 0;
      },
      error: (e) => this.handleError(e),
    });
  }

  onSave(scenario: ScenarioInput): void {
    this.error = '';
    this.api.saveScenario(scenario).subscribe({
      next: (m) => {
        this.saveMsg = `已保存：#${m.id} ${m.name}`;
        this.refreshSaved();
      },
      error: (e) => this.handleError(e),
    });
  }

  refreshSaved(): void {
    this.api.listScenarios().subscribe({
      next: (list) => (this.saved = list),
      error: () => (this.saved = []),
    });
  }

  loadSelected(): void {
    if (this.selectedSavedId === null) return;
    this.api.simulateSaved(this.selectedSavedId).subscribe({
      next: (r) => {
        this.result = r;
        this.schemeIndex = 0;
        this.error = '';
      },
      error: (e) => this.handleError(e),
    });
  }

  deleteSelected(): void {
    if (this.selectedSavedId === null) return;
    this.api.deleteScenario(this.selectedSavedId).subscribe({
      next: () => {
        this.saveMsg = `已删除 #${this.selectedSavedId}`;
        this.selectedSavedId = null;
        this.refreshSaved();
      },
      error: (e) => this.handleError(e),
    });
  }

  private handleError(e: any): void {
    const detail = e?.error?.detail;
    this.error = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: any) => d.msg).join('\n')
        : '请求失败，请检查后端服务与输入参数。';
  }
}
