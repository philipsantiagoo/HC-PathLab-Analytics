<template>
  <Card>
    <template #header>
      <h2 class="text-lg font-bold text-lab-text">Visão Unificada do Caso</h2>
      <p class="text-sm text-gray-500">Dados demográficos, clínicos e de recepção (somente leitura)</p>
    </template>
    <div class="space-y-4 text-sm">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="text-[10px] font-semibold text-gray-400 uppercase">Paciente</p>
          <p class="font-bold text-lab-text text-base">{{ caso.aghu.nomePaciente }}</p>
        </div>
        <Badge v-if="caso.urgente" color="red">Urgente</Badge>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-[10px] font-semibold text-gray-400 uppercase">Prontuário</p>
          <p class="text-gray-700">{{ caso.aghu.prontuario }}</p>
        </div>
        <div>
          <p class="text-[10px] font-semibold text-gray-400 uppercase">Solicitação AGHU</p>
          <p class="text-gray-700">{{ caso.aghu.numeroSolicitacaoAghu }}</p>
        </div>
        <div>
          <p class="text-[10px] font-semibold text-gray-400 uppercase">Código local</p>
          <p class="text-gray-700 font-mono">{{ caso.codigoLocal }}</p>
        </div>
        <div>
          <p class="text-[10px] font-semibold text-gray-400 uppercase">Responsável</p>
          <p class="text-gray-700">{{ responsavel || '—' }}</p>
        </div>
      </div>

      <div>
        <p class="text-[10px] font-semibold text-gray-400 uppercase">Procedimento solicitado</p>
        <p class="text-gray-700">{{ caso.aghu.procedimentoSus }}</p>
      </div>

      <div class="bg-gray-50 border border-gray-100 p-3 rounded-sm">
        <p class="text-[10px] font-semibold text-gray-500 uppercase">Descrição (médico solicitante)</p>
        <p class="text-gray-700 mt-1">{{ caso.aghu.tipoMaterial || 'Não informado.' }}</p>
      </div>

      <div v-if="caso.recepcao" class="border-t border-gray-100 pt-4">
        <p class="text-xs font-bold text-gray-500 uppercase mb-2">Dados da Recepção</p>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-[10px] font-semibold text-gray-400 uppercase">Recebido em</p>
            <p class="text-gray-700">{{ formatDateShort(caso.recepcao.dataEntrada) }}</p>
          </div>
          <div>
            <p class="text-[10px] font-semibold text-gray-400 uppercase">Qtd. frascos</p>
            <p class="text-gray-700">{{ caso.recepcao.quantidadeFrascos }}</p>
          </div>
        </div>
        <div class="mt-3">
          <p class="text-[10px] font-semibold text-gray-400 uppercase">Material confirmado na Recepção</p>
          <p class="text-gray-700">{{ caso.recepcao.descricaoFisica }}</p>
        </div>
      </div>

      <!-- Os frascos do exame andam juntos; ficam listados só para conferência. -->
      <div v-if="frascos.length" class="border-t border-gray-100 pt-4">
        <p class="text-xs font-bold text-gray-500 uppercase mb-2">Frascos deste exame ({{ frascos.length }})</p>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="frasco in frascos"
            :key="frasco.id"
            class="font-mono text-[10px] bg-gray-100 text-gray-600 px-2 py-1 rounded"
            :title="frasco.status"
          >
            {{ frasco.codigo_interno }}
          </span>
        </div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import Card from '../card/card.vue';
import Badge from '../badge/badge.vue';
import { formatDateShort } from '../../utils/date';
import type { ExamCaseDetail } from '../../types/exam';
import type { FrascoOut } from '../../services/exameService';

defineProps<{
  caso: ExamCaseDetail;
  frascos: FrascoOut[];
  responsavel?: string | null;
}>();
</script>
