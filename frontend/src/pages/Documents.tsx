import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useDeleteDocument, useDocuments, useRetryDocument } from '@/hooks/use-documents'
import { useSubjects } from '@/hooks/use-subjects'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/error-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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
import { UploadDialog } from '@/components/upload-dialog'
import type { AppDocument } from '@/types'
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-react'

const PAGE_SIZE = 10

function UploadNotice() {
  return (
    <div
      role="note"
      aria-label="Upload privacy and OCR notice"
      className="space-y-1 text-sm text-muted-foreground"
    >
      <p>Handwriting recognition is not 100% accurate. Review the text after upload.</p>
      <p>Uploaded files and page images are sent to Google Gemini for processing.</p>
    </div>
  )
}

export default function Documents() {
  const navigate = useNavigate()
  const [uploadOpen, setUploadOpen] = useState(false)
  const [subjectId, setSubjectId] = useState('')
  const [page, setPage] = useState(0)
  const [pendingDelete, setPendingDelete] = useState<AppDocument | null>(null)

  const { data: subjects } = useSubjects()
  const {
    data: documents,
    isLoading,
    isError,
    error,
    isFetching,
    refetch,
  } = useDocuments(subjectId || undefined, {
    limit: PAGE_SIZE + 1,
    offset: page * PAGE_SIZE,
  })
  const deleteMutation = useDeleteDocument()
  const retryMutation = useRetryDocument()

  const pageDocuments = documents?.slice(0, PAGE_SIZE) ?? []
  const hasNextPage = (documents?.length ?? 0) > PAGE_SIZE
  const hasPreviousPage = page > 0

  useEffect(() => {
    if (!isLoading && !isError && hasPreviousPage && pageDocuments.length === 0) {
      setPage((current) => Math.max(0, current - 1))
    }
  }, [hasPreviousPage, isError, isLoading, pageDocuments.length])

  const statusColors = {
    uploaded: 'bg-blue-100 text-blue-800',
    processing: 'bg-yellow-100 text-yellow-800',
    ready: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Documents</h1>
        <Button onClick={() => setUploadOpen(true)}>
          <Upload className="mr-2 h-4 w-4" />
          Upload
        </Button>
      </div>

      <UploadNotice />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Label htmlFor="subject-filter" className="shrink-0">
          Subject
        </Label>
        <select
          id="subject-filter"
          aria-label="Filter documents by subject"
          value={subjectId}
          onChange={(event) => {
            setSubjectId(event.target.value)
            setPage(0)
          }}
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <option value="">All subjects</option>
          {subjects?.map((subject) => (
            <option key={subject.id} value={subject.id}>
              {subject.name}
            </option>
          ))}
        </select>
      </div>

      {isError ? (
        <ErrorState
          title="Failed to load documents"
          message={error instanceof Error ? error.message : undefined}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : pageDocuments.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Upload className="h-12 w-12 text-muted-foreground" />
          <h2 className="mt-4 text-xl font-semibold">
            {subjectId ? 'No documents for this subject' : 'No documents yet'}
          </h2>
          <p className="mt-2 text-muted-foreground">
            {subjectId
              ? 'Upload a document or choose All subjects to see everything.'
              : 'Upload your first PDF or images to get started'}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button onClick={() => setUploadOpen(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Upload Document
            </Button>
            {subjectId && (
              <Button variant="outline" onClick={() => setSubjectId('')}>
                Show all subjects
              </Button>
            )}
          </div>
        </div>
      ) : (
        <Card aria-busy={isFetching}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Your Documents
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Table aria-label="Your documents" className="min-w-[760px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Pages</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageDocuments.map((doc) => {
                  const isRetrying =
                    retryMutation.isPending && retryMutation.variables === doc.id
                  const isDeleting =
                    deleteMutation.isPending && deleteMutation.variables === doc.id

                  return (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium">{doc.name}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge className={statusColors[doc.status]}>
                            {doc.status.toUpperCase()}
                          </Badge>
                          {doc.status === 'failed' && doc.error_message && (
                            <span
                              className="max-w-[320px] truncate text-xs text-destructive"
                              title={doc.error_message}
                            >
                              {doc.error_message}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{doc.page_count}</TableCell>
                      <TableCell>{new Date(doc.created_at).toLocaleDateString()}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {doc.status === 'failed' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => retryMutation.mutate(doc.id)}
                              disabled={isRetrying}
                              aria-label={`Retry processing ${doc.name}`}
                            >
                              <RefreshCw
                                className={`mr-1 h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`}
                              />
                              Retry
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/documents/${doc.id}`)}
                            aria-label={`View ${doc.name}`}
                          >
                            View
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setPendingDelete(doc)}
                            disabled={isDeleting}
                            aria-label={`Delete ${doc.name}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>

            <nav
              aria-label="Document pagination"
              className="flex items-center justify-between gap-3"
            >
              <p className="text-sm text-muted-foreground">Page {page + 1}</p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((current) => Math.max(0, current - 1))}
                  disabled={!hasPreviousPage || isFetching}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!hasNextPage || isFetching}
                  aria-label="Next page"
                >
                  Next
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            </nav>
          </CardContent>
        </Card>
      )}

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes {pendingDelete?.name ? `"${pendingDelete.name}"` : 'this document'},
              including its pages and chunks.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (!pendingDelete) return
                deleteMutation.mutate(pendingDelete.id, {
                  onSuccess: () => setPendingDelete(null),
                })
              }}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
