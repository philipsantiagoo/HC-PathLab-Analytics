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
        <p class="text-[10px] text-gray-400 uppercase mt-2">{{ rotuloEtapa }}</p>
      </div>

      <div>
        <label class="form-label" for="destinatario">Repassar para *</label>
        <select id="destinatario" v-model="destinatario" class="form-control" :disabled="carregandoUsuarios">
          <option value="" disabled>
            {{ carregandoUsuarios ? 'Carregando usuários...' : 'Selecione o responsável...' }}
          </option>
          <option v-for="u in candidatos" :key="u.username" :value="u.username">
            {{ u.nome_exibicao || u.username }}
          </option>
        </select>
        <p v-if="!carregandoUsuarios && !candidatos.length" class="text-xs text-amber-600 mt-1">
          Nenhum outro usuário disponível. Os nomes aparecem aqui depois do primeiro acesso de cada pessoa.
        </p>
      </div>

      <div>
        <label class="form-label" for="motivoRepasse">Motivo *</label>
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
        <Button variant="primary" :disabled="!podeConfirmar" :loading="enviando" @click="confirmar">
          Confirmar Repasse
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import Modal from '../modal/modal.vue';
import Button from '../button/button.vue';
import { etapaService, type Etapa, type UsuarioCandidato } from '../../services/etapaService';
import { useAuthStore } from '../../stores/auth';

/**
 * Repasse de posse, comum às quatro estações.
 *
 * A ``etapa`` decide para qual endpoint o repasse vai e também filtra os
 * candidatos: o backend coloca no topo quem já atuou naquele setor.
 */
const props = defineProps<{
  show: boolean;
  etapa: Etapa;
  idExame: string;
  codigoLocal: string;
  nomePaciente: string;
}>();

const emit = defineEmits<{
  close: [];
  repassado: [destinatario: string];
}>();

const ROTULO_ETAPA: Record<Etapa, string> = {
  macroscopia: 'Macroscopia',
  processamento: 'Processamento Técnico',
  microscopia: 'Microscopia',
  congelamento: 'Congelamento',
};

const authStore = useAuthStore();
const destinatario = ref('');
const motivo = ref('');
const enviando = ref(false);
const carregandoUsuarios = ref(false);
const candidatos = ref<UsuarioCandidato[]>([]);

const rotuloEtapa = computed(() => ROTULO_ETAPA[props.etapa]);
// O motivo fica na trilha de auditoria (movimentações) — por isso obrigatório.
const podeConfirmar = computed(() => !!destinatario.value && motivo.value.trim().length >= 3 && !enviando.value);

// O modal fica sempre montado no pai, então carregamos ao abrir e não no mount.
watch(() => props.show, async aberto => {
  if (!aberto) return;
  destinatario.value = '';
  motivo.value = '';
  carregandoUsuarios.value = true;
  try {
    const lista = await etapaService.candidatos(props.etapa);
    // Não faz sentido repassar para si mesmo. A comparação é por username: o
    // nome de exibição não é chave e nunca casava para usuário de AD real.
    candidatos.value = lista.filter(u => u.username !== authStore.user?.username);
  } catch {
    candidatos.value = [];
  } finally {
    carregandoUsuarios.value = false;
  }
});

async function confirmar() {
  if (!podeConfirmar.value) return;
  enviando.value = true;
  try {
    const escolhido = candidatos.value.find(u => u.username === destinatario.value);
    await etapaService.repassar(props.etapa, props.idExame, {
      para_username: destinatario.value,
      para_nome: escolhido?.nome_exibicao ?? undefined,
      motivo: motivo.value.trim(),
    });
    emit('repassado', escolhido?.nome_exibicao || destinatario.value);
    emit('close');
  } catch {
    // interceptor exibe erro
  } finally {
    enviando.value = false;
  }
}
</script>
