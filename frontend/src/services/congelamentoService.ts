import api from './api';
import { invalidarCache } from './requestCache';
import type { WorkspaceBase } from './etapaService';

/** O que é próprio do Congelamento — fila e posse ficam em etapaService. */

export type CondutaCongelamento = 'LIVRE' | 'COMPROMETIDA' | 'AGUARDANDO';

export interface CicloCongelamento {
  id: string;
  ordinal: number;
  residente?: string | null;
  patologista?: string | null;
  quantidade_laminas: number;
  diagnostico: string;
  conduta: CondutaCongelamento;
  observacao?: string | null;
  registrado_por?: string | null;
  criado_em?: string | null;
}

export interface Congelamento {
  id: string;
  status: 'EM_ANALISE' | 'LIBERADO';
  resultado_final?: string | null;
  /** Gerado no backend, dentro da transação da liberação. */
  numero_hp_correlato?: string | null;
  id_exame_hp?: string | null;
  liberado_em?: string | null;
  liberado_por?: string | null;
}

export interface CongelamentoWorkspace extends WorkspaceBase {
  congelamento?: Congelamento | null;
  ciclos: CicloCongelamento[];
  pode_registrar: boolean;
}

export interface CicloCreate {
  residente?: string;
  patologista?: string;
  quantidade_laminas: number;
  diagnostico: string;
  conduta: CondutaCongelamento;
  observacao?: string;
}

export const congelamentoService = {
  async workspace(idExame: string): Promise<CongelamentoWorkspace> {
    const { data } = await api.get(`/api/congelamento/exames/${idExame}`);
    return data;
  },

  /** Aceita o código CONG e também o antigo prefixo CO das etiquetas. */
  async buscar(codigo: string): Promise<{ id_exame: string; numero_solicitacao: string }> {
    const { data } = await api.get('/api/congelamento/buscar', { params: { codigo } });
    return data;
  },

  /**
   * Registra uma rodada de análise. ``COMPROMETIDA`` mantém o exame em
   * andamento aguardando novo fragmento; ``LIVRE`` encerra a etapa e gera o HP
   * correlato no backend.
   */
  async registrarCiclo(idExame: string, dados: CicloCreate): Promise<CongelamentoWorkspace> {
    const { data } = await api.post(`/api/congelamento/exames/${idExame}/ciclos`, dados);
    invalidarCache('dashboard:resumo');
    return data;
  },
};
