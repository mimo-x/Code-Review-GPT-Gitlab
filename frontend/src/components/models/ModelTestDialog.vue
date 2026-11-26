<template>
  <ModelDialog title="测试模型" description="会发送一次测试请求，可能计费。" @close="$emit('close')">
    <p class="pp-model-message pp-test-id">{{ model.label || model.model }}</p>
    <label class="pp-inline-form">测试内容
      <select v-model="mode" class="pp-model-input" :disabled="busy" @change="reset">
        <option value="text">文字响应</option>
        <option value="image">图片识别（红色测试图）</option>
        <option value="structured">结构化输出</option>
      </select>
    </label>
    <p v-if="error" class="pp-model-error" role="alert">{{ error }}</p>
    <div v-if="result" role="status">
      <p class="pp-model-message">测试通过 · {{ result.elapsed_ms }} ms</p>
      <pre class="pp-model-response">{{ result.text }}</pre>
    </div>
    <template #footer>
      <button type="button" class="pp-model-button" @click="$emit('close')">关闭</button>
      <button type="button" class="pp-model-primary" :disabled="busy" @click="run">
        {{ busy ? '测试中…' : '发送测试请求' }}
      </button>
    </template>
  </ModelDialog>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { modelError, testReviewModel, type ReviewModel, type TestMode } from '@/api/models'
import ModelDialog from './ModelDialog.vue'

const props = defineProps<{ model: ReviewModel }>()
defineEmits<{ close: [] }>()
const mode = ref<TestMode>('text')
const busy = ref(false)
const result = ref<Awaited<ReturnType<typeof testReviewModel>> | null>(null)
const error = ref('')
let operation: AbortController | undefined
onBeforeUnmount(() => operation?.abort())
const reset = () => { result.value = null; error.value = '' }
const run = async () => {
  if (busy.value) return
  busy.value = true
  reset()
  operation = new AbortController()
  try {
    result.value = await testReviewModel(props.model.id, mode.value, operation.signal)
  } catch (failure) {
    if (!operation.signal.aborted) error.value = modelError(failure, '模型测试失败')
  } finally {
    busy.value = false
  }
}
</script>
