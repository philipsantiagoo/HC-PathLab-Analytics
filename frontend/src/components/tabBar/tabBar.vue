<template>
  <div class="flex flex-wrap items-center gap-2">
    <button
      v-for="tab in tabs"
      :key="tab.value"
      type="button"
      class="px-4 py-1.5 text-sm font-medium rounded-full transition-colors inline-flex items-center gap-2"
      :class="tab.value === modelValue
        ? 'bg-lab-primary text-white'
        : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'"
      @click="emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
      <span
        v-if="tab.count !== undefined"
        class="text-xs px-1.5 py-0.5 rounded-full font-semibold"
        :class="tab.value === modelValue ? 'bg-white/25 text-white' : 'bg-gray-100 text-gray-500'"
      >
        {{ tab.count }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
export interface Tab {
  value: string;
  label: string;
  count?: number;
}

defineProps<{
  modelValue: string;
  tabs: Tab[];
}>();

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>();
</script>
