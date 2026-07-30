<template>
  <Card>
    <template #header>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-lab-text">Fila da Macroscopia</h2>
          <p class="text-sm text-gray-500">Exames aguardando processamento nesta etapa</p>
        </div>
        <button
          class="text-sm font-medium text-lab-primary hover:underline inline-flex items-center gap-1 shrink-0"
          @click="carregar()"
        >
          <ArrowPathIcon class="h-4 w-4" :class="{ 'animate-spin': carregando }" />
          Atualizar
        </button>
      </div>
    </template>

    <div class="space-y-4">
      <TabBar v-model="abaAtual" :tabs="abas" />

      <DataTable
        :headers="headers"
        :items="itens"
        server-side
        :total="total"
        :loading="carregando"
        :page-size="POR_PAGINA"
        v-model:page="pagina"
        clickable-rows
        @row-click="abrir"
      >
        <template #item-tipoExame="{ item }">
          <span class="font-mono text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
            {{ item.tipoExame }}
          </span>
        </template>
        <template #item-status="{ item }">
          <div class="flex flex-col gap-0.5">
            <Badge :color="item.emAndamento ? 'blue' : 'gray'">{{ item.status }}</Badge>
            <span v-if="item.responsavel" class="text-[10px] text-gray-400">{{ item.responsavel }}</span>
          </div>
        </template>
        <template #actions="{ item }">
          <button @click.stop="abrir(item)" class="text-xs font-medium text-lab-primary hover:underline">
            Abrir
          </button>
        </template>
      </DataTable>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import { ArrowPathIcon } from '@heroicons/vue/24/outline';
import Card from '../card/card.vue';
import Badge from '../badge/badge.vue';
import DataTable from '../dataTable/dataTable.vue';
import TabBar from '../tabBar/tabBar.vue';
import { exameService, type ContadoresFilaMacro, type FiltroFilaMacro } from '../../services/exameService';
import { formatDateShort } from '../../utils/date';

const POR_PAGINA = 10;

const props = defineProps<{ busca?: string }>();
const emit = defineEmits<{ (e: 'abrir', idExame: string): void }>();

interface LinhaFila {
  id: string;
  solicitacao: string;
  paciente: string;
  tipoExame: string;
  frascos: number;
  status: string;
  responsavel: string | null;
  emAndamento: boolean;
}

const headers = [
  { text: 'Código', value: 'solicitacao' },
  { text: 'Paciente', value: 'paciente' },
  { text: 'Tipo', value: 'tipoExame' },
  { text: 'Frascos', value: 'frascos', align: 'center' as const },
  { text: 'Status', value: 'status' },
];

const abaAtual = ref<FiltroFilaMacro>('meus');
const pagina = ref(1);
const itens = ref<LinhaFila[]>([]);
const total = ref(0);
const carregando = ref(false);
const contadores = ref<ContadoresFilaMacro>({ meus: 0, aguardando: 0, em_andamento: 0, todos: 0 });

const abas = computed(() => [
  { value: 'meus', label: 'Meus exames', count: contadores.value.meus },
  { value: 'aguardando', label: 'Aguardando', count: contadores.value.aguardando },
  { value: 'em_andamento', label: 'Em andamento', count: contadores.value.em_andamento },
  { value: 'todos', label: 'Todos', count: contadores.value.todos },
]);

// Troca rápida de aba gera respostas fora de ordem; a anterior é abortada.
let controlador: AbortController | null = null;
let jaAjustouAbaInicial = false;

async function carregar() {
  controlador?.abort();
  controlador = new AbortController();
  carregando.value = true;
  try {
    const dados = await exameService.filaMacroscopia({
      filtro: abaAtual.value,
      pagina: pagina.value,
      por_pagina: POR_PAGINA,
      busca: props.busca || undefined,
      signal: controlador.signal,
    });
    itens.value = dados.itens.map(e => ({
      id: e.id_exame,
      solicitacao: e.numero_solicitacao,
      paciente: e.paciente_nome,
      tipoExame: e.tipo_exame ?? '—',
      frascos: e.total_frascos,
      status: e.etapa_macroscopia === 'EM_ANDAMENTO' ? 'Assumido' : 'Aguardando início',
      responsavel: e.responsavel_macroscopia_nome
        ? `${e.responsavel_macroscopia_nome}${e.assumido_em ? ` · ${formatDateShort(e.assumido_em)}` : ''}`
        : null,
      emAndamento: e.etapa_macroscopia === 'EM_ANDAMENTO',
    }));
    total.value = dados.total;
    contadores.value = dados.contadores;

    // Abrir numa aba vazia é a pior primeira impressão possível.
    if (!jaAjustouAbaInicial) {
      jaAjustouAbaInicial = true;
      if (abaAtual.value === 'meus' && dados.contadores.meus === 0) {
        abaAtual.value = 'aguardando';
        return;
      }
    }

    // Última linha de uma página consumida: não deixar o usuário num vazio.
    if (itens.value.length === 0 && pagina.value > 1) {
      pagina.value = 1;
    }
  } catch (erro: any) {
    if (erro?.code !== 'ERR_CANCELED') itens.value = [];
  } finally {
    carregando.value = false;
  }
}

function abrir(item: { id?: unknown }) {
  if (typeof item.id === 'string') emit('abrir', item.id);
}

watch(abaAtual, () => { pagina.value = 1; carregar(); });
watch(pagina, () => carregar());
watch(() => props.busca, () => { pagina.value = 1; carregar(); });

onMounted(carregar);
onUnmounted(() => controlador?.abort());

defineExpose({ carregar });
</script>
