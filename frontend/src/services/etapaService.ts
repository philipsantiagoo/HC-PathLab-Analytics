import api from './api';
import { emCache, invalidarCache } from './requestCache';

/**
 * Cliente único das quatro estações.
 *
 * Macroscopia, Processamento, Microscopia e Congelamento expõem exatamente as
 * mesmas rotas de fila e posse sob prefixos diferentes, então uma função por
 * estação seria a mesma função copiada quatro vezes.
 */
export type Etapa = 'macroscopia' | 'processamento' | 'microscopia' | 'congelamento';

/** Nome da etapa como o backend a identifica (usado no filtro de candidatos). */
export const ETAPA_BACKEND: Record<Etapa, string> = {
  macroscopia: 'MACROSCOPIA',
  processamento: 'PROCESSAMENTO',
  microscopia: 'MICROSCOPIA',
  congelamento: 'CONGELAMENTO',
};

export type FiltroFila = 'meus' | 'aguardando' | 'em_andamento' | 'todos';
export type SituacaoEtapa = 'AGUARDANDO' | 'EM_ANDAMENTO' | 'CONCLUIDA';
export type Subetapa = 'LAUDO_PREVIO' | 'REVISAO';

/** Uma linha de fila — sempre um exame, nunca um item filho. */
export interface LinhaFila {
  id_exame: string;
  numero_solicitacao: string;
  tipo_exame?: string | null;
  paciente_nome: string;
  numero_exame_aghu?: string | null;
  tipo_peca?: string | null;
  total_frascos: number;
  etapa: string;
  situacao: SituacaoEtapa;
  subetapa?: Subetapa | null;
  ciclo: number;
  responsavel?: string | null;
  responsavel_nome?: string | null;
  assumido_em?: string | null;
  entrou_na_etapa_em?: string | null;
  data_entrada?: string | null;
  atrasado: boolean;
  status_exame?: string | null;
  // Extras por estação.
  total_cassetes?: number | null;
  cassetes_processados?: number | null;
  cassetes_pendentes?: number | null;
  total_blocos?: number | null;
  total_laminas?: number | null;
  papel_esperado?: string | null;
  total_ciclos?: number | null;
  situacao_resultado?: string | null;
}

export interface ContadoresFila {
  meus: number;
  aguardando: number;
  em_andamento: number;
  todos: number;
  laudo_previo?: number | null;
  revisao?: number | null;
}

export interface Fila {
  itens: LinhaFila[];
  pagina: number;
  por_pagina: number;
  total: number;
  total_paginas: number;
  contadores: ContadoresFila;
}

export interface Posse {
  etapa: string;
  situacao: SituacaoEtapa;
  subetapa?: Subetapa | null;
  ciclo: number;
  responsavel?: string | null;
  responsavel_nome?: string | null;
  assumido_em?: string | null;
  sou_o_dono: boolean;
  pode_assumir: boolean;
  pode_liberar: boolean;
  pode_executar: boolean;
}

export interface EtapaHistorico {
  etapa: string;
  situacao: SituacaoEtapa;
  subetapa?: Subetapa | null;
  ciclo: number;
  responsavel_nome?: string | null;
  assumido_em?: string | null;
  concluido_em?: string | null;
  criado_em?: string | null;
}

/** Base comum a todos os workspaces das estações. */
export interface WorkspaceBase {
  exame: LinhaFila;
  posse: Posse;
  historico_etapas: EtapaHistorico[];
}

export interface UsuarioCandidato {
  username: string;
  nome_exibicao?: string | null;
  email?: string | null;
  departamento?: string | null;
  origem: string;
}

export interface ParametrosFila {
  filtro: FiltroFila;
  pagina: number;
  por_pagina: number;
  busca?: string;
  subetapa?: Subetapa;
  signal?: AbortSignal;
}

export const etapaService = {
  /**
   * Uma página da fila. Sem cache de propósito: cachear lista paginada por uma
   * chave só faria a página 2 servir as linhas da 1, e uma chave por página +
   * filtro tornaria a invalidação impossível — depois de "assumir", a própria
   * linha ficaria obsoleta pelo TTL inteiro.
   */
  async fila(etapa: Etapa, params: ParametrosFila): Promise<Fila> {
    const { signal, ...query } = params;
    const { data } = await api.get(`/api/${etapa}/fila`, { params: query, signal });
    return data;
  },

  async workspace<T extends WorkspaceBase>(etapa: Etapa, idExame: string): Promise<T> {
    const { data } = await api.get(`/api/${etapa}/exames/${idExame}`);
    return data;
  },

  async assumir(etapa: Etapa, idExame: string): Promise<LinhaFila> {
    const { data } = await api.post(`/api/${etapa}/exames/${idExame}/assumir`, {});
    invalidarCache('dashboard:resumo');
    return data;
  },

  async repassar(
    etapa: Etapa,
    idExame: string,
    dados: { para_username: string; para_nome?: string; motivo: string },
  ): Promise<LinhaFila> {
    const { data } = await api.post(`/api/${etapa}/exames/${idExame}/repassar`, dados);
    invalidarCache('dashboard:resumo');
    return data;
  },

  async liberar(etapa: Etapa, idExame: string): Promise<LinhaFila> {
    const { data } = await api.post(`/api/${etapa}/exames/${idExame}/liberar`, {});
    invalidarCache('dashboard:resumo');
    return data;
  },

  /** Candidatos ao repasse, priorizando quem já atuou na etapa. */
  async candidatos(etapa?: Etapa, busca?: string): Promise<UsuarioCandidato[]> {
    const chave = `usuarios:candidatos:${etapa ?? ''}:${busca ?? ''}`;
    // A lista de pessoal muda pouco; TTL maior que o padrão.
    return emCache(chave, async () => {
      const params: Record<string, string> = {};
      if (etapa) params.etapa = ETAPA_BACKEND[etapa];
      if (busca) params.busca = busca;
      return (await api.get('/api/usuarios/candidatos', { params })).data;
    }, 5 * 60_000);
  },
};

/** Rótulo humano da situação da etapa, usado nas filas e nos cards. */
export function rotuloSituacao(situacao: SituacaoEtapa | string): string {
  if (situacao === 'EM_ANDAMENTO') return 'Assumido';
  if (situacao === 'CONCLUIDA') return 'Concluída';
  return 'Aguardando início';
}

export function rotuloSubetapa(subetapa?: Subetapa | null): string | null {
  if (subetapa === 'LAUDO_PREVIO') return 'Laudo prévio';
  if (subetapa === 'REVISAO') return 'Revisão';
  return null;
}
