<template>
  <div class="space-y-6">
    
    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
          <QrCodeIcon class="h-5 w-5 text-gray-500" />
          Identificar Cassete
        </h2>
        <p class="text-sm text-gray-500">Bipe o QR Code do Cassete para iniciar o processamento e inclusão.</p>
      </template>

      <form @submit.prevent="identificarCassete" class="flex items-end gap-4 mt-4">
        <div class="flex-1 max-w-md">
          <label for="cassetteCode" class="block text-sm font-medium text-gray-700 mb-1">Código do Cassete</label>
          <input 
            id="cassetteCode"
            v-model="cassetteSearchQuery" 
            type="text" 
            autofocus
            placeholder="Ex: C-442806-01-A"
            class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            :disabled="isLoading"
          />
        </div>
        <Button type="submit" variant="primary" :disabled="!cassetteSearchQuery || isLoading">
          {{ isLoading ? 'Buscando...' : 'Bipar / Buscar' }}
        </Button>
      </form>

      <div v-if="searchError" class="mt-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm">
        {{ searchError }}
      </div>
    </Card>

    <div v-if="casseteIdentificado && aghuData" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Contexto da Amostra</h2>
          <p class="text-sm text-gray-500">Garantia de Rastreabilidade</p>
        </template>
        
        <div class="grid grid-cols-2 gap-4 mt-4">
          <div class="col-span-2">
            <p class="text-xs text-gray-500 font-semibold uppercase">Paciente</p>
            <p class="text-md font-bold text-gray-900">{{ aghuData.nomePaciente }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">Exame AGHU</p>
            <p class="text-md text-gray-800">{{ aghuData.numeroSolicitacao }}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500 font-semibold uppercase">ID Frasco Origem</p>
            <p class="text-md text-gray-800">{{ frascoOrigem }}</p>
          </div>
          <div class="col-span-2 p-3 bg-blue-50 border border-blue-100 rounded-md">
            <p class="text-xs text-blue-500 font-semibold uppercase">Cassete Atual em Processamento</p>
            <p class="text-xl font-mono text-blue-700 font-bold mt-1">{{ casseteIdentificado.id }}</p>
          </div>
        </div>
      </Card>

      <Card>
        <template #header>
          <h2 class="text-lg font-bold text-lab-text">Inclusão e Microtomia</h2>
          <p class="text-sm text-gray-500">Defina os subprodutos (Blocos e Lâminas) a serem gerados</p>
        </template>
        
        <form @submit.prevent="processarEGerarEtiquetas" class="space-y-4 mt-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Técnico Responsável</label>
            <input type="text" v-model="processForm.tecnico" required placeholder="Nome do Técnico" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
          </div>

          <div class="grid grid-cols-2 gap-4 border-t border-gray-100 pt-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Nº de Blocos (Parafina)</label>
              <input type="number" min="1" max="10" v-model.number="processForm.qtdBlocos" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
              <p class="text-xs text-gray-400 mt-1">Normalmente 1 por cassete</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Lâminas por Bloco</label>
              <input type="number" min="1" max="20" v-model.number="processForm.qtdLaminasPorBloco" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Coloração / Técnica</label>
              <select v-model="processForm.coloracao" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm">
                <option value="HE">HE (Rotina)</option>
                <option value="PAS">PAS</option>
                <option value="Giemsa">Giemsa</option>
                <option value="Tricromico">Tricrômico de Masson</option>
                <option value="IHQ">Imunohistoquímica (IHQ)</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Data do Processamento</label>
              <input type="date" v-model="processForm.dataProcessamento" class="block w-full rounded-md border-gray-300 border p-2.5 shadow-sm focus:border-blue-500 sm:text-sm" />
            </div>
          </div>

          <div class="pt-4 border-t border-gray-200 flex justify-end">
            <Button type="submit" variant="primary">
              Registrar Inclusão e Emitir Etiquetas
            </Button>
          </div>
        </form>
      </Card>
    </div>

    <div v-if="etiquetasBlocos.length > 0" class="space-y-6">
      
      <Card class="bg-amber-50 border-amber-200">
        <template #header>
          <h2 class="text-lg font-bold text-amber-800 flex items-center gap-2">
            <CubeIcon class="h-6 w-6" /> Blocos de Parafina Gerados
          </h2>
        </template>
        <div class="flex flex-wrap gap-4 mt-4">
          <VirtualLabel 
            v-for="etiqueta in etiquetasBlocos" 
            :key="etiqueta.codigoEtiqueta"
            :codigoEtiqueta="etiqueta.codigoEtiqueta"
            :titulo="etiqueta.titulo"
            :subtitulo="etiqueta.subtitulo"
          />
        </div>
      </Card>

      <Card class="bg-indigo-50 border-indigo-200">
        <template #header>
          <h2 class="text-lg font-bold text-indigo-800 flex items-center gap-2">
            <DocumentMagnifyingGlassIcon class="h-6 w-6" /> 
            Lâminas de Microscopia Geradas
          </h2>
          <p class="text-sm text-indigo-700">Prontas para montagem e coloração: <strong>{{ processForm.coloracao }}</strong></p>
        </template>
        <div class="flex flex-wrap gap-4 mt-4">
          <VirtualLabel 
            v-for="etiqueta in etiquetasLaminas" 
            :key="etiqueta.codigoEtiqueta"
            :codigoEtiqueta="etiqueta.codigoEtiqueta"
            :titulo="etiqueta.titulo"
            :subtitulo="etiqueta.subtitulo"
          />
        </div>
      </Card>

    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { 
  QrCodeIcon, 
  Square2StackIcon as CubeIcon, // Alias para simular o Bloco
  MagnifyingGlassPlusIcon as DocumentMagnifyingGlassIcon // Alias para simular a Lâmina
} from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import VirtualLabel from '../components/virtualLabel/virtualLabel.vue';
import { fetchAghuExam, type AghuExam } from '../mocks/mockAghu';

// --- ESTADOS ---
const cassetteSearchQuery = ref('');
const isLoading = ref(false);
const searchError = ref('');

const casseteIdentificado = ref<{ id: string; baseSolicitacao: string; sulfixoOrigem: string } | null>(null);
const aghuData = ref<AghuExam | null>(null);

// Reconstroi o ID do frasco a partir do ID do Cassete
const frascoOrigem = computed(() => {
  if (!casseteIdentificado.value) return '';
  // Se o cassete é C-442806-01-A, o frasco de origem é F-442806-01
  return `F-${casseteIdentificado.value.sulfixoOrigem}`;
});

const processForm = reactive({
  tecnico: '',
  qtdBlocos: 1,
  qtdLaminasPorBloco: 1,
  coloracao: 'HE',
  dataProcessamento: new Date().toISOString().split('T')[0]
});

interface EtiquetaGerada {
  codigoEtiqueta: string;
  titulo: string;
  subtitulo: string;
}
const etiquetasBlocos = ref<EtiquetaGerada[]>([]);
const etiquetasLaminas = ref<EtiquetaGerada[]>([]);

// --- MÉTODOS ---

// 1. Validar e Identificar o Cassete bipado (Ex: C-442806-01-A)
const identificarCassete = async () => {
  if (!cassetteSearchQuery.value) return;

  isLoading.value = true;
  searchError.value = '';
  casseteIdentificado.value = null;
  aghuData.value = null;
  etiquetasBlocos.value = [];
  etiquetasLaminas.value = [];

  // Validação: C-[Solicitacao]-[SeqFrasco]-[LetraCassete]
  const partes = cassetteSearchQuery.value.split('-');
  if (partes.length !== 4 || partes[0] !== 'C') {
    searchError.value = 'Código inválido. Certifique-se de bipar uma etiqueta de CASSETE (Ex: C-442806-01-A).';
    isLoading.value = false;
    return;
  }

  const solicitacaoId = partes[1];
  const seqFrascoEletra = `${partes[1]}-${partes[2]}`; // Para reconstruir o frasco

  try {
    const result = await fetchAghuExam(solicitacaoId);
    if (result) {
      aghuData.value = result;
      casseteIdentificado.value = {
        id: cassetteSearchQuery.value,
        baseSolicitacao: solicitacaoId,
        sulfixoOrigem: seqFrascoEletra
      };
    } else {
      searchError.value = 'Cassete lido, mas dados do AGHU não localizados.';
    }
  } catch (error) {
    searchError.value = 'Erro ao consultar rastreabilidade.';
  } finally {
    isLoading.value = false;
  }
};

// 2. Gerar a Hierarquia de Blocos e Lâminas (ADR 005)
const processarEGerarEtiquetas = () => {
  if (!casseteIdentificado.value || !aghuData.value) return;

  etiquetasBlocos.value = [];
  etiquetasLaminas.value = [];

  const baseSufixo = casseteIdentificado.value.id.replace('C-', ''); // Remove o C- para aproveitar a raiz

  // Para cada Bloco solicitado...
  for (let b = 1; b <= processForm.qtdBlocos; b++) {
    // Formato do Bloco: B-[Solicitacao]-[SeqFrasco]-[LetraCassete]-[SeqBloco] -> B-442806-01-A-1
    const idBloco = `B-${baseSufixo}-${b}`;
    
    etiquetasBlocos.value.push({
      codigoEtiqueta: idBloco,
      titulo: `Bloco ${b}`,
      subtitulo: aghuData.value.nomePaciente
    });

    // Para cada Lâmina gerada DESTE bloco...
    for (let l = 1; l <= processForm.qtdLaminasPorBloco; l++) {
      // Formato da Lâmina: L-[SufixoDoBloco]-[SeqLamina] -> L-442806-01-A-1-01
      const seqLamina = l.toString().padStart(2, '0');
      const idLamina = `L-${baseSufixo}-${b}-${seqLamina}`;

      etiquetasLaminas.value.push({
        codigoEtiqueta: idLamina,
        titulo: `Lâmina ${b}-${seqLamina} (${processForm.coloracao})`,
        subtitulo: aghuData.value.nomePaciente
      });
    }
  }

  console.log('Processamento Técnico Salvo:', {
    casseteOrigem: casseteIdentificado.value.id,
    tecnico: processForm.tecnico,
    tecnicaAplicada: processForm.coloracao,
    blocos: etiquetasBlocos.value.map(b => b.codigoEtiqueta),
    laminas: etiquetasLaminas.value.map(l => l.codigoEtiqueta)
  });
};
</script>