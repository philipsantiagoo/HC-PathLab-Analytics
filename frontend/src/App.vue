<template>
  <component :is="layout">
    <router-view />
  </component>
  <LoadingIndicator />
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { onMounted, computed, watch } from 'vue';
import { useAuthStore } from './stores/auth';
import { useNotificacoesStore } from './stores/notificacoes';
import { useToast } from 'vue-toastification';
import AppShell from './layouts/appShell.vue';
import LoginLayout from './layouts/loginLayout.vue';
import LoadingIndicator from './components/loadingIndicator/loadingIndicator.vue';

const route = useRoute();
const layout = computed(() => route.meta.layout === 'LoginLayout' ? LoginLayout : AppShell);

const authStore = useAuthStore();
const notificacoesStore = useNotificacoesStore();
const toast = useToast();

// Carrega notificações de repasse quando o usuário loga (ou já está logado ao abrir).
watch(
  () => authStore.isAuthenticated,
  (autenticado) => {
    if (!autenticado) return;
    const nome = authStore.user?.givenName?.[0] || authStore.user?.username;
    if (!nome) return;

    notificacoesStore.carregarRepassesPendentes(nome);
    notificacoesStore.notificacoes
      .filter(n => !n.lida)
      .forEach(n => {
        toast.info(n.mensagem, { timeout: 8000 });
      });
    notificacoesStore.marcarTodasLidas();
  },
  { immediate: true }
);

onMounted(async () => {
  await authStore.initializeAuth();
});
</script>