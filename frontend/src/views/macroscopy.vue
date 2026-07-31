<template>
  <div class="space-y-6">
    <BuscaExame
      ref="busca"
      titulo="Identificar Exame na Macroscopia"
      descricao="Bipe o QR Code do frasco ou digite o código do exame."
      rotulo="Código do exame ou frasco"
      :mostrar-voltar="modo === 'exame'"
      @buscar="resolverExame"
      @voltar="voltarParaFila"
    />

    <FilaEtapa
      v-if="modo === 'fila'"
      ref="fila"
      etapa="macroscopia"
      titulo="Fila da Macroscopia"
      subtitulo="Exames aguardando clivagem"
      :colunas-extras="colunasExtras"
      @abrir="abrirExame"
    />

    <Card v-else-if="modo === 'nao-encontrado'">
      <div class="flex items-start gap-3 p-2">
        <ExclamationTriangleIcon class="h-6 w-6 shrink-0 text-amber-600" />
        <div>
          <p class="font-semibold text-amber-700">Exame não encontrado</p>
          <p class="text-sm text-gray-600 mt-1">
            Esse código não corresponde a nenhum exame nesta etapa.
          </p>
        </div>
      </div>
    </Card>

    <div v-else-if="modo === 'exame' && workspace && casoAtual" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ResumoCaso
          :caso="casoAtual"
          :frascos="workspace.frascos"
          :responsavel="workspace.posse.responsavel_nome"
        />

        <div class="space-y-6">
          <PosseExameCard
            v-if="!workspace.posse.pode_executar"
            etapa="macroscopia"
            :id-exame="workspace.exame.id_exame"
            :posse="workspace.posse"
            :historico="workspace.historico_etapas"
            :descricao-escopo="`os ${workspace.exame.total_frascos} frasco(s) passam a andar com você`"
            @atualizado="recarregarExame"
            @repassar="modalRepasseAberto = true"
          />

          <template v-else>
            <ClivagemForm
              :id-exame="workspace.exame.id_exame"
              :codigo-local="workspace.exame.numero_solicitacao"
              :total-frascos="workspace.exame.total_frascos"
              @concluido="onClivagemConcluida"
            />
            <div class="flex justify-end gap-4">
              <button class="text-sm font-medium text-gray-500 hover:text-lab-primary" @click="devolver">
                Devolver à fila
              </button>
              <button class="text-sm font-medium text-gray-500 hover:text-lab-primary" @click="modalRepasseAberto = true">
                Repassar este exame
              </button>
            </div>
          </template>
        </div>
      </div>

      <Card v-if="etiquetasCassetes.length" class="border-t-4 border-t-lab-success">
        <div class="space-y-4">
          <div class="flex items-start gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
            <CheckCircleIcon class="h-6 w-6 shrink-0 text-green-600" />
            <div>
              <p class="font-semibold text-green-700">Clivagem finalizada com sucesso!</p>
              <p class="text-sm text-green-600 mt-0.5">
                {{ etiquetasCassetes.length }} cassete(s) gerados para o exame
                {{ workspace.exame.numero_solicitacao }}. O exame já está na fila do Processamento.
              </p>
            </div>
          </div>
          <div class="p-4 bg-gray-50 rounded-lg border border-gray-100">
            <QrcodeBatchPrint :items="etiquetasCassetes" />
          </div>
          <div class="flex justify-end">
            <Button variant="primary" class="w-full md:w-auto md:min-w-[240px]" @click="voltarParaFila">
              <template #icon><ArrowRightIcon class="h-5 w-5" /></template>
              Concluir e voltar para a fila
            </Button>
          </div>
        </div>
      </Card>
    </div>

    <RepassModal
      :show="modalRepasseAberto"
      etapa="macroscopia"
      :id-exame="workspace?.exame.id_exame ?? ''"
      :codigo-local="workspace?.exame.numero_solicitacao ?? ''"
      :nome-paciente="workspace?.exame.paciente_nome ?? ''"
      @close="modalRepasseAberto = false"
      @repassado="onRepassado"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useToast } from 'vue-toastification';
import { ExclamationTriangleIcon, CheckCircleIcon, ArrowRightIcon } from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import QrcodeBatchPrint from '../components/qrcode/qrcodeBatchPrint.vue';
import RepassModal from '../components/repassModal/repassModal.vue';
import BuscaExame from '../components/fila/buscaExame.vue';
import FilaEtapa from '../components/fila/filaEtapa.vue';
import PosseExameCard from '../components/fila/posseExameCard.vue';
import ResumoCaso from '../components/macroscopy/resumoCaso.vue';
import ClivagemForm from '../components/macroscopy/clivagemForm.vue';
import { exameService, mapExameDetalhe, type ExameWorkspace, type MacroscopiaResult } from '../services/exameService';
import { etapaService, type LinhaFila } from '../services/etapaService';
import type { ExamCaseDetail } from '../types/exam';

const toast = useToast();

const modo = ref<'fila' | 'exame' | 'nao-encontrado'>('fila');
const workspace = ref<ExameWorkspace | null>(null);
const casoAtual = ref<ExamCaseDetail | null>(null);
const etiquetasCassetes = ref<{ identificador: string; tipo: 'cassete'; rotulo: string }[]>([]);
const modalRepasseAberto = ref(false);
const fila = ref<InstanceType<typeof FilaEtapa> | null>(null);
const busca = ref<InstanceType<typeof BuscaExame> | null>(null);

const colunasExtras = [
  { text: 'Frascos', value: 'frascos', align: 'center' as const, valor: (l: LinhaFila) => l.total_frascos },
];

async function abrirExame(idExame: string) {
  try {
    workspace.value = await exameService.workspaceMacroscopia(idExame);
    // O detalhe agregado já existe e é usado pelo dashboard: aproveitá-lo evita
    // fabricar o caso a partir de um frasco (que enchia a tela de "—").
    casoAtual.value = mapExameDetalhe(await exameService.detalhe(idExame));
    etiquetasCassetes.value = [];
    modo.value = 'exame';
  } catch {
    modo.value = 'nao-encontrado';
  }
}

async function recarregarExame() {
  if (workspace.value) await abrirExame(workspace.value.exame.id_exame);
}

async function resolverExame(codigo: string) {
  if (!codigo) return;
  try {
    // A busca por frasco resolve para o EXAME: todos os frascos de um exame
    // compartilham o mesmo id_exame, então qualquer um serve de porta de entrada.
    const frascos = await exameService.buscarFrasco(
      /-F?\d+-/i.test(codigo) ? { codigo_interno: codigo } : { numero_solicitacao: codigo },
    );
    if (!frascos.length) { modo.value = 'nao-encontrado'; return; }
    await abrirExame(frascos[0].id_exame);
  } catch {
    modo.value = 'nao-encontrado';
  }
}

function voltarParaFila() {
  modo.value = 'fila';
  workspace.value = null;
  casoAtual.value = null;
  etiquetasCassetes.value = [];
  busca.value?.limpar();
  fila.value?.carregar();
}

async function devolver() {
  if (!workspace.value) return;
  try {
    await etapaService.liberar('macroscopia', workspace.value.exame.id_exame);
    toast.success('Exame devolvido à fila.');
    voltarParaFila();
  } catch {
    // interceptor exibe erro
  }
}

function onClivagemConcluida(resultado: MacroscopiaResult) {
  const codigo = workspace.value?.exame.numero_solicitacao ?? '';
  etiquetasCassetes.value = resultado.cassetes.map(c => ({
    identificador: `${codigo}-${c.letra_fragmento}`,
    tipo: 'cassete' as const,
    rotulo: `Cassete ${c.letra_fragmento} — ${c.descricao_estrutura ?? ''}`,
  }));
}

function onRepassado(destinatario: string) {
  modalRepasseAberto.value = false;
  toast.success(`Exame repassado para ${destinatario}.`);
  voltarParaFila();
}
</script>
