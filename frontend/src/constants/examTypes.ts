export type ExamType = 'HP' | 'CG' | 'CCV' | 'IH' | 'CO';

export const EXAM_TYPE_PREFIX: Record<ExamType, string> = {
  HP: 'HP',
  CG: 'CG',
  CCV: 'CV',
  IH: 'IH',
  CO: 'CO',
};

export const EXAM_TYPE_LABEL: Record<ExamType, string> = {
  HP: 'Histopatológico',
  CG: 'Citologia Geral',
  CCV: 'Citologia Cérvico-vaginal',
  IH: 'Imuno-histoquímica',
  CO: 'Congelação',
};
