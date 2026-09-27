import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from './api.service';
import { ScenarioFormComponent } from './scenario-form.component';
import { ResultViewComponent } from './result-view.component';
import { CompareComponent } from './compare.component';
import { ScenarioIn, SimResult } from './models';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ScenarioFormComponent, ResultViewComponent, CompareComponent],
  template: `
    <header>
      <h1>水库供水教学模拟</h1>
      <span class="note">教学用途：不连接真实闸门，不替代现实供水决策</span>
    </header>
    <nav>
      <button [class.active]="tab === 'edit'" (click)="tab = 'edit'">① 场景设置</button>
      <button [class.active]="tab === 'result'" (click)="tab = 'result'"
              [disabled]="!result">② 模拟结果</button>
      <button [class.active]="tab === 'compare'" (click)="tab = 'compare'">③ 方案对比</button>
    </nav>
    <main>
      <p class="error" *ngIf="error">{{ error }}</p>
      <p class="hint" *ngIf="savedMsg">{{ savedMsg }}</p>

      <ng-container [ngSwitch]="tab">
        <div *ngSwitchCase="'edit'">
          <app-scenario-form (run)="onRun($event)" (save)="onSave($event)">
          </app-scenario-form>
        </div>
        <div *ngSwitchCase="'result'">
          <app-result-view [result]="result" [scenario]="scenario"></app-result-view>
        </div>
        <div *ngSwitchCase="'compare'">
          <app-compare></app-compare>
        </div>
      </ng-container>
    </main>
  `,
})
export class AppComponent {
  tab: 'edit' | 'result' | 'compare' = 'edit';
  scenario: ScenarioIn | null = null;
  result: SimResult | null = null;
  error = '';
  savedMsg = '';

  constructor(private api: ApiService) {}

  onRun(scn: ScenarioIn): void {
    this.error = '';
    this.savedMsg = '';
    this.api.simulate(scn).subscribe({
      next: (r) => {
        this.scenario = scn;
        this.result = r.result;
        this.tab = 'result';
      },
      error: (e) => { this.error = this.errText(e); },
    });
  }

  onSave(scn: ScenarioIn): void {
    this.error = '';
    this.api.saveScenario(scn).subscribe({
      next: (meta) => { this.savedMsg = `已保存场景「${meta.name}」（#${meta.id}），可到“方案对比”页使用。`; },
      error: (e) => { this.error = this.errText(e); },
    });
  }

  private errText(e: any): string {
    const d = e?.error?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) return d.map((x: any) => x.msg).join('\n');
    return '请求失败：请确认后端（http://localhost:8000）已启动。';
  }
}
