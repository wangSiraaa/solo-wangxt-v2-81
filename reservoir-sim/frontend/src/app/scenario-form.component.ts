import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ScenarioIn } from './models';

/** 场景编辑：参数、库容曲线、时间序列（CSV 粘贴）、单位与用水优先级。 */
@Component({
  selector: 'app-scenario-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="card">
      <h2>基本参数</h2>
      <div class="grid">
        <div><label>场景名称</label><input [(ngModel)]="name"></div>
        <div><label>时间步长 Δt（秒）</label><input type="number" [(ngModel)]="dt"></div>
        <div><label>库容下限（{{ uVol }}）</label><input type="number" [(ngModel)]="sMin"></div>
        <div><label>库容上限（{{ uVol }}）</label><input type="number" [(ngModel)]="sMax"></div>
        <div><label>初始库容（{{ uVol }}）</label><input type="number" [(ngModel)]="sInit"></div>
        <div><label>最小生态流量（{{ uFlow }}）</label><input type="number" [(ngModel)]="eco"></div>
      </div>
      <div class="grid" style="margin-top:0.7rem">
        <div>
          <label>流量单位</label>
          <select [(ngModel)]="uFlow">
            <option>m3/s</option><option>L/s</option>
            <option>m3/h</option><option>万m3/d</option>
          </select>
        </div>
        <div>
          <label>库容单位</label>
          <select [(ngModel)]="uVol">
            <option>m3</option><option>万m3</option><option>百万m3</option>
          </select>
        </div>
        <div>
          <label>蒸发单位</label>
          <select [(ngModel)]="uEvap">
            <option>mm/step</option><option>mm/d</option>
          </select>
        </div>
      </div>
      <p class="hint">库容上下限与最小生态流量为硬条件；初始库容必须位于上下限之间。</p>
    </div>

    <div class="card">
      <h2>库容曲线（水位按此曲线由库容换算）</h2>
      <textarea rows="4" [(ngModel)]="curveText"
        placeholder="每行：库容,水位(m),水面面积(m²) —— 库容须严格递增"></textarea>
      <p class="hint">每行三个数：库容（{{ uVol }}）、水位 m、水面面积 m²，用逗号分隔。</p>
    </div>

    <div class="card">
      <h2>两类用水与优先级</h2>
      <div class="grid">
        <div><label>用水 1 名称</label><input [(ngModel)]="use1"></div>
        <div><label>用水 2 名称</label><input [(ngModel)]="use2"></div>
        <div>
          <label>优先保障</label>
          <select [(ngModel)]="priorityFirst">
            <option [value]="use1">{{ use1 }}</option>
            <option [value]="use2">{{ use2 }}</option>
          </select>
        </div>
      </div>
      <p class="hint">水量不足时，优先保障的用水先被满足，另一类承担缺口。</p>
    </div>

    <div class="card">
      <h2>时间序列（每行一个时段）</h2>
      <textarea rows="8" [(ngModel)]="seriesText"
        placeholder="入流,蒸发,需求1,需求2 —— 入流留空表示缺测"></textarea>
      <p class="hint">
        列顺序：入流（{{ uFlow }}，留空=缺测）、蒸发（{{ uEvap }}）、
        {{ use1 }}需求（{{ uFlow }}）、{{ use2 }}需求（{{ uFlow }}）。
        缺测来水在结果中显示为“缺失”，不会按 0 处理。
      </p>
      <div class="actions">
        <button class="primary" (click)="emit(run)">运行模拟</button>
        <button class="ghost" (click)="emit(save)">保存场景</button>
        <button class="ghost" (click)="loadSample()">载入示例（洪峰+干旱+缺测）</button>
      </div>
      <p class="error" *ngIf="parseError">{{ parseError }}</p>
    </div>
  `,
})
export class ScenarioFormComponent {
  @Output() run = new EventEmitter<ScenarioIn>();
  @Output() save = new EventEmitter<ScenarioIn>();

  name = '教学示例';
  dt = 86400;
  sMin = 5e6; sMax = 5e7; sInit = 2e7;
  eco = 8;
  uFlow = 'm3/s'; uVol = 'm3'; uEvap = 'mm/d';
  use1 = '城乡供水'; use2 = '农业灌溉';
  priorityFirst = this.use1;
  curveText = '';
  seriesText = '';
  parseError = '';

  constructor() { this.loadSample(); }

  emit(target: EventEmitter<ScenarioIn>): void {
    try {
      this.parseError = '';
      target.emit(this.build());
    } catch (e) {
      this.parseError = (e as Error).message;
    }
  }

  build(): ScenarioIn {
    const curve = this.parseCurve();
    const series = this.parseSeries();
    const other = this.priorityFirst === this.use1 ? this.use2 : this.use1;
    return {
      name: this.name || '未命名场景',
      description: '',
      dt_seconds: this.dt,
      storage_min: this.sMin,
      storage_max: this.sMax,
      storage_initial: this.sInit,
      eco_flow: this.eco,
      priority: [this.priorityFirst, other],
      demands: { [this.use1]: series.dem1, [this.use2]: series.dem2 },
      inflow: series.inflow,
      evaporation: series.evap,
      curve,
      units: { flow: this.uFlow, volume: this.uVol, evaporation: this.uEvap },
    };
  }

  private parseCurve() {
    const rows = this.rows(this.curveText);
    if (rows.length < 2) throw new Error('库容曲线至少需要两行');
    const storage: number[] = [], level: number[] = [], area: number[] = [];
    rows.forEach((cols, i) => {
      if (cols.length !== 3) throw new Error(`库容曲线第 ${i + 1} 行应有 3 列`);
      const [s, l, a] = cols.map((c) => this.num(c, `库容曲线第 ${i + 1} 行`));
      storage.push(s); level.push(l); area.push(a);
    });
    return { storage, level, area };
  }

  private parseSeries() {
    const rows = this.rows(this.seriesText);
    if (!rows.length) throw new Error('时间序列不能为空');
    const inflow: (number | null)[] = [], evap: number[] = [],
      dem1: number[] = [], dem2: number[] = [];
    rows.forEach((cols, i) => {
      if (cols.length !== 4) throw new Error(`时间序列第 ${i + 1} 行应有 4 列`);
      const where = `时间序列第 ${i + 1} 行`;
      inflow.push(cols[0].trim() === '' ? null : this.num(cols[0], where));
      evap.push(this.num(cols[1], where));
      dem1.push(this.num(cols[2], where));
      dem2.push(this.num(cols[3], where));
    });
    return { inflow, evap, dem1, dem2 };
  }

  private rows(text: string): string[][] {
    return text.split('\n')
      .map((l) => l.trim())
      .filter((l) => l.length > 0)
      .map((l) => l.split(/[,\t;]/));
  }

  private num(s: string, where: string): number {
    const v = Number(s);
    if (!Number.isFinite(v)) throw new Error(`${where}：“${s}”不是数字`);
    return v;
  }

  /** 示例：前期洪峰（弃水）→ 后期干旱（缺口与冲突）→ 中段一个缺测点 */
  loadSample(): void {
    this.curveText = [
      '0,100,0',
      '5000000,110,800000',
      '20000000,120,1500000',
      '50000000,135,2500000',
    ].join('\n');
    const lines: string[] = [];
    for (let d = 0; d < 30; d++) {
      let inflow: string;
      if (d === 15) inflow = '';                       // 缺测
      else if (d >= 5 && d <= 7) inflow = '400';       // 洪峰
      else if (d >= 8) inflow = '5';                   // 干旱
      else inflow = '30';
      lines.push(`${inflow},5,15,25`);
    }
    this.seriesText = lines.join('\n');
  }
}
