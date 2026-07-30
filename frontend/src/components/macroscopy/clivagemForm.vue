<template>
  <Card v-if="!cassetesGerados.length">
    <template #header>
      <h2 class="text-lg font-bold text-lab-text">Clivagem e Descrição Macroscópica</h2>
      <p class="text-sm text-gray-500">
        Uma clivagem para o exame inteiro — {{ totalFrascos }} frasco(s) recebido(s)
      </p>
    </template>
    <div class="space-y-4">
      <div>
        <label class="form-label" for="descricaoMacro">Descrição Macroscópica Completa *</label>
        <textarea
          id="descricaoMacro"
          v-model="descricao"
          rows="4"
          class="form-control"
          placeholder="Ex: Recebido frasco com fixador contendo fragmento de tecido nodular, pardacento, medindo..."
        ></textarea>
      </div>

      <label class="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
        <input type="checkbox" v-model="sobraMaterial" class="h-4 w-4 text-lab-primary rounded border-gray-300">
        Houve sobra de material?
      </label>

      <div class="border-t border-gray-100 pt-4 space-y-3">
        <p class="text-xs font-bold text-gray-500 uppercase">Partes da peça</p>

        <div v-for="(estrutura, i) in estruturas" :key="i" class="flex items-center gap-3">
          <span class="font-mono font-bold text-lab-primary bg-lab-primary/10 px-2.5 py-1.5 rounded text-sm w-9 text-center shrink-0">
            {{ letraParte(i) }}
          </span>
          <input
            v-model="estrutura.nome"
            type="text"
            class="form-control flex-1"
            placeholder="Ex: Útero, trompa direita..."
          >
          <div class="flex items-center gap-1.5 shrink-0">
            <label class="text-xs text-gray-500">Fragmentos</label>
            <input v-model.number="estrutura.quantidadeCassetes" type="number" min="1" class="form-control w-16">
          </div>
          <button v-if="estruturas.length > 1" @click="removerEstrutura(i)" class="text-gray-400 hover:text-red-600 shrink-0">
            <TrashIcon class="h-5 w-5" />
          </button>
        </div>

        <button @click="adicionarEstrutura" class="text-sm font-medium text-lab-primary hover:underline flex items-center gap-1">
          <PlusIcon class="h-4 w-4" /> Adicionar parte
        </button>
      </div>

      <Button variant="primary" :disabled="!podeMapear" class="w-full" @click="mapearFragmentos">
        Mapear Fragmentos (Cassetes)
      </Button>
    </div>
  </Card>

  <Card v-else>
    <template #header>
      <h2 class="text-lg font-bold text-lab-text">Configuração dos Cassetes</h2>
      <p class="text-sm text-gray-500">Confirme a coloração de cada cassete antes de emitir as etiquetas</p>
    </template>
    <div class="space-y-3">
      <div
        v-for="cassete in cassetesGerados"
        :key="cassete.id"
        class="grid grid-cols-[48px_1fr_256px_144px] items-center gap-3 border border-gray-200 rounded-lg p-3"
      >
        <div class="flex flex-col items-center gap-0.5">
          <span class="h-7 w-full font-mono font-bold text-lab-primary bg-lab-primary/10 rounded text-sm inline-flex items-center justify-center">
            {{ cassete.id }}
          </span>
          <span class="text-[9px] text-gray-400 text-center leading-tight truncate w-full">
            {{ cassete.estrutura }}
          </span>
        </div>
        <input
          v-model="cassete.observacao"
          type="text"
          class="form-control h-10 w-full min-w-0"
          placeholder="Observações"
        >
        <select v-model="cassete.coloracao" class="form-control h-10 w-full">
          <option v-for="opcao in STAINING_OPTIONS" :key="opcao" :value="opcao">{{ opcao }}</option>
        </select>
        <span class="h-10 text-xs font-mono text-gray-400 truncate flex items-center justify-start pl-6 leading-none">
          {{ codigoLocal }}-{{ cassete.id }}
        </span>
      </div>

      <div v-if="!finalizado" class="flex justify-end gap-3 pt-2">
        <Button variant="default" :disabled="enviando" @click="cassetesGerados = []">Voltar</Button>
        <Button variant="primary" :disabled="enviando" @click="confirmar">
          Confirmar Clivagem e Emitir Etiquetas
        </Button>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useToast } from 'vue-toastification';
import { PlusIcon, TrashIcon } from '@heroicons/vue/24/outline';
import Card from '../card/card.vue';
import Button from '../button/button.vue';
import { exameService, type MacroscopiaResult } from '../../services/exameService';
import { STAINING_OPTIONS } from '../../constants/staffMembers';
import type { CasseteInfo } from '../../types/exam';

const props = defineProps<{
  idExame: string;
  codigoLocal: string;
  totalFrascos: number;
}>();

const emit = defineEmits<{ (e: 'concluido', resultado: MacroscopiaResult): void }>();

interface EstruturaForm {
  nome: string;
  quantidadeCassetes: number;
}
interface CasseteRascunho extends CasseteInfo {
  indiceParte?: number;
}

const toast = useToast();
const descricao = ref('');
const sobraMaterial = ref(false);
const estruturas = ref<EstruturaForm[]>([{ nome: '', quantidadeCassetes: 1 }]);
const cassetesGerados = ref<CasseteRascunho[]>([]);
const finalizado = ref(false);
const enviando = ref(false);

const podeMapear = computed(() =>
  descricao.value.trim().length > 0 &&
  estruturas.value.every(e => e.nome.trim().length > 0 && e.quantidadeCassetes >= 1)
);

/** Prévia local (A, B, ... Z, AA). Os identificadores reais vêm do backend. */
function letraParte(indice: number): string {
  let restante = indice + 1;
  let letras = '';
  while (restante > 0) {
    restante -= 1;
    letras = String.fromCharCode(65 + (restante % 26)) + letras;
    restante = Math.floor(restante / 26);
  }
  return letras;
}

function adicionarEstrutura() {
  estruturas.value.push({ nome: '', quantidadeCassetes: 1 });
}

function removerEstrutura(index: number) {
  estruturas.value.splice(index, 1);
}

function mapearFragmentos() {
  if (!podeMapear.value) return;
  const lista: CasseteRascunho[] = [];
  for (const [indiceParte, estrutura] of estruturas.value.entries()) {
    const letra = letraParte(indiceParte);
    if (estrutura.quantidadeCassetes === 1) {
      lista.push({ id: letra, estrutura: estrutura.nome, coloracao: STAINING_OPTIONS[0], indiceParte });
    } else {
      for (let i = 1; i <= estrutura.quantidadeCassetes; i++) {
        lista.push({ id: `${letra}${i}`, estrutura: estrutura.nome, coloracao: STAINING_OPTIONS[0], indiceParte });
      }
    }
  }
  cassetesGerados.value = lista;
}

async function confirmar() {
  if (enviando.value || !cassetesGerados.value.length) return;
  enviando.value = true;
  try {
    const resultado = await exameService.registrarMacroscopia({
      id_exame: props.idExame,
      descricao: descricao.value,
      // A API recebe a hierarquia, mas não recebe identificadores. A/B/A1/A2
      // são gerados e persistidos exclusivamente pelo backend.
      partes: estruturas.value.map((estrutura, indiceParte) => ({
        estrutura: estrutura.nome,
        fragmentos: cassetesGerados.value
          .filter(cassete => cassete.indiceParte === indiceParte)
          .map(cassete => ({ coloracao: cassete.coloracao, observacoes: cassete.observacao })),
      })),
    });

    // Substitui a prévia pelos identificadores efetivamente persistidos.
    cassetesGerados.value = resultado.cassetes.map((c): CasseteRascunho => ({
      id: c.letra_fragmento,
      estrutura: c.descricao_estrutura ?? '',
      coloracao: c.coloracao_padrao,
      observacao: c.observacoes_macroscopia ?? undefined,
    }));
    finalizado.value = true;
    toast.success(`Clivagem registrada: ${resultado.cassetes.length} cassete(s) para ${resultado.frascos.length} frasco(s).`);
    emit('concluido', resultado);
  } catch {
    // interceptor exibe erro
  } finally {
    enviando.value = false;
  }
}
</script>
