export interface AghuExam {
  numeroSolicitacao: string; // Ex: "442806"
  registro: string;          // Prontuário (Ex: "21692793")
  nomePaciente: string;
  idade: number;
  sexo: 'M' | 'F' | 'O';
  origem: string;            // Ex: "8 NORTE", "Bloco Cirúrgico"
  procedimento: string;      // Ex: "Anatomopatológico geral"
  descricaoAghu: string;     // Material descrito pelo médico solicitante
}

export const mockAghuExams: AghuExam[] = [
  {
    numeroSolicitacao: '442806',
    registro: '21692793',
    nomePaciente: 'CLAUDIANO DE FARIAS SANTOS',
    idade: 44,
    sexo: 'M',
    origem: '8 NORTE',
    procedimento: 'Anatomopatológico geral',
    descricaoAghu: '1-COLON A DIREITA; 2-LINFONODO DA ARTERIA CÓLICA MÉDIA'
  },
  {
    numeroSolicitacao: '9865468',
    registro: '12345678',
    nomePaciente: 'MARIA JOSE MARIA JOSE',
    idade: 69,
    sexo: 'F',
    origem: '11° NORTE',
    procedimento: 'Anatomopatológico geral',
    descricaoAghu: 'FRAGMENTOS DE ENDOMETRIO'
  }
];

// Função utilitária para simular a busca no backend
export const fetchAghuExam = async (solicitacao: string): Promise<AghuExam | undefined> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(mockAghuExams.find(e => e.numeroSolicitacao === solicitacao));
    }, 500); // Simulando delay de rede de 500ms
  });
};