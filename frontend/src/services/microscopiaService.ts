import api from './api';
import { invalidarCache } from './requestCache';
import type { Subetapa, WorkspaceBase } from './etapaService';

/**
 * O que é próprio da Microscopia — fila e posse ficam em etapaService.
 *
 * Nenhuma destas chamadas manda um nome de responsável: quem assina é sempre o
 * usuário autenticado. A tela antiga mandava um nome escolhido num `select`,
 * o que permitia registrar um laudo em nome de outra pessoa.
 */

export interface LaminaMicroscopia {
  id: string;
  codigo_lamina: string;
  coloracao: string;
  status: string;
  qr_code: string;
  codigo_bloco?: string | null;
  cassete?: string | null;
}

export interface Laudo {
  laudo_previo?: string | null;
  residente?: string | null;
  laudo_previo_em?: string | null;
  conclusao?: string | null;
  patologista?: string | null;
  liberado_em?: string | null;
  ciclo: number;
}

export interface MicroscopiaWorkspace extends WorkspaceBase {
  subetapa?: Subetapa | null;
  papel_esperado?: string | null;
  laminas: LaminaMicroscopia[];
  laudo?: Laudo | null;
  pode_registrar_laudo_previo: boolean;
  pode_revisar: boolean;
}

export const microscopiaService = {
  async workspace(idExame: string): Promise<MicroscopiaWorkspace> {
    const { data } = await api.get(`/api/microscopia/exames/${idExame}`);
    return data;
  },

  /** Resolve o código de uma lâmina, bloco ou solicitação para o exame. */
  async buscar(codigo: string): Promise<{ id_exame: string }> {
    const { data } = await api.get('/api/microscopia/buscar', { params: { codigo } });
    return data;
  },

  /** Residente conclui o laudo prévio; o exame volta à fila do patologista. */
  async registrarLaudoPrevio(idExame: string, laudo: string) {
    const { data } = await api.post(`/api/microscopia/exames/${idExame}/laudo-previo`, { laudo });
    invalidarCache('dashboard:resumo');
    return data;
  },

  /** Patologista aprova e encerra o exame. */
  async liberarLaudo(idExame: string, conclusao?: string) {
    const { data } = await api.post(`/api/microscopia/exames/${idExame}/liberar-laudo`, { conclusao });
    invalidarCache('dashboard:resumo');
    return data;
  },

  /** IHQ/complemento: encerra a posse e reabre o Processamento em novo ciclo. */
  async solicitarComplemento(idExame: string, marcadores: string) {
    const { data } = await api.post(`/api/microscopia/exames/${idExame}/complemento`, { marcadores });
    invalidarCache('dashboard:resumo');
    return data;
  },

  /** Revisão interna: encerra a posse e abre um novo ciclo de revisão. */
  async solicitarRevisao(idExame: string, motivo: string) {
    const { data } = await api.post(`/api/microscopia/exames/${idExame}/revisao`, { motivo });
    invalidarCache('dashboard:resumo');
    return data;
  },
};
