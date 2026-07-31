import api from './api';
import { invalidarCache } from './requestCache';
import type { WorkspaceBase } from './etapaService';

/** O que é próprio do Processamento — fila e posse ficam em etapaService. */

export interface LaminaResumo {
  id: string;
  codigo_lamina: string;
  numero_lamina: number;
  coloracao: string;
  qr_code: string;
  status: string;
}

export interface BlocoResumo {
  id: string;
  codigo_bloco: string;
  qr_code: string;
  status: string;
}

/** O cassete com toda a sua descendência: a bancada enxerga o exame inteiro. */
export interface CasseteWorkspace {
  id: string;
  identificador: string;
  qr_code: string;
  status: string;
  coloracao_padrao: string;
  descricao_estrutura?: string | null;
  id_lote_processamento?: string | null;
  bloco?: BlocoResumo | null;
  laminas: LaminaResumo[];
}

export interface LoteResumo {
  id: string;
  responsavel?: string | null;
  status: string;
  observacoes?: string | null;
  iniciado_em?: string | null;
  concluido_em?: string | null;
}

export interface ProcessamentoWorkspace extends WorkspaceBase {
  cassetes: CasseteWorkspace[];
  lotes: LoteResumo[];
  progresso: {
    total_cassetes: number;
    cassetes_processados: number;
    total_blocos: number;
    total_laminas: number;
  };
  /** O que ainda impede o envio à Microscopia, em linguagem de bancada. */
  pendencias_conclusao: string[];
  pode_concluir: boolean;
}

export const processamentoService = {
  async workspace(idExame: string): Promise<ProcessamentoWorkspace> {
    const { data } = await api.get(`/api/processamento/exames/${idExame}`);
    return data;
  },

  /** Resolve o QR Code (ou código legível) de um cassete para o exame dono. */
  async buscarCassete(codigo: string): Promise<{ id_exame: string; id_cassete: string | null; numero_solicitacao: string }> {
    const { data } = await api.get('/api/processamento/cassetes/buscar', { params: { codigo } });
    return data;
  },

  async iniciarLote(dados: { cassete_ids: string[]; observacoes?: string }): Promise<{ lote: { id: string }; total_cassetes: number }> {
    const { data } = await api.post('/api/processamento/lote', dados);
    return data;
  },

  async concluirLote(idLote: string, dados: { observacoes?: string }): Promise<{ lote: { id: string }; blocos_gerados: number; blocos: BlocoResumo[] }> {
    const { data } = await api.post(`/api/processamento/lote/${idLote}/concluir`, dados);
    return data;
  },

  /**
   * Gera as lâminas do bloco. ``coloracoes`` traz uma coloração por lâmina —
   * antes todas saíam com a mesma e a especial pedida na macroscopia sumia.
   */
  async gerarLaminas(idBloco: string, dados: { quantidade: number; coloracao: string; coloracoes?: string[] }) {
    const { data } = await api.post(`/api/processamento/blocos/${idBloco}/laminas`, dados);
    return data;
  },

  /** Única porta de saída para a Microscopia. 409 lista o que falta. */
  async concluirExame(idExame: string): Promise<{ id_exame: string; numero_solicitacao: string; status: string; total_laminas: number }> {
    const { data } = await api.post(`/api/processamento/exames/${idExame}/concluir`, {});
    invalidarCache('dashboard:resumo');
    return data;
  },
};
