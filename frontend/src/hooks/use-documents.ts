import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentApi } from '@/services/api'
import { useToast } from '@/hooks/use-toast'

const QUERY_KEY = ['documents']

export function useDocuments(subjectId?: string) {
  return useQuery({
    queryKey: [...QUERY_KEY, subjectId],
    queryFn: () => documentApi.list(subjectId),
  })
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: [...QUERY_KEY, id],
    queryFn: () => documentApi.get(id),
    enabled: !!id,
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (id: string) => documentApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      toast({ title: 'Document deleted' })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to delete', description: error.message, variant: 'destructive' })
    },
  })
}

export function useRetryDocument() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (id: string) => documentApi.retry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      toast({ title: 'Retrying document...' })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to retry', description: error.message, variant: 'destructive' })
    },
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ file, subjectId, docType }: { file: File; subjectId: string; docType: string }) =>
      documentApi.upload(file, subjectId, docType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      toast({ title: 'Document uploaded' })
    },
    onError: (error: Error) => {
      toast({ title: 'Upload failed', description: error.message, variant: 'destructive' })
    },
  })
}
