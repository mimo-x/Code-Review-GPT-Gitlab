/* Ported from Robbings/Paperpane, commit 9aad46c. */
export type Protocol = "openai-responses" | "openai-chat" | "anthropic" | "gemini";

export const protocols: { value: Protocol; label: string }[] = [
  { value: "openai-responses", label: "OpenAI Responses" },
  { value: "openai-chat", label: "OpenAI Chat Completions" },
  { value: "anthropic", label: "Anthropic Messages" },
  { value: "gemini", label: "Gemini 原生" },
];

export interface ProviderBrand {
  id: string;
  name: string;
  website: string;
  description: string;
  keywords: string;
  group: "popular" | "more" | "platform";
  color: string;
}
export const providerBrands: ProviderBrand[] = [
  {
    id: "openai",
    name: "OpenAI",
    website: "platform.openai.com",
    description: "GPT 系列",
    keywords: "chatgpt gpt",
    group: "popular",
    color: "var(--pp-text)",
  },
  {
    id: "anthropic",
    name: "Claude",
    website: "console.anthropic.com",
    description: "Anthropic · Claude 系列",
    keywords: "anthropic sonnet opus haiku",
    group: "popular",
    color: "#c76b49",
  },
  {
    id: "google",
    name: "Gemini",
    website: "aistudio.google.com",
    description: "Google · Gemini 系列",
    keywords: "google 谷歌",
    group: "popular",
    color: "#4285f4",
  },
  {
    id: "xai",
    name: "Grok",
    website: "console.x.ai",
    description: "xAI · Grok 系列",
    keywords: "xai x.ai",
    group: "popular",
    color: "var(--pp-text)",
  },
  {
    id: "alibaba",
    name: "Qwen · 通义千问",
    website: "bailian.console.aliyun.com",
    description: "阿里云百炼",
    keywords: "qwen alibaba 阿里 千问 通义",
    group: "popular",
    color: "#7855e8",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    website: "platform.deepseek.com",
    description: "DeepSeek 系列",
    keywords: "深度求索",
    group: "popular",
    color: "#4d6bfe",
  },
  {
    id: "moonshotai",
    name: "Kimi",
    website: "platform.moonshot.cn",
    description: "月之暗面 · Kimi 系列",
    keywords: "moonshot 月之暗面",
    group: "popular",
    color: "#6156e8",
  },
  {
    id: "zhipuai",
    name: "GLM · 智谱",
    website: "open.bigmodel.cn",
    description: "智谱开放平台",
    keywords: "zhipu zai z.ai glm 智谱",
    group: "popular",
    color: "#3b63dd",
  },
  {
    id: "minimax",
    name: "MiniMax",
    website: "platform.minimaxi.com",
    description: "MiniMax 系列",
    keywords: "海螺 稀宇",
    group: "more",
    color: "#ee536d",
  },
  {
    id: "volcengine",
    name: "豆包 · 火山引擎",
    website: "console.volcengine.com/ark",
    description: "火山方舟 · Doubao Seed",
    keywords: "doubao seed byte 字节 火山 豆包",
    group: "more",
    color: "#2397e8",
  },
  {
    id: "stepfun",
    name: "阶跃星辰 · StepFun",
    website: "platform.stepfun.com",
    description: "Step 系列",
    keywords: "step 阶跃",
    group: "more",
    color: "#3564ef",
  },
  {
    id: "mistral",
    name: "Mistral",
    website: "console.mistral.ai",
    description: "Mistral · Magistral 系列",
    keywords: "magistral codestral",
    group: "more",
    color: "#eb7725",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    website: "openrouter.ai",
    description: "一个接口，连接多家模型",
    keywords: "聚合 路由",
    group: "platform",
    color: "#7561ba",
  },
  {
    id: "siliconflow",
    name: "硅基流动",
    website: "cloud.siliconflow.cn",
    description: "SiliconFlow · 开源模型服务",
    keywords: "siliconflow 硅基",
    group: "platform",
    color: "#7650d6",
  },
  {
    id: "groq",
    name: "Groq",
    website: "console.groq.com",
    description: "开源模型推理服务",
    keywords: "llama oss",
    group: "platform",
    color: "#ed5837",
  },
];
export interface ProviderPreset {
  id: string;
  brand: string;
  provider: string;
  name: string;
  protocol: Protocol;
  url: string;
  region?: string;
}
export const presets: ProviderPreset[] = [
  {
    id: "openai",
    brand: "openai",
    provider: "openai",
    name: "OpenAI",
    protocol: "openai-responses",
    url: "https://api.openai.com/v1",
  },
  {
    id: "anthropic",
    brand: "anthropic",
    provider: "anthropic",
    name: "Claude · Anthropic",
    protocol: "anthropic",
    url: "https://api.anthropic.com/v1",
  },
  {
    id: "google",
    brand: "google",
    provider: "google",
    name: "Google Gemini",
    protocol: "gemini",
    url: "https://generativelanguage.googleapis.com/v1beta",
  },
  {
    id: "xai",
    brand: "xai",
    provider: "xai",
    name: "xAI · Grok",
    protocol: "openai-chat",
    url: "https://api.x.ai/v1",
  },
  {
    id: "alibaba-cn",
    brand: "alibaba",
    provider: "alibaba-cn",
    name: "Qwen · 中国内地",
    protocol: "openai-chat",
    url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    region: "中国内地",
  },
  {
    id: "alibaba-intl",
    brand: "alibaba",
    provider: "alibaba",
    name: "Qwen · 国际",
    protocol: "openai-chat",
    url: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    region: "国际",
  },
  {
    id: "deepseek",
    brand: "deepseek",
    provider: "deepseek",
    name: "DeepSeek",
    protocol: "openai-chat",
    url: "https://api.deepseek.com/v1",
  },
  {
    id: "moonshotai-cn",
    brand: "moonshotai",
    provider: "moonshotai-cn",
    name: "Kimi",
    protocol: "openai-chat",
    url: "https://api.moonshot.cn/v1",
  },
  {
    id: "zhipuai",
    brand: "zhipuai",
    provider: "zhipuai",
    name: "GLM · 智谱",
    protocol: "openai-chat",
    url: "https://open.bigmodel.cn/api/paas/v4",
  },
  {
    id: "minimax-cn",
    brand: "minimax",
    provider: "minimax-cn",
    name: "MiniMax",
    protocol: "anthropic",
    url: "https://api.minimax.cn/anthropic/v1",
  },
  {
    id: "volcengine",
    brand: "volcengine",
    provider: "volcengine",
    name: "豆包 · 火山引擎",
    protocol: "openai-chat",
    url: "https://ark.cn-beijing.volces.com/api/v3",
  },
  {
    id: "stepfun",
    brand: "stepfun",
    provider: "stepfun",
    name: "阶跃星辰 · StepFun",
    protocol: "openai-chat",
    url: "https://api.stepfun.com/v1",
  },
  {
    id: "mistral",
    brand: "mistral",
    provider: "mistral",
    name: "Mistral",
    protocol: "openai-chat",
    url: "https://api.mistral.ai/v1",
  },
  {
    id: "openrouter",
    brand: "openrouter",
    provider: "openrouter",
    name: "OpenRouter",
    protocol: "openai-chat",
    url: "https://openrouter.ai/api/v1",
  },
  {
    id: "siliconflow-cn",
    brand: "siliconflow",
    provider: "siliconflow-cn",
    name: "硅基流动",
    protocol: "openai-chat",
    url: "https://api.siliconflow.cn/v1",
  },
  {
    id: "groq",
    brand: "groq",
    provider: "groq",
    name: "Groq",
    protocol: "openai-chat",
    url: "https://api.groq.com/openai/v1",
  },
  {
    id: "custom",
    brand: "custom",
    provider: "",
    name: "自定义兼容服务",
    protocol: "openai-chat",
    url: "",
  },
];
export const catalogProviders = [
  ...new Set(presets.map((p) => p.provider).filter(Boolean)),
];
export function providerBrand(presetId?: string) {
  const id = presets.find((p) => p.id === presetId)?.brand;
  return providerBrands.find((b) => b.id === id);
}
