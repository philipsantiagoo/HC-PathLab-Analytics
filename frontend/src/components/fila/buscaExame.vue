<template>
  <Card>
    <template #header>
      <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
        <QrCodeIcon class="h-5 w-5 text-gray-400" />
        {{ titulo }}
      </h2>
      <p class="text-sm text-gray-500">{{ descricao }}</p>
    </template>

    <div class="flex flex-wrap items-end gap-3">
      <div class="flex-1 min-w-[220px] max-w-xs">
        <label class="form-label" :for="idCampo">{{ rotulo }}</label>
        <input
          :id="idCampo"
          v-model="codigo"
          type="text"
          class="form-control"
          :placeholder="placeholder"
          @keyup.enter="emit('buscar', codigo.trim())"
        >
      </div>
      <Button variant="primary" :disabled="!codigo.trim()" @click="emit('buscar', codigo.trim())">
        Buscar
      </Button>
      <Button v-if="mostrarVoltar" variant="default" @click="voltar">Voltar para a fila</Button>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { QrCodeIcon } from '@heroicons/vue/24/outline';
import Card from '../card/card.vue';
import Button from '../button/button.vue';

/**
 * Barra de leitura de código das estações.
 *
 * O leitor de QR Code é uma pistola HID: ele digita a string no campo e manda
 * um Enter. Por isso a busca é só um input com @keyup.enter — não há integração
 * de hardware envolvida.
 */
withDefaults(defineProps<{
  titulo: string;
  descricao: string;
  rotulo: string;
  placeholder?: string;
  idCampo?: string;
  mostrarVoltar?: boolean;
}>(), {
  placeholder: 'Digite ou bipe aqui',
  idCampo: 'codigoBusca',
  mostrarVoltar: false,
});

const emit = defineEmits<{
  (e: 'buscar', codigo: string): void;
  (e: 'voltar'): void;
}>();

const codigo = ref('');

function voltar() {
  codigo.value = '';
  emit('voltar');
}

defineExpose({ limpar: () => { codigo.value = ''; } });
</script>
