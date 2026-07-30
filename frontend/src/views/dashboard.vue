<template>
  <div class="space-y-6">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-if="qtdAtrasados > 0"
        class="flex items-start gap-3 p-4 rounded-lg bg-red-50 border border-red-200"
      >
        <ExclamationTriangleIcon class="h-6 w-6 shrink-0 text-red-600" />
        <div>
          <p class="font-semibold text-red-700">Exames fora da meta de 20 dias</p>
          <p class="text-sm mt-0.5 text-red-600">
            Há {{ qtdAtrasados }} caso(s) que excederam o prazo máximo estabelecido pela UACAP.
          </p>
        </div>
      </div>

      <div
        v-if="qtdNoAlerta > 0"
        class="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200"
      >
        <ClockIcon class="h-6 w-6 shrink-0 text-amber-600" />
        <div>
          <p class="font-semibold text-amber-700">Exames próximos da meta de 20 dias</p>
          <p class="text-sm mt-0.5 text-amber-600">
            Há {{ qtdNoAlerta }} caso(s) na zona de alerta precisando de atenção para não estourar o prazo.
          </p>
        </div>
      </div>
    </div>

    <!-- Cards de status: clicar filtra a tabela por etapa -->
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-4">
      <div
        v-for="card in statusCards"
        :key="card.label"
        @click="selecionarEtapaCard(card.label)"
        class="cursor-pointer transition-all duration-200"
      >
        <Card
          :class="[
            'h-full border hover:shadow-md transition-all',
            filtroEtapa === card.label ? 'border-[#173f42] ring-2 ring-[#173f42]/20 bg-teal-50/40' : 'border-gray-200'
          ]"
        >
          <p class="text-xs font-medium text-gray-500 truncate" :title="card.label">{{ card.label }}</p>
          <p class="text-2xl font-bold text-lab-text mt-1">{{ card.count }}</p>
        </Card>
      </div>
    </div>

    <Card>
      <template #header>
        <div class="space-y-4">
          <div>
            <h2 class="text-lg font-bold text-lab-text">Exames</h2>
            <p class="text-sm text-gray-500">
              Uma linha por exame — os frascos de um mesmo exame andam juntos.
              Início do trabalho: quando alguém assumiu o exame na macroscopia.
              Tempo total: relógio desde a entrada no sistema (meta: 20 dias).
            </p>
          </div>

          <div class="p-4 bg-gray-50/80 rounded-lg border border-gray-200/80 space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-sm font-semibold text-lab-text">
                <FunnelIcon class="h-4 w-4 text-[#173f42]" />
                <span>Filtros de Pesquisa</span>
              </div>
              <button
                v-if="temFiltroAtivo"
                @click="limparFiltros"
                class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-red-600 transition-colors"
              >
                <XMarkIcon class="h-3.5 w-3.5" />
                Limpar filtros
              </button>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Nome do Paciente</label>
                <div class="relative">
                  <input
                    v-model="filtroNomePaciente"
                    type="text"
                    placeholder="Buscar por nome..."
                    class="w-full text-xs pl-8 pr-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-[#173f42] focus:border-[#173f42]"
                  />
                  <MagnifyingGlassIcon class="h-4 w-4 text-gray-400 absolute left-2.5 top-2.5" />
                </div>
              </div>

              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Código Interno</label>
                <input
                  v-model="filtroCodigoInterno"
                  type="text"
                  placeholder="Ex: HP-0001/26.1"
                  class="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-[#173f42] focus:border-[#173f42]"
                />
              </div>

              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Código AGHU</label>
                <input
                  v-model="filtroCodigoAghu"
                  type="text"
                  placeholder="Ex: 123456"
                  class="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-[#173f42] focus:border-[#173f42]"
                />
              </div>

              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Etapa do Processo</label>
                <select
                  v-model="filtroEtapa"
                  class="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-[#173f42] focus:border-[#173f42]"
                >
                  <option value="">Todas as etapas</option>
                  <option v-for="status in EXAM_STATUSES" :key="status" :value="status">
                    {{ status }}
                  </option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </template>

      <DataTable
        :headers="headers"
        :items="examesComSla"
        server-side
        :total="total"
        :loading="carregando"
        :page-size="POR_PAGINA"
        v-model:page="pagina"
      >
        <template #item-codigoAghu="{ item }">
          <span class="text-xs font-mono text-gray-600">{{ item.codigoAghu }}</span>
        </template>

        <template #item-etapa="{ item }">
          <Badge :color="STATUS_COLOR[item.etapa]">{{ item.etapa }}</Badge>
        </template>

        <template #item-tempoInicioTrabalho="{ item }">
          <div class="flex flex-col gap-0.5">
            <span :class="item.atrasado ? 'text-red-600 font-medium' : 'text-gray-500'">
              {{ item.tempoInicioTrabalhoFormatado }}
            </span>
            <span v-if="item.responsavel" class="text-[10px] text-gray-400">{{ item.responsavel }}</span>
          </div>
        </template>

        <template #item-tempoTotal="{ item }">
          <span class="inline-flex items-center gap-1.5" :class="TEMPO_TOTAL_CLASS[item.slaStatus]">
            <ExclamationTriangleIcon v-if="item.slaStatus === 'atrasado'" class="h-4 w-4" />
            <ClockIcon v-else-if="item.slaStatus === 'alerta'" class="h-4 w-4" />
            {{ item.tempoTotalFormatado }}
          </span>
        </template>

        <template #actions="{ item }">
          <button
            @click="verDetalhes(item)"
            class="text-xs font-medium text-gray-500 hover:text-[#173f42] underline decoration-transparent hover:decoration-[#173f42] underline-offset-4 transition-all duration-200 focus:outline-none"
          >
            Ver detalhes
          </button>
        </template>
      </DataTable>
    </Card>

    <ExamDetailsModal
      :show="modalAberto"
      :detalhe="detalheSelecionado"
      @close="modalAberto = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import {
  ExclamationTriangleIcon,
  ClockIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import DataTable from '../components/dataTable/dataTable.vue';
import Badge from '../components/badge/badge.vue';
import ExamDetailsModal from '../components/examDetailsModal/examDetailsModal.vue';
import { STATUS_COLOR, EXAM_STATUSES } from '../constants/statuses';
import { diasDesde, getSlaStatus, formatTempoTotal, type SlaStatus } from '../utils/sla';
import type { ExamCaseDetail } from '../types/exam';
import { exameService, mapExameDetalhe, type DashboardFilterParams } from '../services/exameService';
import { parseDataApi } from '../utils/date';

const POR_PAGINA = 10;

// "Chegada na etapa" foi removida: nunca teve fonte no backend e renderizava
// "—" em toda linha desde sempre. Recolocar exige uma coluna de carimbo por
// etapa, que não existe hoje.
const headers = [
  { text: 'Solicitação', value: 'solicitacao' },
  { text: 'Código AGHU', value: 'codigoAghu' },
  { text: 'Paciente', value: 'paciente' },
  { text: 'Etapa', value: 'etapa' },
  { text: 'Frascos', value: 'frascos', align: 'center' as const },
  { text: 'Início do trabalho', value: 'tempoInicioTrabalho' },
  { text: 'Tempo total', value: 'tempoTotal' },
];

const TEMPO_TOTAL_CLASS: Record<SlaStatus, string> = {
  ok: 'text-gray-500',
  alerta: 'text-amber-600 font-medium',
  atrasado: 'text-red-600 font-medium',
};

// --- Filtros ---
const filtroNomePaciente = ref('');
const filtroCodigoInterno = ref('');
const filtroCodigoAghu = ref('');
const filtroEtapa = ref('');

const temFiltroAtivo = computed(() =>
  filtroNomePaciente.value.trim() !== '' ||
  filtroCodigoInterno.value.trim() !== '' ||
  filtroCodigoAghu.value.trim() !== '' ||
  filtroEtapa.value !== ''
);

function limparFiltros() {
  filtroNomePaciente.value = '';
  filtroCodigoInterno.value = '';
  filtroCodigoAghu.value = '';
  filtroEtapa.value = '';
}

function selecionarEtapaCard(etapa: string) {
  filtroEtapa.value = filtroEtapa.value === etapa ? '' : etapa;
}

const modalAberto = ref(false);
const detalheSelecionado = ref<ExamCaseDetail | null>(null);

async function verDetalhes(item: any) {
  try {
    const d = await exameService.detalhe(item.id);
    detalheSelecionado.value = mapExameDetalhe(d);
    modalAberto.value = true;
  } catch {
    // interceptor exibe erro
  }
}

interface ExameDashboardItem {
  id: string;
  solicitacao: string;
  codigoAghu: string;
  paciente: string;
  etapa: string;
  atrasado: boolean;
  frascos: number;
  dataEntrada: Date;
  // Quando alguém assumiu o exame na macroscopia.
  dataInicioTrabalho?: Date;
  responsavel?: string | null;
}

const exames = ref<ExameDashboardItem[]>([]);
const resumo = ref<{ por_status: Record<string, number>; atrasados: number; alerta: number }>({ por_status: {}, atrasados: 0, alerta: 0 });
const carregando = ref(true);
const pagina = ref(1);
const total = ref(0);

// Filtro digitado e troca de página geram respostas fora de ordem; a anterior
// é abortada para a última resposta não sobrescrever a busca atual.
let controlador: AbortController | null = null;

async function carregarPagina() {
  controlador?.abort();
  controlador = new AbortController();
  carregando.value = true;
  try {
    const filtros: DashboardFilterParams = {};
    if (filtroEtapa.value) filtros.etapa = filtroEtapa.value;
    if (filtroCodigoAghu.value.trim()) filtros.codigo_aghu = filtroCodigoAghu.value.trim();
    if (filtroCodigoInterno.value.trim()) filtros.codigo_interno = filtroCodigoInterno.value.trim();
    if (filtroNomePaciente.value.trim()) filtros.nome_paciente = filtroNomePaciente.value.trim();

    const dados = await exameService.dashboardPaginado({
      pagina: pagina.value,
      por_pagina: POR_PAGINA,
      signal: controlador.signal,
      ...filtros,
    });
    total.value = dados.total;
    exames.value = dados.itens.map(e => ({
      id: e.id,
      solicitacao: e.solicitacao,
      codigoAghu: e.codigo_aghu || '—',
      paciente: e.paciente,
      etapa: e.etapa,
      atrasado: e.atrasado,
      frascos: e.total_frascos,
      dataEntrada: parseDataApi(e.data_entrada) ?? new Date(),
      dataInicioTrabalho: parseDataApi(e.data_inicio_trabalho) ?? undefined,
      responsavel: e.responsavel_macroscopia_nome,
    }));
  } catch (erro: any) {
    if (erro?.code !== 'ERR_CANCELED') exames.value = [];
  } finally {
    carregando.value = false;
  }
}

// Debounce só nos campos de texto; a etapa vem de select/card e é imediata.
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

watch([filtroNomePaciente, filtroCodigoInterno, filtroCodigoAghu], () => {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    pagina.value = 1;   // filtro novo, resultado novo: volta para a primeira página
    carregarPagina();
  }, 300);
});

watch(filtroEtapa, () => {
  pagina.value = 1;
  carregarPagina();
});

watch(pagina, carregarPagina);

onMounted(async () => {
  // O resumo é agregado no banco e cobre a base inteira; só a lista pagina.
  exameService.resumoDashboard().then(d => { resumo.value = d; }).catch(() => {});
  await carregarPagina();
});

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
  controlador?.abort();
});

const examesComSla = computed(() => {
  return exames.value.map(exame => {
    const dias = diasDesde(exame.dataEntrada);
    const slaStatus = getSlaStatus(dias);
    return {
      ...exame,
      tempoInicioTrabalhoFormatado: exame.dataInicioTrabalho
        ? formatTempoTotal(diasDesde(exame.dataInicioTrabalho))
        : '—',
      tempoTotalFormatado: formatTempoTotal(dias),
      slaStatus,
    };
  });
});

const qtdAtrasados = computed(() => resumo.value.atrasados);
const qtdNoAlerta = computed(() => resumo.value.alerta);

const statusCards = computed(() => {
  return EXAM_STATUSES.map(status => ({
    label: status,
    count: resumo.value.por_status[status] ?? 0,
  }));
});
</script>
