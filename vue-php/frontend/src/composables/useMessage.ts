import { createDiscreteApi } from 'naive-ui'

const { message } = createDiscreteApi(['message'])

export function useMessage() {
  return {
    success: (text: string) => message.success(text),
    error: (text: string) => message.error(text),
    info: (text: string) => message.info(text),
  }
}
