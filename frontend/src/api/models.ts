import request from '@/utils/request'
import { getApiUrl } from '@/config/api'

export interface ReviewModel {
  id: number
  model: string
  label: string
  is_active: boolean
}

export interface ModelProvider {
  id: number
  name: string
  preset: string
  provider: string
  api_base: string | null
  has_api_key: boolean
  timeout: number
  models: ReviewModel[]
}

export type ConnectionSettings = Pick<ModelProvider, 'name' | 'preset' | 'provider' | 'api_base' | 'timeout'> & {
  api_key?: string
}

const authHeader = { 'X-Requested-With': 'XMLHttpRequest' }
const modelRequest = { headers: authHeader, inlineError: true }
const providers = '/llm-providers/'
const models = '/llm-configs/'

export const getModelProviders = () =>
  request<unknown, ModelProvider[]>({ ...modelRequest, url: getApiUrl(providers) })

export const saveModelProvider = (id: number | null, data: ConnectionSettings) =>
  request<unknown, ModelProvider>({
    ...modelRequest,
    url: getApiUrl(id === null ? providers : `${providers}${id}/`),
    method: id === null ? 'post' : 'patch',
    data,
  })

export type ModelEntry = Pick<ReviewModel, 'model' | 'label'>
export type TestMode = 'text' | 'image' | 'structured'

export const addReviewModels = (providerId: number, entries: ModelEntry[]) =>
  request<unknown, ReviewModel[]>({
    ...modelRequest, url: getApiUrl(`${providers}${providerId}/models/`), method: 'post', data: entries,
  })

export const activateReviewModel = (id: number) =>
  request({ ...modelRequest, url: getApiUrl(`${models}${id}/activate/`), method: 'post' })

export const listEndpointModels = (id: number, signal: AbortSignal) =>
  request<unknown, { models: Array<{ modelId: string; label: string }> }>({
    ...modelRequest, url: getApiUrl(`${providers}${id}/endpoint-models/`), method: 'post', signal,
  })

export const testReviewModel = (id: number, mode: TestMode, signal: AbortSignal) =>
  request<unknown, { text: string; elapsed_ms: number }>({
    ...modelRequest, url: getApiUrl(`${models}${id}/test/`), method: 'post',
    data: { mode }, timeout: 55000, signal,
  })

export const duplicateModelProvider = (id: number) =>
  request<unknown, ModelProvider>({
    ...modelRequest, url: getApiUrl(`${providers}${id}/duplicate/`), method: 'post',
  })

export const updateReviewModel = (id: number, data: ModelEntry) =>
  request<unknown, ReviewModel>({
    ...modelRequest, url: getApiUrl(`${models}${id}/`), method: 'patch', data,
  })

export const removeModelProvider = (id: number) =>
  request({ ...modelRequest, url: getApiUrl(`${providers}${id}/`), method: 'delete' })

export const removeReviewModel = (id: number) =>
  request({ ...modelRequest, url: getApiUrl(`${models}${id}/`), method: 'delete' })

export const modelError = (failure: unknown, fallback: string) => {
  const error = failure as { response?: { data?: { message?: unknown } } }
  const message = error?.response?.data?.message
  return typeof message === 'string' ? message : fallback
}
