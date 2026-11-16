export async function api(path, { method = 'GET', data } = {}) {
  const headers = {}
  if (method !== 'GET') headers['X-Preg-Request'] = '1'
  const multipart = data instanceof FormData
  if (data !== undefined && !multipart) headers['Content-Type'] = 'application/json'

  let response
  try {
    response = await fetch('/api' + path, {
      method,
      headers,
      body: multipart ? data : JSON.stringify(data),
      cache: 'no-store',
    })
  } catch {
    throw new Error('暂时无法连接，请检查网络后重试。')
  }

  if (response.status === 204) return null
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const validation = Array.isArray(body?.detail) && body.detail.find(error => /[\u3400-\u9fff]/u.test(error.msg))
    const message = typeof body?.detail === 'string' ? body.detail : validation?.msg
    const error = new Error(message || (response.status === 422 ? '请检查填写的内容。' : '操作失败，请重试。'))
    error.status = response.status
    throw error
  }
  return body
}
