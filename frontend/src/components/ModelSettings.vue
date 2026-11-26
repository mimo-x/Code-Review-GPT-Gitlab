<template>
  <section class="pp-model-settings pp-model-theme p-6" aria-label="模型配置">
    <h3 class="text-lg font-semibold">模型配置</h3>
    <div class="pp-default-review-model">
      <label for="review-model">默认审查模型</label>
      <select id="review-model" class="pp-model-input" :value="activeModel?.id ?? ''"
        :disabled="busy || !providersWithModels.length" @change="chooseModel">
        <option disabled value="">{{ providersWithModels.length ? '选择供应商和模型' : '请先添加模型' }}</option>
        <optgroup v-for="item in providersWithModels" :key="item.id" :label="item.name">
          <option v-for="model in item.models" :key="model.id" :value="model.id">{{ model.label || model.model }}</option>
        </optgroup>
      </select>
    </div>

    <p v-if="error" class="pp-model-error" role="alert">{{ error }}</p>
    <p v-if="status" class="sr-only" role="status">{{ status }}</p>

    <template v-if="!draft">
      <div class="pp-settings-heading">
        <h4>模型服务</h4>
        <button type="button" class="pp-model-button" :disabled="busy" @click="addingProvider = true">
          <Plus :size="15" /> 添加供应商
        </button>
      </div>
      <p v-if="loading" class="pp-model-message">正在加载…</p>
      <p v-else-if="!providers.length" class="pp-model-message">尚未添加供应商</p>
      <div v-else class="pp-provider-list">
        <button v-for="item in providers" :key="item.id" type="button" class="pp-provider-card"
          :disabled="busy" @click="editProvider(item)">
          <span class="pp-provider-card__main">
            <ProviderLogo :brand="providerBrand(item.preset)?.id" size="lg" />
            <span class="pp-model-grow">
              <span class="pp-provider-card__title">
                <strong>{{ item.name }}</strong>
                <span v-if="item.models.some((model) => model.is_active)" class="pp-provider-default-tag">默认服务</span>
              </span>
              <small class="pp-provider-address">{{ item.api_base || '默认 API 地址' }}</small>
            </span>
            <span class="pp-provider-key-state" :data-ready="item.has_api_key"
              :title="item.has_api_key ? '已设置 API Key' : '未设置 API Key'">
              <Lock v-if="item.has_api_key" :size="13" /><SlidersHorizontal v-else :size="13" />
            </span>
            <span class="pp-provider-card__arrow"><ChevronRight :size="16" /></span>
          </span>
          <span class="pp-provider-card__footer">
            <span class="pp-provider-protocol" :title="routeNames[item.provider]"><Link2 :size="13" /></span>
            <span class="pp-provider-model-summary"><Box :size="14" /><b>{{ item.models.length }} 个模型</b>
              <span>{{ previewModels(item) }}</span>
            </span>
          </span>
        </button>
      </div>
    </template>

    <template v-else>
      <header class="pp-model-detail-toolbar">
        <div class="pp-model-detail-identity">
          <button type="button" class="pp-model-icon-btn" aria-label="返回模型服务" :disabled="busy" @click="closeProvider">
            <ChevronLeft :size="17" />
          </button>
          <ProviderLogo :brand="providerBrand(draft.preset)?.id" size="sm" />
          <h4>{{ selectedProvider?.name || draft.name || '添加供应商' }}</h4>
        </div>
        <div class="pp-detail-actions">
          <template v-if="selectedProvider">
            <button type="button" class="pp-model-icon-btn" title="复制供应商" aria-label="复制供应商"
              :disabled="busy" @click="copyProvider"><Copy :size="15" /></button>
            <button type="button" class="pp-model-icon-btn" aria-label="移除供应商"
              :title="providerIsDefault ? '请先切换默认审查模型' : '移除供应商'"
              :disabled="busy || providerIsDefault" @click="openRemove(selectedProvider)">
              <Trash2 :size="15" />
            </button>
          </template>
          <span class="pp-save-state">{{ dirty ? '未保存' : '已保存' }}</span>
          <button v-if="selectedProvider" type="button" class="pp-model-icon-btn" title="重置连接设置" aria-label="重置连接设置"
            :disabled="busy || !dirty" @click="resetConnection"><RotateCcw :size="15" /></button>
          <button type="submit" form="llm-provider-connection" class="pp-model-primary" :disabled="busy || !dirty || needsNewKey">
            保存
          </button>
        </div>
      </header>
      <form id="llm-provider-connection" class="pp-connection" @submit.prevent="saveConnection">
        <h4>连接</h4>
        <label class="pp-detail-row">
          <span>服务名称</span>
          <input v-model.trim="draft.name" class="pp-model-input" maxlength="80" required :disabled="busy" />
        </label>
        <label class="pp-detail-row">
          <span>API 格式</span>
          <select v-model="draft.provider" class="pp-model-input" :disabled="busy">
            <option v-for="(label, value) in routeNames" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label class="pp-detail-row">
          <span>API 地址</span>
          <input v-model.trim="draft.api_base" class="pp-model-input" type="url" maxlength="500" :disabled="busy"
            :required="draft.preset === 'custom'" placeholder="https://api.example.com/v1" />
        </label>
        <div class="pp-detail-row">
          <label for="provider-key">API 密钥</label>
          <div class="pp-key-input">
            <input id="provider-key" v-model.trim="keyDraft" class="pp-model-input" :type="revealKey ? 'text' : 'password'"
              autocomplete="new-password" :disabled="busy"
              :placeholder="clearKey ? '保存后清除 API Key' : selectedProvider?.has_api_key ? '留空保留已保存的 Key' : '填写 API Key'"
              @input="clearKey = false" />
            <button type="button" class="pp-model-icon-btn" :aria-label="revealKey ? '隐藏新密钥' : '显示新密钥'"
              :title="revealKey ? '隐藏新密钥' : '显示新密钥'" :disabled="!keyDraft"
              @click="revealKey = !revealKey"><Lock :size="15" /></button>
            <button type="button" class="pp-model-icon-btn" aria-label="清除密钥" title="清除密钥"
              :disabled="!selectedProvider?.has_api_key && !keyDraft" @click="markKeyCleared"><X :size="16" /></button>
          </div>
        </div>
        <p v-if="needsNewKey" class="pp-model-message">更改 API 地址或格式后，请重新填写或清除 Key。</p>
      </form>

      <div class="pp-settings-heading">
        <h4>模型</h4>
        <div v-if="selectedProvider" class="pp-detail-actions">
          <span class="pp-model-message">{{ selectedProvider.models.length }}</span>
          <button type="button" class="pp-model-icon-btn" title="添加模型" aria-label="添加模型"
            :disabled="busy || dirty" @click="addingModel = true"><Plus :size="18" /></button>
        </div>
      </div>
      <template v-if="selectedProvider">
        <label class="pp-input-with-icon">
          <Search :size="16" /><input v-model.trim="modelQuery" class="pp-model-input" aria-label="搜索已添加的模型" placeholder="搜索模型" />
        </label>
        <ul v-if="visibleModels.length" class="pp-saved-models">
          <li v-for="model in visibleModels" :key="model.id" class="pp-saved-model">
            <span class="pp-model-grow">
              <strong>{{ model.label || model.model }}</strong>
              <small v-if="model.label && model.label !== model.model">{{ model.model }}</small>
            </span>
            <div class="pp-saved-model-actions">
              <span v-if="catalogFacts.get(model.model)?.contextWindow" class="pp-model-message">{{ contextLabel(model) }}</span>
              <Image v-if="catalogFacts.get(model.model)?.vision" :size="14" aria-label="支持图片" />
              <Gauge v-if="hasReasoning(model)" :size="14" aria-label="支持思考" />
              <span v-if="model.is_active" class="pp-provider-default-tag">默认</span>
              <button type="button" class="pp-model-icon-btn" :title="dirty ? '请先保存连接' : '测试模型'" aria-label="测试模型"
                :disabled="busy || dirty" @click="testing = model"><FlaskConical :size="15" /></button>
              <button type="button" class="pp-model-icon-btn" title="编辑模型" aria-label="编辑模型" :disabled="busy"
                @click="openModelEdit(model)"><Pencil :size="15" /></button>
              <button v-if="!model.is_active" type="button" class="pp-model-icon-btn" title="设为默认模型" aria-label="设为默认模型"
                :disabled="busy" @click="activate(model.id)"><ArrowUp :size="15" /></button>
              <button type="button" class="pp-model-icon-btn" title="移除模型" aria-label="移除模型"
                :disabled="busy || model.is_active" @click="openRemove(model)"><Trash2 :size="15" /></button>
            </div>
          </li>
        </ul>
        <p v-else class="pp-model-message">{{ modelQuery ? '没有匹配的模型。' : '尚未添加模型。' }}</p>
      </template>
      <p v-else class="pp-model-message">保存供应商后可添加模型。</p>
    </template>

    <ProviderPicker v-if="addingProvider" @close="addingProvider = false" @select="selectPreset" />
    <ModelPicker v-if="addingModel && selectedProvider" :provider="selectedProvider"
      @close="addingModel = false" @saved="updateSavedModels" />
    <ModelTestDialog v-if="testing" :model="testing" @close="testing = null" />

    <ModelDialog v-if="modelEdit" title="编辑模型" :locked="busy" @close="modelEdit = null">
      <form id="llm-edit-model" class="pp-inline-form" @submit.prevent="saveModelEdit">
        <label>模型 ID<input v-model.trim="modelEdit.model" class="pp-model-input" maxlength="100" required /></label>
        <label>显示名称<input v-model.trim="modelEdit.label" class="pp-model-input" maxlength="100" /></label>
      </form>
      <p v-if="modalError" class="pp-model-error" role="alert">{{ modalError }}</p>
      <template #footer>
        <button type="button" class="pp-model-button" :disabled="busy" @click="modelEdit = null">取消</button>
        <button type="submit" form="llm-edit-model" class="pp-model-primary" :disabled="busy">保存</button>
      </template>
    </ModelDialog>

    <ModelDialog v-if="removing" :title="'移除' + ('models' in removing ? '供应商' : '模型')" :locked="busy"
      @close="removing = null">
      <p class="pp-model-message">
        移除 {{ 'models' in removing ? removing.name + ' 及其模型' : removing.label || removing.model }}？
      </p>
      <p v-if="modalError" class="pp-model-error" role="alert">{{ modalError }}</p>
      <template #footer>
        <button type="button" class="pp-model-button" :disabled="busy" @click="removing = null">取消</button>
        <button type="button" class="pp-model-primary pp-danger-button" :disabled="busy" @click="confirmRemove">确认移除</button>
      </template>
    </ModelDialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowUp, Box, ChevronLeft, ChevronRight, Copy, FlaskConical, Gauge, Image, Link2, Lock, Pencil, Plus,
  RotateCcw, Search, SlidersHorizontal, Trash2, X } from 'lucide-vue-next'
import { activateReviewModel, duplicateModelProvider, getModelProviders, modelError, removeModelProvider,
  removeReviewModel, saveModelProvider, updateReviewModel,
  type ConnectionSettings, type ModelProvider, type ReviewModel } from '@/api/models'
import ModelDialog from './models/ModelDialog.vue'
import ModelPicker from './models/ModelPicker.vue'
import ModelTestDialog from './models/ModelTestDialog.vue'
import ProviderLogo from './models/ProviderLogo.vue'
import ProviderPicker from './models/ProviderPicker.vue'
import { presets, providerBrand, type ProviderPreset } from './models/provider-presets'
import { bundledCatalog } from './models/model-catalog'
import './models/paperpane-models.css'

const routeNames: Record<string, string> = {
  openai_responses: 'OpenAI Responses', openai: 'OpenAI Chat Completions', anthropic: 'Anthropic Messages',
  gemini: 'Gemini 原生', deepseek: 'DeepSeek', unionllm: 'UnionLLM', litellm: 'LiteLLM',
}
const routeForProtocol = { 'openai-responses': 'openai_responses', 'openai-chat': 'openai', anthropic: 'anthropic', gemini: 'gemini' }
const providers = ref<ModelProvider[]>([])
const selectedId = ref<number | null>(null)
const draft = ref<ConnectionSettings | null>(null)
const keyDraft = ref('')
const clearKey = ref(false)
const revealKey = ref(false)
const modelQuery = ref('')
const addingProvider = ref(false)
const addingModel = ref(false)
const testing = ref<ReviewModel | null>(null)
const modelEdit = ref<ReviewModel | null>(null)
const removing = ref<ModelProvider | ReviewModel | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const modalError = ref('')
const status = ref('')

const selectedProvider = computed(() => providers.value.find((item) => item.id === selectedId.value))
const providersWithModels = computed(() => providers.value.filter((item) => item.models.length))
const activeModel = computed(() => providers.value.flatMap((item) => item.models).find((model) => model.is_active))
const providerIsDefault = computed(() => selectedProvider.value?.models.some((item) => item.is_active))
const normalBase = (value?: string | null) => (value ?? '').replace(/\/+$/, '')
const connectionChanged = computed(() => {
  const saved = selectedProvider.value
  return Boolean(saved && draft.value &&
    (saved.provider !== draft.value.provider || normalBase(saved.api_base) !== normalBase(draft.value.api_base)))
})
const needsNewKey = computed(() => selectedProvider.value?.has_api_key && connectionChanged.value && !keyDraft.value && !clearKey.value)
const dirty = computed(() => Boolean(draft.value &&
  (!selectedProvider.value || connectionChanged.value || selectedProvider.value.name !== draft.value.name ||
    keyDraft.value || clearKey.value)))
const visibleModels = computed(() => (selectedProvider.value?.models ?? []).filter((model) =>
  (model.label + ' ' + model.model).toLowerCase().includes(modelQuery.value.toLowerCase())))
const catalogFacts = computed(() => {
  const preset = presets.find((item) => item.id === selectedProvider.value?.preset)
  return new Map(bundledCatalog.models.filter((item) => item.provider === preset?.provider).map((item) => [item.modelId, item]))
})
const contextLabel = (model: ReviewModel) => Math.round((catalogFacts.value.get(model.model)?.contextWindow ?? 0) / 1000) + 'K'
const hasReasoning = (model: ReviewModel) => {
  const kind = catalogFacts.value.get(model.model)?.reasoning.kind
  return kind && kind !== 'none' && kind !== 'unknown'
}
const previewModels = (item: ModelProvider) =>
  item.models.slice(0, 2).map((model) => model.label || model.model).join(' · ') + (item.models.length > 2 ? ' 等' : '')

const setDraft = (id: number | null, connection: ConnectionSettings) => {
  selectedId.value = id
  draft.value = { ...connection }
  keyDraft.value = ''
  clearKey.value = false
  revealKey.value = false
  modelQuery.value = ''
  error.value = ''
}
const editProvider = ({ id, name, preset, provider, api_base, timeout }: ModelProvider) =>
  setDraft(id, { name, preset, provider, api_base, timeout })
const selectPreset = (preset: ProviderPreset) => {
  addingProvider.value = false
  setDraft(null, { name: preset.id === 'custom' ? '' : preset.name, preset: preset.id,
    provider: routeForProtocol[preset.protocol], api_base: preset.url || null, timeout: 600 })
}
const closeProvider = () => {
  draft.value = null
  selectedId.value = null
  keyDraft.value = ''
  error.value = ''
}
const resetConnection = () => { if (selectedProvider.value) editProvider(selectedProvider.value) }
const markKeyCleared = () => {
  keyDraft.value = ''
  clearKey.value = !!selectedProvider.value?.has_api_key
  revealKey.value = false
}

const run = async (operation: () => Promise<void>, fallback: string, modal = false) => {
  busy.value = true
  const target = modal ? modalError : error
  target.value = ''
  status.value = ''
  try {
    await operation()
  } catch (failure) {
    target.value = modelError(failure, fallback)
  } finally {
    busy.value = false
  }
}

const keepProvider = (saved: ModelProvider) => {
  const index = providers.value.findIndex((item) => item.id === saved.id)
  if (index === -1) providers.value.push(saved)
  else providers.value[index] = saved
  editProvider(saved)
}
const saveConnection = () => {
  if (!draft.value || needsNewKey.value) return
  const payload = { ...draft.value, api_base: normalBase(draft.value.api_base) || null }
  if (keyDraft.value || clearKey.value) payload.api_key = clearKey.value ? '' : keyDraft.value
  return run(async () => {
    keepProvider(await saveModelProvider(selectedId.value, payload))
    status.value = '供应商已保存'
  }, '保存供应商失败')
}

const copyProvider = () => {
  const id = selectedId.value
  if (id === null) return
  return run(async () => { keepProvider(await duplicateModelProvider(id)) }, '复制供应商失败')
}
const updateSavedModels = (models: ReviewModel[]) => {
  if (selectedProvider.value) selectedProvider.value.models = models
}
const openModelEdit = (model: ReviewModel) => { modelEdit.value = { ...model }; modalError.value = '' }
const saveModelEdit = () => {
  const model = modelEdit.value
  const provider = selectedProvider.value
  if (!model || !provider) return
  return run(async () => {
    const saved = await updateReviewModel(model.id, { label: model.label, model: model.model })
    provider.models = provider.models.map((item) => item.id === saved.id ? saved : item)
    modelEdit.value = null
  }, '保存模型失败', true)
}

const openRemove = (item: ReviewModel | ModelProvider) => { removing.value = item; modalError.value = '' }
const confirmRemove = () => {
  const item = removing.value
  if (!item) return
  return run(async () => {
    if ('models' in item) {
      await removeModelProvider(item.id)
      providers.value = providers.value.filter((provider) => provider.id !== item.id)
      closeProvider()
    } else if (selectedProvider.value) {
      await removeReviewModel(item.id)
      selectedProvider.value.models = selectedProvider.value.models.filter((model) => model.id !== item.id)
    }
    removing.value = null
  }, '移除失败', true)
}

const activate = (id: number) => run(async () => {
  await activateReviewModel(id)
  for (const provider of providers.value) {
    for (const model of provider.models) model.is_active = model.id === id
  }
  status.value = '默认审查模型已更新'
}, '切换模型失败')
const chooseModel = async (event: Event) => {
  const field = event.target as HTMLSelectElement
  await activate(Number(field.value))
  field.value = String(activeModel.value?.id ?? '')
}
onMounted(async () => {
  try {
    providers.value = await getModelProviders()
  } catch {
    error.value = '加载模型供应商失败'
  } finally {
    loading.value = false
  }
})
</script>
