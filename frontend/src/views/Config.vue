<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-gray-900">配置管理</h2>
      <div class="flex gap-3">
        <button @click="handleSave" :disabled="saving" class="btn-primary">
          <Save class="w-4 h-4" />
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <button @click="handleReset" :disabled="saving" class="btn-secondary">
          <RotateCcw class="w-4 h-4" />
          重置
        </button>
      </div>
    </div>

    <!-- 状态消息 -->
    <div v-if="message" :class="[
      'p-4 rounded-md',
      messageType === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
    ]">
      <div class="flex">
        <div class="flex-shrink-0">
          <CheckCircle v-if="messageType === 'success'" class="h-5 w-5 text-green-400" />
          <XCircle v-else class="h-5 w-5 text-red-400" />
        </div>
        <div class="ml-3">
          <p class="text-sm font-medium">{{ message }}</p>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="config-tabs">
      <nav class="-mb-px flex space-x-8">
        <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key" :class="[
          'config-tab',
          activeTab === tab.key ? 'config-tab-active' : 'config-tab-inactive'
        ]">
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- LLM Config -->
    <div v-show="activeTab === 'llm'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-apple-blue-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">LLM 配置</h3>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="config-field-group">
            <label class="config-label">LLM 提供商</label>
            <select v-model="config.llm.provider" class="input-field">
              <option value="openai">OpenAI GPT-4</option>
              <option value="deepseek">DeepSeek</option>
              <option value="claude">Anthropic Claude</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>

          <div class="config-field-group">
            <label class="config-label">模型名称</label>
            <input v-model="config.llm.model" type="text" class="input-field" placeholder="例如: gpt-4" />
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">API Key</label>
            <div class="relative">
              <input v-model="config.llm.apiKey" :type="showLlmApiKey ? 'text' : 'password'" class="input-field pr-20"
                placeholder="请输入 API Key" />
              <div class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button type="button" @click="toggleVisibility('llmApiKey')"
                  class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                  :title="showLlmApiKey ? '隐藏' : '显示'">
                  <Eye v-if="!showLlmApiKey" class="w-4 h-4" />
                  <EyeOff v-else class="w-4 h-4" />
                </button>
                <button type="button" @click="copyToClipboard(config.llm.apiKey, 'API Key')"
                  class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                  title="复制">
                  <Copy class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">API Base URL (可选)</label>
            <input v-model="config.llm.apiBase" type="text" class="input-field" placeholder="自定义API端点" />
          </div>
        </div>
      </div>
    </div>

    <!-- GitLab Config -->
    <div v-show="activeTab === 'gitlab'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-orange-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">GitLab 配置</h3>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="md:col-span-2 config-field-group">
            <label class="config-label">GitLab URL</label>
            <input v-model="config.gitlab.serverUrl" type="text" class="input-field" placeholder="https://gitlab.com" />
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">Access Token</label>
            <div class="relative">
              <input v-model="config.gitlab.privateToken" :type="showGitlabToken ? 'text' : 'password'"
                class="input-field pr-20" placeholder="GitLab Access Token" />
              <div class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button type="button" @click="toggleVisibility('gitlabToken')"
                  class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                  :title="showGitlabToken ? '隐藏' : '显示'">
                  <Eye v-if="!showGitlabToken" class="w-4 h-4" />
                  <EyeOff v-else class="w-4 h-4" />
                </button>
                <button type="button" @click="copyToClipboard(config.gitlab.privateToken, 'Access Token')"
                  class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                  title="复制">
                  <Copy class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

        </div>

        <!-- Webhook URL Section -->
        <div class="border-t border-apple-200/50 pt-6 space-y-4">
          <div class="flex items-center gap-3">
            <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
            <h3 class="text-lg font-semibold text-apple-900">Webhook 配置</h3>
          </div>

          <div
            class="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200/60 rounded-xl p-4 text-sm text-purple-700">
            <div class="font-medium mb-2">📌 配置 GitLab Webhook</div>
            <div class="text-xs space-y-1 text-purple-600">
              <div>1. 在 GitLab 项目中进入 Settings → Webhooks</div>
              <div>2. 将下方地址复制到 URL 字段</div>
              <div>4. 点击 Add webhook 完成配置</div>
              <!-- 注意将 {host} 和 {port} 替换为实际的域名和端口 -->
              <div>5. 将 {host} 和 {port} 替换为实际的域名和端口</div>
            </div>
          </div>

          <!-- Primary Webhook URL -->
          <div class="space-y-2">
            <div
              class="flex items-center gap-2 bg-gradient-to-r from-apple-blue-50 to-indigo-50 border-2 border-apple-blue-300 rounded-lg px-3 py-2.5">
              <div class="flex items-center gap-2 flex-1 min-w-0">
                <Link class="w-4 h-4 text-apple-blue-600 flex-shrink-0" />
                <span class="text-xs text-apple-blue-700 font-semibold">Webhook 地址:</span>
                <code
                  class="text-xs text-apple-blue-700 bg-white px-2 py-1 rounded border border-apple-blue-200 truncate flex-1 font-mono">
                  {{ webhookUrl }}
                </code>
              </div>
              <button @click="copyWebhookUrl(webhookUrl)"
                class="flex-shrink-0 p-1.5 text-apple-blue-600 hover:text-apple-blue-700 hover:bg-white/50 rounded-lg transition-colors"
                title="复制地址">
                <Copy class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Claude CLI Config -->
    <div v-show="activeTab === 'claude-cli'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">Claude CLI 配置</h3>
        </div>

        <div class="bg-apple-50/50 border border-apple-200/40 rounded-xl p-4 text-sm text-apple-600">
          配置 Claude CLI 运行所需的环境变量。这些配置将在执行代码审查时自动注入到 Claude 命令环境中。
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="md:col-span-2 config-field-group">
            <label class="config-label">
              ANTHROPIC_BASE_URL
            </label>
            <input v-model="config.claude_cli.anthropic_base_url" type="text" class="input-field"
              placeholder="https://api.anthropic.com" />
            <p class="text-xs text-apple-500 mt-1">Claude API 的基础地址，留空使用默认值</p>
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">ANTHROPIC_AUTH_TOKEN</label>
            <div class="relative">
              <input v-model="config.claude_cli.anthropic_auth_token" :type="showClaudeToken ? 'text' : 'password'"
                class="input-field pr-20" placeholder="请输入 Claude 认证令牌" />
              <div class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button type="button" @click="toggleVisibility('claudeToken')"
                  class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                  :title="showClaudeToken ? '隐藏' : '显示'">
                  <Eye v-if="!showClaudeToken" class="w-4 h-4" />
                  <EyeOff v-else class="w-4 h-4" />
                </button>
                <button type="button" @click="copyToClipboard(config.claude_cli.anthropic_auth_token, 'Auth Token')"
                  class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                  title="复制">
                  <Copy class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <div class="config-field-group">
            <label class="config-label">CLI 路径</label>
            <input v-model="config.claude_cli.cli_path" type="text" class="input-field" placeholder="claude" />
            <p class="text-xs text-apple-500 mt-1">Claude CLI 可执行文件路径</p>
          </div>

          <div class="config-field-group">
            <label class="config-label">超时时间（秒）</label>
            <input v-model.number="config.claude_cli.timeout" type="number" class="input-field" placeholder="300"
              min="30" max="600" />
          </div>
        </div>

        <!-- 测试按钮 -->
        <div class="border-t border-apple-200/50 pt-6">
          <button @click="testClaudeCliConfig" :disabled="testingClaude" class="btn-secondary">
            <Play class="w-4 h-4" />
            {{ testingClaude ? '测试中...' : '测试 Claude CLI 连接' }}
          </button>
          <p class="text-xs text-apple-500 mt-2">
            点击测试按钮验证 Claude CLI 是否正确安装并可以连接
          </p>
        </div>
      </div>
    </div>

    <!-- Webhook Events Config -->
    <div v-show="activeTab === 'webhook-events'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">Webhook 事件规则</h3>
        </div>

        <div class="bg-apple-50/50 border border-apple-200/40 rounded-xl p-4 text-sm text-apple-600">
          管理全局 Webhook 事件识别规则。当前仅支持 Merge Request 相关事件，包括创建和更新两种场景。
        </div>

        <div class="flex items-center justify-between">
          <h4 class="text-sm font-semibold text-apple-900">事件规则列表</h4>
          <button @click="initializeDefaultRules" :disabled="initializing" class="btn-secondary">
            {{ initializing ? '初始化中...' : '初始化默认规则' }}
          </button>
        </div>

        <div v-if="filteredEventRules.length === 0"
          class="p-6 bg-apple-50 border border-dashed border-apple-200 text-center rounded-xl text-sm text-apple-500">
          暂无事件规则，请点击「初始化默认规则」开始配置。
        </div>

        <div v-else class="space-y-4">
          <div v-for="rule in filteredEventRules" :key="rule.id"
            class="p-4 border border-apple-200/60 rounded-xl bg-white shadow-sm space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2">
                  <div class="text-sm font-semibold text-apple-900">{{ rule.name }}</div>
                  <span v-if="!rule.is_active" class="badge bg-apple-200 text-apple-700">停用</span>
                </div>
                <div class="text-xs text-apple-500 mb-2">{{ rule.description || '暂无描述' }}</div>
                <div class="text-xs text-apple-400 space-y-1">
                  <div>事件类型：{{ rule.event_type }}</div>
                  <div class="font-mono bg-apple-50 p-2 rounded text-xs">
                    匹配规则：{{ JSON.stringify(rule.match_rules, null, 2) }}
                  </div>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-3 pt-2">
              <button class="btn-secondary" @click="editEventRule(rule)">
                <Pencil class="w-4 h-4" />
                编辑
              </button>
              <button class="btn-secondary" @click="testEventRule(rule)">
                <Play class="w-4 h-4" />
                测试
              </button>
            </div>
          </div>
        </div>

        <!-- 规则编辑弹窗 -->
        <div v-if="ruleEditorVisible"
          class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-auto">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold">编辑事件规则</h3>
              <button @click="ruleEditorVisible = false" class="text-apple-500 hover:text-apple-700">
                <X class="w-5 h-5" />
              </button>
            </div>
            <div class="space-y-4">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium mb-2">规则名称</label>
                  <input v-model="editingRule.name" type="text" class="w-full p-3 border border-apple-200 rounded-lg"
                    placeholder="输入规则名称" />
                </div>
                <div>
                  <label class="block text-sm font-medium mb-2">事件类型</label>
                  <select v-model="editingRule.event_type" class="w-full p-3 border border-apple-200 rounded-lg"
                    :disabled="true">
                    <option value="mr_open">MR 创建</option>
                    <option value="mr_update">MR 更新</option>
                  </select>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium mb-2">描述</label>
                <textarea v-model="editingRule.description" class="w-full p-3 border border-apple-200 rounded-lg"
                  rows="3" placeholder="输入规则描述"></textarea>
              </div>

              <div>
                <label class="block text-sm font-medium mb-2">匹配规则 (JSON格式)</label>
                <textarea v-model="editingRule.matchRulesText"
                  class="w-full p-3 border border-apple-200 rounded-lg font-mono text-xs" rows="6"
                  placeholder="输入匹配规则，JSON格式"></textarea>
              </div>

              <div class="flex items-center gap-4">
                <label class="flex items-center gap-2 text-sm">
                  <input v-model="editingRule.is_active" type="checkbox" />
                  启用此规则
                </label>
              </div>

              <div class="flex justify-end gap-3">
                <button @click="ruleEditorVisible = false" class="btn-secondary">取消</button>
                <button @click="saveEventRule" class="btn-primary" :disabled="ruleSaving">
                  {{ ruleSaving ? '保存中...' : '保存规则' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 规则测试弹窗 -->
        <div v-if="testDialogVisible"
          class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-auto">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold">测试事件规则</h3>
              <button @click="testDialogVisible = false" class="text-apple-500 hover:text-apple-700">
                <X class="w-5 h-5" />
              </button>
            </div>
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium mb-2">测试 Payload (JSON格式)</label>
                <textarea v-model="testPayload" class="w-full p-3 border border-apple-200 rounded-lg font-mono text-xs"
                  rows="10" placeholder="粘贴要测试的 GitLab Webhook Payload"></textarea>
              </div>
              <div v-if="testResult" class="p-4 rounded-lg"
                :class="testResult.is_match ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'">
                <div class="font-medium mb-2">
                  {{ testResult.is_match ? '✅ 匹配成功' : '❌ 匹配失败' }}
                </div>
                <div class="text-sm">
                  <div>规则：{{ testResult.rule_name }}</div>
                  <div v-if="testResult.is_match" class="text-green-600">该 payload 匹配当前规则</div>
                  <div v-else class="text-red-600">该 payload 不匹配当前规则</div>
                </div>
              </div>
              <div class="flex justify-end gap-3">
                <button @click="testDialogVisible = false" class="btn-secondary">关闭</button>
                <button @click="executeTest" class="btn-primary" :disabled="!testPayload.trim()">
                  开始测试
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Notification Config -->
    <div v-show="activeTab === 'notification'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-green-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">通知配置</h3>
        </div>

        <div class="bg-apple-50/50 border border-apple-200/40 rounded-xl p-4 text-sm text-apple-600">
          管理全局通知通道。每个项目可在项目详情页选择需要启用的通道，支持为不同项目配置独立的通知名称与 Webhook。
        </div>

        <div class="flex items-center justify-between">
          <h4 class="text-sm font-semibold text-apple-900">通道列表</h4>
          <button @click="openChannelDialog()" class="btn-primary">
            <PlusCircle class="w-4 h-4" />
            新建通道
          </button>
        </div>

        <div v-if="totalChannelCount === 0"
          class="p-6 bg-apple-50 border border-dashed border-apple-200 text-center rounded-xl text-sm text-apple-500">
          暂无通知通道，请点击「新建通道」开始配置。
        </div>

        <div v-else class="space-y-6">
          <div v-for="type in channelTypes" :key="type.value" class="space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-sm font-medium text-apple-900">
                <img v-if="channelIcons[type.value]" :src="channelIcons[type.value]" :alt="type.label"
                  class="w-5 h-5 object-contain" />
                <span>{{ type.label }}</span>
              </div>
              <button @click="openChannelDialog(type.value)"
                class="text-xs text-apple-blue-600 hover:text-apple-blue-500 flex items-center gap-1">
                <PlusCircle class="w-3 h-3" />
                新增
              </button>
            </div>

            <div v-if="groupedChannels[type.value]?.length" class="space-y-3">
              <div v-for="channel in groupedChannels[type.value]" :key="channel.id"
                class="p-4 border border-apple-200/60 rounded-xl bg-white shadow-sm space-y-3">
                <div class="flex items-start justify-between gap-3">
                  <div class="flex items-start gap-2">
                    <img v-if="channelIcons[channel.notification_type]" :src="channelIcons[channel.notification_type]"
                      :alt="channel.notification_type" class="w-6 h-6 mt-0.5 object-contain flex-shrink-0" />
                    <div>
                      <div class="text-sm font-semibold text-apple-900">{{ channel.name }}</div>
                      <div class="text-xs text-apple-500 mt-1">{{ channel.description || '暂无备注' }}</div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <span v-if="channel.is_default" class="badge badge-success">默认</span>
                    <span v-if="channel.is_active === false" class="badge bg-apple-200 text-apple-700">停用</span>
                  </div>
                </div>
                <div class="text-xs text-apple-500 space-y-1">
                  <div v-if="channel.webhook_url">Webhook：{{ channel.webhook_url }}</div>
                  <div v-else>未配置 Webhook</div>
                </div>
                <div class="flex items-center gap-3 pt-2">
                  <button class="btn-secondary" @click="editChannel(channel)">
                    <Pencil class="w-4 h-4" />
                    编辑
                  </button>
                  <button class="btn-secondary" @click="testChannel(channel)"
                    :disabled="testingChannelId === channel.id">
                    <Play class="w-4 h-4" />
                    {{ testingChannelId === channel.id ? '发送中...' : '测试' }}
                  </button>
                  <button class="btn-ghost text-red-500 hover:text-red-600" @click="removeChannel(channel)">
                    <Trash2 class="w-4 h-4" />
                    删除
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-xs text-apple-500 bg-apple-50 rounded-lg px-3 py-2">暂无 {{ type.label }} 通道</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 通道编辑弹窗 -->
    <div v-if="channelDialogVisible" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-auto">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold">{{ channelForm.id ? '编辑通知通道' : '新建通知通道' }}</h3>
          <button @click="closeChannelDialog" class="text-apple-500 hover:text-apple-700">
            <X class="w-5 h-5" />
          </button>
        </div>
        <div class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="config-field-group">
              <label class="config-label">通道名称</label>
              <input v-model="channelForm.name" type="text" class="input-field" placeholder="用于区分不同项目的通道名称" />
            </div>
            <div class="config-field-group">
              <label class="config-label">通道类型</label>
              <div class="space-y-2">
                <select v-model="channelForm.notification_type" class="input-field" :disabled="channelForm.id !== null">
                  <option v-for="type in channelTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
                </select>
                <div v-if="channelIcons[channelForm.notification_type]"
                  class="flex items-center gap-2 text-xs text-apple-500">
                  <img :src="channelIcons[channelForm.notification_type]" :alt="channelForm.notification_type"
                    class="w-5 h-5 object-contain" />
                  <span>{{ baseChannelTypes[channelForm.notification_type] }}</span>
                </div>
              </div>
            </div>
            <div class="config-field-group md:col-span-2">
              <label class="config-label">备注</label>
              <textarea v-model="channelForm.description" class="input-field" rows="2"
                placeholder="补充说明该通道的使用场景"></textarea>
            </div>
            <div class="config-field-group md:col-span-2"
              v-if="['dingtalk', 'feishu', 'slack', 'wechat'].includes(channelForm.notification_type)">
              <label class="config-label">Webhook URL</label>
              <input v-model="channelForm.webhook_url" type="text" class="input-field" placeholder="https://" />
            </div>
            <div class="config-field-group md:col-span-2"
              v-if="['dingtalk', 'feishu'].includes(channelForm.notification_type)">
              <label class="config-label">Secret <span class="text-sm text-gray-400">(可选)</span></label>
              <div class="relative">
                <input v-model="channelForm.secret" :type="showChannelSecret ? 'text' : 'password'"
                  class="input-field pr-20" placeholder="签名密钥（不填则不使用签名验证）" />
                <div class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <button type="button" @click="toggleVisibility('channelSecret')"
                    class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                    :title="showChannelSecret ? '隐藏' : '显示'">
                    <Eye v-if="!showChannelSecret" class="w-4 h-4" />
                    <EyeOff v-else class="w-4 h-4" />
                  </button>
                  <button type="button" @click="copyToClipboard(channelForm.secret, 'Secret')"
                    class="p-1.5 text-apple-500 hover:text-apple-700 hover:bg-apple-50 rounded transition-colors"
                    title="复制">
                    <Copy class="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
            <!-- 自定义Webhook专用字段 -->
            <template v-if="channelForm.notification_type === 'custom_webhook'">
              <div class="config-field-group md:col-span-2">
                <label class="config-label">Webhook URL</label>
                <input v-model="channelForm.webhook_url" type="text" class="input-field" placeholder="https://your-api.com/webhook" />
              </div>
              <div class="config-field-group">
                <label class="config-label">HTTP 方法</label>
                <select v-model="channelForm.http_method" class="input-field">
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                  <option value="PATCH">PATCH</option>
                  <option value="GET">GET</option>
                  <option value="DELETE">DELETE</option>
                </select>
              </div>
              <div class="config-field-group">
                <label class="config-label">超时 (秒)</label>
                <input v-model="channelForm.http_timeout" type="number" class="input-field" min="1" max="300" placeholder="30" />
              </div>
              <div class="config-field-group md:col-span-2">
                <label class="config-label">自定义 Headers (JSON)</label>
                <textarea v-model="channelForm.headers_text" class="input-field" rows="3" placeholder='{"Authorization": "Bearer xxx", "Content-Type": "application/json"}'></textarea>
              </div>
              <div class="config-field-group md:col-span-2">
                <label class="config-label">
                  消息模板 (JSON)
                  <span class="text-sm text-gray-400">可用变量: {'{'}project_name{'}'}, {'{'}mr_title{'}'}, {'{'}mr_author{'}'}, {'{'}review_content{'}'}, {'{'}review_score{'}'}, {'{'}timestamp{'}'}</span>
                </label>
                <textarea v-model="channelForm.payload_template_text" class="input-field font-mono text-xs" rows="8"
                  placeholder='{"msgtype": "text", "text": {"content": "{review_content}"}}'></textarea>
              </div>
            </template>
            <div class="flex items-center gap-4 md:col-span-2">
              <label class="flex items-center gap-2 text-xs text-apple-600">
                <input v-model="channelForm.is_active" type="checkbox" />
                启用此通道
              </label>
              <label class="flex items-center gap-2 text-xs text-apple-600">
                <input v-model="channelForm.is_default" type="checkbox" />
                设为默认通道
              </label>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button @click="submitChannelForm" class="btn-primary" :disabled="channelSaving">
              <Save class="w-4 h-4" />
              {{ channelSaving ? '保存中...' : '保存通道' }}
            </button>
            <button @click="closeChannelDialog" class="btn-secondary" :disabled="channelSaving">
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { Save, RotateCcw, CheckCircle, XCircle, PlusCircle, Pencil, Trash2, Eye, EyeOff, Copy, Play, X, Link } from 'lucide-vue-next'
import {
  getConfigSummary,
  batchUpdateConfig,
  getNotificationChannels,
  createNotificationChannel,
  updateNotificationChannel,
  deleteNotificationChannel,
  testNotificationChannel,
  getWebhookEventRules,
  createWebhookEventRule,
  updateWebhookEventRule,
  deleteWebhookEventRule,
  testWebhookEventRule,
  validateWebhookPayload,
  initializeDefaultWebhookEventRules
} from '@/api/index'

// 响应式数据
const activeTab = ref('gitlab')
const saving = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')

// 密码字段显示/隐藏状态
const showLlmApiKey = ref(false)
const showGitlabToken = ref(false)
const showChannelSecret = ref(false)
const showClaudeToken = ref(false)

// 测试状态
const testingClaude = ref(false)

const tabs = [
  { key: 'gitlab', label: 'GitLab 配置' },
  { key: 'claude-cli', label: 'Claude CLI 配置' },
  { key: 'webhook-events', label: 'Webhook 事件' },
  { key: 'notification', label: '通知配置' }
]

const config = ref({
  llm: {
    provider: 'openai',
    model: 'gpt-4',
    apiKey: '',
    apiBase: ''
  },
  gitlab: {
    serverUrl: 'https://gitlab.com',
    privateToken: ''
  },
  claude_cli: {
    anthropic_base_url: '',
    anthropic_auth_token: '',
    cli_path: 'claude',
    timeout: 300
  }
})

const channels = ref<any[]>([])
const webhookEventRules = ref<any[]>([])
const baseChannelTypes: Record<string, string> = {
  dingtalk: '钉钉通知',
  feishu: '飞书通知',
  wechat: '企业微信通知',
  slack: 'Slack 通知',
  gitlab: 'GitLab 评论',
  email: '邮件通知',
  custom_webhook: '自定义Webhook'
}

// 通道类型图标映射
const channelIcons: Record<string, string> = {
  dingtalk: new URL('../assets/icons/dingtalk.png', import.meta.url).href,
  feishu: new URL('../assets/icons/feishu.png', import.meta.url).href,
  wechat: new URL('../assets/icons/wechat.png', import.meta.url).href,
  gitlab: new URL('../assets/icons/gitlab.png', import.meta.url).href
}

// 支持的事件类型（仅支持 MR 创建和更新）
const supportedEventTypeValues = new Set(['mr_open', 'mr_update'])

const channelDialogVisible = ref(false)
const channelSaving = ref(false)
const testingChannelId = ref<number | null>(null)
const channelForm = ref({
  id: null as number | null,
  name: '',
  notification_type: 'dingtalk',
  description: '',
  webhook_url: '',
  secret: '',
  http_method: 'POST' as string,
  http_timeout: 30 as number,
  headers_text: '' as string,
  payload_template_text: '' as string,
  is_active: true,
  is_default: false
})

const channelTypes = computed(() => {
  const typeSet = new Set<string>(Object.keys(baseChannelTypes))
  channels.value.forEach(channel => typeSet.add(channel.notification_type))
  return Array.from(typeSet).map(value => ({
    value,
    label: baseChannelTypes[value] || value
  }))
})

const groupedChannels = computed(() => {
  const map: Record<string, any[]> = {}
  channelTypes.value.forEach(item => {
    map[item.value] = []
  })
  channels.value.forEach(channel => {
    if (!map[channel.notification_type]) {
      map[channel.notification_type] = []
    }
    map[channel.notification_type].push(channel)
  })
  return map
})

const totalChannelCount = computed(() => channels.value.length)
const totalEventRuleCount = computed(() => webhookEventRules.value.length)

// 过滤只显示支持的事件规则
const filteredEventRules = computed(() => {
  return webhookEventRules.value.filter(rule =>
    supportedEventTypeValues.has(rule.event_type)
  )
})

// Webhook URL 计算属性
const webhookUrl = computed(() => {
  // 显示占位符格式
  return `http://{host}:{port}/api/webhook/gitlab/`
})

// Webhook事件规则相关
const initializing = ref(false)

// 测试相关
const testDialogVisible = ref(false)
const testPayload = ref('')
const testResult = ref<any>(null)
const currentTestRule = ref<any>(null)

// 规则编辑相关
const ruleEditorVisible = ref(false)
const ruleSaving = ref(false)
const editingRule = ref({
  id: null as number | null,
  name: '',
  event_type: 'mr_open',
  description: '',
  matchRulesText: '',
  is_active: true
})

// 原始配置，用于重置
const originalConfig = ref({})

// 显示消息
const showMessage = (text: string, type: 'success' | 'error' = 'success') => {
  message.value = text
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 3000)
}

// 切换密码显示/隐藏
const toggleVisibility = (field: string) => {
  switch (field) {
    case 'llmApiKey':
      showLlmApiKey.value = !showLlmApiKey.value
      break
    case 'gitlabToken':
      showGitlabToken.value = !showGitlabToken.value
      break
    case 'channelSecret':
      showChannelSecret.value = !showChannelSecret.value
      break
    case 'claudeToken':
      showClaudeToken.value = !showClaudeToken.value
      break
  }
}

// 复制到剪贴板
const copyToClipboard = async (text: string, label: string) => {
  if (!text) {
    showMessage(`${label} 为空，无法复制`, 'error')
    return
  }

  try {
    await navigator.clipboard.writeText(text)
    showMessage(`${label} 已复制到剪贴板`)
  } catch (error) {
    console.error('Failed to copy:', error)
    showMessage(`复制 ${label} 失败`, 'error')
  }
}

const normalizeChannelList = (data: any) => {
  if (!data) return []
  if (Array.isArray(data)) return data
  if (Array.isArray(data.results)) return data.results
  if (Array.isArray(data.channels)) return data.channels
  return []
}

const resetChannelForm = (notificationType?: string) => {
  channelForm.value = {
    id: null,
    name: '',
    notification_type: notificationType || channelTypes.value[0]?.value || 'dingtalk',
    description: '',
    webhook_url: '',
    secret: '',
    http_method: 'POST',
    http_timeout: 30,
    headers_text: '',
    payload_template_text: '',
    is_active: true,
    is_default: false
  }
}

const refreshChannels = async () => {
  try {
    const response = await getNotificationChannels()
    channels.value = normalizeChannelList(response)
  } catch (error) {
    console.error('Failed to load channels:', error)
    showMessage('加载通知通道失败', 'error')
  }
}

// 加载配置
const loadConfig = async () => {
  try {
    const response = await getConfigSummary()
    console.log('API Response:', response) // 添加调试日志
    const data = response

    // 更新LLM配置
    if (data.llm) {
      config.value.llm = {
        provider: data.llm.provider || 'openai',
        model: data.llm.model || 'gpt-4',
        apiKey: data.llm.api_key || '',
        apiBase: data.llm.api_base || ''
      }
    }

    // 更新GitLab配置
    if (data.gitlab) {
      config.value.gitlab = {
        serverUrl: data.gitlab.server_url || 'https://gitlab.com',
        privateToken: data.gitlab.private_token || ''
      }
    }

    // 更新 Claude CLI 配置
    if (data.claude_cli) {
      config.value.claude_cli = {
        anthropic_base_url: data.claude_cli.anthropic_base_url || '',
        anthropic_auth_token: data.claude_cli.anthropic_auth_token || '',
        cli_path: data.claude_cli.cli_path || 'claude',
        timeout: data.claude_cli.timeout || 300
      }
    }

    // 更新通知通道列表
    if (data.channels) {
      channels.value = normalizeChannelList(data.channels)
    } else {
      await refreshChannels()
    }

    // 更新webhook事件规则列表
    if (data.webhook_events) {
      webhookEventRules.value = Array.isArray(data.webhook_events) ? data.webhook_events : []
    } else {
      await refreshWebhookEventRules()
    }

    // 保存原始配置
    originalConfig.value = JSON.parse(JSON.stringify(config.value))

  } catch (error) {
    console.error('Failed to load config:', error)
    showMessage('加载配置失败', 'error')
  }
}

// 测试 Claude CLI 配置
const testClaudeCliConfig = async () => {
  testingClaude.value = true

  // 提示用户测试可能需要较长时间
  showMessage('正在测试 Claude CLI 配置，包括网络连通性、CLI 安装和 API 认证，预计需要 15-45 秒...', 'success')

  try {
    const { testClaudeCliConfigApi } = await import('@/api/index')
    const response: any = await testClaudeCliConfigApi({
      claude_cli: config.value.claude_cli
    })

    if (response.status === 'success') {
      showMessage(
        `✅ 测试成功！Claude CLI 版本: ${response.version || 'unknown'}`,
        'success'
      )
    } else {
      showMessage(`❌ 测试失败: ${response.message}`, 'error')
    }
  } catch (error: any) {
    const errorMsg = error?.response?.data?.message || error?.message || '未知错误'
    showMessage(`❌ 测试失败: ${errorMsg}`, 'error')
  } finally {
    testingClaude.value = false
  }
}

// 保存配置
const handleSave = async () => {
  saving.value = true
  try {
    // 准备API数据格式
    const apiData = {
      llm: {
        provider: config.value.llm.provider,
        model: config.value.llm.model,
        api_key: config.value.llm.apiKey,
        api_base: config.value.llm.apiBase || null,
        is_active: true
      },
      gitlab: {
        server_url: config.value.gitlab.serverUrl,
        private_token: config.value.gitlab.privateToken,
        is_active: true
      },
      claude_cli: {
        anthropic_base_url: config.value.claude_cli.anthropic_base_url || null,
        anthropic_auth_token: config.value.claude_cli.anthropic_auth_token,
        cli_path: config.value.claude_cli.cli_path || 'claude',
        timeout: config.value.claude_cli.timeout || 300,
        is_active: true
      }
    }

    await batchUpdateConfig(apiData)
    showMessage('配置保存成功')

    // 更新原始配置
    originalConfig.value = JSON.parse(JSON.stringify(config.value))

  } catch (error) {
    console.error('Failed to save config:', error)
    showMessage('保存配置失败', 'error')
  } finally {
    saving.value = false
  }
}

const openChannelDialog = (notificationType?: string) => {
  resetChannelForm(notificationType)
  channelDialogVisible.value = true
}

const editChannel = (channel: any) => {
  channelForm.value = {
    id: channel.id,
    name: channel.name,
    notification_type: channel.notification_type,
    description: channel.description || '',
    webhook_url: channel.webhook_url || '',
    secret: channel.secret || '',
    http_method: channel.http_method || 'POST',
    http_timeout: channel.http_timeout || 30,
    headers_text: channel.headers_text || '',
    payload_template_text: channel.payload_template_text || '',
    is_active: channel.is_active !== false,
    is_default: channel.is_default || false
  }
  channelDialogVisible.value = true
}

const closeChannelDialog = () => {
  channelDialogVisible.value = false
  resetChannelForm()
}

const submitChannelForm = async () => {
  channelSaving.value = true
  try {
    const payload: any = {
      name: channelForm.value.name,
      notification_type: channelForm.value.notification_type,
      description: channelForm.value.description,
      is_active: channelForm.value.is_active,
      is_default: channelForm.value.is_default
    }

    if (['dingtalk', 'feishu', 'slack', 'wechat'].includes(channelForm.value.notification_type)) {
      payload.webhook_url = channelForm.value.webhook_url
    }

    if (['dingtalk', 'feishu'].includes(channelForm.value.notification_type)) {
      // Secret是可选的，如果为空则不发送
      payload.secret = channelForm.value.secret?.trim() || null
    }

    if (channelForm.value.notification_type === 'custom_webhook') {
      payload.webhook_url = channelForm.value.webhook_url
      payload.http_method = channelForm.value.http_method || 'POST'
      payload.http_timeout = channelForm.value.http_timeout || 30
      payload.headers_text = channelForm.value.headers_text || ''
      payload.payload_template_text = channelForm.value.payload_template_text || ''
    }

    if (channelForm.value.id) {
      await updateNotificationChannel(channelForm.value.id, payload)
      showMessage('通知通道更新成功')
    } else {
      await createNotificationChannel(payload)
      showMessage('通知通道创建成功')
    }

    channelDialogVisible.value = false
    resetChannelForm()
    await refreshChannels()

  } catch (error) {
    console.error('Failed to save notification channel:', error)
    showMessage('保存通知通道失败', 'error')
  } finally {
    channelSaving.value = false
  }
}

const removeChannel = async (channel: any) => {
  if (!channel?.id) return

  const confirmed = window.confirm(`确认删除通道「${channel.name}」吗？`)
  if (!confirmed) return

  try {
    await deleteNotificationChannel(channel.id)
    showMessage('已删除通知通道')
    await refreshChannels()
  } catch (error) {
    console.error('Failed to delete notification channel:', error)
    showMessage('删除通知通道失败', 'error')
  }
}

// 测试通知渠道
const testChannel = async (channel: any) => {
  if (!channel?.id) return

  testingChannelId.value = channel.id
  try {
    await testNotificationChannel(channel.id)
    showMessage(`${channel.name} 测试消息发送成功`)
  } catch (error: any) {
    console.error('Failed to test notification channel:', error)
    const errorMessage = error?.response?.data?.message || error?.message || '测试消息发送失败'
    showMessage(`${channel.name} 测试失败: ${errorMessage}`, 'error')
  } finally {
    testingChannelId.value = null
  }
}

// Webhook事件规则管理方法
const refreshWebhookEventRules = async () => {
  try {
    const response = await getWebhookEventRules()
    // 处理分页响应
    if (response && response.results) {
      webhookEventRules.value = response.results
    } else if (Array.isArray(response)) {
      webhookEventRules.value = response
    } else {
      webhookEventRules.value = []
    }
  } catch (error) {
    console.error('Failed to load webhook event rules:', error)
    showMessage('加载webhook事件规则失败', 'error')
  }
}

const initializeDefaultRules = async () => {
  const confirmed = window.confirm('确认初始化默认事件规则吗？\n\n系统将创建 2 条 Merge Request 事件规则：\n1. MR 创建 - 当新的 Merge Request 被创建时\n2. MR 更新 - 当 Merge Request 被更新时（如推送新提交）\n\n这是系统内置的规则，不支持自定义修改。')
  if (!confirmed) return

  initializing.value = true
  try {
    const response = await initializeDefaultWebhookEventRules()

    const created = response.created_count || 0
    const skipped = response.skipped_count || 0

    if (created > 0 && skipped > 0) {
      showMessage(`初始化完成：新建 ${created} 条规则，跳过 ${skipped} 条已存在的规则`)
    } else if (created > 0) {
      showMessage(`初始化成功：已创建 ${created} 条默认规则`)
    } else if (skipped > 0) {
      showMessage(`所有默认规则已存在（${skipped} 条），无需重复创建`)
    } else {
      showMessage('初始化完成')
    }

    await refreshWebhookEventRules()
  } catch (error) {
    console.error('Failed to initialize default rules:', error)
    showMessage('初始化默认规则失败', 'error')
  } finally {
    initializing.value = false
  }
}

const testEventRule = (rule: any) => {
  currentTestRule.value = rule
  testResult.value = null
  testPayload.value = JSON.stringify({
    "object_kind": "merge_request",
    "object_attributes": {
      "action": "open",
      "iid": 1,
      "title": "Test MR"
    },
    "project": {
      "id": 123,
      "name": "test-project"
    }
  }, null, 2)
  testDialogVisible.value = true
}


const executeTest = async () => {
  if (!testPayload.value.trim()) {
    showMessage('请输入测试payload', 'error')
    return
  }

  let payload: any
  try {
    payload = JSON.parse(testPayload.value)
  } catch {
    showMessage('Payload格式不正确，请输入有效的JSON', 'error')
    return
  }

  try {
    if (currentTestRule.value) {
      // 测试特定规则
      const result = await testWebhookEventRule(currentTestRule.value.id, payload)
      const responseData = result.data || result
      testResult.value = {
        rule_name: currentTestRule.value.name,
        is_match: responseData.is_match,
        payload: responseData.payload,
        match_rules: responseData.match_rules
      }
    }
  } catch (error) {
    console.error('Failed to test rule:', error)
    showMessage('测试失败', 'error')
  }
}

// 编辑事件规则
const editEventRule = (rule: any) => {
  editingRule.value = {
    id: rule.id,
    name: rule.name,
    event_type: rule.event_type,
    description: rule.description || '',
    matchRulesText: JSON.stringify(rule.match_rules, null, 2),
    is_active: rule.is_active !== false
  }
  ruleEditorVisible.value = true
}

// 保存事件规则
const saveEventRule = async () => {
  if (!editingRule.value.name.trim()) {
    showMessage('请输入规则名称', 'error')
    return
  }

  let matchRules
  try {
    matchRules = JSON.parse(editingRule.value.matchRulesText)
  } catch {
    showMessage('匹配规则格式不正确，请输入有效的JSON', 'error')
    return
  }

  ruleSaving.value = true
  try {
    const payload = {
      name: editingRule.value.name,
      event_type: editingRule.value.event_type,
      description: editingRule.value.description,
      match_rules: matchRules,
      is_active: editingRule.value.is_active
    }

    await updateWebhookEventRule(editingRule.value.id!, payload)
    showMessage('事件规则更新成功')
    ruleEditorVisible.value = false
    await refreshWebhookEventRules()
  } catch (error) {
    console.error('Failed to save event rule:', error)
    showMessage('保存事件规则失败', 'error')
  } finally {
    ruleSaving.value = false
  }
}

// 重置配置
const handleReset = () => {
  if (JSON.stringify(originalConfig.value)) {
    config.value = JSON.parse(JSON.stringify(originalConfig.value))
    showMessage('配置已重置')
  }
}

// 页面加载时获取配置
onMounted(() => {
  loadConfig()
})
</script>
