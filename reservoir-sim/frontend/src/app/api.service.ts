import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CompareResponse, ScenarioIn, ScenarioMeta, SimResult } from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  simulate(s: ScenarioIn): Observable<{ name: string; result: SimResult }> {
    return this.http.post<{ name: string; result: SimResult }>(`${this.base}/simulate`, s);
  }

  saveScenario(s: ScenarioIn): Observable<ScenarioMeta> {
    return this.http.post<ScenarioMeta>(`${this.base}/scenarios`, s);
  }

  listScenarios(): Observable<ScenarioMeta[]> {
    return this.http.get<ScenarioMeta[]>(`${this.base}/scenarios`);
  }

  compare(aId: number, bId: number): Observable<CompareResponse> {
    return this.http.post<CompareResponse>(`${this.base}/compare`, { a_id: aId, b_id: bId });
  }
}
