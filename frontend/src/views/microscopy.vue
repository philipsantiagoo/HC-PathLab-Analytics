<!-- src/views/microscopy.vue -->
<template>
  <div class="space-y-6">
    
    <!-- 1. IDENTIFICAÇÃO DA LÂMINA -->
    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
          <QrCodeIcon class="h-5 w-5 text-gray-500" />
          Identificar Lâmina
        </h2>
        <p class="text-sm text-gray-500">Bipe o QR Code da Lâmina de vidro para carregar o histórico do caso.</p>
      </template>

      <form @submit.prevent="identificarLamina" class="flex items-end gap-4 mt-4">
        <div class="flex-1 max-w-md">
          <label for="slideCode" class="block text-sm font-medium text-gray-700 mb-1">Código da Lâmina</label>
          <input 
            id="slideCode"
            v-model="slideSearchQuery" 
            type="text" 
            autofocus
            placeholder="Ex: L-442806-01-A-1-01"
            class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            :disabled="isLoading"
          />
        </div>
        <Button type="submit" variant="primary" :disabled="!slideSearchQuery || isLoading">
          {{ isLoading ? 'Buscando...' : 'Bipar / Buscar' }}
        </Button>
      </form>

      <div v-if="searchError" class="mt-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">
        {{ searchError }}
      </div>
    </Card>

    <!-- 2. VISÃO UNIFICADA E ANÁLISE -->
    <div v-if="laminaIdentificada && aghuData" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <!-- Lado Esquerdo: Histórico e Visão Unificada -->
      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Visão Unificada Clínica</h2>
          <p class="text-sm text-gray-500">Dados do AGHU cruzados com a árvore da lâmina atual</p>
        </template>
        
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Paciente</p>
            <p class="text-md font-bold text-gray-900">{{ aghuData.nomePaciente }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Solicitação (AGHU)</p>
            <p class="text-md text-gray-800">{{ aghuData.numeroSolicitacao }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Idade / Sexo</p>
            <p class="text-md text-gray-800">{{ aghuData.idade }} anos / {{ aghuData.sexo }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Hipótese Diagnóstica (AGHU)</p>
            <div class="bg-gray-50 p-2 text-sm text-gray-700 border border-gray-200 rounded mt-1">
              {{ aghuData.descricaoAghu }}
            </div>
          </div>
          <div class="col-span-2 p-3 bg-indigo-50 border border-indigo-100 rounded-md flex justify-between items-center">
            <div>
              <p class="text-xs text-indigo-500 font-semibold uppercase">Lâmina em Análise</p>
              <p class="text-xl font-mono text-indigo-700 font-bold mt-1">{{ laminaIdentificada.id }}</p>
            </div>
            <div class="text-right text-xs text-indigo-600 font-mono">
              <p>Frasco: {{ laminaIdentificada.arvore.frasco }}</p>
              <p>Cassete: {{ laminaIdentificada.arvore.cassete }}</p>
              <p>Bloco: {{ laminaIdentificada.arvore.bloco }}</p>
            </div>
          </div>
        </div>
      </Card>

      <!-- Lado Direito: Formulário de Decisão e Laudo Prévio -->
      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Registro de Microscopia</h2>
          <p class="text-sm text-gray-500">Defina o laudo prévio e a conduta para este caso</p>
        </template>
        
        <form @submit.prevent="salvarMicroscopia" class="space-y-4 mt-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Patologista / Residente Responsável</label>
            <input type="text" v-model="microscopyForm.responsavel" required placeholder="Dr(a)." class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Laudo Prévio (UACAP)</label>
            <textarea 
              v-model="microscopyForm.laudoPrevio" 
              rows="4" 
              required
              placeholder="Digite o diagnóstico preliminar local..."
              class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm"
            ></textarea>
            <p class="text-xs text-red-500 mt-1">* O laudo oficial de liberação continuará sendo digitado obrigatoriamente no sistema AGHU.</p>
          </div>

          <div class="pt-4 border-t border-gray-200">
            <label class="block text-sm font-medium text-gray-700 mb-2">Conduta para a Lâmina</label>
            <div class="flex flex-col gap-3">
              <label class="flex items-center gap-2 p-3 border border-gray-200 rounded-md hover:bg-gray-50 cursor-pointer transition-colors" :class="{'border-green-500 bg-green-50 hover:bg-green-50': microscopyForm.conduta === 'LIBERAR'}">
                <input type="radio" v-model="microscopyForm.conduta" value="LIBERAR" class="h-4 w-4 text-green-600" />
                <span class="font-medium text-gray-800">Conclusivo: Liberar Exame Local</span>
              </label>

              <label class="flex items-center gap-2 p-3 border border-gray-200 rounded-md hover:bg-gray-50 cursor-pointer transition-colors" :class="{'border-amber-500 bg-amber-50 hover:bg-amber-50': microscopyForm.conduta === 'COMPLEMENTO'}">
                <input type="radio" v-model="microscopyForm.conduta" value="COMPLEMENTO" class="h-4 w-4 text-amber-600" />
                <span class="font-medium text-gray-800">Inconclusivo: Solicitar Complemento / Imunohistoquímica</span>
              </label>
            </div>
          </div>

          <!-- Sub-formulário dinâmico caso peçam complemento -->
          <div v-if="microscopyForm.conduta === 'COMPLEMENTO'" class="p-4 bg-amber-50 rounded-md border border-amber-200 mt-4 space-y-3">
            <h3 class="font-bold text-amber-800 text-sm">Pedido de Retrabalho (IHQ / Nova Coloração)</h3>
            <div>
              <label class="block text-xs font-medium text-amber-900 mb-1">Marcadores / Técnica Desejada</label>
              <input type="text" v-model="microscopyForm.marcadores" placeholder="Ex: CD34, HER2, p53..." class="block w-full rounded-md border-amber-300 border p-2 shadow-sm focus:border-amber-500 sm:text-sm" />
            </div>
            <div>
              <label class="block text-xs font-medium text-amber-900 mb-1">Observação para a Bancada</label>
              <input type="text" v-model="microscopyForm.obsRetrabalho" placeholder="Ex: Fazer recortes seriados..." class="block w-full rounded-md border-amber-300 border p-2 shadow-sm focus:border-amber-500 sm:text-sm" />
            </div>
          </div>

          <div class="pt-4 flex justify-end">
            <Button type="submit" variant="primary" :class="{'bg-green-600 hover:bg-green-700': microscopyForm.conduta === 'LIBERAR'}">
              {{ microscopyForm.conduta === 'LIBERAR' ? 'Salvar e Liberar Exame' : 'Salvar e Solicitar Retrabalho' }}
            </Button>
          </div>
        </form>
      </Card>
    </div>

    <!-- 3. FEEDBACK DE SUCESSO -->
    <Card v-if="fluxoConcluido" :class="microscopyForm.conduta === 'LIBERAR' ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'">
      <div class="flex items-center gap-3">
        <CheckBadgeIcon v-if="microscopyForm.conduta === 'LIBERAR'" class="h-8 w-8 text-green-600" />
        <ArrowPathIcon v-else class="h-8 w-8 text-amber-600" />
        <div>
          <h2 class="text-lg font-bold" :class="microscopyForm.conduta === 'LIBERAR' ? 'text-green-800' : 'text-amber-800'">
            {{ microscopyForm.conduta === 'LIBERAR' ? 'Exame Liberado Localmente!' : 'Retrabalho Solicitado!' }}
          </h2>
          <p class="text-sm" :class="microscopyForm.conduta === 'LIBERAR' ? 'text-green-700' : 'text-amber-700'">
            {{ microscopyForm.conduta === 'LIBERAR' ? 'Não esqueça de registrar o laudo oficial no AGHU. As lâminas já podem ser arquivadas.' : 'A amostra retornou para a fila de Processamento Técnico da bancada.' }}
          </p>
        </div>
      </div>
    </Card>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { QrCodeIcon, CheckBadgeIcon, ArrowPathIcon } from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import { fetchAghuExam, type AghuExam } from '../mocks/mockAghu';

// --- ESTADOS ---
const slideSearchQuery = ref('');
const isLoading = ref(false);
const searchError = ref('');
const fluxoConcluido = ref(false);

const laminaIdentificada = ref<{ 
  id: string; 
  solicitacao: string;
  arvore: { frasco: string, cassete: string, bloco: string }
} | null>(null);

const aghuData = ref<AghuExam | null>(null);

const microscopyForm = reactive({
  responsavel: '',
  laudoPrevio: '',
  conduta: 'LIBERAR' as 'LIBERAR' | 'COMPLEMENTO',
  marcadores: '',
  obsRetrabalho: ''
});

// --- MÉTODOS ---

// 1. Identificar a Lâmina bipada (Ex: L-442806-01-A-1-01)
const identificarLamina = async () => {
  if (!slideSearchQuery.value) return;

  isLoading.value = true;
  searchError.value = '';
  fluxoConcluido.value = false;
  laminaIdentificada.value = null;
  aghuData.value = null;

  // Quebra o identificador para recuperar a árvore hierárquica reversa (ADR 005)
  const partes = slideSearchQuery.value.split('-');
  if (partes.length !== 6 || partes[0] !== 'L') {
    searchError.value = 'Código inválido. Certifique-se de bipar uma etiqueta de LÂMINA (Ex: L-442806-01-A-1-01).';
    isLoading.value = false;
    return;
  }

  const solicitacaoId = partes[1];

  try {
    const result = await fetchAghuExam(solicitacaoId);
    if (result) {
      aghuData.value = result;
      laminaIdentificada.value = {
        id: slideSearchQuery.value,
        solicitacao: solicitacaoId,
        arvore: {
          frasco: `F-${partes[1]}-${partes[2]}`,
          cassete: `C-${partes[1]}-${partes[2]}-${partes[3]}`,
          bloco: `B-${partes[1]}-${partes[2]}-${partes[3]}-${partes[4]}`
        }
      };
    } else {
      searchError.value = 'Lâmina lida, mas dados do AGHU não localizados.';
    }
  } catch (error) {
    searchError.value = 'Erro ao consultar o histórico.';
  } finally {
    isLoading.value = false;
  }
};

// 2. Salvar Laudo Prévio e atualizar Rastreabilidade Local
const salvarMicroscopia = () => {
  if (!laminaIdentificada.value || !aghuData.value) return;

  // Log simulando payload para o backend PostgreSQL
  console.log('Decisão da Microscopia salva:', {
    laminaID: laminaIdentificada.value.id,
    responsavel: microscopyForm.responsavel,
    laudoPrevioLocal: microscopyForm.laudoPrevio,
    conduta: microscopyForm.conduta,
    retrabalho: microscopyForm.conduta === 'COMPLEMENTO' ? {
      marcadores: microscopyForm.marcadores,
      observacao: microscopyForm.obsRetrabalho
    } : null
  });

  fluxoConcluido.value = true;
  
  // Limpa o formulário visualmente, mantendo o Card de Sucesso ativo
  laminaIdentificada.value = null;
  aghuData.value = null;
  slideSearchQuery.value = '';
};
</script>