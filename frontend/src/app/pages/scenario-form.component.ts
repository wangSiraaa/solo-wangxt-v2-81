import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PriorityMode, ScenarioInput, SchemeInput } from '../models/api.model';
import { buildSampleScenario } from '../models/sample';

@Component({
  selector: 'app-scenario-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="card">
      <h2>① 场景与参数设置</h2>

      <div class="row">
        <div style="flex:2">
          <label>场景名称</label>
          <input [(ngModel)]="scenario.name">
        </div>
        <div>
          <label>时间步长（小时）</label>
          <input type="number" [(ngModel)]="scenario.timestep_hours">
        </div>
        <div>
          <label>水面面积 m²（蒸发为 mm 时用）</label>
          <input type="number" [(ngModel)]="surfaceArea">
        </div>
      </div>

      <h3>库容上下限与初始库容（硬条件，m³）</h3>
      <div class="row">
        <div>
          <label>死库容 S_min</label>
          <input type="number" [(ngModel)]="scenario.min_storage_m3">
        </div>
        <div>
          <label>正常蓄水位库容 S_max</label>
          <input type="number" [(ngModel)]="scenario.max_storage_m3">
        </div>
        <div>
          <label>初始库容 S₀</label>
          <input type="number" [(ngModel)]="scenario.initial_storage_m3">
        </div>
      </div>

      <h3>库容曲线（库容 m³, 水位 m，至少 2 点，须覆盖上下限）</h3>
      <div *ngFor="let p of scenario.level_curve; let i = index" class="row" style="margin-bottom:6px">
        <div><label>库容</label><input type="number" [(ngModel)]="p.storage_m3"></div>
        <div><label>水位</label><input type="number" [(ngModel)]="p.level_m"></div>
      </div>

      <h3>逐时段序列（固定时间步对齐；空单元格 = 缺测，按“缺失”处理而非 0）</h3>
      <p class="muted">
        来水单位：
        <select [(ngModel)]="scenario.inflow.unit" (ngModelChange)="onInflowUnit()">
          <option value="m3/s">m³/s（流量强度，×时长换算）</option>
          <option value="m3/d">m³/d</option>
          <option value="m3">m³（直接给时段体积）</option>
          <option value="10^4m3">万 m³</option>
          <option value="10^8m3">亿 m³</option>
        </select>
        蒸发单位：
        <select [(ngModel)]="scenario.evaporation!.unit">
          <option value="mm">mm（水深 × 水面面积）</option>
          <option value="cm">cm</option>
          <option value="m3">m³</option>
        </select>
      </p>

      <div style="overflow:auto">
        <table style="font-size:12px">
          <thead>
            <tr>
              <th>时段</th>
              <th>标签</th>
              <th>来水（{{ scenario.inflow.unit }}）</th>
              <th>蒸发（{{ scenario.evaporation!.unit }}）</th>
              <th>生态基流（{{ scenario.environmental_flow!.unit }}）</th>
              <th>城市用水需求（{{ scenario.schemes[0].urban_demand!.unit }}）</th>
              <th>农业用水需求（{{ scenario.schemes[0].agriculture_demand!.unit }}）</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let i of periodIndices">
              <td>{{ i + 1 }}</td>
              <td><input [(ngModel)]="scenario.labels[i]" style="min-width:70px"></td>
              <td><input type="number" [ngModel]="scenario.inflow.values[i]"
                         (ngModelChange)="setNum(scenario.inflow.values, i, $event)"></td>
              <td><input type="number" [ngModel]="scenario.evaporation!.values[i]"
                         (ngModelChange)="setNum(scenario.evaporation!.values, i, $event)"></td>
              <td><input type="number" [ngModel]="scenario.environmental_flow!.values[i]"
                         (ngModelChange)="setNum(scenario.environmental_flow!.values, i, $event)"></td>
              <td><input type="number" [ngModel]="scenario.schemes[0].urban_demand!.values[i]"
                         (ngModelChange)="setDemand('urban', i, $event)"></td>
              <td><input type="number" [ngModel]="scenario.schemes[0].agriculture_demand!.values[i]"
                         (ngModelChange)="setDemand('agriculture', i, $event)"></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="row" style="margin-top:8px">
        <button class="secondary" (click)="addPeriod()">+ 增加时段</button>
        <button class="secondary" (click)="removePeriod()">− 删除末时段</button>
      </div>

      <h3>两个供水方案（可比较）</h3>
      <div *ngFor="let s of scenario.schemes; let k = index" class="card" style="background:#f8fafc">
        <div class="row">
          <div style="flex:2"><label>方案 {{ k + 1 }} 名称</label><input [(ngModel)]="s.name"></div>
          <div>
            <label>两类用水优先级</label>
            <select [(ngModel)]="s.priority">
              <option [value]="'urban_first'">城市优先（农业先承担缺口）</option>
              <option [value]="'agriculture_first'">农业优先（城市先承担缺口）</option>
              <option [value]="'equal'">同优先级（按需求比例分摊）</option>
            </select>
          </div>
        </div>
        <p *ngIf="k === 1" class="muted" style="margin:6px 0 0">方案 2 的两类用水需求默认与方案 1 相同，仅优先级不同。</p>
      </div>
      <div class="row">
        <button class="secondary" (click)="toggleSecondScheme()">
          {{ scenario.schemes.length === 2 ? '只保留一个方案' : '添加第二个方案用于比较' }}
        </button>
        <button class="secondary" (click)="resetSample()">重置为教学样例</button>
      </div>

      <div style="margin-top:14px">
        <button (click)="run()">▶ 运行逐时段模拟</button>
        <button class="secondary" (click)="save()">保存场景到 PostgreSQL</button>
      </div>
    </div>
  `,
})
export class ScenarioFormComponent {
  @Output() runScenario = new EventEmitter<ScenarioInput>();
  @Output() saveScenario = new EventEmitter<ScenarioInput>();

  scenario: ScenarioInput = buildSampleScenario();
  surfaceArea = 1_000_000;
  envUnit = 'm3/s';
  demandUnit = 'm3/s';

  get periodIndices(): number[] {
    return this.scenario.inflow.values.map((_, i) => i);
  }

  onInflowUnit(): void {
    const u = this.scenario.inflow.unit;
    this.scenario.inflow.kind = u === 'm3/s' || u === 'm3/d' ? 'flow' : 'volume';
  }

  setNum(arr: (number | null)[], i: number, v: any): void {
    arr[i] = v === null || v === '' || v === undefined ? null : Number(v);
  }

  setDemand(kind: 'urban' | 'agriculture', i: number, v: any): void {
    const val = v === null || v === '' || v === undefined ? null : Number(v);
    this.scenario.schemes.forEach((s) => {
      const ts = kind === 'urban' ? s.urban_demand : s.agriculture_demand;
      if (ts) ts.values[i] = val;
    });
  }

  addPeriod(): void {
    const s = this.scenario;
    const i = s.inflow.values.length + 1;
    s.labels.push(`第${i}天`);
    s.inflow.values.push(null);
    s.evaporation?.values.push(0);
    s.environmental_flow?.values.push(0);
    s.schemes.forEach((sc) => {
      sc.urban_demand?.values.push(0);
      sc.agriculture_demand?.values.push(0);
    });
  }

  removePeriod(): void {
    const s = this.scenario;
    if (s.inflow.values.length <= 1) return;
    s.labels.pop();
    s.inflow.values.pop();
    s.evaporation?.values.pop();
    s.environmental_flow?.values.pop();
    s.schemes.forEach((sc) => {
      sc.urban_demand?.values.pop();
      sc.agriculture_demand?.values.pop();
    });
  }

  toggleSecondScheme(): void {
    if (this.scenario.schemes.length === 2) {
      this.scenario.schemes = [this.scenario.schemes[0]];
    } else {
      const src = this.scenario.schemes[0];
      const copy: SchemeInput = {
        name: '方案B：农业优先',
        priority: 'agriculture_first' as PriorityMode,
        urban_demand: src.urban_demand,
        agriculture_demand: src.agriculture_demand,
      };
      this.scenario.schemes.push(copy);
    }
  }

  resetSample(): void {
    this.scenario = buildSampleScenario();
    this.surfaceArea = 1_000_000;
    this.envUnit = 'm3/s';
    this.demandUnit = 'm3/s';
  }

  private _syncSurfaceArea(): void {
    if (this.scenario.evaporation) {
      this.scenario.evaporation.surface_area_m2 = this.surfaceArea;
    }
  }

  run(): void {
    this._syncSurfaceArea();
    this.runScenario.emit(structuredClone(this.scenario));
  }

  save(): void {
    this._syncSurfaceArea();
    this.saveScenario.emit(structuredClone(this.scenario));
  }
}
