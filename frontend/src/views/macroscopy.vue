<template>
  <div class="space-y-6">
    <!-- Busca -->
    <Card>
      <template #header>
        <h2 class="text-lg font-bold text-lab-text flex items-center gap-2">
          <QrCodeIcon class="h-5 w-5 text-gray-400" />
          Identificar Exame na Macroscopia
        </h2>
        <p class="text-sm text-gray-500">Bipe o QR Code do frasco ou digite o código do exame.</p>
      </template>

      <div class="flex items-end gap-3">
        <div class="flex-1 max-w-xs">
          <label class="form-label" for="codigoBusca">Código do exame ou frasco</label>
          <input
            id="codigoBusca"
            v-model="codigoBusca"
            type="text"
            class="form-control"
            placeholder="Digite aqui"
            @keyup.enter="resolverExame"
          >
        </div>
        <Button variant="primary" @click="resolverExame">Buscar</Button>
        <Button v-if="modo === 'exame'" variant="default" @click="voltarParaFila">Voltar para a fila</Button>
      </div>
    </Card>

    <!-- Fila -->
    <FilaMacroscopia v-if="modo === 'fila'" ref="fila" @abrir="abrirExame" />

    <!-- Não encontrado -->
    <Card v-else-if="modo === 'nao-encontrado'">
      <div class="flex items-start gap-3 p-2">
        <ExclamationTriangleIcon class="h-6 w-6 shrink-0 text-amber-600" />
        <div>
          <p class="font-semibold text-amber-700">Exame não encontrado</p>
          <p class="text-sm text-gray-600 mt-1">
            Esse código não corresponde a nenhum exame registrado nesta etapa.
          </p>
        </div>
      </div>
    </Card>

    <!-- Exame aberto -->
    <div v-else-if="modo === 'exame' && workspace && casoAtual" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ResumoCaso
          :caso="casoAtual"
          :frascos="workspace.frascos"
          :responsavel="workspace.posse.responsavel_nome"
        />

        <AssumirExame
          v-if="!workspace.posse.sou_o_dono || workspace.exame.etapa_macroscopia === 'CONCLUIDA'"
          :id-exame="workspace.exame.id_exame"
          :posse="workspace.posse"
          :total-frascos="workspace.exame.total_frascos"
          @atualizado="recarregarExame"
          @repassar="modalRepasseAberto = true"
        />

        <div v-else class="space-y-6">
          <ClivagemForm
            :id-exame="workspace.exame.id_exame"
            :codigo-local="workspace.exame.numero_solicitacao"
            :total-frascos="workspace.exame.total_frascos"
            @concluido="onClivagemConcluida"
          />
          <div class="flex justify-end">
            <button class="text-sm font-medium text-gray-500 hover:text-lab-primary" @click="modalRepasseAberto = true">
              Repassar este exame
            </button>
          </div>
        </div>
      </div>

      <!-- Etiquetas após a clivagem -->
      <Card v-if="etiquetasCassetes.length" class="border-t-4 border-t-lab-success">
        <div class="space-y-4">
          <div class="flex items-start gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
            <CheckCircleIcon class="h-6 w-6 shrink-0 text-green-600" />
            <div>
              <p class="font-semibold text-green-700">Clivagem finalizada com sucesso!</p>
              <p class="text-sm text-green-600 mt-0.5">
                {{ etiquetasCassetes.length }} cassete(s) gerados para o exame {{ workspace.exame.numero_solicitacao }}.
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
import {
  QrCodeIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowRightIcon,
} from '@heroicons/vue/24/outline';
import Card from '../components/card/card.vue';
import Button from '../components/button/button.vue';
import QrcodeBatchPrint from '../components/qrcode/qrcodeBatchPrint.vue';
import RepassModal from '../components/repassModal/repassModal.vue';
import FilaMacroscopia from '../components/macroscopy/filaMacroscopia.vue';
import ResumoCaso from '../components/macroscopy/resumoCaso.vue';
import AssumirExame from '../components/macroscopy/assumirExame.vue';
import ClivagemForm from '../components/macroscopy/clivagemForm.vue';
import { exameService, mapExameDetalhe, type ExameWorkspace, type MacroscopiaResult } from '../services/exameService';
import type { ExamCaseDetail } from '../types/exam';

const toast = useToast();

const modo = ref<'fila' | 'exame' | 'nao-encontrado'>('fila');
const codigoBusca = ref('');
const workspace = ref<ExameWorkspace | null>(null);
const casoAtual = ref<ExamCaseDetail | null>(null);
const etiquetasCassetes = ref<{ identificador: string; tipo: 'cassete'; rotulo: string }[]>([]);
const modalRepasseAberto = ref(false);
const fila = ref<InstanceType<typeof FilaMacroscopia> | null>(null);

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

async function resolverExame() {
  const codigo = codigoBusca.value.trim();
  if (!codigo) return;
  try {
    // A busca por frasco resolve para o EXAME: todos os frascos de um exame
    // compartilham o mesmo id_exame, então qualquer um serve de porta de entrada.
    const frascos = await exameService.buscarFrasco(
      /-F?\d+-/i.test(codigo) ? { codigo_interno: codigo } : { numero_solicitacao: codigo }
    );
    if (!frascos.length) { modo.value = 'nao-encontrado'; return; }
    await abrirExame(frascos[0].id_exame);
  } catch {
    modo.value = 'nao-encontrado';
  }
}

function voltarParaFila() {
  modo.value = 'fila';
  codigoBusca.value = '';
  workspace.value = null;
  casoAtual.value = null;
  etiquetasCassetes.value = [];
  fila.value?.carregar();
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
