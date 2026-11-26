<template>
  <ModelDialog wide :title="selected ? '连接 ' + selected.name : '添加供应商'"
    :description="selected ? '选择 API 密钥对应的服务区域。' : '选择供应商并配置审查模型。'"
    @close="$emit('close')">
    <template v-if="selected">
      <div class="pp-provider-variant-heading">
        <ProviderLogo :brand="selected.id" size="lg" />
        <div><h3>{{ selected.name }}</h3><p>{{ selected.website }}</p></div>
      </div>
      <div class="pp-provider-variants">
        <button v-for="preset in choices(selected.id)" :key="preset.id" type="button"
          @click="$emit('select', preset)">
          <span><strong>{{ preset.region || preset.name }}</strong><small>{{ preset.url }}</small></span>
          <ChevronRight :size="16" />
        </button>
      </div>
    </template>
    <template v-else>
      <div class="pp-provider-picker-tools">
        <label class="pp-input-with-icon">
          <Search :size="16" />
          <input v-model.trim="query" class="pp-model-input" aria-label="搜索供应商"
            placeholder="搜索厂商、模型或平台名称..." autofocus />
        </label>
        <div class="pp-provider-filters" aria-label="供应商分类">
          <button v-for="[id, title] in filters" :key="id" type="button" :aria-pressed="filter === id" @click="filter = id">{{ title }}</button>
          <span aria-live="polite">{{ matches.length }} 家服务</span>
        </div>
      </div>
      <div class="pp-provider-sections">
        <section v-for="group in sections" :key="group.id">
          <h3>{{ group.name }} <span>{{ group.brands.length }}</span></h3>
          <div class="pp-provider-presets">
            <button v-for="brand in group.brands" :key="brand.id" type="button"
              class="pp-provider-preset" @click="pick(brand.id)">
              <ProviderLogo :brand="brand.id" />
              <span class="pp-provider-preset__copy">
                <strong>{{ brand.name }}</strong><small>{{ brand.website }}</small>
                <span>{{ choices(brand.id).length > 1 ? choices(brand.id).length + ' 个区域可选' : brand.description }}</span>
              </span>
              <ChevronRight :size="16" class="pp-provider-preset__arrow" />
            </button>
          </div>
        </section>
      </div>
      <div v-if="!matches.length" class="pp-provider-search-empty"><Search :size="24" /><strong>未找到匹配的供应商</strong></div>
    </template>
    <template #footer>
      <button v-if="selected" type="button" class="pp-model-button" @click="variant = null">返回供应商</button>
      <button v-else type="button" class="pp-provider-custom" @click="$emit('select', custom)">
        <ProviderLogo size="sm" /><span><strong>自定义兼容服务</strong><small>使用自己的 API 地址或本地模型</small></span><Plus :size="18" />
      </button>
    </template>
  </ModelDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, Plus, Search } from 'lucide-vue-next'
import { presets, providerBrands, type ProviderPreset } from './provider-presets'
import ProviderLogo from './ProviderLogo.vue'
import ModelDialog from './ModelDialog.vue'

// Provider groups and search adapted from Paperpane's ProviderPicker.
const emit = defineEmits<{ select: [preset: ProviderPreset]; close: [] }>()
const query = ref('')
const filters = [['all', '全部'], ['direct', '模型厂商'], ['platform', '聚合服务']] as const
const filter = ref<typeof filters[number][0]>('all')
const variant = ref<string | null>(null)
const selected = computed(() => providerBrands.find((brand) => brand.id === variant.value))
const groups = [
  { id: 'popular', name: '常用厂商' },
  { id: 'more', name: '更多模型厂商' },
  { id: 'platform', name: '聚合与推理服务' },
]
const matches = computed(() => providerBrands.filter((brand) =>
  (filter.value === 'all' || (filter.value === 'platform' ? brand.group === 'platform' : brand.group !== 'platform')) &&
  (brand.name + ' ' + brand.website + ' ' + brand.keywords).toLowerCase().includes(query.value.toLowerCase())))
const sections = computed(() => groups.map((group) => ({
  ...group, brands: matches.value.filter((brand) => brand.group === group.id),
})).filter((group) => group.brands.length))
const choices = (brand: string) => presets.filter((preset) => preset.brand === brand)
const custom = presets.find((preset) => preset.id === 'custom')!
const pick = (brand: string) => {
  const options = choices(brand)
  if (options.length > 1) variant.value = brand
  else if (options[0]) emit('select', options[0])
}
</script>
