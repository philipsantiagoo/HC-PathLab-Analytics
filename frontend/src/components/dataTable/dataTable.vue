<template>
  <div class="w-full">
    <div class="w-full overflow-x-auto rounded-lg shadow-xs">
      <table class="w-full whitespace-no-wrap">
        <thead>
          <tr class="text-xs font-semibold tracking-wider text-gray-500 uppercase border-b border-gray-200 bg-gray-50">
            <th
              v-for="header in headers"
              :key="header.value"
              class="px-4 py-2"
              :class="[header.align === 'center' ? 'text-center' : header.align === 'right' ? 'text-right' : 'text-left']"
            >
              {{ header.text }}
            </th>
            <th v-if="$slots.actions" class="px-4 py-2 text-center"></th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-100">
          <tr
            v-for="item in paginatedItems"
            :key="item.id"
            class="text-gray-700 hover:bg-gray-100"
            :class="{ 'cursor-pointer': clickableRows }"
            @click="clickableRows && emit('row-click', item)"
          >
            <td
              v-for="header in headers"
              :key="header.value"
              class="px-4 py-3 text-sm"
              :class="[header.align === 'center' ? 'text-center' : header.align === 'right' ? 'text-right' : 'text-left']"
            >
              <slot :name="`item-${header.value}`" :item="item">
                {{ item[header.value] }}
              </slot>
            </td>
            <td v-if="$slots.actions" class="px-4 py-3 text-sm text-center">
              <slot name="actions" :item="item"></slot>
            </td>
          </tr>
          <!-- Enquanto carrega não mostramos o vazio: em modo servidor toda
               troca de página passaria por "Nenhum dado encontrado". -->
          <tr v-if="loading">
            <td :colspan="totalColunas" class="px-6 py-6 text-center text-gray-400">
              <span class="inline-flex items-center gap-2">
                <span class="h-4 w-4 rounded-full border-2 border-gray-300 border-t-lab-primary animate-spin"></span>
                Carregando...
              </span>
            </td>
          </tr>
          <tr v-else-if="items.length === 0">
            <td :colspan="totalColunas" class="px-6 py-4 text-center text-gray-500">
              Nenhum dado encontrado.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="totalPages > 1" class="flex flex-wrap items-center justify-center gap-3 mt-4">
      <button
        @click="currentPage = 1"
        :disabled="currentPage === 1"
        class="px-2 py-1 rounded-md text-xs font-medium text-gray-500 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        Primeira
      </button>
      <button
        @click="currentPage--"
        :disabled="currentPage === 1"
        class="p-2 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        <ChevronLeftIcon class="h-5 w-5" />
      </button>

      <span class="text-sm text-gray-500">
        Página
        <input
          :value="currentPage"
          @change="irPara(($event.target as HTMLInputElement).value)"
          type="number"
          min="1"
          :max="totalPages"
          class="w-16 mx-1 px-2 py-1 text-center border border-gray-300 rounded-md text-sm"
        >
        de {{ totalPages }}
        <span class="text-gray-400">· {{ totalRegistros }} registro(s)</span>
      </span>

      <button
        @click="currentPage++"
        :disabled="currentPage === totalPages"
        class="p-2 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        <ChevronRightIcon class="h-5 w-5" />
      </button>
      <button
        @click="currentPage = totalPages"
        :disabled="currentPage === totalPages"
        class="px-2 py-1 rounded-md text-xs font-medium text-gray-500 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        Última
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, useSlots } from 'vue';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/vue/24/outline';

interface Header {
  text: string;
  value: string;
  align?: 'left' | 'center' | 'right'; // Nova propriedade opcional
}

interface Item {
  id: number | string;
  [key: string]: any;
}

const props = defineProps({
  headers: {
    type: Array as () => Header[],
    required: true,
  },
  items: {
    type: Array as () => Item[],
    required: true,
  },
  pageSize: {
    type: Number,
    default: 7, // Mantido em 7 itens por página
  },
  // Opt-in: só as tabelas que tratam 'row-click' ganham cursor e clique na linha.
  clickableRows: {
    type: Boolean,
    default: false,
  },
  // --- Modo servidor -------------------------------------------------
  // Com serverSide, 'items' já é a página pronta: o componente não fatia
  // nada e delega a troca de página ao pai via v-model:page.
  serverSide: {
    type: Boolean,
    default: false,
  },
  total: {
    type: Number,
    default: 0,
  },
  page: {
    type: Number,
    default: 1,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits<{
  (e: 'row-click', item: Item): void;
  (e: 'update:page', pagina: number): void;
}>();

const slots = useSlots();
const totalColunas = computed(() => props.headers.length + (slots.actions ? 1 : 0));

const paginaLocal = ref(1);
const currentPage = computed({
  get: () => (props.serverSide ? props.page : paginaLocal.value),
  set: (valor: number) => {
    const alvo = Math.min(Math.max(1, valor), totalPages.value);
    if (props.serverSide) emit('update:page', alvo);
    else paginaLocal.value = alvo;
  },
});

const totalRegistros = computed(() => (props.serverSide ? props.total : props.items.length));
const totalPages = computed(() => Math.max(1, Math.ceil(totalRegistros.value / props.pageSize)));

const paginatedItems = computed(() => {
  if (props.serverSide) return props.items;
  const start = (currentPage.value - 1) * props.pageSize;
  return props.items.slice(start, start + props.pageSize);
});

function irPara(valor: string) {
  const n = Number(valor);
  if (Number.isFinite(n)) currentPage.value = n;
}

watch(() => props.items.length, () => {
  // Em modo servidor quem manda na página é o pai; mexer aqui causaria
  // disputa pelo controle a cada resposta.
  if (props.serverSide) return;
  if (paginaLocal.value > totalPages.value) {
    paginaLocal.value = 1;
  }
});
</script>
