import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentApi } from '@/services/api'
import { useToast } from '@/hooks/use-toast'

const QUERY_KEY = ['documents']

export function useDocuments(
  subjectId?: string,
  pagination?: { limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: [...QUERY_KEY, subjectId ?? null, pagination?.limit ?? null, pagination?.offset ?? null],
    queryFn: () => documentApi.list(subjectId, pagination),
    refetchInterval: (query) => {
      const documents = query.state.data
      return documents?.some(
        (document) => document.status === 'uploaded' || document.status === 'processing'
      )
        ? 3000
        : false
    },
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

export function useRerunPageOcr(documentId?: string) {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ pageId }: { pageId: string }) =>
      documentApi.rerunPageOcr(documentId!, pageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...QUERY_KEY, documentId, 'pages'] })
      queryClient.invalidateQueries({ queryKey: [...QUERY_KEY, documentId, 'chunks'] })
      toast({ title: 'Page re-read with OCR' })
    },
    onError: (error: Error) => {
      toast({ title: 'Re-read failed', description: error.message, variant: 'destructive' })
    },
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ files, subjectId, docType }: { files: File[]; subjectId: string; docType: string }) =>
      documentApi.upload(files, subjectId, docType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      toast({ title: 'Document uploaded' })
    },
    onError: (error: Error) => {
      toast({ title: 'Upload failed', description: error.message, variant: 'destructive' })
    },
  })
}
