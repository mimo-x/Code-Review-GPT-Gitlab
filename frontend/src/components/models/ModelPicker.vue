<template>
  <ModelDialog :title="'添加模型 · ' + provider.name" :locked="saving" @close="$emit('close')">
    <div class="pp-model-tabs" role="tablist" aria-label="模型来源">
      <button v-for="[id, label] in tabs" :key="id" type="button" role="tab"
        :aria-selected="source === id" @click="changeSource(id)">{{ label }}</button>
    </div>

    <form v-if="source === 'manual'" id="pp-manual-model" class="pp-inline-form" @submit.prevent="addManual">
      <label>模型 ID<input v-model.trim="manual.model" class="pp-model-input" maxlength="100" required
        placeholder="填写供应商提供的模型 ID" /></label>
      <label>显示名称<input v-model.trim="manual.label" class="pp-model-input" maxlength="100" placeholder="可选" /></label>
    </form>
    <template v-else>
      <div class="pp-model-picker-tools">
        <label>能力筛选
          <select v-model="capability" class="pp-model-input">
            <option value="all">全部模型</option><option value="vision">支持图片</option><option value="reasoning">支持思考</option>
          </select>
        </label>
        <label v-if="source === 'catalog'">模型厂商
          <select v-model="brand" class="pp-model-input">
            <option v-for="item in catalogBrands" :key="item.provider" :value="item.provider">{{ item.name }}</option>
          </select>
        </label>
        <button v-if="source === 'catalog'" type="button" class="pp-model-icon-btn"
          aria-label="更新常用模型目录" :title="'目录更新于 ' + catalog.updatedAt.slice(0, 10)"
          :disabled="loading" @click="refreshCatalog"><RefreshCw :size="16" /></button>
        <button v-else type="button" class="pp-model-button" :disabled="loading" @click="getEndpointModels">
          {{ loading ? '获取中…' : '获取模型列表' }}
        </button>
        <label class="pp-picker-search">
          <span class="sr-only">搜索模型</span>
          <input v-model.trim="query" class="pp-model-input" placeholder="搜索名称或 ID" />
        </label>
      </div>
      <div class="pp-model-candidates">
        <label v-for="item in results.slice(0, limit)" :key="item.modelId" class="pp-model-candidate">
          <input v-model="chosen" type="checkbox" :value="item.modelId"
            :disabled="existing.has(item.modelId) || saving" />
          <span class="pp-model-grow">
            <strong>{{ item.label }}</strong><small>{{ item.modelId }}</small>
            <span class="pp-model-badges">
              <span v-if="existing.has(item.modelId)">已添加</span>
              <span v-if="item.protocol">{{ protocols.find((protocol) => protocol.value === item.protocol)?.label }}</span>
              <span v-if="item.contextWindow">{{ Math.round(item.contextWindow / 1000) }}K 上下文</span>
              <span v-if="item.vision">图片</span>
            </span>
          </span>
        </label>
        <button v-if="results.length > limit" type="button" class="pp-model-button pp-more-models" @click="limit += 80">显示更多</button>
        <p v-if="!results.length && !loading && !error" class="pp-model-message">没有匹配的模型。</p>
      </div>
    </template>
    <p v-if="error" class="pp-model-error" role="alert">{{ error }}</p>
    <p v-else-if="message" class="pp-model-message" role="status">{{ message }}</p>

    <template #footer>
      <button type="button" class="pp-model-button" :disabled="saving" @click="$emit('close')">取消</button>
      <button v-if="source === 'manual'" type="submit" form="pp-manual-model" class="pp-model-primary"
        :disabled="saving || !manual.model">添加</button>
      <button v-else type="button" class="pp-model-primary" :disabled="saving || !chosen.length"
        @click="addSelection">添加 {{ chosen.length }} 个模型</button>
    </template>
  </ModelDialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { addReviewModels, listEndpointModels, modelError, type ModelEntry, type ModelProvider, type ReviewModel } from '@/api/models'
import ModelDialog from './ModelDialog.vue'
import { bundledCatalog, parseCatalog, readJson, type CatalogModel } from './model-catalog'
import { presets, protocols } from './provider-presets'

const props = defineProps<{ provider: ModelProvider }>()
const emit = defineEmits<{ saved: [models: ReviewModel[]]; close: [] }>()
const tabs = [['catalog', '常用模型'], ['endpoint', '此端点模型'], ['manual', '手动添加']] as const
type Source = typeof tabs[number][0]
type Candidate = Pick<CatalogModel, 'modelId' | 'label'> & Partial<CatalogModel>

const source = ref<Source>('catalog')
const catalog = ref(bundledCatalog)
const preset = presets.find((item) => item.id === props.provider.preset)
const brand = ref(preset?.provider || 'openai')
const catalogBrands = [...new Map(presets.filter((item) => item.provider).map((item) => [item.provider, item])).values()]
const capability = ref('all')
const query = ref('')
const limit = ref(80)
const chosen = ref<string[]>([])
const endpoint = ref<Candidate[] | null>(null)
const manual = ref<ModelEntry>({ model: '', label: '' })
const saving = ref(false)
const loading = ref(false)
const error = ref('')
const message = ref('')
const existing = computed(() => new Set(props.provider.models.map((item) => item.model)))
const items = computed<Candidate[]>(() => source.value === 'catalog'
  ? catalog.value.models.filter((item) => item.provider === brand.value)
  : endpoint.value ?? [])
const results = computed(() => items.value.filter((item) =>
  item.modelId.length <= 100 &&
  (capability.value !== 'vision' || item.vision) &&
  (capability.value !== 'reasoning' || (item.reasoning && !['unknown', 'none'].includes(item.reasoning.kind))) &&
  (item.label + ' ' + item.modelId).toLowerCase().includes(query.value.toLowerCase())))

watch([brand, capability, query], () => { limit.value = 80 })
watch(brand, () => { chosen.value = [] })
let fetchOperation: AbortController | undefined
onBeforeUnmount(() => fetchOperation?.abort())
const load = async (operation: (signal: AbortSignal) => Promise<void>, fallback: string) => {
  fetchOperation?.abort()
  const controller = new AbortController()
  fetchOperation = controller
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    await operation(controller.signal)
  } catch (failure) {
    if (!controller.signal.aborted) error.value = modelError(failure, fallback)
  } finally {
    if (fetchOperation === controller) loading.value = false
  }
}

const getEndpointModels = () => load(async (signal) => {
  const data = await listEndpointModels(props.provider.id, signal)
  // Only the preset's own endpoint inherits metadata from the public directory.
  const known = preset?.url === props.provider.api_base
    ? new Map(catalog.value.models.filter((item) => item.provider === preset?.provider).map((item) => [item.modelId, item]))
    : new Map<string, CatalogModel>()
  endpoint.value = data.models.map((item) => ({ ...known.get(item.modelId), ...item }))
  message.value = '找到 ' + endpoint.value.length + ' 个模型'
}, '获取端点模型失败')

const refreshCatalog = () => load(async (signal) => {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 15000)
  const cancel = () => controller.abort()
  signal.addEventListener('abort', cancel, { once: true })
  try {
    const response = await fetch('https://models.dev/api.json', { credentials: 'omit', redirect: 'error', signal: controller.signal })
    catalog.value = parseCatalog(await readJson(response, 8_000_000))
    message.value = '常用模型目录已更新'
  } finally {
    signal.removeEventListener('abort', cancel)
    clearTimeout(timeout)
  }
}, '更新目录失败，保留当前目录。')

const changeSource = (tab: Source) => {
  if (tab === source.value || saving.value) return
  fetchOperation?.abort()
  source.value = tab
  chosen.value = []
  query.value = ''
  capability.value = 'all'
  limit.value = 80
  error.value = ''
  message.value = ''
  if (tab === 'endpoint' && endpoint.value === null) void getEndpointModels()
}

const add = async (entries: ModelEntry[], keepOpen = false) => {
  error.value = ''
  message.value = ''
  if (entries.length > 100) {
    error.value = '每次最多添加 100 个模型。'
    return
  }
  if (!entries.length || saving.value) return
  saving.value = true
  try {
    emit('saved', await addReviewModels(props.provider.id, entries))
    if (keepOpen) {
      message.value = '已添加 ' + entries[0].model
      manual.value = { model: '', label: '' }
    } else {
      emit('close')
    }
  } catch (failure) {
    error.value = modelError(failure, '添加模型失败')
  } finally {
    saving.value = false
  }
}

const addManual = () => {
  if (existing.value.has(manual.value.model)) {
    error.value = '此供应商已添加该模型。'
    return
  }
  if (manual.value.model) void add([manual.value], true)
}

const addSelection = () => add(items.value
  .filter((item) => chosen.value.includes(item.modelId) && !existing.value.has(item.modelId))
  .map((item) => ({ model: item.modelId, label: item.label.slice(0, 100) })))
</script>
