/* Ported from Robbings/Paperpane, commit 9aad46c. */
import snapshot from "./model-catalog-data.json";
import { presets, catalogProviders, type Protocol } from "./provider-presets";

type ReasoningCapability =
  | { kind: "none" | "toggle" | "auto" | "unknown" }
  | { kind: "effort"; values: string[] }
  | { kind: "budget"; minTokens: number; maxTokens: number; presets: number[] };

export interface CatalogModel {
  provider: string;
  protocol?: Protocol;
  modelId: string;
  label: string;
  vision?: boolean;
  reasoning: ReasoningCapability;
  contextWindow?: number;
  inputLimit?: number;
  maxOutputTokens?: number;
  status?: string;
  releaseDate?: string;
  /** Some facts are defaults, not looked up: the reader should check them. */
  guessed?: boolean;
}
export interface Catalog {
  updatedAt: string;
  models: CatalogModel[];
}
export const bundledCatalog = snapshot as Catalog;
const limit = (v: unknown) =>
  typeof v === "number" && Number.isInteger(v) && v > 0 && v <= 10_000_000
    ? v
    : undefined;
/** Parse the public v1 API defensively. Missing facts remain unknown. */
export function parseCatalog(data: unknown): Catalog {
  if (!data || typeof data !== "object" || Array.isArray(data))
    throw new Error("模型目录格式不正确。");
  const models: CatalogModel[] = [];
  for (const provider of catalogProviders) {
    const group = (data as Record<string, any>)[provider]?.models;
    if (!group || typeof group !== "object") continue;
    for (const [id, m] of Object.entries(group) as [string, any][]) {
      if (models.length >= 5000) throw new Error("模型目录过大。");
      if (
        !m ||
        typeof m !== "object" ||
        id.length > 300 ||
        !id.trim() ||
        !Array.isArray(m.modalities?.output) ||
        !m.modalities.output.includes("text")
      )
        continue;
      const options = Array.isArray(m.reasoning_options)
        ? m.reasoning_options
        : [];
      const effort = options
        .find((o: any) => o?.type === "effort")
        ?.values?.filter((v: unknown) => typeof v === "string");
      const budget = options.find((o: any) => o?.type === "budget_tokens");
      const reasoning: ReasoningCapability =
        Array.isArray(effort) &&
        effort.length &&
        effort.length <= 16 &&
        effort.every((x: unknown) => typeof x === "string" && x.length < 40)
          ? { kind: "effort", values: effort }
          : limit(budget?.max) &&
              Number.isFinite(budget?.min ?? 0) &&
              Math.max(0, budget.min ?? 0) <= budget.max
            ? {
                kind: "budget",
                minTokens: Math.max(0, budget.min ?? 0),
                maxTokens: budget.max,
                presets: [
                  ...new Set([Math.max(0, budget.min ?? 0), budget.max]),
                ],
              }
            : options.some((o: any) => o?.type === "toggle")
              ? { kind: "toggle" }
              : m.reasoning === false
                ? { kind: "none" }
                : m.reasoning === true
                  ? { kind: "auto" }
                  : { kind: "unknown" };
      models.push({
        provider,
        modelId: id,
        label: typeof m.name === "string" ? m.name.slice(0, 200) : id,
        protocol: presets.find((p) => p.provider === provider)?.protocol,
        vision: Array.isArray(m.modalities?.input)
          ? m.modalities.input.some(
              (x: unknown) =>
                typeof x === "string" &&
                (x === "image" || x.startsWith("image/")),
            )
          : undefined,
        reasoning,
        contextWindow: limit(m.limit?.context),
        inputLimit: limit(m.limit?.input),
        maxOutputTokens: limit(m.limit?.output),
        status: typeof m.status === "string" ? m.status : "active",
        releaseDate: typeof m.release_date === "string" ? m.release_date : "",
      });
    }
  }
  if (!models.length) throw new Error("目录没有可用的文字模型，保留现有目录。");
  return { updatedAt: new Date().toISOString(), models };
}

export async function readJson(
  response: Response,
  maxBytes = 2_000_000,
): Promise<any> {
  if (!response.ok)
    throw new Error(
      response.status === 401 || response.status === 403
        ? "鉴权失败，请检查密钥与访问权限。"
        : response.status === 404
          ? "此端点没有模型列表接口，可从常用目录或手动添加。"
          : response.status === 429
            ? "请求过于频繁，请稍后重试。"
            : `接口返回 HTTP ${response.status}。`,
    );
  const reader = response.body?.getReader();
  if (!reader) throw new Error("接口未返回数据。");
  const decoder = new TextDecoder();
  let text = "",
    size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new Error("返回数据过大。");
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    return JSON.parse(text);
  } catch (e) {
    if (e instanceof SyntaxError) throw new Error("接口返回的不是有效 JSON。");
    throw e;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
