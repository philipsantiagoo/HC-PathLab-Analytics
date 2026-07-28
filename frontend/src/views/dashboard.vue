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
        <h2 class="text-lg font-bold text-lab-text">Últimos exames movimentados</h2>
        <p class="text-sm text-gray-500">
          Chegada na etapa: quando o caso entrou na fase atual.
          Início do trabalho: quando alguém efetivamente iniciou ação nessa fase.
          Tempo total: relógio desde a entrada no sistema (meta: 20 dias).
        </p>
      </template>

      <DataTable :headers="headers" :items="examesComSla">
        <template #item-etapa="{ item }">
          <Badge :color="STATUS_COLOR[item.etapa]">{{ item.etapa }}</Badge>
        </template>

        <template #item-tempoChegadaEtapa="{ item }">
          <span class="text-gray-500">{{ item.tempoChegadaEtapaFormatado }}</span>
        </template>

        <template #item-tempoInicioTrabalho="{ item }">
          <span :class="item.atrasado ? 'text-red-600 font-medium' : 'text-gray-500'">
            {{ item.tempoInicioTrabalhoFormatado }}
          </span>
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
import { ref, computed, onMounted } from 'vue';
import { ExclamationTriangleIcon, ClockIcon } from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import DataTable from '../components/dataTable/dataTable.vue';
import Badge from '../components/badge/badge.vue';
import ExamDetailsModal from '../components/examDetailsModal/examDetailsModal.vue';
import { STATUS_COLOR, EXAM_STATUSES } from '../constants/statuses';
import { diasDesde, getSlaStatus, formatTempoTotal, type SlaStatus } from '../utils/sla';
import type { ExamCaseDetail } from '../types/exam';
import { exameService, mapExameDetalhe } from '../services/exameService';

const headers = [
  { text: 'Solicitação', value: 'solicitacao' },
  { text: 'Paciente', value: 'paciente' },
  { text: 'Etapa', value: 'etapa' },
  { text: 'Chegada na etapa', value: 'tempoChegadaEtapa' },
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
  dataEntrada: Date;
  // Quando o caso chegou nessa etapa específica (ex: saiu da Recepção e chegou na Macroscopia)
  dataChegadaEtapa?: Date;
  // Quando alguém efetivamente iniciou ação nessa etapa (assumiu, abriu o frasco etc.)
  dataInicioTrabalho?: Date;
}

const exames = ref<ExameDashboardItem[]>([]);

onMounted(async () => {
  const dados = await exameService.dashboard();
  exames.value = dados.map(e => ({
    id: e.id,
    solicitacao: e.solicitacao,
    paciente: e.paciente,
    etapa: e.etapa,
    atrasado: e.atrasado,
    dataEntrada: new Date(e.data_entrada),
    dataChegadaEtapa: e.data_chegada_etapa ? new Date(e.data_chegada_etapa) : undefined,
    dataInicioTrabalho: e.data_inicio_trabalho ? new Date(e.data_inicio_trabalho) : undefined,
  }));
});

const examesComSla = computed(() => {
  return exames.value.map(exame => {
    const dias = diasDesde(exame.dataEntrada);
    const slaStatus = getSlaStatus(dias);
    return {
      ...exame,
      tempoChegadaEtapaFormatado: exame.dataChegadaEtapa
        ? formatTempoTotal(diasDesde(exame.dataChegadaEtapa))
        : '—',
      tempoInicioTrabalhoFormatado: exame.dataInicioTrabalho
        ? formatTempoTotal(diasDesde(exame.dataInicioTrabalho))
        : '—',
      tempoTotalFormatado: formatTempoTotal(dias),
      slaStatus,
    };
  });
});

const qtdAtrasados = computed(() => examesComSla.value.filter(e => e.slaStatus === 'atrasado').length);
const qtdNoAlerta = computed(() => examesComSla.value.filter(e => e.slaStatus === 'alerta').length);

const statusCards = computed(() => {
  return EXAM_STATUSES.map(status => ({
    label: status,
    count: exames.value.filter(e => e.etapa === status).length,
  }));
});
</script>