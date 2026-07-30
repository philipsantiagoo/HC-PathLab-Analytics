<template>
  <Card>
    <template #header>
      <h2 class="text-lg font-bold text-lab-text">Assumir Exame</h2>
      <p class="text-sm text-gray-500">O exame fica sob sua responsabilidade até ser repassado</p>
    </template>

    <div class="space-y-4">
      <!-- Livre -->
      <div v-if="!posse.responsavel" class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 border border-gray-200">
        <ClockIcon class="h-5 w-5 shrink-0 text-gray-400 mt-0.5" />
        <p class="text-sm text-gray-600">
          Este exame ainda não foi assumido. Ao assumir, os
          <strong>{{ totalFrascos }} frasco(s)</strong> passam a andar com você.
        </p>
      </div>

      <!-- Com outra pessoa -->
      <div v-else-if="!posse.sou_o_dono" class="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
        <LockClosedIcon class="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
        <div class="text-sm">
          <p class="font-semibold text-amber-700">Em clivagem por {{ posse.responsavel_nome || posse.responsavel }}</p>
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

      <div class="flex flex-wrap gap-3 pt-2">
        <Button
          v-if="!posse.sou_o_dono"
          variant="primary"
          class="flex-1 min-w-[160px]"
          :disabled="enviando || !!posse.responsavel"
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
          Liberar para a fila
        </Button>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useToast } from 'vue-toastification';
import { ClockIcon, LockClosedIcon, CheckCircleIcon } from '@heroicons/vue/24/outline';
import Card from '../card/card.vue';
import Button from '../button/button.vue';
import { exameService, type PosseExame } from '../../services/exameService';
import { formatDateShort } from '../../utils/date';

const props = defineProps<{
  idExame: string;
  posse: PosseExame;
  totalFrascos: number;
}>();

const emit = defineEmits<{
  (e: 'atualizado'): void;
  (e: 'repassar'): void;
}>();

const toast = useToast();
// Trava o duplo clique; a barreira real contra corrida é o UPDATE condicional
// no backend, que devolve 409 para o segundo.
const enviando = ref(false);

async function assumir() {
  if (enviando.value) return;
  enviando.value = true;
  try {
    await exameService.assumirExame(props.idExame);
    toast.success('Exame assumido. Pode iniciar a clivagem.');
    emit('atualizado');
  } catch {
    // 409 já vem com a mensagem certa pelo interceptor; recarrega para o
    // estado local não continuar mentindo sobre quem é o dono.
    emit('atualizado');
  } finally {
    enviando.value = false;
  }
}

async function liberar() {
  if (enviando.value) return;
  enviando.value = true;
  try {
    await exameService.liberarExame(props.idExame);
    toast.success('Exame devolvido à fila.');
    emit('atualizado');
  } catch {
    emit('atualizado');
  } finally {
    enviando.value = false;
  }
}
</script>
