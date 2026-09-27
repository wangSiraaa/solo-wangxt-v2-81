import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chart, registerables } from 'chart.js';
import { SchemeResult } from '../models/api.model';
import { fmtInt, fmtLevel, fmtVolume } from '../models/format';

Chart.register(...registerables);

@Component({
  selector: 'app-period-table',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="card">
      <h2>
        ③ 逐时段水量平衡
        <span class="badge green">{{ scheme.summary.name }}</span>
      </h2>

      <div class="stat-grid" style="margin-bottom:12px">
        <div class="stat"><div class="k">总入流</div><div class="v">{{ fmtVol(scheme.summary.total_inflow_m3) }}</div></div>
        <div class="stat"><div class="k">总蒸发</div><div class="v">{{ fmtVol(scheme.summary.total_evap_m3) }}</div></div>
        <div class="stat"><div class="k">生态泄放合计</div><div class="v">{{ fmtVol(scheme.summary.total_env_release_m3) }}</div></div>
        <div class="stat"><div class="k">城市供水合计</div><div class="v">{{ fmtVol(scheme.summary.total_urban_supply_m3) }}</div></div>
        <div class="stat"><div class="k">农业供水合计</div><div class="v">{{ fmtVol(scheme.summary.total_ag_supply_m3) }}</div></div>
        <div class="stat"><div class="k">总弃水</div><div class="v" style="color:var(--orange)">{{ fmtVol(scheme.summary.total_spill_m3) }}</div></div>
        <div class="stat"><div class="k">总需求缺口</div><div class="v" style="color:var(--red)">{{ fmtVol(scheme.summary.total_shortage_m3) }}</div></div>
        <div class="stat"><div class="k">期末库容 / 最高水位</div>
          <div class="v">{{ fmtVol(scheme.summary.final_storage_m3) }} / {{ fmtLvl(scheme.summary.max_level_m) }}</div>
        </div>
      </div>

      <h3>库容与水位过程</h3>
      <div class="chart-box"><canvas #storageChart></canvas></div>
      <h3>取水与需求缺口</h3>
      <div class="chart-box"><canvas #supplyChart></canvas></div>

      <h3>逐时段明细表（单位 m³；残差应恒为 0）</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时段</th>
              <th>期初库容</th>
              <th>入流</th>
              <th>蒸发</th>
              <th>生态放水<br><small>(目标/实际)</small></th>
              <th>城市<br><small>需求/供水</small></th>
              <th>农业<br><small>需求/供水</small></th>
              <th>弃水</th>
              <th>期末库容</th>
              <th>水位(m)</th>
              <th>缺口</th>
              <th>守恒残差</th>
            </tr>
          </thead>
          <tbody>
            <ng-container *ngFor="let p of scheme.periods">
              <tr [class.conflict]="!p.feasible"
                  [class.missing]="p.missing_data"
                  [class.spill]="(p.spill_m3 ?? 0) > 0"
                  [class.shortage]="(p.shortage_m3 ?? 0) > 0">
                <td>
                  {{ p.label ?? ('第' + (p.index + 1) + '时段') }}
                  <span *ngIf="!p.feasible" class="badge red">冲突</span>
                  <span *ngIf="p.missing_data" class="badge gray">缺测</span>
                  <span *ngIf="(p.spill_m3 ?? 0) > 0" class="badge orange">弃水</span>
                </td>
                <td>{{ cell(p.storage_start_m3) }}</td>
                <td>{{ cell(p.inflow_m3) }}</td>
                <td>{{ cell(p.evaporation_m3) }}</td>
                <td>{{ pair(p.env_target_m3, p.env_release_m3) }}</td>
                <td>{{ pair(p.urban_demand_m3, p.urban_supply_m3) }}</td>
                <td>{{ pair(p.agriculture_demand_m3, p.agriculture_supply_m3) }}</td>
                <td>{{ cell(p.spill_m3) }}</td>
                <td>{{ cell(p.storage_end_m3) }}</td>
                <td>{{ p.level_end_m === null ? '缺失' : p.level_end_m.toFixed(2) }}</td>
                <td>{{ cell(p.shortage_m3) }}</td>
                <td [title]="p.warnings.join('&#10;')">
                  {{ p.balance_residual_m3 === null ? '缺失' : fmtInt(p.balance_residual_m3) }}
                </td>
              </tr>
            </ng-container>
          </tbody>
        </table>
      </div>
      <p class="muted" style="margin-top:6px">
        鼠标悬停残差列可查看该时段提示。守恒式：
        S末 = S初 + 入流 − 蒸发 − 生态放水 − 城市供水 − 农业供水 − 弃水。
      </p>
    </div>
  `,
})
export class PeriodTableComponent implements AfterViewInit, OnChanges {
  @Input() scheme!: SchemeResult;
  @ViewChild('storageChart') storageCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('supplyChart') supplyCanvas!: ElementRef<HTMLCanvasElement>;

  private chartStorage?: Chart;
  private chartSupply?: Chart;

  fmtVol = fmtVolume;
  fmtLvl = fmtLevel;
  fmtInt = fmtInt;

  cell(v: number | null): string {
    return v === null ? '缺失' : fmtInt(v);
  }

  pair(d: number | null, s: number | null): string {
    if (d === null && s === null) return '缺失';
    return `${this.cell(d)} / ${this.cell(s)}`;
  }

  ngAfterViewInit(): void {
    this.render();
  }

  ngOnChanges(): void {
    if (this.storageCanvas) this.render();
  }

  private render(): void {
    const ps = this.scheme.periods;
    const labels = ps.map((p) => p.label ?? `${p.index + 1}`);
    const nulls = ps.map(() => null);

    this.chartStorage?.destroy();
    this.chartStorage = new Chart(this.storageCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '期末库容 (万m³)',
            data: ps.map((p) => (p.storage_end_m3 === null ? null : p.storage_end_m3 / 1e4)),
            borderColor: '#1f6feb',
            backgroundColor: 'rgba(31,111,235,.12)',
            fill: true,
            tension: 0.25,
            spanGaps: false,
          },
          {
            label: '水位 (m)',
            data: ps.map((p) => p.level_end_m),
            borderColor: '#1a7f4b',
            yAxisID: 'y1',
            tension: 0.25,
            spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { title: { display: true, text: '库容 万m³' } },
          y1: { position: 'right', title: { display: true, text: '水位 m' }, grid: { drawOnChartArea: false } },
        },
        plugins: {
          tooltip: {
            callbacks: {
              afterLabel: (ctx) =>
                ps[ctx.dataIndex].missing_data ? '该时段及之后来水缺测，状态缺失' : '',
            },
          },
        },
      },
    });

    this.chartSupply?.destroy();
    this.chartSupply = new Chart(this.supplyCanvas.nativeElement, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: '城市供水', data: ps.map((p) => (p.urban_supply_m3 ?? 0) / 1e4), backgroundColor: '#1f6feb' },
          { label: '农业供水', data: ps.map((p) => (p.agriculture_supply_m3 ?? 0) / 1e4), backgroundColor: '#1a7f4b' },
          {
            label: '需求缺口',
            data: ps.map((p) => (p.shortage_m3 ?? 0) / 1e4),
            backgroundColor: '#dc2626',
          },
          {
            label: '弃水',
            data: ps.map((p) => (p.spill_m3 ?? 0) / 1e4),
            backgroundColor: '#d97706',
          },
          { label: '生态放水', data: ps.map((p) => (p.env_release_m3 ?? 0) / 1e4), backgroundColor: '#94a3b8' },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: '万m³' } } },
      },
    });
    void nulls;
  }
}
