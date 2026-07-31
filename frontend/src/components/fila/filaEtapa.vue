<template>
  <Card>
    <template #header>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-lab-text">{{ titulo }}</h2>
          <p class="text-sm text-gray-500">{{ subtitulo }}</p>
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
        :headers="colunas"
        :items="itens"
        server-side
        :total="total"
        :loading="carregando"
        :page-size="porPagina"
        v-model:page="pagina"
        clickable-rows
        @row-click="abrir"
      >
        <template #item-tipoExame="{ item }">
          <span class="font-mono text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-1 rounded">
            {{ item.tipoExame }}
          </span>
        </template>
        <template #item-situacao="{ item }">
          <div class="flex flex-col gap-0.5">
            <Badge :color="item.emAndamento ? 'blue' : 'gray'">{{ item.situacao }}</Badge>
            <span v-if="item.responsavel" class="text-[10px] text-gray-400">{{ item.responsavel }}</span>
          </div>
        </template>
        <!-- Colunas extras da estação, repassadas por quem usa o componente. -->
        <template v-for="nome in nomesExtras" :key="nome" #[`item-${nome}`]="{ item }">
          <slot :name="`item-${nome}`" :item="item">{{ item[nome] }}</slot>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { ArrowPathIcon } from '@heroicons/vue/24/outline';
import Card from '../card/card.vue';
import Badge from '../badge/badge.vue';
import DataTable from '../dataTable/dataTable.vue';
import TabBar from '../tabBar/tabBar.vue';
import {
  etapaService,
  rotuloSituacao,
  type ContadoresFila,
  type Etapa,
  type FiltroFila,
  type LinhaFila,
  type Subetapa,
} from '../../services/etapaService';
import { formatDateShort } from '../../utils/date';

/**
 * Fila de uma etapa: abas, paginação no servidor, busca e atualização.
 *
 * Nasceu como a fila da macroscopia e foi generalizada — as quatro estações
 * consomem o mesmo endpoint com prefixo diferente, então uma cópia por estação
 * seria a mesma tabela quatro vezes.
 */

interface Aba {
  value: string;
  label: string;
  /** Filtro enviado ao backend; por padrão é o próprio ``value``. */
  filtro?: FiltroFila;
  subetapa?: Subetapa;
  contador?: keyof ContadoresFila;
}

interface ColunaExtra {
  text: string;
  value: string;
  align?: 'left' | 'center' | 'right';
  /** Como derivar o valor a partir da linha crua da API. */
  valor: (linha: LinhaFila) => unknown;
}

const props = withDefaults(defineProps<{
  etapa: Etapa;
  titulo: string;
  subtitulo?: string;
  busca?: string;
  abas?: Aba[];
  colunasExtras?: ColunaExtra[];
  porPagina?: number;
}>(), {
  subtitulo: 'Exames aguardando processamento nesta etapa',
  porPagina: 10,
});

const emit = defineEmits<{ (e: 'abrir', idExame: string): void }>();

const ABAS_PADRAO: Aba[] = [
  { value: 'meus', label: 'Meus exames', contador: 'meus' },
  { value: 'aguardando', label: 'Aguardando', contador: 'aguardando' },
  { value: 'em_andamento', label: 'Em andamento', contador: 'em_andamento' },
  { value: 'todos', label: 'Todos', contador: 'todos' },
];

const definicaoAbas = computed(() => props.abas ?? ABAS_PADRAO);
const nomesExtras = computed(() => (props.colunasExtras ?? []).map(c => c.value));

const colunas = computed(() => [
  { text: 'Código', value: 'solicitacao' },
  { text: 'Paciente', value: 'paciente' },
  { text: 'Tipo', value: 'tipoExame' },
  ...(props.colunasExtras ?? []).map(({ text, value, align }) => ({ text, value, align })),
  { text: 'Situação', value: 'situacao' },
]);

const abaAtual = ref(definicaoAbas.value[0].value);
const pagina = ref(1);
const itens = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const carregando = ref(false);
const contadores = ref<ContadoresFila>({ meus: 0, aguardando: 0, em_andamento: 0, todos: 0 });

const abas = computed(() => definicaoAbas.value.map(a => ({
  value: a.value,
  label: a.label,
  count: a.contador ? (contadores.value[a.contador] ?? 0) as number : undefined,
})));

// Troca rápida de aba gera respostas fora de ordem; a anterior é abortada.
let controlador: AbortController | null = null;
let jaAjustouAbaInicial = false;

function mapear(linha: LinhaFila): Record<string, unknown> {
  const extras = Object.fromEntries(
    (props.colunasExtras ?? []).map(c => [c.value, c.valor(linha)]),
  );
  return {
    id: linha.id_exame,
    solicitacao: linha.numero_solicitacao,
    paciente: linha.paciente_nome,
    tipoExame: linha.tipo_exame ?? '—',
    situacao: rotuloSituacao(linha.situacao),
    responsavel: linha.responsavel_nome
      ? `${linha.responsavel_nome}${linha.assumido_em ? ` · ${formatDateShort(linha.assumido_em)}` : ''}`
      : null,
    emAndamento: linha.situacao === 'EM_ANDAMENTO',
    bruto: linha,
    ...extras,
  };
}

async function carregar() {
  controlador?.abort();
  controlador = new AbortController();
  carregando.value = true;
  const aba = definicaoAbas.value.find(a => a.value === abaAtual.value) ?? definicaoAbas.value[0];
  try {
    const dados = await etapaService.fila(props.etapa, {
      filtro: aba.filtro ?? (aba.value as FiltroFila),
      subetapa: aba.subetapa,
      pagina: pagina.value,
      por_pagina: props.porPagina,
      busca: props.busca || undefined,
      signal: controlador.signal,
    });
    itens.value = dados.itens.map(mapear);
    total.value = dados.total;
    contadores.value = dados.contadores;

    // Abrir numa aba vazia é a pior primeira impressão possível.
    if (!jaAjustouAbaInicial) {
      jaAjustouAbaInicial = true;
      if (abaAtual.value === 'meus' && (dados.contadores.meus ?? 0) === 0) {
        abaAtual.value = definicaoAbas.value[1]?.value ?? abaAtual.value;
        return;
      }
    }

    // Última linha de uma página consumida: não deixar o usuário num vazio.
    if (itens.value.length === 0 && pagina.value > 1) pagina.value = 1;
  } catch (erro: any) {
    // O interceptor do axios não exibe toast para requisição cancelada.
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
