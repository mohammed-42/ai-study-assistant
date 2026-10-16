import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentApi } from '@/services/api'
import { DocumentPage, DocumentChunk } from '@/types'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertCircle, FileText, Upload, Pencil, Check, X } from 'lucide-react'
import { useState } from 'react'

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editingPageId, setEditingPageId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const { data: document, isLoading } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => documentApi.get(id!),
    enabled: !!id,
  })

  const { data: pages } = useQuery({
    queryKey: ['documents', id, 'pages'],
    queryFn: () => documentApi.getPages(id!),
    enabled: !!id,
  })

  const { data: chunks } = useQuery({
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
  })

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

  if (!document) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-muted-foreground" />
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{document.name}</h1>
          <p className="text-sm text-muted-foreground">
            Page {document.page_count} • Uploaded {new Date(document.created_at).toLocaleDateString()}
          </p>
        </div>
        <Badge className={statusColors[document.status]}>
          {document.status.toUpperCase()}
        </Badge>
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
          {pages && pages.length > 0 ? (
            <div className="mt-2 space-y-3">
              {pages.map((page: DocumentPage) => (
                <div key={page.id} className="rounded-md border bg-card p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Page {page.page_number}</span>
                    <div className="flex gap-2">
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
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() => startEdit(page)}
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  {editingPageId === page.id ? (
                    <div className="mt-2 space-y-2">
                      <textarea
                        className="w-full min-h-[100px] rounded-md border p-2 text-sm"
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
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
                    <p className="mt-1 text-sm text-muted-foreground line-clamp-3">
                      {page.text || 'No text extracted'}
                    </p>
                  )}
                </div>
              ))}
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
          {chunks && chunks.length > 0 ? (
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
    </div>
  )
}
