import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PeriodResult } from '../models/api.model';
import { fmtInt } from '../models/format';

interface Guess {
  inflow: number | null;
  env: number | null;
  urban: number | null;
  agri: number | null;
  spill: number | null;
  end: number | null;
}

/**
 * 逐时段问答：每个时段先让学员回答
 *  - 水从哪里来：入流（以及期初库存）
 *  - 水到哪里去：蒸发、生态放水、城市/农业供水、弃水、期末库存
 * 提交后揭晓引擎结果并对照，要求能复述守恒关系。
 */
@Component({
  selector: 'app-period-quiz',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="card">
      <h2>② 逐时段问答：水从哪里来，到哪里去？</h2>
      <p class="muted">
        先自己估算本时段各水量（m³，缺测时段无法作答），再点“揭晓核对”。
        守恒关系：<b>期末 = 期初 + 入流 − 蒸发 − 生态放水 − 城市 − 农业 − 弃水</b>。
      </p>

      <div class="tabs">
        <button *ngFor="let p of periods; let i = index"
                [class.active]="i === step"
                (click)="go(i)">
          {{ i + 1 }}
          <span *ngIf="p.missing_data" class="badge gray">缺</span>
          <span *ngIf="!p.feasible && !p.missing_data" class="badge red">冲</span>
        </button>
      </div>

      <ng-container *ngIf="current as p">
        <div class="quiz-step" [class.good]="checked && ok" [class.bad]="checked && !ok">
          <h3 style="margin-top:0">
            {{ p.label ?? ('第' + (p.index + 1) + '时段') }}
            <span *ngIf="p.missing_data" class="badge gray">来水缺测</span>
            <span *ngIf="!p.feasible && !p.missing_data" class="badge red">硬条件冲突</span>
            <span *ngIf="(p.spill_m3 ?? 0) > 0" class="badge orange">有弃水</span>
          </h3>

          <div *ngIf="p.missing_data">
            <p>本时段来水缺测。教学要点：缺测不等于零来水——
              在没有来水数据时，本时段及之后的水量平衡<b>无法闭合</b>，
              期末库容只能标为“缺失”，不能当作 0 或沿用上一时段。</p>
            <div class="quiz-nav">
              <button class="secondary" [disabled]="step === 0" (click)="go(step - 1)">上一时段</button>
              <button [disabled]="step === periods.length - 1" (click)="go(step + 1)">下一时段</button>
            </div>
          </div>

          <div *ngIf="!p.missing_data">
            <p>
              已知条件（m³）：期初库容
              <b>{{ fmtInt(p.storage_start_m3) }}</b>，蒸发损失
              <b>{{ fmtInt(p.evaporation_m3) }}</b>，生态基流目标
              <b>{{ fmtInt(p.env_target_m3) }}</b>，城市需求
              <b>{{ fmtInt(p.urban_demand_m3) }}</b>，农业需求
              <b>{{ fmtInt(p.agriculture_demand_m3) }}</b>，库容上下限为硬条件。
            </p>

            <div class="row">
              <div>
                <label>水从哪里来：入流</label>
                <input type="number" [(ngModel)]="guess.inflow" [disabled]="checked">
              </div>
              <div>
                <label>到哪去：生态放水</label>
                <input type="number" [(ngModel)]="guess.env" [disabled]="checked">
              </div>
              <div>
                <label>到哪去：城市供水</label>
                <input type="number" [(ngModel)]="guess.urban" [disabled]="checked">
              </div>
              <div>
                <label>到哪去：农业供水</label>
                <input type="number" [(ngModel)]="guess.agri" [disabled]="checked">
              </div>
              <div>
                <label>到哪去：弃水</label>
                <input type="number" [(ngModel)]="guess.spill" [disabled]="checked">
              </div>
              <div>
                <label>期末库容</label>
                <input type="number" [(ngModel)]="guess.end" [disabled]="checked">
              </div>
            </div>

            <div class="quiz-nav">
              <button class="secondary" [disabled]="step === 0" (click)="go(step - 1)">上一时段</button>
              <button *ngIf="!checked" (click)="reveal()">揭晓核对</button>
              <button class="secondary" *ngIf="checked" (click)="resetGuess()">重新作答</button>
              <button *ngIf="checked && step < periods.length - 1" (click)="go(step + 1)">下一时段 →</button>
            </div>

            <div *ngIf="checked" style="margin-top:12px">
              <table>
                <thead>
                  <tr><th>项目</th><th>你的回答</th><th>引擎计算</th><th>偏差</th></tr>
                </thead>
                <tbody>
                  <tr *ngFor="let r of rows">
                    <td style="text-align:left">{{ r.label }}</td>
                    <td>{{ r.guess === null ? '未填' : fmtInt(r.guess) }}</td>
                    <td>{{ fmtInt(r.actual) }}</td>
                    <td [style.color]="r.guess !== null && close(r) ? 'var(--green)' : 'var(--red)'">
                      {{ r.guess === null ? '—' : (((r.guess - r.actual) > 0 ? '+' : '') + fmtInt(r.guess - r.actual)) }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p *ngIf="ok" style="color:var(--green); font-weight:600">✔ 全部答对，水量平衡闭合！</p>
              <p *ngIf="!ok" style="color:var(--red); font-weight:600">
                ✘ 存在偏差，请对照引擎结果想想：水是被库容上限“挤”成弃水，还是被死库容/生态基流“卡”住了？
              </p>
              <ul class="muted" *ngIf="p.warnings.length">
                <li *ngFor="let w of p.warnings">{{ w }}</li>
              </ul>
            </div>
          </div>
        </div>
      </ng-container>
    </div>
  `,
})
export class PeriodQuizComponent {
  @Input() periods: PeriodResult[] = [];

  step = 0;
  checked = false;
  tol = 100; // m³，容许手算误差
  guess: Guess = { inflow: null, env: null, urban: null, agri: null, spill: null, end: null };

  get current(): PeriodResult | undefined {
    return this.periods[this.step];
  }

  get rows(): { label: string; guess: number | null; actual: number }[] {
    const p = this.current!;
    return [
      { label: '入流', guess: this.guess.inflow, actual: p.inflow_m3! },
      { label: '生态放水', guess: this.guess.env, actual: p.env_release_m3! },
      { label: '城市供水', guess: this.guess.urban, actual: p.urban_supply_m3! },
      { label: '农业供水', guess: this.guess.agri, actual: p.agriculture_supply_m3! },
      { label: '弃水', guess: this.guess.spill, actual: p.spill_m3! },
      { label: '期末库容', guess: this.guess.end, actual: p.storage_end_m3! },
    ];
  }

  get ok(): boolean {
    return this.rows.every(
      (r) => r.guess !== null && Math.abs(r.guess - r.actual) <= this.tol
    );
  }

  go(i: number): void {
    this.step = i;
    this.resetGuess();
  }

  resetGuess(): void {
    this.checked = false;
    this.guess = { inflow: null, env: null, urban: null, agri: null, spill: null, end: null };
  }

  reveal(): void {
    this.checked = true;
  }

  close(r: { guess: number | null; actual: number }): boolean {
    return r.guess !== null && Math.abs(r.guess - r.actual) <= this.tol;
  }

  fmtInt = fmtInt;
}
