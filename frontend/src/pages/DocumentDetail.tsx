import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentApi } from '@/services/api'
import { DocumentPage, DocumentChunk } from '@/types'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/error-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, Upload, Pencil, Check, X, RefreshCw, Trash2, Maximize2 } from 'lucide-react'
import { useState } from 'react'
import { useDeleteDocument, useRerunPageOcr, useRetryDocument } from '@/hooks/use-documents'
import { toast } from '@/hooks/use-toast'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

function PageImage({ documentId, page }: { documentId: string; page: DocumentPage }) {
  const { data, isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: ['documents', documentId, 'pages', page.id, 'image-url'],
    queryFn: () => documentApi.getPageImageUrl(documentId, page.id),
    enabled: !!page.page_image_key,
  })

  if (isLoading || (isFetching && !data)) {
    return <Skeleton className="aspect-[3/4] w-full" />
  }

  if (isError || !data?.url) {
    return (
      <ErrorState
        title="Could not load page image"
        message={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
        className="min-h-48 py-6"
      />
    )
  }

  return (
    <a
      href={data.url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open page ${page.page_number} image full size`}
      className="group relative block overflow-hidden rounded-md border bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <img
        src={data.url}
        alt={`Scanned page ${page.page_number}`}
        className="h-auto w-full object-contain"
        loading="lazy"
      />
      <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md bg-background/90 px-2 py-1 text-xs shadow-sm">
        <Maximize2 className="h-3 w-3" />
        Full size
      </span>
    </a>
  )
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editingPageId, setEditingPageId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)

  const {
    data: document,
    isLoading,
    isError: documentError,
    error: documentQueryError,
    refetch: refetchDocument,
  } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => documentApi.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'uploaded' || status === 'processing' ? 3000 : false
    },
  })

  const {
    data: pages,
    isError: pagesError,
    error: pagesQueryError,
    refetch: refetchPages,
  } = useQuery({
    queryKey: ['documents', id, 'pages'],
    queryFn: () => documentApi.getPages(id!),
    enabled: !!id,
  })

  const {
    data: chunks,
    isError: chunksError,
    error: chunksQueryError,
    refetch: refetchChunks,
  } = useQuery({
    queryKey: ['documents', id, 'chunks'],
    queryFn: () => documentApi.getChunks(id!),
    enabled: !!id && document?.status === 'ready',
  })

  const editPageMutation = useMutation({
    mutationFn: ({ pageId, text }: { pageId: string; text: string }) =>
      documentApi.editPage(id!, pageId, { text, user_edited: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', id, 'pages'] })
      queryClient.invalidateQueries({ queryKey: ['documents', id, 'chunks'] })
      setEditingPageId(null)
      setEditText('')
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to save page', description: error.message, variant: 'destructive' })
    },
  })

  const rerunOcrMutation = useRerunPageOcr(id)
  const deleteMutation = useDeleteDocument()
  const retryMutation = useRetryDocument()

  const rerunOcr = (page: DocumentPage) => {
    const confirmed = window.confirm(
      'This replaces the current text, including your edits.'
    )
    if (!confirmed) return
    rerunOcrMutation.mutate({ pageId: page.id })
  }

  const startEdit = (page: DocumentPage) => {
    setEditingPageId(page.id)
    setEditText(page.text)
  }

  const cancelEdit = () => {
    setEditingPageId(null)
    setEditText('')
  }

  const saveEdit = () => {
    if (editingPageId && editText !== null) {
      editPageMutation.mutate({ pageId: editingPageId, text: editText })
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-32" />
      </div>
    )
  }

  if (documentError) {
    return (
      <ErrorState
        title="Failed to load document"
        message={documentQueryError instanceof Error ? documentQueryError.message : undefined}
        onRetry={() => refetchDocument()}
      />
    )
  }

  if (!document) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="mt-4 text-muted-foreground">Document not found</p>
        <Button onClick={() => navigate('/documents')} className="mt-4">
          Back to Documents
        </Button>
      </div>
    )
  }

  const statusColors = {
    uploaded: 'bg-blue-100 text-blue-800',
    processing: 'bg-yellow-100 text-yellow-800',
    ready: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-bold tracking-tight">{document.name}</h1>
          <p className="text-sm text-muted-foreground">
            Page {document.page_count} • Uploaded {new Date(document.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge className={statusColors[document.status]}>
            {document.status.toUpperCase()}
          </Badge>
          {document.status === 'failed' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => retryMutation.mutate(document.id)}
              disabled={retryMutation.isPending}
              aria-label={`Retry processing ${document.name}`}
            >
              <RefreshCw
                className={`mr-1 h-4 w-4 ${retryMutation.isPending ? 'animate-spin' : ''}`}
              />
              Retry
            </Button>
          )}
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setDeleteOpen(true)}
            aria-label={`Delete ${document.name}`}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {document.error_message && (
        <div className="rounded-md bg-destructive/15 p-4">
          <p className="text-sm text-destructive">{document.error_message}</p>
        </div>
      )}

      <div className="grid gap-4">
        <div className="rounded-lg border p-4">
          <h2 className="flex items-center gap-2 font-semibold">
            <FileText className="h-5 w-5" />
            Pages
          </h2>
          {pagesError ? (
            <ErrorState
              title="Failed to load pages"
              message={pagesQueryError instanceof Error ? pagesQueryError.message : undefined}
              onRetry={() => refetchPages()}
              className="mt-2 py-6"
            />
          ) : pages && pages.length > 0 ? (
            <div className="mt-2 space-y-3">
              {pages.map((page: DocumentPage) => {
                const isRerunning =
                  rerunOcrMutation.isPending &&
                  rerunOcrMutation.variables?.pageId === page.id

                const controls = (
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {page.needs_review && (
                      <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
                        Needs Review
                      </Badge>
                    )}
                    {page.source === 'ocr' && (
                      <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                        OCR
                      </Badge>
                    )}
                    {page.user_edited && (
                      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                        Edited
                      </Badge>
                    )}
                    {page.page_image_key && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() => rerunOcr(page)}
                        disabled={isRerunning}
                        aria-label={`Re-read page ${page.page_number} with OCR`}
                      >
                        <RefreshCw
                          className={`h-3 w-3 ${isRerunning ? 'animate-spin' : ''}`}
                        />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => startEdit(page)}
                      aria-label={`Edit text for page ${page.page_number}`}
                    >
                      <Pencil className="h-3 w-3" />
                    </Button>
                  </div>
                )

                const textContent = (
                  <>
                    {rerunOcrMutation.isError &&
                      rerunOcrMutation.variables?.pageId === page.id && (
                        <p className="text-sm text-destructive">
                          {rerunOcrMutation.error.message}
                        </p>
                      )}
                    {editingPageId === page.id ? (
                      <div className="space-y-2">
                        <textarea
                          className="w-full min-h-[100px] rounded-md border p-2 text-sm"
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          aria-label={`OCR text for page ${page.page_number}`}
                        />
                        <div className="flex gap-2">
                          <Button size="sm" onClick={saveEdit} disabled={editPageMutation.isPending}>
                            <Check className="h-3 w-3 mr-1" /> Save
                          </Button>
                          <Button size="sm" variant="outline" onClick={cancelEdit}>
                            <X className="h-3 w-3 mr-1" /> Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground line-clamp-3">
                        {page.text || 'No text extracted'}
                      </p>
                    )}
                  </>
                )

                return (
                  <div key={page.id} className="rounded-md border bg-card p-3">
                    {page.page_image_key ? (
                      <div className="grid gap-4 md:grid-cols-2">
                        <PageImage documentId={id!} page={page} />
                        <div className="min-w-0 space-y-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-sm font-medium">Page {page.page_number}</span>
                            {controls}
                          </div>
                          {textContent}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-medium">Page {page.page_number}</span>
                          {controls}
                        </div>
                        <div className="mt-2">{textContent}</div>
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              {document.status === 'ready' ? 'No pages extracted yet' : 'Pages will appear when processing completes'}
            </p>
          )}
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="flex items-center gap-2 font-semibold">
            <Upload className="h-5 w-5" />
            Chunks ({chunks?.length || 0})
          </h2>
          {chunksError ? (
            <ErrorState
              title="Failed to load chunks"
              message={chunksQueryError instanceof Error ? chunksQueryError.message : undefined}
              onRetry={() => refetchChunks()}
              className="mt-2 py-6"
            />
          ) : chunks && chunks.length > 0 ? (
            <div className="mt-2 space-y-2">
              {chunks.slice(0, 5).map((chunk: DocumentChunk) => (
                <div key={chunk.id} className="rounded-md bg-muted p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      Pages {chunk.page_start}–{chunk.page_end}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ~{chunk.token_count} tokens
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                    {chunk.content}
                  </p>
                </div>
              ))}
              {chunks.length > 5 && (
                <p className="text-sm text-muted-foreground">
                  +{chunks.length - 5} more chunks
                </p>
              )}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              {document.status === 'ready' ? 'No chunks generated yet' : 'Chunks will appear when processing completes'}
            </p>
          )}
        </div>
      </div>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes "{document.name}", including its pages and chunks.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() =>
                deleteMutation.mutate(document.id, {
                  onSuccess: () => {
                    setDeleteOpen(false)
                    navigate('/documents')
                  },
                })
              }
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
