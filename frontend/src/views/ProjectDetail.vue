<template>
  <div class="space-y-6">
    <!-- Header with Back Button -->
    <div class="flex items-center gap-4">
      <button
        @click="goBack"
        class="btn-ghost"
      >
        <ArrowLeft class="w-4 h-4" />
        <span>返回</span>
      </button>
      <div class="flex-1">
        <h1 class="section-header">{{ project?.project_name }}</h1>
        <p class="text-xs text-apple-500 mt-1">{{ project?.namespace }}</p>
      </div>
      <span
        :class="[
          'badge',
          project?.review_enabled ? 'badge-success' : 'bg-apple-200 text-apple-700'
        ]"
      >
        {{ project?.review_enabled ? '审查已开启' : '审查已关闭' }}
      </span>
    </div>

    <!-- Tabs -->
    <div class="config-tabs">
      <nav class="-mb-px flex space-x-8">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="handleTabChange(tab.key)"
          :class="[
            'config-tab',
            activeTab === tab.key ? 'config-tab-active' : 'config-tab-inactive'
          ]"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- Tab Content -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <div class="lg:col-span-3">
        <!-- Project Info Tab -->
        <div v-show="activeTab === 'info'" class="config-section">
          <div class="p-6 space-y-6">
            <div class="flex items-center gap-3">
              <div class="w-2 h-2 bg-apple-blue-500 rounded-full"></div>
              <h3 class="text-lg font-semibold text-apple-900">项目信息</h3>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div class="space-y-4">
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">项目名称</div>
                  <div class="text-sm text-apple-900">{{ project?.project_name }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">命名空间</div>
                  <div class="text-sm text-apple-900">{{ project?.namespace }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">项目地址</div>
                  <div class="flex items-center gap-2">
                    <span class="text-sm text-apple-blue-600 truncate">{{ project?.project_url }}</span>
                    <button
                      @click="openProjectUrl(project?.project_url)"
                      class="flex-shrink-0 text-apple-600 hover:text-apple-blue-600 transition-colors"
                    >
                      <ExternalLink class="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              <div class="space-y-4">
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">创建时间</div>
                  <div class="text-sm text-apple-900">{{ project?.created_at ? new Date(project.created_at).toLocaleDateString() : '未知' }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">最后活动</div>
                  <div class="text-sm text-apple-900">{{ project?.last_activity || '未知' }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">团队成员</div>
                  <div class="flex items-center gap-2">
                    <Users class="w-4 h-4 text-apple-600" />
                    <span class="text-sm text-apple-900">{{ project?.members_count || 0 }} 成员</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-6 pt-6 border-t border-apple-200/50">
              <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">项目描述</div>
              <p class="text-sm text-apple-700">{{ project?.description || '暂无项目描述' }}</p>
            </div>
          </div>
        </div>

        <!-- Statistics Tab -->
        <div v-show="activeTab === 'stats'" class="config-section">
          <div class="p-6 space-y-6">
            <div class="flex items-center gap-3">
              <div class="w-2 h-2 bg-green-500 rounded-full"></div>
              <h3 class="text-lg font-semibold text-apple-900">统计图表</h3>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div class="card">
                <div class="p-6">
                  <h4 class="section-header mb-4">审查统计</h4>
                  <div ref="reviewChartRef" class="h-64"></div>
                </div>
              </div>

              <div class="card">
                <div class="p-6">
                  <h4 class="section-header mb-4">问题分布</h4>
                  <div ref="issueChartRef" class="h-64"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Webhook Events Tab -->
        <div v-show="activeTab === 'webhook-events'" class="config-section">
          <div class="p-6 space-y-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
                <h3 class="text-lg font-semibold text-apple-900">Webhook 事件配置</h3>
              </div>
              <button
                class="btn-primary"
                :disabled="webhookEventSaving"
                @click="saveProjectWebhookEvents"
              >
                <Save class="w-4 h-4" />
                {{ webhookEventSaving ? '保存中...' : '保存' }}
              </button>
            </div>

            <div class="bg-apple-50/50 border border-apple-200/40 rounded-xl p-4 text-sm text-apple-600">
              选择触发代码审查的 Webhook 事件。只有选中的事件类型才会触发自动代码审查。
            </div>

            <div v-if="webhookEventRules.length === 0" class="p-6 bg-apple-50 border border-dashed border-apple-200 text-center rounded-xl text-sm text-apple-500">
              暂无可用的 Webhook 事件规则，请在配置管理中创建。
            </div>

            <div v-else class="space-y-3">
              <label
                v-for="rule in webhookEventRules"
                :key="rule.id"
                class="flex items-start gap-3 p-4 rounded-xl transition-all duration-200"
                :class="[
                  selectedEventIds.includes(Number(rule.id))
                    ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-500 shadow-md hover:shadow-lg cursor-pointer'
                    : 'bg-white border border-apple-200/60 hover:border-apple-300 cursor-pointer',
                  !rule.is_active && 'opacity-60 cursor-not-allowed'
                ]"
              >
                <input
                  type="checkbox"
                  class="mt-1 w-4 h-4 accent-green-600"
                  :value="Number(rule.id)"
                  v-model="selectedEventIds"
                  :disabled="!rule.is_active"
                />
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <div
                      class="text-sm font-semibold"
                      :class="selectedEventIds.includes(Number(rule.id)) ? 'text-green-900' : 'text-apple-900'"
                    >
                      {{ rule.name }}
                    </div>
                    <span
                      v-if="selectedEventIds.includes(Number(rule.id))"
                      class="badge badge-success flex items-center gap-1"
                    >
                      <CheckCircle2 class="w-3 h-3" />
                      已启用
                    </span>
                    <span v-else-if="!rule.is_active" class="badge bg-apple-200 text-apple-700">停用</span>
                    <span
                      class="text-xs px-2 py-0.5 rounded-full"
                      :class="selectedEventIds.includes(Number(rule.id)) ? 'bg-green-100 text-green-700' : 'bg-apple-100 text-apple-600'"
                    >
                      {{ rule.event_type }}
                    </span>
                  </div>
                  <div
                    class="text-xs mb-2"
                    :class="selectedEventIds.includes(Number(rule.id)) ? 'text-green-700' : 'text-apple-600'"
                  >
                    {{ rule.description || '暂无描述' }}
                  </div>
                  <div
                    class="text-xs font-mono p-2 rounded"
                    :class="selectedEventIds.includes(Number(rule.id)) ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-apple-50 text-apple-500'"
                  >
                    {{ JSON.stringify(rule.match_rules) }}
                  </div>
                </div>
              </label>
            </div>

            <div v-if="selectedEventIds.length > 0" class="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-400 rounded-xl p-4 shadow-sm">
              <div class="flex items-center gap-2 mb-2">
                <CheckCircle2 class="w-5 h-5 text-green-600" />
                <div class="text-sm font-semibold text-green-900">已选择 {{ selectedEventIds.length }} 个事件</div>
              </div>
              <div class="text-xs text-green-700">这些事件将触发自动代码审查</div>
            </div>
            <div v-else class="bg-orange-50 border border-orange-200 rounded-xl p-4">
              <div class="flex items-center gap-2 mb-2">
                <AlertCircle class="w-5 h-5 text-orange-600" />
                <div class="text-sm font-medium text-orange-900">未选择任何事件</div>
              </div>
              <div class="text-xs text-orange-700">请至少选择一个事件以启用自动代码审查</div>
            </div>
          </div>
        </div>

        <!-- Event Prompts Tab -->
        <div v-show="activeTab === 'event-prompts'" class="config-section">
          <div class="p-6 space-y-6">
            <div class="flex items-center gap-3">
              <div class="w-2 h-2 bg-indigo-500 rounded-full"></div>
              <h3 class="text-lg font-semibold text-apple-900">审查提示词配置</h3>
            </div>

            <div class="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200/60 rounded-xl p-4 text-sm text-indigo-700">
              <div class="font-medium mb-2">💡 为每个 Webhook 事件类型自定义代码审查的提示词</div>
              <div class="text-xs space-y-1">
                <div>• 让 AI 更符合项目特点进行审查</div>
                <div>• 支持变量占位符：{project_name}, {author}, {title}, {source_branch} 等</div>
                <div>• 留空则使用系统默认提示词</div>
              </div>
            </div>

            <div v-if="eventPrompts.length === 0" class="p-6 bg-apple-50 border border-dashed border-apple-200 text-center rounded-xl text-sm text-apple-500">
              暂无配置，请先在 Webhook 事件页面启用事件。
            </div>

            <div v-else class="space-y-4">
              <div
                v-for="promptConfig in eventPrompts"
                :key="promptConfig.event_rule"
                class="bg-white border border-apple-200/60 rounded-xl p-5 hover:shadow-md transition-shadow duration-200"
              >
                <div class="flex items-start justify-between mb-4">
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                      <div class="text-base font-semibold text-apple-900">
                        {{ promptConfig.event_rule_name }}
                      </div>
                      <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                        {{ promptConfig.event_rule_type }}
                      </span>
                    </div>
                    <div class="text-xs text-apple-500">
                      {{ promptConfig.event_rule_description || '暂无描述' }}
                    </div>
                  </div>
                  <label class="config-toggle flex-shrink-0">
                    <input
                      type="checkbox"
                      class="config-toggle-input"
                      v-model="promptConfig.use_custom"
                      @change="savePromptConfig(promptConfig)"
                    />
                    <div class="config-toggle-slider"></div>
                  </label>
                </div>

                <div v-if="promptConfig.use_custom" class="space-y-2">
                  <textarea
                    v-model="promptConfig.custom_prompt"
                    class="w-full min-h-[240px] p-3 text-sm border border-apple-200 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 resize-vertical font-mono"
                    placeholder="请输入自定义的审查提示词，支持 Markdown 格式和变量占位符...

示例：
请对项目 {project_name} 的 MR #{mr_iid} 进行代码审查。
作者：{author}
标题：{title}
分支：{source_branch} -> {target_branch}

请重点关注：
1. 代码安全性
2. 性能优化
3. 最佳实践"
                  ></textarea>
                  <div class="flex items-center justify-between">
                    <div class="text-xs text-apple-500">
                      支持的占位符：{project_name}, {author}, {title}, {description}, {source_branch}, {target_branch}, {mr_iid}, {file_count}, {changes_count}
                    </div>
                    <button
                      class="btn-primary text-sm min-w-[100px]"
                      :disabled="promptSaving"
                      @click="savePromptConfig(promptConfig)"
                    >
                      <Save class="w-4 h-4" />
                      {{ promptSaving ? '保存中...' : '保存' }}
                    </button>
                  </div>
                </div>
                <div v-else class="text-xs text-apple-400 italic py-2">
                  当前使用系统默认提示词
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Notification Settings Tab -->
        <div v-show="activeTab === 'notifications'" class="config-section">
          <div class="p-6 space-y-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-2 h-2 bg-orange-500 rounded-full"></div>
                <h3 class="text-lg font-semibold text-apple-900">通知设置</h3>
              </div>
              <button
                class="btn-primary"
                :disabled="notificationSaving"
                @click="saveProjectNotificationSettings"
              >
                <Save class="w-4 h-4" />
                {{ notificationSaving ? '保存中...' : '保存' }}
              </button>
            </div>

            <div class="flex items-center justify-between bg-apple-50 border border-apple-200/60 rounded-lg px-3 py-2">
              <span class="text-xs text-apple-700">GitLab 评论通知</span>
              <label class="config-toggle">
                <input type="checkbox" class="config-toggle-input" v-model="gitlabCommentEnabled" />
                <div class="config-toggle-slider"></div>
              </label>
            </div>

            <div class="space-y-4">
            <div
              v-for="type in computedChannelTypes"
                :key="type.value"
                class="space-y-2"
              >
                <div class="flex items-center gap-2 text-xs font-semibold text-apple-600 uppercase tracking-wide">
                  <img v-if="channelIcons[type.value]" :src="channelIcons[type.value]" :alt="type.label" class="w-4 h-4 object-contain" />
                  <span>{{ type.label }}</span>
                </div>
                <div v-if="groupedNotificationChannels[type.value]?.length" class="space-y-2">
                  <div
                    v-for="channel in groupedNotificationChannels[type.value]"
                    :key="channel.id"
                    class="flex items-center justify-between bg-apple-50 border border-apple-200/60 rounded-lg px-4 py-3 hover:bg-apple-100/50 transition-colors duration-200"
                  >
                    <div class="flex items-start gap-2 flex-1 mr-3">
                      <img v-if="channelIcons[channel.notification_type]" :src="channelIcons[channel.notification_type]" :alt="channel.notification_type" class="w-5 h-5 mt-0.5 object-contain flex-shrink-0" />
                      <div class="flex-1">
                        <div class="text-sm text-apple-900 font-medium">{{ channel.name }}</div>
                        <div class="text-xs text-apple-500 mt-0.5">{{ channel.description || '暂无备注' }}</div>
                      </div>
                    </div>
                    <label class="config-toggle flex-shrink-0">
                      <input
                        type="checkbox"
                        class="config-toggle-input"
                        :value="Number(channel.id)"
                        v-model="selectedChannelIds"
                      />
                      <div class="config-toggle-slider"></div>
                    </label>
                  </div>
                </div>
                <div v-else class="text-xs text-apple-400 bg-apple-50 rounded-lg px-3 py-2 border border-dashed border-apple-200">
                  该类型暂无可用通道
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Recent Events Tab -->
        <div v-show="activeTab === 'events'" class="config-section">
          <div class="p-6 space-y-6">
            <div class="flex items-center gap-3">
              <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
              <h3 class="text-lg font-semibold text-apple-900">最近事件</h3>
            </div>

            <div class="space-y-4">
              <div
                v-for="(event, index) in recentEvents"
                :key="index"
                class="flex gap-4 p-4 rounded-xl bg-apple-50 hover:bg-apple-100 transition-colors duration-200"
              >
                <div class="flex-shrink-0">
                  <div
                    :class="[
                      'w-10 h-10 rounded-xl flex items-center justify-center',
                      getEventBgColor(event.type)
                    ]"
                  >
                    <component
                      :is="getEventIcon(event.type)"
                      class="w-5 h-5 text-white"
                    />
                  </div>
                </div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1">
                      <h4 class="text-sm font-semibold text-apple-900">{{ event.title }}</h4>
                      <p class="text-xs text-apple-600 mt-0.5">{{ event.description }}</p>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                      <button
                        v-if="getGitLabEventUrl(event)"
                        @click="openProjectUrl(getGitLabEventUrl(event))"
                        class="text-apple-600 hover:text-apple-blue-600 transition-colors p-1 rounded-lg hover:bg-apple-200/50"
                        title="在 GitLab 中查看"
                      >
                        <ExternalLink class="w-4 h-4" />
                      </button>
                      <span class="text-2xs text-apple-500">{{ event.time }}</span>
                    </div>
                  </div>
                  <div class="flex items-center gap-3 mt-2">
                    <div class="flex items-center gap-1.5 text-2xs text-apple-600">
                      <User class="w-3 h-3" />
                      <span>{{ event.author }}</span>
                    </div>
                    <div class="flex items-center gap-1.5 text-2xs text-apple-600">
                      <GitBranch class="w-3 h-3" />
                      <span>{{ event.branch }}</span>
                    </div>
                    <span
                      :class="[
                        'badge',
                        getEventBadgeClass(event.status)
                      ]"
                    >
                      {{ event.status }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- 分页组件 -->
              <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 pt-4">
                <button
                  @click="handlePageChange(currentPage - 1)"
                  :disabled="currentPage === 1"
                  class="px-3 py-2 text-sm rounded-lg border border-apple-200 hover:bg-apple-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  上一页
                </button>

                <div class="flex items-center gap-1">
                  <!-- 第一页 -->
                  <button
                    v-if="currentPage > 3"
                    @click="handlePageChange(1)"
                    class="px-3 py-2 text-sm rounded-lg border border-apple-200 hover:bg-apple-50 transition-colors"
                  >
                    1
                  </button>
                  <span v-if="currentPage > 4" class="px-2 text-apple-400">...</span>

                  <!-- 当前页附近的页码 -->
                  <button
                    v-for="page in visiblePages"
                    :key="page"
                    @click="handlePageChange(page)"
                    :class="[
                      'px-3 py-2 text-sm rounded-lg transition-colors',
                      currentPage === page
                        ? 'bg-apple-blue-500 text-white'
                        : 'border border-apple-200 hover:bg-apple-50'
                    ]"
                  >
                    {{ page }}
                  </button>

                  <!-- 最后一页 -->
                  <span v-if="currentPage < totalPages - 3" class="px-2 text-apple-400">...</span>
                  <button
                    v-if="currentPage < totalPages - 2"
                    @click="handlePageChange(totalPages)"
                    class="px-3 py-2 text-sm rounded-lg border border-apple-200 hover:bg-apple-50 transition-colors"
                  >
                    {{ totalPages }}
                  </button>
                </div>

                <button
                  @click="handlePageChange(currentPage + 1)"
                  :disabled="currentPage === totalPages"
                  class="px-3 py-2 text-sm rounded-lg border border-apple-200 hover:bg-apple-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  下一页
                </button>
              </div>

              <!-- 数据为空提示 -->
              <div v-if="recentEvents.length === 0" class="p-8 text-center">
                <div class="text-apple-400 text-sm">暂无事件记录</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Sidebar -->
      <div class="space-y-6">
        <!-- Quick Stats -->
        <div class="card">
          <div class="p-6 space-y-4">
            <h3 class="section-header mb-4">项目统计</h3>

            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <GitCommit class="w-4 h-4" />
                  <span>总提交数</span>
                </div>
                <span class="text-sm font-semibold text-apple-900">{{ project?.commits_count || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <GitPullRequest class="w-4 h-4" />
                  <span>合并请求</span>
                </div>
                <span class="text-sm font-semibold text-apple-900">{{ project?.mr_count || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <CheckCircle2 class="w-4 h-4" />
                  <span>审查完成</span>
                </div>
                <span class="text-sm font-semibold text-green-600">{{ projectStats?.reviews?.completed || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <AlertCircle class="w-4 h-4" />
                  <span>本周审查</span>
                </div>
                <span class="text-sm font-semibold text-orange-600">{{ projectStats?.reviews?.weekly || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <TrendingUp class="w-4 h-4" />
                  <span>审查成功率</span>
                </div>
                <span class="text-sm font-semibold text-apple-blue-600">{{ projectStats?.reviews?.completion_rate?.toFixed(1) || 0 }}%</span>
              </div>
            </div>
          </div>
        </div>

  
        <!-- Contributors -->
        <div class="card">
          <div class="p-6">
            <h3 class="section-header mb-4">活跃贡献者</h3>
            <div class="space-y-3">
              <div
                v-for="(contributor, index) in topContributors"
                :key="index"
                class="flex items-center gap-3 p-3 rounded-xl hover:bg-apple-50 transition-colors duration-200"
              >
                <div class="w-8 h-8 rounded-full bg-gradient-to-br from-apple-blue-500 to-apple-blue-600 flex items-center justify-center text-white text-xs font-semibold">
                  {{ contributor.initials }}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium text-apple-900">{{ contributor.name }}</div>
                  <div class="text-2xs text-apple-500">{{ contributor.commits }} commits</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="card">
          <div class="p-6 space-y-3">
            <button
              @click="toggleReview"
              :disabled="loading"
              class="btn-primary w-full"
            >
              <Power class="w-4 h-4" />
              <span>{{ project?.review_enabled ? '关闭审查' : '开启审查' }}</span>
            </button>
            <button
              @click="openProjectUrl(project?.project_url)"
              class="btn-secondary w-full"
            >
              <ExternalLink class="w-4 h-4" />
              <span>查看 GitLab</span>
            </button>
            <button
              @click="refreshData"
              :disabled="loading"
              class="btn-ghost w-full"
            >
              <Settings class="w-4 h-4" />
              <span>{{ loading ? '刷新中...' : '刷新数据' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import {
  ArrowLeft,
  ExternalLink,
  Users,
  GitCommit,
  GitPullRequest,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Power,
  Settings,
  User,
  GitBranch,
  FileCheck,
  AlertTriangle,
  XCircle,
  Save
} from 'lucide-vue-next'
import {
  getProjectDetail,
  getProjectWebhookLogs,
  getProjectReviewHistory,
  enableProjectReview,
  disableProjectReview,
  getNotificationChannels,
  getProjectNotifications,
  updateProjectNotifications,
  getWebhookEventRules,
  getProjectWebhookEvents,
  updateProjectWebhookEvents,
  getProjectWebhookEventPrompts,
  updateProjectWebhookEventPrompt
} from '@/api'
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()

// Tab 相关状态
const activeTab = ref('info')
const tabs = [
  { key: 'info', label: '项目信息' },
  { key: 'webhook-events', label: 'Webhook事件' },
  { key: 'event-prompts', label: '审查提示词' },
  { key: 'notifications', label: '通知设置' },
  { key: 'events', label: '最近事件' }
]

const reviewChartRef = ref<HTMLElement>()
const issueChartRef = ref<HTMLElement>()
const loading = ref(false)

const project = ref<any>(null)
const projectStats = ref<any>(null)
const recentEvents = ref<any[]>([])
const topContributors = ref<any[]>([])

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const totalEvents = ref(0)

const notificationChannels = ref<any[]>([])
const channelTypeLabels: Record<string, string> = {
  dingtalk: '钉钉通知',
  feishu: '飞书通知',
  wechat: '企业微信通知',
  slack: 'Slack 通知',
  email: '邮件通知',
  gitlab: 'GitLab 评论'
}

// 通道类型图标映射
const channelIcons: Record<string, string> = {
  dingtalk: new URL('../assets/icons/dingtalk.png', import.meta.url).href,
  feishu: new URL('../assets/icons/feishu.png', import.meta.url).href,
  wechat: new URL('../assets/icons/wechat.png', import.meta.url).href,
  gitlab: new URL('../assets/icons/gitlab.png', import.meta.url).href
}

const selectedChannelIds = ref<number[]>([])
const gitlabCommentEnabled = ref(true)
const notificationSaving = ref(false)

// Webhook 事件配置相关
const webhookEventRules = ref<any[]>([])
const selectedEventIds = ref<number[]>([])
const webhookEventSaving = ref(false)

// Webhook 事件 Prompt 配置相关
const eventPrompts = ref<any[]>([])
const promptSaving = ref(false)

const computedChannelTypes = computed(() => {
  const set = new Set(notificationChannels.value.map(item => item.notification_type))
  return Array.from(set).map(value => ({
    value,
    label: channelTypeLabels[value] || value
  }))
})

const groupedNotificationChannels = computed(() => {
  const map: Record<string, any[]> = {}
  computedChannelTypes.value.forEach(item => {
    map[item.value] = []
  })

  notificationChannels.value.forEach(channel => {
    if (!map[channel.notification_type]) {
      map[channel.notification_type] = []
    }
    map[channel.notification_type].push(channel)
  })

  return map
})

const loadProjectDetail = async () => {
  try {
    loading.value = true
    const projectId = route.params.id as string
    const response = await getProjectDetail(projectId)

    if (response && response.status === 'success') {
      project.value = response.project
      projectStats.value = response.stats
    }
  } catch (error) {
    console.error('Failed to load project detail:', error)
    toast.error('加载项目详情失败')
  } finally {
    loading.value = false
  }
}

const loadRecentEvents = async (page: number = 1) => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectWebhookLogs(projectId, {
      limit: pageSize.value,
      offset: (page - 1) * pageSize.value
    })

    if (response && response.status === 'success' && response.logs) {
      recentEvents.value = response.logs.map((log: any) => ({
        type: log.event_type,
        title: getEventTitle(log.event_type, log.merge_request_iid),
        description: getEventDescription(log.event_type, log.object_attributes),
        author: log.user_name || log.user_email || '未知',
        branch: log.source_branch || log.target_branch || '未知分支',
        status: getEventStatus(log.event_type, log.processed),
        time: formatTimeAgo(log.created_at),
        // 添加跳转需要的字段
        merge_request_iid: log.merge_request_iid,
        issue_iid: log.issue_iid,
        note_id: log.note_id,
        source_branch: log.source_branch,
        target_branch: log.target_branch,
        created_at: log.created_at
      }))
      // 更新总数
      totalEvents.value = response.total || response.logs.length
    }
  } catch (error) {
    console.error('Failed to load recent events:', error)
  }
}

const loadReviewHistory = async () => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectReviewHistory(projectId, { limit: 20, days: 30 })

    if (response && response.status === 'success' && response.reviews) {
      // Process review history to create charts data
      processReviewData(response.reviews)

      // 提取活跃贡献者
      const contributorsMap = new Map()
      response.reviews.forEach((review: any) => {
        const author = review.author || '未知'
        if (!contributorsMap.has(author)) {
          contributorsMap.set(author, {
            name: author,
            initials: author.substring(0, 2).toUpperCase(),
            commits: 0
          })
        }
        contributorsMap.get(author).commits++
      })

      topContributors.value = Array.from(contributorsMap.values())
        .sort((a, b) => b.commits - a.commits)
        .slice(0, 5)
    }
  } catch (error) {
    console.error('Failed to load review history:', error)
  }
}

const normalizeChannelList = (data: any) => {
  if (!data) return []
  if (Array.isArray(data)) return data
  if (Array.isArray(data.results)) return data.results
  if (Array.isArray(data.channels)) return data.channels
  return []
}

const loadNotificationChannelList = async () => {
  try {
    const response = await getNotificationChannels()
    notificationChannels.value = normalizeChannelList(response)
  } catch (error) {
    console.error('Failed to load notification channels:', error)
  }
}

const loadProjectNotificationSettings = async () => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectNotifications(projectId)

    if (response && response.status === 'success') {
      gitlabCommentEnabled.value = response.gitlab_comment_enabled !== false
      selectedChannelIds.value = Array.isArray(response.channels)
        ? response.channels.map((item: any) => Number(item.channel_id)).filter(Boolean)
        : []
    }
  } catch (error) {
    console.error('Failed to load project notification settings:', error)
  }
}

const saveProjectNotificationSettings = async () => {
  notificationSaving.value = true
  try {
    const projectId = route.params.id as string
    const normalizedIds = Array.from(new Set(selectedChannelIds.value.map(id => Number(id)))).filter(id => !Number.isNaN(id))
    await updateProjectNotifications(projectId, {
      gitlab_comment_enabled: gitlabCommentEnabled.value,
      channel_ids: normalizedIds
    })
    toast.success('通知设置已更新')
    await loadProjectNotificationSettings()
  } catch (error) {
    console.error('Failed to save project notifications:', error)
    toast.error('保存通知设置失败')
  } finally {
    notificationSaving.value = false
  }
}

const loadWebhookEventRules = async () => {
  try {
    const response = await getWebhookEventRules()
    if (response && response.results) {
      webhookEventRules.value = response.results
    } else if (Array.isArray(response)) {
      webhookEventRules.value = response
    } else {
      webhookEventRules.value = []
    }
  } catch (error) {
    console.error('Failed to load webhook event rules:', error)
  }
}

const loadProjectWebhookEvents = async () => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectWebhookEvents(projectId)

    if (response && response.status === 'success') {
      const enabledIds = Array.isArray(response.enabled_event_ids)
        ? response.enabled_event_ids.map((id: any) => Number(id)).filter(Boolean)
        : []

      // 过滤掉前端没有对应规则的事件ID（双重保险）
      const validIds = enabledIds.filter(id =>
        webhookEventRules.value.some(rule => Number(rule.id) === id)
      )

      if (validIds.length !== enabledIds.length) {
        console.warn('Some event IDs were filtered out as they no longer exist:',
          enabledIds.filter(id => !validIds.includes(id))
        )
      }

      selectedEventIds.value = validIds
    }
  } catch (error) {
    console.error('Failed to load project webhook events:', error)
  }
}

const saveProjectWebhookEvents = async () => {
  webhookEventSaving.value = true
  try {
    const projectId = route.params.id as string
    const normalizedIds = Array.from(new Set(selectedEventIds.value.map(id => Number(id)))).filter(id => !Number.isNaN(id))
    await updateProjectWebhookEvents(projectId, {
      event_ids: normalizedIds
    })
    toast.success('Webhook事件配置已更新')
    await loadProjectWebhookEvents()
    // 事件更新后重新加载 prompt 配置
    await loadProjectWebhookEventPrompts()
  } catch (error) {
    console.error('Failed to save project webhook events:', error)
    toast.error('保存Webhook事件配置失败')
  } finally {
    webhookEventSaving.value = false
  }
}

const loadProjectWebhookEventPrompts = async () => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectWebhookEventPrompts(projectId)

    if (response && response.prompts) {
      eventPrompts.value = response.prompts
    }
  } catch (error) {
    console.error('Failed to load project webhook event prompts:', error)
  }
}

const savePromptConfig = async (promptConfig: any) => {
  promptSaving.value = true
  try {
    const projectId = route.params.id as string
    await updateProjectWebhookEventPrompt(projectId, {
      event_rule_id: promptConfig.event_rule,
      custom_prompt: promptConfig.custom_prompt,
      use_custom: promptConfig.use_custom
    })
    toast.success('提示词配置已保存')
    await loadProjectWebhookEventPrompts()
  } catch (error) {
    console.error('Failed to save prompt config:', error)
    toast.error('保存失败，请重试')
  } finally {
    promptSaving.value = false
  }
}

const getEventTitle = (eventType: string, mrIid?: number) => {
  const titleMap: Record<string, string> = {
    'merge_request': `Merge Request #${mrIid} 已审查`,
    'push': '新的提交已推送',
    'issue': '发现代码问题',
    'note': '新增评论'
  }
  return titleMap[eventType] || '未知事件'
}

const getGitLabEventUrl = (event: any) => {
  if (!project.value?.project_url) return null

  const baseUrl = project.value.project_url.replace(/\.git$/, '')

  switch (event.type) {
    case 'merge_request':
      if (event.merge_request_iid) {
        return `${baseUrl}/-/merge_requests/${event.merge_request_iid}`
      }
      break
    case 'push':
      if (event.source_branch) {
        return `${baseUrl}/-/commits/${event.source_branch}`
      }
      break
    case 'note':
      if (event.merge_request_iid && event.note_id) {
        return `${baseUrl}/-/merge_requests/${event.merge_request_iid}#note_${event.note_id}`
      } else if (event.issue_iid && event.note_id) {
        return `${baseUrl}/-/issues/${event.issue_iid}#note_${event.note_id}`
      }
      break
    case 'issue':
      if (event.issue_iid) {
        return `${baseUrl}/-/issues/${event.issue_iid}`
      }
      break
  }

  return baseUrl
}

const getEventDescription = (eventType: string, objectAttributes?: any) => {
  if (eventType === 'merge_request' && objectAttributes) {
    return objectAttributes.title || '合并请求'
  }
  if (eventType === 'push' && objectAttributes) {
    return objectAttributes.message || '代码提交'
  }
  return '事件描述'
}

const getEventStatus = (eventType: string, processed: boolean) => {
  if (!processed) return '处理中'

  const statusMap: Record<string, string> = {
    'merge_request': '通过',
    'push': '已推送',
    'issue': '警告',
    'note': '已评论'
  }
  return statusMap[eventType] || '完成'
}

const formatTimeAgo = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 30) return `${days} 天前`

  return date.toLocaleDateString()
}

const processReviewData = (reviews: any[]) => {
  // Process reviews to create charts data
  const dailyStats: Record<string, number> = {}
  const issueTypes: Record<string, number> = {}

  reviews.forEach(review => {
    const date = new Date(review.created_at).toLocaleDateString()
    dailyStats[date] = (dailyStats[date] || 0) + 1

    // Analyze review content for issue types
    if (review.review_content) {
      const content = review.review_content.toLowerCase()
      if (content.includes('security') || content.includes('安全')) {
        issueTypes['安全问题'] = (issueTypes['安全问题'] || 0) + 1
      } else if (content.includes('performance') || content.includes('性能')) {
        issueTypes['性能优化'] = (issueTypes['性能优化'] || 0) + 1
      } else if (content.includes('style') || content.includes('规范')) {
        issueTypes['代码规范'] = (issueTypes['代码规范'] || 0) + 1
      } else {
        issueTypes['代码质量'] = (issueTypes['代码质量'] || 0) + 1
      }
    }
  })

  // Update charts with real data
  updateChartsWithData(dailyStats, issueTypes)
}

const updateChartsWithData = (dailyStats: Record<string, number>, issueTypes: Record<string, number>) => {
  // This will be called after data is loaded to update charts
  // Implementation depends on chart initialization
}

const getEventIcon = (type: string) => {
  const iconMap: Record<string, any> = {
    merge: FileCheck,
    commit: GitCommit,
    issue: AlertTriangle,
    error: XCircle
  }
  return iconMap[type] || GitCommit
}

const getEventBgColor = (type: string) => {
  const colorMap: Record<string, string> = {
    merge: 'bg-green-500',
    commit: 'bg-apple-blue-500',
    issue: 'bg-orange-500',
    error: 'bg-red-500'
  }
  return colorMap[type] || 'bg-apple-400'
}

const getEventBadgeClass = (status: string) => {
  const classMap: Record<string, string> = {
    '通过': 'badge-success',
    '待审查': 'badge-info',
    '警告': 'badge-warning',
    '失败': 'badge-danger'
  }
  return classMap[status] || 'bg-apple-200 text-apple-700'
}

const initReviewChart = () => {
  if (!reviewChartRef.value) return

  const chart = echarts.init(reviewChartRef.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e8e8ed',
      borderWidth: 1,
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      padding: 12,
      borderRadius: 12
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#e8e8ed' } },
      axisLabel: { color: '#86868b', fontSize: 10 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#86868b', fontSize: 10 },
      splitLine: { lineStyle: { color: '#f5f5f7', type: 'dashed' } }
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: [12, 18, 15, 22, 28, 19, 24],
        lineStyle: { color: '#007aff', width: 2 },
        itemStyle: { color: '#007aff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 122, 255, 0.2)' },
            { offset: 1, color: 'rgba(0, 122, 255, 0)' }
          ])
        }
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const initIssueChart = () => {
  if (!issueChartRef.value) return

  const chart = echarts.init(issueChartRef.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e8e8ed',
      borderWidth: 1,
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      padding: 12,
      borderRadius: 12
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#86868b', fontSize: 11 }
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false },
        labelLine: { show: false },
        data: [
          { value: 45, name: '代码质量', itemStyle: { color: '#007aff' } },
          { value: 28, name: '安全问题', itemStyle: { color: '#ff3b30' } },
          { value: 32, name: '性能优化', itemStyle: { color: '#34c759' } },
          { value: 19, name: '代码规范', itemStyle: { color: '#ff9500' } }
        ]
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const goBack = () => {
  router.push('/projects')
}

const toggleReview = async () => {
  if (!project.value) return

  try {
    const projectId = project.value.project_id
    const originalStatus = project.value.review_enabled
    project.value.review_enabled = !originalStatus

    try {
      if (project.value.review_enabled) {
        await enableProjectReview(projectId.toString())
        toast.success('已启用代码审查')
      } else {
        await disableProjectReview(projectId.toString())
        toast.success('已禁用代码审查')
      }
    } catch (apiError) {
      // Revert on API error
      project.value.review_enabled = originalStatus
      throw apiError
    }
  } catch (error) {
    console.error('Failed to toggle review:', error)
    toast.error('操作失败，请重试')
  }
}

const openProjectUrl = (url?: string) => {
  if (url) {
    window.open(url, '_blank')
  }
}

const refreshData = async () => {
  await Promise.all([
    loadProjectDetail(),
    loadRecentEvents(currentPage.value),
    loadReviewHistory()
  ])
  await loadNotificationChannelList()
  await loadProjectNotificationSettings()
  // 先加载所有事件规则，再加载项目的事件配置（确保可以正确过滤无效ID）
  await loadWebhookEventRules()
  await loadProjectWebhookEvents()
  // 加载 webhook 事件 prompt 配置
  await loadProjectWebhookEventPrompts()
}

// 分页相关计算属性和方法
const totalPages = computed(() => Math.ceil(totalEvents.value / pageSize.value))

// 计算可见的页码（当前页前后各2页）
const visiblePages = computed(() => {
  const pages: number[] = []
  const start = Math.max(1, currentPage.value - 2)
  const end = Math.min(totalPages.value, currentPage.value + 2)

  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return pages
})

const handlePageChange = async (page: number) => {
  currentPage.value = page
  await loadRecentEvents(page)
}

const initializeCharts = () => {
  // 延迟初始化图表，确保 DOM 元素已渲染
  setTimeout(() => {
    if (activeTab.value === 'stats') {
      initReviewChart()
      initIssueChart()
    }
  }, 100)
}

// 监听 tab 切换，当切换到统计 tab 时初始化图表
const handleTabChange = (tabKey: string) => {
  activeTab.value = tabKey
  if (tabKey === 'stats') {
    initializeCharts()
  }
}

onMounted(() => {
  refreshData()
  // 初始化时如果默认 tab 是 stats，也需要初始化图表
  if (activeTab.value === 'stats') {
    initializeCharts()
  }
})
</script>
