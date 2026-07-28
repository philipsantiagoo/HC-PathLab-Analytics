export const RESPONSAVEIS_MACROSCOPIA: string[] = [
  'Dr. Marcelo Tavares',
  'Dra. Fernanda Lopes',
  'Carlos Lima',
  'Residente — Rodrigo Nunes',
];

export const RESPONSAVEIS_PROCESSAMENTO: string[] = [
  'Rafael Costa',
  'Beatriz Andrade',
  'Célia Ferreira',
];

export const RESPONSAVEIS_MICROSCOPIA: string[] = [
  'Dr. Marcelo Tavares',
  'Dra. Fernanda Lopes',
  'Residente — Rodrigo Nunes',
  'Residente — Ana Paula Melo',
];

export const RESIDENTES_CONGELAMENTO: string[] = [
  'Residente — Rodrigo Nunes',
  'Residente — Ana Paula Melo',
  'Residente — Carlos Henrique',
];

export const PATOLOGISTAS_CONGELAMENTO: string[] = [
  'Dr. Marcelo Tavares',
  'Dra. Fernanda Lopes',
  'Dr. João Batista',
];

export const STAINING_OPTIONS: string[] = [
  'HE (Hematoxilina-Eosina) - Rotina',
  'Congelação',
  'Giemsa',
  'PAS (Ácido Periódico de Schiff)',
  'Ziehl-Neelsen',
  'Outra (especificar na observação)',
];

export const RESULTADO_CONGELAMENTO_OPTIONS = [
  { value: 'aguardando', label: 'Aguardando análise' },
  { value: 'livre', label: 'Margem livre' },
  { value: 'comprometida', label: 'Margem comprometida' },
] as const;

export type ResultadoCongelamento = typeof RESULTADO_CONGELAMENTO_OPTIONS[number]['value'];