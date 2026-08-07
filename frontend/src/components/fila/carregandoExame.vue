<!--
  Placeholder das estações de bancada enquanto o exame carrega.

  Sem ele, as telas exibiam "não encontrado" no instante em que a busca começava
  — o cartão de erro só depende de "já buscou" e o dado ainda não voltou. Quem
  clicava em assumir um exame lia "não existe" antes de ver o caso.
-->
<template>
  <Card>
    <div class="flex items-center gap-3 p-2">
      <span
        class="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-gray-200 border-t-lab-primary"
        aria-hidden="true"
      ></span>
      <p class="text-sm text-gray-600" role="status" aria-live="polite">{{ mensagem }}</p>
    </div>
  </Card>
</template>

<script setup lang="ts">
import Card from '../card/card.vue';

withDefaults(defineProps<{ mensagem?: string }>(), {
  mensagem: 'Carregando exame...',
});
</script>
