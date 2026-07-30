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

    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-4">
      <Card v-for="card in statusCards" :key="card.label">
        <p class="text-sm text-gray-500">{{ card.label }}</p>
        <p class="text-3xl font-bold text-lab-text mt-1">{{ card.count }}</p>
      </Card>
    </div>

    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text">Exames</h2>
        <p class="text-sm text-gray-500">
          Uma linha por exame — os frascos de um mesmo exame andam juntos.
          Início do trabalho: quando alguém assumiu o exame na macroscopia.
          Tempo total: relógio desde a entrada no sistema (meta: 20 dias).
        </p>
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
import { ref, computed, onMounted, watch } from 'vue';
import { ExclamationTriangleIcon, ClockIcon } from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import DataTable from '../components/dataTable/dataTable.vue';
import Badge from '../components/badge/badge.vue';
import ExamDetailsModal from '../components/examDetailsModal/examDetailsModal.vue';
import { STATUS_COLOR, EXAM_STATUSES } from '../constants/statuses';
import { diasDesde, getSlaStatus, formatTempoTotal, type SlaStatus } from '../utils/sla';
import type { ExamCaseDetail } from '../types/exam';
import { exameService, mapExameDetalhe } from '../services/exameService';
import { parseDataApi } from '../utils/date';

const POR_PAGINA = 10;

// "Chegada na etapa" foi removida: nunca teve fonte no backend e renderizava
// "—" em toda linha desde sempre. Recolocar exige uma coluna de carimbo por
// etapa, que não existe hoje.
const headers = [
  { text: 'Solicitação', value: 'solicitacao' },
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

// Trocas rápidas de página produzem respostas fora de ordem.
let controlador: AbortController | null = null;

async function carregarPagina() {
  controlador?.abort();
  controlador = new AbortController();
  carregando.value = true;
  try {
    const dados = await exameService.dashboardPaginado({
      pagina: pagina.value,
      por_pagina: POR_PAGINA,
      signal: controlador.signal,
    });
    total.value = dados.total;
    exames.value = dados.itens.map(e => ({
      id: e.id,
      solicitacao: e.solicitacao,
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

onMounted(async () => {
  // O resumo é agregado no banco e cobre a base inteira; só a lista pagina.
  exameService.resumoDashboard().then(d => { resumo.value = d; }).catch(() => {});
  await carregarPagina();
});

watch(pagina, carregarPagina);

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
