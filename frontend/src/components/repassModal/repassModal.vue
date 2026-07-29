<template>
  <Modal :show="show" @close="$emit('close')">
    <template #header>
      <h2 class="text-lg font-bold text-lab-text">Repassar Exame</h2>
    </template>

    <div class="space-y-4">
      <div class="bg-gray-50 border border-gray-100 p-3 rounded-sm text-sm">
        <p class="text-[10px] font-semibold text-gray-400 uppercase">Exame</p>
        <p class="font-mono font-bold text-lab-text mt-1">{{ codigoLocal }}</p>
        <p class="text-gray-600 mt-0.5">{{ nomePaciente }}</p>
      </div>

      <div>
        <label class="form-label" for="destinatario">Repassar para *</label>
        <select id="destinatario" v-model="destinatario" class="form-control">
          <option value="" disabled>Selecione o responsável...</option>
          <option
            v-for="nome in responsaveisDisponiveis"
            :key="nome"
            :value="nome"
          >
            {{ nome }}
          </option>
        </select>
      </div>

      <div>
        <label class="form-label" for="motivoRepasse">Motivo (opcional)</label>
        <textarea
          id="motivoRepasse"
          v-model="motivo"
          rows="2"
          class="form-control"
          placeholder="Ex: Ausência, sobrecarga de trabalho..."
        ></textarea>
      </div>
    </div>

    <template #footer>
      <div class="flex gap-3 justify-end">
        <Button variant="default" @click="$emit('close')">Cancelar</Button>
        <Button variant="primary" :disabled="!destinatario" :loading="enviando" @click="confirmar">
          Confirmar Repasse
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useToast } from 'vue-toastification';
import Modal from '../modal/modal.vue';
import Button from '../button/button.vue';
import { RESPONSAVEIS_MACROSCOPIA } from '../../constants/staffMembers';
import { useAuthStore } from '../../stores/auth';

const props = defineProps<{
  show: boolean;
  codigoLocal: string;
  nomePaciente: string;
  frascoId: string;
}>();

const emit = defineEmits<{
  close: [];
  repassado: [destinatario: string];
}>();

const toast = useToast();
const authStore = useAuthStore();
const destinatario = ref('');
const motivo = ref('');
const enviando = ref(false);

// Remove o usuário logado da lista (não faz sentido repassar pra si mesmo).
const responsaveisDisponiveis = computed(() =>
  RESPONSAVEIS_MACROSCOPIA.filter(n => n !== authStore.user?.givenName?.[0])
);

async function confirmar() {
  if (!destinatario.value) return;
  enviando.value = true;
  try {
    // TODO: chamar endpoint de repasse quando existir no backend.
    // await exameService.repassarMacroscopia(props.frascoId, {
    //   destinatario: destinatario.value,
    //   motivo: motivo.value,
    // });

    // Salva o repasse pendente no localStorage pra simular a notificação
    // que o destinatário vai ver quando abrir o sistema.
    const repassesPendentes = JSON.parse(localStorage.getItem('repassesPendentes') || '[]');
    repassesPendentes.push({
      destinatario: destinatario.value,
      codigoLocal: props.codigoLocal,
      nomePaciente: props.nomePaciente,
      remetente: authStore.user?.givenName?.[0] || authStore.user?.username || 'Colega',
      motivo: motivo.value || null,
      timestamp: new Date().toISOString(),
    });
    localStorage.setItem('repassesPendentes', JSON.stringify(repassesPendentes));

    toast.success(`Exame repassado para ${destinatario.value} com sucesso.`);
    emit('repassado', destinatario.value);
    emit('close');
  } catch {
    // interceptor exibe erro
  } finally {
    enviando.value = false;
  }
}
</script>