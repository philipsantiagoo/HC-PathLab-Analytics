<template>
  <div class="flex flex-col items-center bg-white border-2 border-dashed border-gray-300 p-4 rounded-lg w-64">
    <qrcode-vue :value="codigoEtiqueta" :size="150" level="H" />
    
    <div class="mt-4 text-center w-full">
      <h3 class="font-bold text-lg text-gray-800">{{ titulo }}</h3>
      <p class="text-sm text-gray-600 truncate">{{ subtitulo }}</p>
      <p class="text-xs text-gray-400 mt-1 font-mono">{{ codigoEtiqueta }}</p>
    </div>

    <div class="mt-4 flex gap-2 w-full">
      <button 
        @click="imprimir" 
        class="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded text-sm transition-colors"
      >
        Imprimir
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import QrcodeVue from 'qrcode.vue'

// O que este componente recebe de quem o chama (Props)
const props = defineProps<{
  codigoEtiqueta: string; // O ID que vai dentro do QR Code (Ex: "F-442806-01")
  titulo: string;         // Ex: "Frasco 01" ou "Lâmina H&E"
  subtitulo: string;      // Ex: O nome do paciente para dupla checagem visual
}>();

// Função para simular a impressão
const imprimir = () => {
  // No futuro, isso pode enviar um comando ZPL para o backend (Zebra).
  // Por enquanto, aciona a impressão do navegador ou um alerta.
  console.log(`Enviando comando de impressão para a etiqueta: ${props.codigoEtiqueta}`);
  window.print(); 
};
</script>

<style scoped>
/* Ao imprimir a página (window.print), escondemos tudo exceto a etiqueta */
@media print {
  body * {
    visibility: hidden;
  }
  .flex-col, .flex-col * {
    visibility: visible;
  }
  .flex-col {
    position: absolute;
    left: 0;
    top: 0;
    border: none; /* Remove a borda tracejada na impressão real */
  }
  button {
    display: none; /* Esconde o botão na hora de imprimir o papel */
  }
}
</style>