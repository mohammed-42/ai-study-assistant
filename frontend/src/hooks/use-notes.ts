import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { noteApi } from '@/services/api'
import { useToast } from './use-toast'

const NOTES_QUERY_KEY = ['notes']
const NOTE_QUERY_KEY = (id: string) => ['note', id]

export function useNotes(subjectId?: string, documentId?: string) {
  return useQuery({
    queryKey: [...NOTES_QUERY_KEY, subjectId, documentId],
    queryFn: () => noteApi.list(subjectId, documentId),
  })
}

export function useNote(id: string) {
  return useQuery({
    queryKey: NOTE_QUERY_KEY(id),
    queryFn: () => noteApi.get(id),
    enabled: !!id,
  })
}

export function useCreateNote() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: Parameters<typeof noteApi.create>[0]) => noteApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to create note', description: error.message, variant: 'destructive' })
    },
  })
}

export function useUpdateNote() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Parameters<typeof noteApi.create>[0]> }) =>
      noteApi.update(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: NOTE_QUERY_KEY(variables.id) })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to update note', description: error.message, variant: 'destructive' })
    },
  })
}

export function useDeleteNote() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (id: string) => noteApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY })
      toast({ title: 'Note deleted' })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to delete', description: error.message, variant: 'destructive' })
    },
  })
}

export function useGenerateNote() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (params: Parameters<typeof noteApi.generate>[0]) => noteApi.generate(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to generate note', description: error.message, variant: 'destructive' })
    },
  })
}
