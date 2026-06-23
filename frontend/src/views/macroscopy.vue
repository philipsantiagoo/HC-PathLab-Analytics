<template>
  <div class="space-y-6">
    
    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
          <QrCodeIcon class="h-5 w-5 text-gray-500" />
          Identificar Frasco na Macroscopia
        </h2>
        <p class="text-sm text-gray-500">Bipe o QR Code do Frasco ou digite o identificador local (Ex: F-442806-01).</p>
      </template>

      <form @submit.prevent="identificarFrasco" class="flex items-end gap-4 mt-4">
        <div class="flex-1 max-w-md">
          <label Desert for="flaskCode" class="block text-sm font-medium text-gray-700 mb-1">Código do Frasco</label>
          <input 
            id="flaskCode"
            v-model="flaskSearchQuery" 
            type="text" 
            autofocus
            placeholder="Ex: F-442806-01"
            class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            :disabled="isLoading"
          />
        </div>
        <Button type="submit" variant="primary" :disabled="!flaskSearchQuery || isLoading">
          {{ isLoading ? 'Identificando...' : 'Bipar / Buscar' }}
        </Button>
      </form>

      <div v-if="searchError" class="mt-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">
        {{ searchError }}
      </div>
    </Card>

    <div v-if="frascoIdentificado && aghuData" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Visão Unificada do Caso</h2>
          <p class="text-sm text-gray-500">Dados demográficos e clínicos de origem [Somente Leitura]</p>
        </template>
        
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Paciente</p>
            <p class="text-md font-bold text-gray-900">{{ aghuData.nomePaciente }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Prontuário</p>
            <p class="text-md text-gray-800">{{ aghuData.registro }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Solicitação AGHU</p>
            <p class="text-md text-gray-800">{{ aghuData.numeroSolicitacao }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">ID Frasco Atual</p>
            <p class="text-md font-mono text-blue-700 font-bold">{{ frascoIdentificado.id }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Procedimento Solicitado</p>
            <p class="text-sm text-gray-800">{{ aghuData.procedimento }}</p>
          </div>
        </div>
      </Card>

      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Clivagem e Descrição Macroscópica</h2>
          <p class="text-sm text-gray-500">Registro de fragmentação da peça cirúrgica</p>
        </template>
        
        <form @submit.prevent="gerarEstruturaCassetes" class="space-y-4 mt-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Responsável (Macro)</label>
              <input type="text" v-model="macroForm.responsavel" required placeholder="Dr(a). Patologista / Residente" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Data da Macro</label>
              <input type="date" v-model="macroForm.dataRealizacao" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Descrição Macroscópica Completa</label>
            <textarea 
              v-model="macroForm.descricao" 
              rows="4" 
              required
              placeholder="Ex: Recebido frasco com fixador contendo fragmento de tecido nodular, pardacento, medindo..."
              class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm"
            ></textarea>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Nº de Cassetes a Gerar</label>
              <input type="number" min="1" max="50" v-model.number="macroForm.numeroCassetes" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
            </div>
            <div class="flex items-center mt-6">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" v-model="macroForm.sobraMaterial" class="h-4 w-4 text-blue-600 focus:ring-blue-500 rounded border-gray-300" />
                <span class="text-sm font-medium text-gray-700">Houve sobra de material?</span>
              </label>
            </div>
          </div>

          <div class="pt-4 border-t border-gray-200 flex justify-end">
            <Button type="submit" variant="primary">
              Mapear Fragmentos (Cassetes)
            </Button>
          </div>
        </form>
      </Card>
    </div>

    <Card v-if="cassetesPreMapeados.length > 0 && !etiquetasGeradas.length">
      <template #header>
        <h2 class="text-lg font-bold text-lab-text">Configuração dos Fragmentos Hidro-resistentes</h2>
        <p class="text-sm text-gray-500">Confirme as letras dos fragmentos e a coloração padrão antes de enviar para o processamento técnico.</p>
      </template>

      <div class="mt-4 space-y-3">
        <div v-for="(cassete, index) in cassetesPreMapeados" :key="index" class="flex items-center gap-4 p-3 bg-gray-50 rounded-md border border-gray-200">
          <span class="font-mono font-bold bg-blue-100 text-blue-800 px-3 py-1.5 rounded text-sm shrink-0">
            Letra {{ cassete.letra }}
          </span>
          <div class="flex-1 grid grid-cols-2 gap-3">
            <input type="text" v-model="cassete.observacoes" placeholder="Observação específica deste fragmento (opcional)" class="rounded-md border-gray-300 border px-3 py-1 text-xs shadow-sm focus:border-blue-500 w-full" />
            <select v-model="cassete.coloracao" class="rounded-md border-gray-300 border px-3 py-1 text-xs shadow-sm focus:border-blue-500 w-full">
              <option value="HE">HE (Hematoxilina-Eosina) - Rotina</option>
              <option value="Congela">Congelação</option>
            </select>
          </div>
          <span class="text-xs font-mono text-gray-400 shrink-0">ID Alvo: {{ cassete.idSugerido }}</span>
        </div>
      </div>

      <div class="mt-4 pt-4 border-t border-gray-200 flex justify-end">
        <Button @click="finalizarMacroscopia" variant="primary">
          Confirmar Clivagem e Emitir Etiquetas
        </Button>
      </div>
    </Card>

    <Card v-if="etiquetasGeradas.length > 0" class="bg-green-50 border-green-200">
      <template #header>
        <h2 class="text-lg font-bold text-green-800 flex items-center gap-2">
          <CheckBadgeIcon class="h-6 w-6" />
          Clivagem Finalizada com Sucesso!
        </h2>
        <p class="text-sm text-green-700">Cassetes salvos na árvore hierárquica local. Imprima ou use os códigos na tela para identificação física.</p>
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
import { QrCodeIcon, CheckBadgeIcon } from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import VirtualLabel from '../components/virtualLabel/virtualLabel.vue';
import { fetchAghuExam, type AghuExam } from '../mocks/mockAghu';

// --- ESTADOS ---
const flaskSearchQuery = ref('');
const isLoading = ref(false);
const searchError = ref('');

const frascoIdentificado = ref<{ id: string; solicitacao: string } | null>(null);
const aghuData = ref<AghuExam | null>(null);

const macroForm = reactive({
  responsavel: '',
  dataRealizacao: new Date().toISOString().split('T')[0], // Hoje por padrão
  descricao: '',
  numeroCassetes: 1,
  sobraMaterial: false
});

// Interfaces para o controle dinâmico de fragmentos
interface CassetePreMapeado {
  letra: string;
  observacoes: string;
  coloracao: string;
  idSugerido: string;
}
const cassetesPreMapeados = ref<CassetePreMapeado[]>([]);

interface EtiquetaCassete {
  codigoEtiqueta: string;
  titulo: string;
  subtitulo: string;
}
const etiquetasGeradas = ref<EtiquetaCassete[]>([]);

// --- MÉTODOS ---

// 1. Identificar o Frasco bipado da recepção (Ex: F-442806-01)
const identificarFrasco = async () => {
  if (!flaskSearchQuery.value) return;

  isLoading.value = true;
  searchError.value = '';
  frascoIdentificado.value = null;
  aghuData.value = null;
  cassetesPreMapeados.value = [];
  etiquetasGeradas.value = [];

  // Validação simples do padrão esperado de QR Code de frasco: F-[Solicitacao]-[Sequencial]
  const partes = flaskSearchQuery.value.split('-');
  if (partes.length !== 3 || partes[0] !== 'F') {
    searchError.value = 'Código inválido. Certifique-se de que está bipando uma etiqueta de FRASCO válida (Ex: F-442806-01).';
    isLoading.value = false;
    return;
  }

  const solicitacaoId = partes[1];

  try {
    const result = await fetchAghuExam(solicitacaoId);
    if (result) {
      aghuData.value = result;
      frascoIdentificado.value = {
        id: flaskSearchQuery.value,
        solicitacao: solicitacaoId
      };
    } else {
      searchError.value = 'Frasco válido, mas a solicitação correspondente não foi localizada no cache local ou no AGHU.';
    }
  } catch (error) {
    searchError.value = 'Erro ao processar validação do frasco.';
  } finally {
    isLoading.value = false;
  }
};

// 2. Mapeia a quantidade de cassetes gerando as letras sequenciais (A, B, C...)
const gerarEstruturaCassetes = () => {
  if (!frascoIdentificado.value) return;

  cassetesPreMapeados.value = [];
  etiquetasGeradas.value = [];

  for (let i = 0; i < macroForm.numeroCassetes; i++) {
    // Transforma índice numérico em letras maiúsculas de A-Z (ASCII 65 em diante)
    const letra = String.fromCharCode(65 + i);
    
    // Regra de nomenclatura da árvore hierárquica: C-[NumSolicitacao]-[SequencialFrasco]-[LetraFragmento]
    // Ex: C-442806-01-A
    const sufixoFrasco = flaskSearchQuery.value.replace('F-', '');
    const idSugerido = `C-${sufixoFrasco}-${letra}`;

    cassetesPreMapeados.value.push({
      letra,
      observacoes: '',
      coloracao: 'HE',
      idSugerido
    });
  }
};

// 3. Salva a macroscopia localmente e gera as etiquetas reais dos cassetes
const finalizarMacroscopia = () => {
  if (!frascoIdentificado.value || !aghuData.value) return;

  etiquetasGeradas.value = [];

  // Converte a lista pré-mapeada nas etiquetas estruturadas para o VirtualLabel
  cassetesPreMapeados.value.forEach(item => {
    etiquetasGeradas.value.push({
      codigoEtiqueta: item.idSugerido,
      titulo: `Cassete ${item.letra}`,
      subtitulo: aghuData.value?.nomePaciente || ''
    });
  });

  // Log simulando o payload persistido em banco local (UACAP PostgreSQL)
  console.log('Dados da Macroscopia e Cassetes salvos com integridade referencial:', {
    frascoMatriz: frascoIdentificado.value.id,
    laudoMacroscopico: macroForm.descricao,
    responsavel: macroForm.responsavel,
    data: macroForm.dataRealizacao,
    cassetesSalvos: cassetesPreMapeados.value
  });
};
</script>