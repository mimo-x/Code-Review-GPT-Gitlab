<template>
  <span class="pp-provider-logo" :data-size="size" :style="style" aria-hidden="true">
    <span v-if="mark" class="pp-provider-logo__mark" />
    <SlidersHorizontal v-else :size="23" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SlidersHorizontal } from 'lucide-vue-next'
import { providerBrands } from './provider-presets'
import marks from './provider-icons.json'

// Paperpane's local marks come from models.dev and Lobe Icons (MIT).
const props = defineProps<{ brand?: string; size?: 'sm' | 'md' | 'lg' }>()
const mark = computed(() => marks[props.brand as keyof typeof marks])
const style = computed(() => ({
  '--provider-ink': providerBrands.find((item) => item.id === props.brand)?.color ?? 'var(--pp-accent)',
  '--provider-mark': mark.value ? 'url("data:image/svg+xml,' + encodeURIComponent(mark.value) + '")' : undefined,
}))
</script>
