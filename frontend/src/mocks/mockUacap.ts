export type TipoItem = 'Frasco' | 'Cassete' | 'Bloco' | 'Lamina';

export interface HistoricoItem {
  id: string;                // ID único gerado no QR Code (Ex: "F-442806-01")
  numeroSolicitacaoAghu: string;
  tipo: TipoItem;
  statusAtual: string;       // Ex: "Aguardando Macroscopia", "Processando"
  dataCriacao: string;
  criadoPor: string;
}

export const mockUacapItems: HistoricoItem[] = [
  {
    id: 'F-442806-01', // Frasco 1 da solicitação 442806
    numeroSolicitacaoAghu: '442806',
    tipo: 'Frasco',
    statusAtual: 'Aguardando Macroscopia',
    dataCriacao: '2026-06-10T10:00:00Z',
    criadoPor: 'Recepcionista'
  },
  {
    id: 'C-442806-01-A', // Cassete A do Frasco 1
    numeroSolicitacaoAghu: '442806',
    tipo: 'Cassete',
    statusAtual: 'Aguardando Processamento',
    dataCriacao: '2026-06-10T11:30:00Z',
    criadoPor: 'Macroscopista'
  }
];