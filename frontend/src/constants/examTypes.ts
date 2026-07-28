export type ExamType = 'HP' | 'CG' | 'CCV' | 'IHQ' | 'CONG';

export const EXAM_TYPE_PREFIX: Record<ExamType, string> = {
  HP: 'HP',
  CG: 'CG',
  CCV: 'CV',
  IHQ: 'IHQ',
  CONG: 'CONG',
};

export const EXAM_TYPE_LABEL: Record<ExamType, string> = {
  HP: 'Histopatológico',
  CG: 'Citologia Geral',
  CCV: 'Citologia Cérvico-vaginal',
  IHQ: 'Imuno-histoquímica',
  CONG: 'Congelação',
};
