<template>
  <component :is="layout">
    <router-view />
  </component>
  <LoadingIndicator />
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { onMounted, computed } from 'vue';
import { useAuthStore } from './stores/auth';
import AppShell from './layouts/appShell.vue';
import LoginLayout from './layouts/loginLayout.vue';
import LoadingIndicator from './components/loadingIndicator/loadingIndicator.vue';

const route = useRoute();
const layout = computed(() => route.meta.layout === 'LoginLayout' ? LoginLayout : AppShell);

const authStore = useAuthStore();

onMounted(async () => {
  // O repasse era simulado em localStorage e notificado por toast no login.
  // Agora ele é persistido no servidor e a notificação real é o exame
  // aparecer na aba "Meus exames" da Macroscopia. Limpa o resíduo antigo.
  localStorage.removeItem('repassesPendentes');
  await authStore.initializeAuth();
});
</script>
