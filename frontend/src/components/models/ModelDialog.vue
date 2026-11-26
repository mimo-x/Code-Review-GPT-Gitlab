<template>
  <dialog ref="dialog" class="pp-model-dialog pp-model-theme" :class="wide ? 'pp-model-dialog--wide' : ''"
    :aria-label="title" @close="$emit('close')" @cancel="cancel" @click.self="close">
    <div class="pp-dialog-shell">
      <header class="pp-dialog-heading">
        <div>
          <h2>{{ title }}</h2>
          <p v-if="description">{{ description }}</p>
        </div>
        <button type="button" class="pp-model-icon-btn" aria-label="关闭" :disabled="locked" @click="close"><X :size="17" /></button>
      </header>
      <div class="pp-dialog-scroll"><slot /></div>
      <footer v-if="$slots.footer" class="pp-dialog-buttons"><slot name="footer" /></footer>
    </div>
  </dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{ title: string; description?: string; wide?: boolean; locked?: boolean }>()
defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const close = () => { if (!props.locked) dialog.value?.close() }
const cancel = (event: Event) => { if (props.locked) event.preventDefault() }
onMounted(() => dialog.value?.showModal())
</script>
