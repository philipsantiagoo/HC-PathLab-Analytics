import { defineStore } from 'pinia';
import { ref } from 'vue';

export interface Notificacao {
  id: string;
  tipo: 'repasse';
  titulo: string;
  mensagem: string;
  timestamp: string;
  lida: boolean;
}

export const useNotificacoesStore = defineStore('notificacoes', () => {
  const notificacoes = ref<Notificacao[]>([]);

  function carregarRepassesPendentes(nomeUsuario: string) {
    const todos = JSON.parse(localStorage.getItem('repassesPendentes') || '[]');
    const meus = todos.filter((r: any) => r.destinatario === nomeUsuario);

    if (meus.length === 0) return;

    meus.forEach((r: any) => {
      notificacoes.value.push({
        id: `${r.codigoLocal}-${r.timestamp}`,
        tipo: 'repasse',
        titulo: 'Exame repassado para você',
        mensagem: `${r.remetente} repassou o exame ${r.codigoLocal} (${r.nomePaciente})${r.motivo ? ` — ${r.motivo}` : ''}.`,
        timestamp: r.timestamp,
        lida: false,
      });
    });

    // Remove os que já foram carregados (não notifica de novo na próxima abertura).
    const restantes = todos.filter((r: any) => r.destinatario !== nomeUsuario);
    localStorage.setItem('repassesPendentes', JSON.stringify(restantes));
  }

  function marcarTodasLidas() {
    notificacoes.value.forEach(n => n.lida = true);
  }

  const naoLidas = () => notificacoes.value.filter(n => !n.lida).length;

  return { notificacoes, carregarRepassesPendentes, marcarTodasLidas, naoLidas };
});