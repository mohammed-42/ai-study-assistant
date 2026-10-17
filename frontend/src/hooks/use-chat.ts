import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/services/api'
import { useToast } from '@/hooks/use-toast'

const SESSIONS_QUERY_KEY = ['chat-sessions']
const MESSAGES_QUERY_KEY = (sessionId: string) => ['chat-messages', sessionId]

export function useChatSessions() {
  return useQuery({
    queryKey: SESSIONS_QUERY_KEY,
    queryFn: () => chatApi.listSessions(),
  })
}

export function useChatMessages(sessionId: string) {
  return useQuery({
    queryKey: MESSAGES_QUERY_KEY(sessionId),
    queryFn: () => chatApi.listMessages(sessionId),
    enabled: !!sessionId,
  })
}

export function useCreateChatSession() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: { subject_id?: string; title?: string }) =>
      chatApi.createSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to create session', description: error.message, variant: 'destructive' })
    },
  })
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (id: string) => chatApi.deleteSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY })
      toast({ title: 'Session deleted' })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to delete', description: error.message, variant: 'destructive' })
    },
  })
}

export function useSendChatMessage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ sessionId, data }: { sessionId: string; data: Parameters<typeof chatApi.sendMessage>[1] }) =>
      chatApi.sendMessage(sessionId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: MESSAGES_QUERY_KEY(variables.sessionId) })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to send message', description: error.message, variant: 'destructive' })
    },
  })
}
