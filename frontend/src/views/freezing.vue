<template>
  <div class="space-y-6">
    <!-- Busca -->
    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
          <QrCodeIcon class="h-5 w-5 text-gray-400" />
          Identificar Amostra de Congelamento
        </h2>
        <p class="text-sm text-gray-500">
          Bipe o código de barras da etiqueta CO ou digite o número da solicitação.
          O material deve chegar <strong>sem formol</strong> (fresco).
        </p>
      </template>

      <div class="flex items-end gap-3">
        <div class="flex-1 max-w-xs">
          <label class="form-label" for="codigoCO">Nº Solicitação / Código CO</label>
          <input
            id="codigoCO"
            v-model="codigoBusca"
            type="text"
            class="form-control"
            placeholder="Ex: CO-0001/26.1"
            @keyup.enter="buscar"
          >
        </div>
        <Button variant="primary" @click="buscar">Buscar</Button>
      </div>
    </Card>

    <!-- Não encontrado -->
    <Card v-if="buscou && !casoAtual">
      <div class="flex items-start gap-3 p-2">
        <ExclamationTriangleIcon class="h-6 w-6 shrink-0 text-amber-600" />
        <div>
          <p class="font-semibold text-amber-700">Solicitação não encontrada</p>
          <p class="text-sm text-gray-600 mt-1">
            Verifique se a unidade executora no AGHU está correta (unidade 205 — Congelamento).
            Se a solicitação vier como histopatológico, altere a unidade executora antes de buscar aqui.
          </p>
        </div>
      </div>
    </Card>

    <!-- Caso encontrado -->
    <div v-else-if="buscou && casoAtual" class="space-y-6">

      <!-- Aviso de correlação HP já existente -->
      <div v-if="casoAtual.correlacaoHp" class="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <InformationCircleIcon class="h-6 w-6 shrink-0 text-blue-600" />
        <div>
          <p class="font-semibold text-blue-700">Congelamento correlacionado com HP</p>
          <p class="text-sm text-blue-600 mt-0.5">
            Este caso tem um HP vinculado: <strong class="font-mono">{{ casoAtual.correlacaoHp }}</strong>.
            Após liberar o resultado, o material deve retornar à Recepção para entrada como histopatológico.
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Visão Unificada -->
        <Card>
          <template #header>
            <h2 class="text-lg font-bold text-lab-text">Dados da Amostra (AGHU)</h2>
            <p class="text-sm text-gray-500">Somente leitura — informações puxadas do AGHU</p>
          </template>

          <div class="space-y-4 text-sm">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-[10px] font-semibold text-gray-400 uppercase">Paciente</p>
                <p class="font-bold text-lab-text text-base">{{ casoAtual.aghu.nomePaciente }}</p>
              </div>
              <Badge color="purple">Congelamento</Badge>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <p class="text-[10px] font-semibold text-gray-400 uppercase">Prontuário</p>
                <p class="text-gray-700">{{ casoAtual.aghu.prontuario }}</p>
              </div>
              <div>
                <p class="text-[10px] font-semibold text-gray-400 uppercase">Solicitação AGHU</p>
                <p class="text-gray-700">{{ casoAtual.aghu.numeroSolicitacaoAghu }}</p>
              </div>
              <div>
                <p class="text-[10px] font-semibold text-gray-400 uppercase">Código CO</p>
                <p class="text-gray-700 font-mono">{{ casoAtual.codigoLocal }}</p>
              </div>
              <div>
                <p class="text-[10px] font-semibold text-gray-400 uppercase">Origem</p>
                <p class="text-gray-700">{{ casoAtual.aghu.origem }}{{ casoAtual.aghu.clinica ? ` · ${casoAtual.aghu.clinica}` : '' }}</p>
              </div>
            </div>

            <div class="bg-gray-50 border border-gray-100 p-3 rounded-sm">
              <p class="text-[10px] font-semibold text-gray-500 uppercase">Descrição do material (AGHU)</p>
              <p class="text-gray-700 mt-1">{{ casoAtual.aghu.tipoMaterial || 'Não informado pelo médico solicitante.' }}</p>
            </div>

            <div class="bg-amber-50 border border-amber-100 p-3 rounded-sm">
              <p class="text-[10px] font-semibold text-amber-700 uppercase">Indicação clínica</p>
              <p class="text-gray-800 mt-1">{{ casoAtual.aghu.indicacaoClinica }}</p>
            </div>

            <!-- Ciclos anteriores -->
            <div v-if="casoAtual.ciclosCongelamento?.length" class="border-t border-gray-100 pt-4">
              <p class="text-xs font-bold text-gray-500 uppercase mb-2">
                Ciclos anteriores ({{ casoAtual.ciclosCongelamento.length }})
              </p>
              <div class="space-y-2">
                <div
                  v-for="(ciclo, i) in casoAtual.ciclosCongelamento"
                  :key="i"
                  class="flex flex-col gap-2 p-3 bg-gray-50 rounded-lg text-xs"
                >
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-gray-500 font-semibold">Ciclo {{ i + 1 }} — {{ formatDateShort(ciclo.data) }}</span>
                    <Badge :color="ciclo.conduta === 'comprometida' ? 'red' : (ciclo.conduta === 'livre' ? 'green' : 'gray')">
                      {{ ciclo.conduta === 'comprometida' ? 'Requer ampliação' : (ciclo.conduta === 'livre' ? 'Margem livre / Liberado' : 'Pendente') }}
                    </Badge>
                  </div>
                  <div>
                    <span class="text-[10px] font-semibold text-gray-400 uppercase">Diagnóstico:</span>
                    <p class="text-gray-700 font-medium whitespace-pre-line mt-0.5">{{ ciclo.resultado }}</p>
                  </div>
                  <div v-if="ciclo.observacao" class="bg-white p-2 border border-gray-100 rounded text-gray-600 italic">
                    {{ ciclo.observacao }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <!-- Formulário de registro -->
        <Card v-if="!liberado">
          <template #header>
            <h2 class="text-lg font-bold text-lab-text">Registro do Congelamento</h2>
            <p class="text-sm text-gray-500">Preencha os dados do processamento intraoperatório</p>
          </template>

          <div class="space-y-4">
            <div class="grid grid-cols-1 gap-4">
              <div>
                <label class="form-label" for="residenteCO">Residente de plantão *</label>
                <select id="residenteCO" v-model="residente" class="form-control">
                  <option value="" disabled>Selecione...</option>
                  <option v-for="nome in RESIDENTES_CONGELAMENTO" :key="nome" :value="nome">{{ nome }}</option>
                </select>
              </div>
              <div>
                <label class="form-label" for="patologistaCO">Patologista de plantão *</label>
                <select id="patologistaCO" v-model="patologista" class="form-control">
                  <option value="" disabled>Selecione...</option>
                  <option v-for="nome in PATOLOGISTAS_CONGELAMENTO" :key="nome" :value="nome">{{ nome }}</option>
                </select>
              </div>
              <div>
                <label class="form-label" for="qtdLaminas">Quantidade de lâminas geradas *</label>
                <input
                  id="qtdLaminas"
                  v-model.number="quantidadeLaminas"
                  type="number"
                  min="1"
                  class="form-control max-w-[120px]"
                >
              </div>
            </div>

            <div class="border-t border-gray-100 pt-4">
              <label class="form-label" for="diagnostico">Diagnóstico / Achados do Patologista *</label>
              <textarea
                id="diagnostico"
                v-model="diagnostico"
                rows="3"
                class="form-control"
                placeholder="Ex: Carcinoma ductal invasivo presente na amostra..."
              ></textarea>
            </div>

            <div class="border-t border-gray-100 pt-4 space-y-2">
              <label class="form-label font-bold text-gray-700">Conduta Clínica / Ação *</label>
              <div class="flex flex-col gap-2">
                <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="radio" v-model="conduta" value="livre" class="form-radio text-lab-primary" />
                  <span>Liberar Resultado Final (Margens Livres / Concluído)</span>
                </label>
                <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="radio" v-model="conduta" value="comprometida" class="form-radio text-lab-primary" />
                  <span>Solicitar Novo Fragmento (Margem Comprometida / Requer Ampliação)</span>
                </label>
                <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="radio" v-model="conduta" value="aguardando" class="form-radio text-lab-primary" />
                  <span>Resultado Pendente (Apenas salvar registro parcial)</span>
                </label>
              </div>
            </div>

            <!-- Margem comprometida: campo de observação + novo ciclo -->
            <div v-if="conduta === 'comprometida'" class="bg-red-50 border border-red-200 p-4 rounded-lg space-y-3">
              <div class="flex items-start gap-2">
                <ExclamationTriangleIcon class="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
                <p class="text-sm font-semibold text-red-700">
                  Margem comprometida — avisar cirurgião e aguardar novo fragmento
                </p>
              </div>
              <div>
                <label class="form-label" for="obsCO">Observação para o cirurgião *</label>
                <textarea
                  id="obsCO"
                  v-model="observacao"
                  rows="2"
                  class="form-control"
                  placeholder="Ex: Margem superior comprometida, necessário ampliar ressecção..."
                ></textarea>
              </div>
              <Button
                variant="danger"
                :disabled="!podeRegistrar || !observacao.trim()"
                class="w-full"
                @click="registrarCiclo"
              >
                Registrar e Aguardar Novo Fragmento
              </Button>
            </div>

            <!-- Margem livre: liberar -->
            <div v-else-if="conduta === 'livre'" class="space-y-3 bg-green-50 border border-green-200 p-4 rounded-lg">
              <div class="flex items-start gap-2">
                <CheckCircleIcon class="h-5 w-5 shrink-0 text-green-600 mt-0.5" />
                <p class="text-sm font-semibold text-green-700">
                  Resultado finalizado e margens livres de neoplasia.
                </p>
              </div>
              <div>
                <label class="form-label" for="laudoCO">Conclusão / Observações adicionais (opcional)</label>
                <textarea
                  id="laudoCO"
                  v-model="observacao"
                  rows="2"
                  class="form-control"
                  placeholder="Ex: Margens cirúrgicas livres de neoplasia no fragmento congelado."
                ></textarea>
              </div>
              <Button
                variant="primary"
                :disabled="!podeRegistrar"
                class="w-full"
                @click="liberarResultado"
              >
                <template #icon><CheckCircleIcon class="h-5 w-5" /></template>
                Liberar Resultado e Encaminhar para HP
              </Button>
            </div>

            <!-- Aguardando: só registra sem liberar -->
            <div v-else-if="conduta === 'aguardando'" class="bg-gray-50 border border-gray-200 p-4 rounded-lg space-y-3">
              <div class="flex items-start gap-2">
                <InformationCircleIcon class="h-5 w-5 shrink-0 text-gray-600 mt-0.5" />
                <p class="text-sm font-semibold text-gray-700">
                  Salvar análise parcial sem encerrar o congelamento.
                </p>
              </div>
              <Button
                variant="default"
                :disabled="!podeRegistrar"
                class="w-full"
                @click="registrarCiclo"
              >
                Salvar Registro (Resultado Pendente)
              </Button>
            </div>
          </div>
        </Card>

        <!-- Caso já liberado -->
        <Card v-else>
          <template #header>
            <h2 class="text-lg font-bold text-lab-text">Resultado Liberado</h2>
          </template>
          <div class="flex items-start gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
            <CheckCircleIcon class="h-6 w-6 shrink-0 text-green-600" />
            <div>
              <p class="font-semibold text-green-700">Margem livre — resultado liberado!</p>
              <p class="text-sm text-green-600 mt-0.5">
                Cirurgião foi notificado. O material deve retornar à Recepção para entrada como
                <strong class="font-mono">{{ hpCorrelato }}</strong>.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <!-- Orientação pós-liberação: retorno do material para HP -->
      <Card v-if="liberado" class="border-t-4 border-t-lab-primary">
        <div class="space-y-3">
          <h3 class="text-sm font-bold text-lab-text uppercase tracking-wide">Próximo passo obrigatório</h3>
          <ol class="list-decimal list-inside space-y-2 text-sm text-gray-700">
            <li>Coloque o material residual de volta no frasco original.</li>
            <li>Encaminhe o frasco para a <strong>Recepção</strong>.</li>
            <li>
              Na Recepção, o caso deve ser recebido como
              <strong class="font-mono">{{ hpCorrelato }}</strong>
              e seguir o fluxo histopatológico normal (Macroscopia → Processamento → Microscopia).
            </li>
          </ol>
        </div>
      </Card>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useToast } from 'vue-toastification';
import {
  QrCodeIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
} from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import Badge from '../components/badge/badge.vue';
import { useExamSequenceStore } from '../stores/examSequence';
import { formatDateShort } from '../utils/date';
import {
  RESIDENTES_CONGELAMENTO,
  PATOLOGISTAS_CONGELAMENTO,
} from '../constants/staffMembers';
import { formatExamCode } from '../utils/examCode';

interface CicloCongelamento {
  data: Date;
  residente: string;
  patologista: string;
  quantidadeLaminas: number;
  resultado: string; // Guarda o diagnóstico em texto livre
  conduta: 'livre' | 'comprometida' | 'aguardando';
  observacao?: string;
}

interface CasoCongelamento {
  codigoLocal: string;
  correlacaoHp?: string;
  ciclosCongelamento: CicloCongelamento[];
  aghu: {
    numeroSolicitacaoAghu: string;
    nomePaciente: string;
    prontuario: string;
    origem: 'Internado' | 'Ambulatorial';
    clinica?: string;
    tipoMaterial: string;
    indicacaoClinica: string;
  };
}

// Mock do AGHU — mesmo padrão das outras telas.
const AGHU_CO_MOCK: Record<string, CasoCongelamento> = {
  'CO-0001/26.1': {
    codigoLocal: 'CO-0001/26.1',
    ciclosCongelamento: [],
    aghu: {
      numeroSolicitacaoAghu: '443901',
      nomePaciente: 'Francisca Maria de Souza',
      prontuario: '309881',
      origem: 'Internado',
      clinica: 'Mastologia',
      tipoMaterial: 'Quadrante supero-externo mama esquerda',
      indicacaoClinica: 'Carcinoma ductal invasivo mama esquerda — avaliação de margens cirúrgicas durante quadrantectomia.',
    },
  },
  'CO-0002/26.1': {
    codigoLocal: 'CO-0002/26.1',
    ciclosCongelamento: [],
    aghu: {
      numeroSolicitacaoAghu: '444502',
      nomePaciente: 'Roberto Alves Pereira',
      prontuario: '120044',
      origem: 'Internado',
      clinica: 'Cirurgia Geral',
      tipoMaterial: 'Nódulo hepático — achado intraoperatório',
      indicacaoClinica: 'Achado nodular em lobo direito durante colecistectomia laparoscópica.',
    },
  },
};

const toast = useToast();
const sequenceStore = useExamSequenceStore();

const codigoBusca = ref('');
const buscou = ref(false);
const casoAtual = ref<CasoCongelamento | null>(null);

const residente = ref('');
const patologista = ref('');
const quantidadeLaminas = ref(1);
const diagnostico = ref('');
const conduta = ref<'livre' | 'comprometida' | 'aguardando' | ''>('');
const observacao = ref('');
const liberado = ref(false);
const hpCorrelato = ref('');

const podeRegistrar = computed(() => {
  return (
    residente.value !== '' &&
    patologista.value !== '' &&
    quantidadeLaminas.value >= 1 &&
    diagnostico.value.trim() !== '' &&
    conduta.value !== ''
  );
});

function buscar() {
  buscou.value = true;
  liberado.value = false;
  residente.value = '';
  patologista.value = '';
  quantidadeLaminas.value = 1;
  diagnostico.value = '';
  conduta.value = '';
  observacao.value = '';
  hpCorrelato.value = '';
  casoAtual.value = AGHU_CO_MOCK[codigoBusca.value.trim()] ?? null;
}

function registrarCiclo() {
  if (!podeRegistrar.value || !casoAtual.value) return;

  casoAtual.value.ciclosCongelamento.push({
    data: new Date(),
    residente: residente.value,
    patologista: patologista.value,
    quantidadeLaminas: quantidadeLaminas.value,
    resultado: diagnostico.value,
    conduta: conduta.value as 'comprometida' | 'aguardando',
    observacao: observacao.value || undefined,
  });

  if (conduta.value === 'comprometida') {
    toast.warning('Margem comprometida registrada. Aguardando novo fragmento do cirurgião.');
  } else {
    toast.info('Registro salvo. Resultado ainda pendente de análise.');
  }

  // Limpa o formulário pro próximo ciclo, mantendo o caso aberto.
  residente.value = '';
  patologista.value = '';
  quantidadeLaminas.value = 1;
  diagnostico.value = '';
  conduta.value = '';
  observacao.value = '';
}

function liberarResultado() {
  if (!podeRegistrar.value || !casoAtual.value) return;

  // Registra o ciclo final (margem livre).
  casoAtual.value.ciclosCongelamento.push({
    data: new Date(),
    residente: residente.value,
    patologista: patologista.value,
    quantidadeLaminas: quantidadeLaminas.value,
    resultado: diagnostico.value,
    conduta: 'livre',
    observacao: observacao.value || undefined,
  });

  // Gera o código HP correlato (caso seguinte na esteira normal).
  const caso = sequenceStore.nextSequencial();
  hpCorrelato.value = formatExamCode('HP', caso.sequencial, caso.ano, caso.semestre);
  casoAtual.value.correlacaoHp = hpCorrelato.value;

  liberado.value = true;
  toast.success(`Resultado liberado — margem livre. Material deve retornar à Recepção como ${hpCorrelato.value}.`);
}
</script>