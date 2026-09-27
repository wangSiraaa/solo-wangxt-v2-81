import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ScenarioInput,
  ScenarioMeta,
  SimulationResponse,
} from '../models/api.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  simulate(payload: ScenarioInput): Observable<SimulationResponse> {
    return this.http.post<SimulationResponse>('/api/simulate', payload);
  }

  saveScenario(payload: ScenarioInput): Observable<ScenarioMeta> {
    return this.http.post<ScenarioMeta>('/api/scenarios', payload);
  }

  listScenarios(): Observable<ScenarioMeta[]> {
    return this.http.get<ScenarioMeta[]>('/api/scenarios');
  }

  loadScenario(id: number): Observable<ScenarioMeta> {
    return this.http.get<ScenarioMeta>(`/api/scenarios/${id}`);
  }

  simulateSaved(id: number): Observable<SimulationResponse> {
    return this.http.post<SimulationResponse>(`/api/scenarios/${id}/simulate`, {});
  }

  deleteScenario(id: number): Observable<void> {
    return this.http.delete<void>(`/api/scenarios/${id}`);
  }
}
