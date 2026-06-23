<template>
  <div class="space-y-6">
    <!-- 1. BLOCO DE BUSCA -->
    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
          <MagnifyingGlassIcon class="h-5 w-5 text-gray-500" />
          Buscar Solicitação AGHU
        </h2>
        <p class="text-sm text-gray-500">Escaneie o código de barras da requisição ou digite o número da solicitação.</p>
      </template>
      
      <form @submit.prevent="buscarAghu" class="flex items-end gap-4 mt-4">
        <div class="flex-1 max-w-md">
          <label for="search" class="block text-sm font-medium text-gray-700 mb-1">Nº Solicitação / Registro</label>
          <input 
            id="search"
            v-model="searchQuery" 
            type="text" 
            autofocus
            placeholder="Ex: 442806"
            class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            :disabled="isLoading"
          />
        </div>
        <Button type="submit" variant="primary" :disabled="!searchQuery || isLoading">
          {{ isLoading ? 'Buscando...' : 'Buscar' }}
        </Button>
      </form>

      <div v-if="searchError" class="mt-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">
        {{ searchError }}
      </div>
    </Card>

    <!-- 2. DADOS AGHU & FORMULÁRIO LOCAL -->
    <div v-if="aghuData" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <!-- Lado Esquerdo: Dados Importados do AGHU (Somente Leitura) -->
      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Dados do Paciente (AGHU)</h2>
          <p class="text-sm text-gray-500">Visualização unificada (Somente Leitura)</p>
        </template>
        
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Nome do Paciente</p>
            <p class="text-md font-bold text-gray-900">{{ aghuData.nomePaciente }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Registro (Prontuário)</p>
            <p class="text-md text-gray-800">{{ aghuData.registro }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Solicitação</p>
            <p class="text-md text-gray-800">{{ aghuData.numeroSolicitacao }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Idade / Sexo</p>
            <p class="text-md text-gray-800">{{ aghuData.idade }} anos / {{ aghuData.sexo }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Origem</p>
            <p class="text-md text-gray-800">{{ aghuData.origem }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Procedimento</p>
            <p class="text-md text-gray-800">{{ aghuData.procedimento }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Descrição (Médico Solicitante)</p>
            <div class="bg-gray-50 p-3 rounded border text-sm text-gray-700 mt-1">
              {{ aghuData.descricaoAghu }}
            </div>
          </div>
        </div>
      </Card>

      <!-- Lado Direito: Formulário de Rastreabilidade UACAP -->
      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Registro de Peça (UACAP)</h2>
          <p class="text-sm text-gray-500">Preencha os dados físicos recebidos na bancada</p>
        </template>
        
        <form @submit.prevent="registrarRecebimento" class="space-y-4 mt-4">
          <div class="flex items-center gap-6 mb-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="localForm.urgente" class="h-4 w-4 text-red-600 focus:ring-red-500 rounded border-gray-300" />
              <span class="text-sm font-medium text-red-700">Exame de Urgência?</span>
            </label>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">A/E (Ambulatório/Enfermaria)</label>
              <select v-model="localForm.tipoOrigem" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm">
                <option value="A">Ambulatório</option>
                <option value="E">Enfermaria</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Qtd. de Frascos Físicos</label>
              <input type="number" min="1" max="20" v-model="localForm.qtdFrascos" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Descrição do Material Físico (O que chegou?)</label>
            <textarea 
              v-model="localForm.descricao" 
              rows="3" 
              placeholder="Ex: Frasco contendo fragmentos de tecido pardacento..."
              class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm"
            ></textarea>
          </div>

          <div class="pt-4 border-t border-gray-200 flex justify-end">
            <Button type="submit" variant="primary" :disabled="!localForm.qtdFrascos">
              Registrar e Gerar Etiquetas
            </Button>
          </div>
        </form>
      </Card>
    </div>

    <!-- 3. ETIQUETAS GERADAS (VIRTUAL LABELS) -->
    <Card v-if="etiquetasGeradas.length > 0" class="bg-green-50 border-green-200">
      <template #header>
        <h2 class="text-lg font-bold text-green-800 flex items-center gap-2">
          <CheckBadgeIcon class="h-6 w-6" />
          Recebimento Registrado com Sucesso!
        </h2>
        <p class="text-sm text-green-700">O sistema UACAP assumiu a rastreabilidade. Imprima as etiquetas e cole nos frascos correspondentes.</p>
      </template>

      <div class="flex flex-wrap gap-6 mt-6 justify-center lg:justify-start">
        <VirtualLabel 
          v-for="etiqueta in etiquetasGeradas" 
          :key="etiqueta.codigoEtiqueta"
          :codigoEtiqueta="etiqueta.codigoEtiqueta"
          :titulo="etiqueta.titulo"
          :subtitulo="etiqueta.subtitulo"
        />
      </div>
    </Card>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { MagnifyingGlassIcon, CheckBadgeIcon } from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import VirtualLabel from '../components/virtualLabel/virtualLabel.vue';
import { fetchAghuExam, type AghuExam } from '../mocks/mockAghu';

// --- ESTADOS DA TELA ---
const searchQuery = ref('');
const isLoading = ref(false);
const searchError = ref('');
const aghuData = ref<AghuExam | null>(null);

const localForm = reactive({
  urgente: false,
  tipoOrigem: 'E',
  qtdFrascos: 1,
  descricao: ''
});

// Tipagem local para as etiquetas que vamos gerar
interface EtiquetaData {
  codigoEtiqueta: string;
  titulo: string;
  subtitulo: string;
}
const etiquetasGeradas = ref<EtiquetaData[]>([]);

// --- FUNÇÕES ---

// 1. Busca os dados no Mock do AGHU
const buscarAghu = async () => {
  if (!searchQuery.value) return;
  
  isLoading.value = true;
  searchError.value = '';
  aghuData.value = null;
  etiquetasGeradas.value = []; // Reseta etiquetas anteriores

  try {
    const result = await fetchAghuExam(searchQuery.value);
    if (result) {
      aghuData.value = result;
      // Pre-popula a descrição local com a do AGHU para facilitar, mas o usuário pode editar
      localForm.descricao = result.descricaoAghu; 
    } else {
      searchError.value = 'Solicitação não encontrada no AGHU. Verifique o número digitado.';
    }
  } catch (error) {
    searchError.value = 'Erro ao conectar com a base do HC.';
  } finally {
    isLoading.value = false;
  }
};

// 2. Registra o recebimento (No futuro: envia via POST para a API /provider/uacap)
const registrarRecebimento = () => {
  if (!aghuData.value) return;

  etiquetasGeradas.value = [];
  
  // Gera N etiquetas baseadas na quantidade de frascos que o usuário informou
  for (let i = 1; i <= localForm.qtdFrascos; i++) {
    // Formata o sequencial (ex: 1 vira "01")
    const sequencial = i.toString().padStart(2, '0');
    
    // Regra de negócio: ID do Frasco (F-[NumSolicitacao]-[Sequencial])
    const novoCodigo = `F-${aghuData.value.numeroSolicitacao}-${sequencial}`;

    etiquetasGeradas.value.push({
      codigoEtiqueta: novoCodigo,
      titulo: `Frasco ${sequencial}/${localForm.qtdFrascos.toString().padStart(2, '0')}`,
      subtitulo: aghuData.value.nomePaciente
    });
  }

  // Feedback de conclusão (poderia usar um toast notification aqui também)
  console.log('Dados salvos no banco local da Patologia:', {
    aghuReferencia: aghuData.value.numeroSolicitacao,
    dadosUacap: { ...localForm },
    etiquetas: etiquetasGeradas.value
  });
};
</script>