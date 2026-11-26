<template>
  <div class="space-y-4">
    <section class="config-section engine-panel" aria-labelledby="review-engine-heading">
      <h3 id="review-engine-heading" class="mb-4 text-base font-semibold text-apple-900">审查方式</h3>
      <div class="engine-choices">
        <label v-for="item in primaryEngines" :key="item.kind" class="engine-choice">
          <span class="engine-icon" aria-hidden="true">
            <GitBranch v-if="item.kind === 'review_agent'" :size="19" />
            <FileDiff v-else :size="19" />
          </span>
          <strong>{{ item.label }}</strong>
          <span :id="`engine-description-${item.kind}`" class="engine-description">{{ item.description }}</span>
          <input type="radio" name="review-engine" :value="item.kind" :checked="kind === item.kind"
            :aria-label="item.label" :aria-describedby="`engine-description-${item.kind}`" @change="$emit('select', item.kind)">
        </label>
      </div>

      <div v-if="tierOption || basicOptions.length || advancedOptions.length" class="engine-options">
        <div v-if="tierOption" class="tier-settings">
          <h4 id="review-tier-heading">{{ tierOption.label }}</h4>
          <div class="tier-choices" role="radiogroup" aria-labelledby="review-tier-heading">
            <label v-for="[value, label] in tierOption.choices" :key="value" class="tier-option">
              <input type="radio" name="review-tier" :value="value" :checked="tier === value"
                :aria-label="value === 'low' ? `${label}，推荐` : label" aria-describedby="review-tier-description"
                @change="$emit('update-option', 'tier', value)">
              <span class="tier-option-content">
                {{ label }} <small v-if="value === 'low'" class="tier-recommended">推荐</small>
              </span>
            </label>
          </div>
          <p id="review-tier-description" class="tier-description" :class="{ 'tier-description-expert': tier === 'xhigh' }"
            aria-live="polite">{{ tierDescriptions[tier] || tierOption.help }}</p>
        </div>

        <div v-if="basicOptions.length" class="engine-fields">
          <div v-for="option in basicOptions" :key="option.key" class="config-field-group">
            <label :for="`engine-option-${option.key}`" class="config-label">{{ option.label }}</label>
            <select v-if="option.kind === 'select'" :id="`engine-option-${option.key}`"
              :value="options[option.key] ?? option.default" class="input-field" @change="updateOption(option, $event)">
              <option v-for="[value, label] in option.choices" :key="value" :value="value">{{ label }}</option>
            </select>
            <input v-else :id="`engine-option-${option.key}`" :value="options[option.key] ?? option.default" type="number"
              class="input-field" :min="option.minimum ?? undefined" :max="option.maximum ?? undefined"
              @input="updateOption(option, $event)">
            <p v-if="option.help" class="option-help">{{ option.help }}</p>
          </div>
        </div>

        <details v-if="advancedOptions.length" class="engine-advanced">
          <summary><ChevronRight :size="14" aria-hidden="true" />高级设置</summary>
          <div class="engine-fields">
            <div v-for="option in advancedOptions" :key="option.key" class="config-field-group">
              <label :for="`engine-option-${option.key}`" class="config-label">{{ option.label }}</label>
              <select v-if="option.kind === 'select'" :id="`engine-option-${option.key}`"
                :value="options[option.key] ?? option.default" class="input-field" @change="updateOption(option, $event)">
                <option v-for="[value, label] in option.choices" :key="value" :value="value">{{ label }}</option>
              </select>
              <input v-else :id="`engine-option-${option.key}`" :value="options[option.key] ?? option.default" type="number"
                class="input-field" :min="option.minimum ?? undefined" :max="option.maximum ?? undefined"
                @input="updateOption(option, $event)">
              <p v-if="option.help" class="option-help">{{ option.help }}</p>
            </div>
          </div>
        </details>
      </div>
    </section>

    <section v-if="thirdPartyEngines.length" class="config-section engine-panel external-panel" aria-labelledby="external-engine-heading">
      <h3 id="external-engine-heading" class="mb-3 text-base font-semibold text-apple-900">第三方引擎</h3>
      <div class="external-choices">
        <label v-for="item in thirdPartyEngines" :key="item.kind" class="engine-choice">
          <span class="engine-icon" aria-hidden="true"><Terminal :size="19" /></span>
          <span>
            <strong>{{ item.label }}</strong>
            <span :id="`engine-description-${item.kind}`" class="engine-description">{{ item.description }}</span>
          </span>
          <input type="radio" name="review-engine" :value="item.kind" :checked="kind === item.kind"
            :aria-label="item.label" :aria-describedby="`engine-description-${item.kind}`" @change="$emit('select', item.kind)">
        </label>
      </div>
      <button v-if="kind === 'claude_code'" type="button" class="engine-link mt-3" @click="$emit('configure-claude')">
        配置 Claude CLI
      </button>
    </section>

    <details v-if="hasMock" class="test-tools">
      <summary>
        <FlaskConical :size="16" aria-hidden="true" />测试工具
        <span v-if="kind === 'mock'" class="mock-tag">已选 Mock</span>
        <ChevronRight :size="14" aria-hidden="true" />
      </summary>
      <div class="test-tools-content">
        <p>预览 GitLab 示例评论，或选择 Mock 测试发布流程。</p>
        <div class="flex flex-wrap items-center gap-3">
          <button type="button" class="btn-secondary" @click="mockDialog?.showModal()">预览示例评论</button>
          <button v-if="kind !== 'mock'" type="button" class="engine-link" @click="$emit('select', 'mock')">选择 Mock 引擎</button>
        </div>
      </div>
    </details>

    <dialog ref="mockDialog" class="mock-dialog" aria-labelledby="mock-preview-title">
      <div class="flex items-center justify-between gap-4">
        <h3 id="mock-preview-title" class="font-semibold text-apple-900">示例审查评论</h3>
        <form method="dialog"><button type="submit" class="btn-secondary">关闭</button></form>
      </div>
      <div class="mock-note">
        <strong><span class="mock-tag">模拟</span> 示例问题</strong>
        <p class="mt-1">这条行内评论用于检查 GitLab 的展示样式。</p>
      </div>
    </dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, FileDiff, FlaskConical, GitBranch, Terminal } from 'lucide-vue-next'
import type { EngineInfo, EngineOption, EngineOptions, EngineOptionValue } from '@/api/index'

const props = defineProps<{ engines: EngineInfo[]; kind: string; options: EngineOptions }>()
const emit = defineEmits<{
  select: [kind: string]
  'update-option': [key: string, value: EngineOptionValue]
  'configure-claude': []
}>()

const PRIMARY_ENGINE_KINDS = ['review_agent', 'diff_llm']
const primaryEngines = computed(() => PRIMARY_ENGINE_KINDS.flatMap(kind => props.engines.filter(engine => engine.kind === kind)))
const thirdPartyEngines = computed(() => props.engines.filter(engine =>
  engine.kind !== 'mock' && !PRIMARY_ENGINE_KINDS.includes(engine.kind)))
const hasMock = computed(() => props.engines.some(engine => engine.kind === 'mock'))
const currentOptions = computed(() => props.engines.find(engine => engine.kind === props.kind)?.options ?? [])
const tierOption = computed(() => props.kind === 'review_agent'
  ? currentOptions.value.find(option => option.key === 'tier' && option.kind === 'select')
  : undefined)
const tier = computed(() => String(props.options.tier ?? tierOption.value?.default ?? ''))
const basicOptions = computed(() => currentOptions.value.filter(option => !option.advanced && option !== tierOption.value))
const advancedOptions = computed(() => currentOptions.value.filter(option => option.advanced))
const mockDialog = ref<HTMLDialogElement | null>(null)

const tierDescriptions: Record<string, string> = {
  low: '优先调查会影响合并的问题，追踪相关的跨文件调用。适合大多数 PR，通常更快。',
  high: '用更多轮次核对调用方和边界条件。适合跨模块重构或影响范围不明确的改动，通常更耗时。',
  xhigh: '会消耗更多 token、花费更多时间，通常也会输出更多评论。适合关键版本发布前的专项排查，例如大规模跨模块重构或核心业务流程调整。',
}

function updateOption(option: EngineOption, event: Event) {
  const value = (event.target as HTMLInputElement | HTMLSelectElement).value
  emit('update-option', option.key, option.kind === 'number' && value !== '' ? Number(value) : value)
}
</script>

<style scoped>
.engine-panel { padding: 22px; container-type: inline-size; }
.engine-choices, .external-choices, .engine-fields { display: grid; gap: 10px; }
@container (min-width: 600px) {
  .engine-choices, .engine-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.engine-choice {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px 12px;
  border: 1px solid #dce2eb;
  border-radius: 10px;
  padding: 12px 14px;
  background: #fff;
  cursor: pointer;
  color: #1b2435;
}
.engine-choices .engine-choice {
  grid-template-areas: "icon title radio" "description description description";
  align-content: start;
}
.engine-choices .engine-icon { grid-area: icon; }
.engine-choices strong { grid-area: title; }
.engine-choices .engine-description { grid-area: description; }
.engine-choices input { grid-area: radio; }
.engine-choice:hover { border-color: #a9b7d1; }
.engine-choice:has(input:checked) { border-color: #8ba2eb; background: #f3f6ff; }
.engine-choice:has(input:focus-visible) { outline: 2px solid #2856d8; outline-offset: 2px; }
.engine-choice strong { font-size: 14px; font-weight: 650; }
.engine-choice input { width: 17px; height: 17px; accent-color: #2856d8; }
.engine-description, .option-help { display: block; color: #566174; font-size: 13px; line-height: 1.6; }
.option-help { font-size: 12px; }
.engine-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 9px;
  background: #eef0f4;
  color: #46536c;
}
.engine-choice:has(input:checked) .engine-icon { color: #2856d8; background: #e5edff; }
.external-panel { padding-block: 16px; }
.engine-options { border-top: 1px solid #e1e6ef; margin-top: 18px; }
.tier-settings { padding-block: 14px 10px; }
.tier-settings h4 { margin-bottom: 8px; color: #1b2435; font-size: 13px; font-weight: 650; }
.tier-choices {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 3px;
  width: min(100%, 325px);
  padding: 3px;
  border: 1px solid #e1e6ef;
  border-radius: 9px;
  background: #eef1f6;
}
.tier-option { position: relative; min-width: 0; cursor: pointer; }
.tier-option input { position: absolute; opacity: 0; width: 1px; height: 1px; margin: 0; }
.tier-option-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 33px;
  padding: 4px 2px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #566174;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.tier-option:hover .tier-option-content { color: #1b2435; }
.tier-option input:checked + .tier-option-content { color: #2856d8; background: #fff; border-color: #d8e1f3; }
.tier-option input:focus-visible + .tier-option-content { outline: 2px solid #2856d8; outline-offset: 1px; }
.tier-option input[value="xhigh"]:checked + .tier-option-content {
  color: #85490b;
  background: #fff4da;
  border-color: #e5bb74;
}
.tier-recommended {
  color: #2547a9;
  background: #e2eafd;
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 10px;
}
.tier-description {
  margin-top: 7px;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #566174;
  font-size: 12px;
  line-height: 1.6;
}
.tier-description-expert { color: #783f09; background: #fff8e9; border-color: #edcb91; }
.engine-advanced { border-top: 1px solid #e1e6ef; padding-top: 8px; }
details > summary { display: flex; align-items: center; gap: 6px; width: fit-content; cursor: pointer; list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details[open] > summary svg:last-child, .engine-advanced[open] > summary svg { transform: rotate(90deg); }
.engine-advanced summary, .test-tools summary { color: #566174; font-size: 13px; }
.engine-fields { margin-top: 12px; }
.engine-link { color: #2856d8; font-size: 13px; font-weight: 550; }
.engine-link:hover { text-decoration: underline; }
.test-tools > summary { margin-left: auto; }
.test-tools-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 9px;
  color: #566174;
  font-size: 13px;
}
.mock-dialog {
  width: min(calc(100% - 32px), 440px);
  padding: 20px;
  border: 1px solid #dce2eb;
  border-radius: 12px;
}
.mock-dialog::backdrop { background: #17223555; }
.mock-tag { color: #714718; background: #fbf0d8; border-radius: 4px; padding: 2px 5px; font-size: 11px; }
.mock-note { margin-top: 14px; padding: 12px; border: 1px solid #dce2eb; border-radius: 8px; color: #46536c; font-size: 13px; }
@media (max-width: 570px) {
  .engine-panel { padding-inline: 13px; }
  .engine-choice { padding-inline: 10px; gap: 8px 9px; }
}
</style>
