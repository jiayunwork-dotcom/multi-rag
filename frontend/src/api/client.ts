import axios from 'axios'

const API_TOKEN = localStorage.getItem('api_token') || 'rag-token-secret'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000,
  headers: {
    'Authorization': `Bearer ${API_TOKEN}`,
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('api_token') || 'rag-token-secret'
  config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error('认证失败，请检查API Token')
    }
    return Promise.reject(error)
  }
)

export const setApiToken = (token: string) => {
  localStorage.setItem('api_token', token)
  api.defaults.headers.Authorization = `Bearer ${token}`
}

export default api
