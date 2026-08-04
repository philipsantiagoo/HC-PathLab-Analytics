<template>
  <Card>
    <template #header>
      <h2 class="text-lg font-bold text-lab-text">Posse do Exame</h2>
      <p class="text-sm text-gray-500">
        O exame inteiro fica sob sua responsabilidade até ser concluído ou repassado
      </p>
    </template>

    <div class="space-y-4">
      <!-- Livre -->
      <div v-if="!posse.responsavel" class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 border border-gray-200">
        <ClockIcon class="h-5 w-5 shrink-0 text-gray-400 mt-0.5" />
        <p class="text-sm text-gray-600">
          Este exame ainda não foi assumido<span v-if="descricaoEscopo">. Ao assumir, {{ descricaoEscopo }}</span>.
        </p>
      </div>

      <!-- Com outra pessoa -->
      <div v-else-if="!posse.sou_o_dono" class="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
        <LockClosedIcon class="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
        <div class="text-sm">
          <p class="font-semibold text-amber-700">
            Com {{ posse.responsavel_nome || posse.responsavel }}
          </p>
          <p class="text-amber-700/80 mt-0.5">
            Desde {{ formatDateShort(posse.assumido_em) }}. Só essa pessoa pode repassar o exame.
          </p>
        </div>
      </div>

      <!-- Meu -->
      <div v-else class="flex items-start gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
        <CheckCircleIcon class="h-5 w-5 shrink-0 text-green-600 mt-0.5" />
        <p class="text-sm text-green-700">
          Exame assumido por você em {{ formatDateShort(posse.assumido_em) }}.
        </p>
      </div>

      <!-- Papel esperado (microscopia) -->
      <div v-if="papelEsperado" class="flex items-center gap-2 text-xs text-gray-500">
        <UserIcon class="h-4 w-4 shrink-0" />
        Etapa aguardando: <strong class="text-gray-700">{{ papelEsperado }}</strong>
        <span v-if="posse.ciclo > 1" class="text-gray-400">· ciclo {{ posse.ciclo }}</span>
      </div>

      <div class="flex flex-wrap gap-3 pt-2">
        <Button
          v-if="!posse.sou_o_dono"
          variant="primary"
          class="flex-1 min-w-[160px]"
          :disabled="enviando || !posse.pode_assumir"
          @click="assumir"
        >
          Assumir exame
        </Button>
        <Button
          v-if="posse.sou_o_dono"
          variant="default"
          class="flex-1 min-w-[160px]"
          :disabled="enviando"
          @click="emit('repassar')"
        >
          Repassar
        </Button>
        <Button
          v-if="posse.pode_liberar"
          variant="default"
          class="flex-1 min-w-[160px]"
          :disabled="enviando"
          @click="liberar"
        >
          Devolver à fila
        </Button>
      </div>

      <!-- Trilha das etapas: onde o exame já passou e com quem. -->
      <div v-if="historico.length > 1" class="border-t border-gray-100 pt-3">
        <p class="text-[10px] font-semibold text-gray-400 uppercase mb-2">Percurso do exame</p>
        <ol class="space-y-1.5">
          <li
            v-for="(e, i) in historico"
            :key="`${e.etapa}-${e.ciclo}-${i}`"
            class="flex items-center justify-between gap-3 text-xs"
          >
            <span class="text-gray-600">
              {{ rotuloEtapa(e.etapa) }}
              <span v-if="e.ciclo > 1" class="text-gray-400">(ciclo {{ e.ciclo }})</span>
              <span v-if="e.responsavel_nome" class="text-gray-400">· {{ e.responsavel_nome }}</span>
            </span>
            <Badge :color="e.situacao === 'CONCLUIDA' ? 'green' : e.situacao === 'EM_ANDAMENTO' ? 'blue' : 'gray'">
              {{ rotuloSituacao(e.situacao) }}
            </Badge>
          </li>
        </ol>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useToast } from 'vue-toastification';
import { ClockIcon, LockClosedIcon, CheckCircleIcon, UserIcon } from '@heroicons/vue/24/outline';
import Card from '../card/card.vue';
import Badge from '../badge/badge.vue';
import Button from '../button/button.vue';
import {
  etapaService,
  rotuloSituacao,
  type Etapa,
  type EtapaHistorico,
  type Posse,
} from '../../services/etapaService';
import { formatDateShort } from '../../utils/date';

/**
 * Card de posse comum às quatro estações: assumir, repassar e devolver à fila.
 *
 * O botão "Assumir" fica sempre visível; quem barra a segunda pessoa é o
 * UPDATE condicional do backend, que devolve 409 nomeando o dono atual.
 */

const props = defineProps<{
  etapa: Etapa;
  idExame: string;
  posse: Posse;
  historico?: EtapaHistorico[];
  /** Frase completando "Ao assumir, ...". Ex.: "os 3 frascos passam a andar com você". */
  descricaoEscopo?: string;
  papelEsperado?: string | null;
}>();

const emit = defineEmits<{
  (e: 'atualizado'): void;
  (e: 'repassar'): void;
}>();

const toast = useToast();
// Trava o duplo clique; a barreira real contra corrida é o UPDATE condicional
// no backend, que devolve 409 para o segundo.
const enviando = ref(false);

const historico = computed(() => props.historico ?? []);

const ROTULO_ETAPA: Record<string, string> = {
  MACROSCOPIA: 'Macroscopia',
  PROCESSAMENTO: 'Processamento',
  MICROSCOPIA: 'Microscopia',
  CONGELAMENTO: 'Congelamento',
};

function rotuloEtapa(etapa: string) {
  return ROTULO_ETAPA[etapa] ?? etapa;
}

async function assumir() {
  if (enviando.value) return;
  enviando.value = true;
  try {
    await etapaService.assumir(props.etapa, props.idExame);
    toast.success('Exame assumido.');
  } catch {
    // O 409 já vem com a mensagem certa pelo interceptor. Recarrega de todo
    // jeito, para o estado local não continuar mentindo sobre quem é o dono.
  } finally {
    enviando.value = false;
    emit('atualizado');
  }
}

async function liberar() {
  if (enviando.value) return;
  enviando.value = true;
  try {
    await etapaService.liberar(props.etapa, props.idExame);
    toast.success('Exame devolvido à fila.');
  } catch {
    // interceptor exibe o erro
  } finally {
    enviando.value = false;
    emit('atualizado');
  }
}
</script>
