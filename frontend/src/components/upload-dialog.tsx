import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, documentApi } from '@/services/api'
import { useUploadDocument } from '@/hooks/use-documents'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArrowDown, ArrowUp, FileText, Loader2, Upload, X } from 'lucide-react'
import type { AppDocument, DocumentStatus, Subject } from '@/types'

const MAX_FILE_SIZE = 50 * 1024 * 1024
const MAX_IMAGES = 20
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

const isPdf = (file: File) =>
  file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

const isImage = (file: File) => {
  const name = file.name.toLowerCase()
  return (
    ['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ||
    IMAGE_EXTENSIONS.some((extension) => name.endsWith(extension))
  )
}

const isFinalStatus = (status?: DocumentStatus) =>
  status === 'ready' || status === 'failed'

const formatBytes = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(1)} MB`

function validateSelection(files: File[]): string | null {
  if (files.length === 0) return 'Choose a PDF or at least 2 images.'

  const unsupported = files.find((file) => !isPdf(file) && !isImage(file))
  if (unsupported) {
    return `${unsupported.name} is not supported. Use PDF, JPG, PNG, or WebP.`
  }

  const pdfs = files.filter(isPdf)
  const images = files.filter(isImage)

  if (pdfs.length > 0) {
    if (files.length !== 1) return 'Select one PDF or 2-20 images, not both.'
    if (files[0]!.size > MAX_FILE_SIZE) {
      return `PDF files can be up to ${formatBytes(MAX_FILE_SIZE)}.`
    }
    return null
  }

  if (images.length < 2) return 'Select at least 2 images, or one PDF.'
  if (images.length > MAX_IMAGES) {
    return `You can upload at most ${MAX_IMAGES} images.`
  }

  const oversized = images.find((file) => file.size > MAX_FILE_SIZE)
  if (oversized) {
    return `${oversized.name} is larger than ${formatBytes(MAX_FILE_SIZE)}.`
  }

  return null
}

interface UploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  preselectedSubjectId?: string
}

export function UploadDialog({ open, onOpenChange, preselectedSubjectId }: UploadDialogProps) {
  const queryClient = useQueryClient()
  const uploadMutation = useUploadDocument()
  const [subjectId, setSubjectId] = useState(preselectedSubjectId ?? '')
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [uploaded, setUploaded] = useState<AppDocument | null>(null)
  const finalizedId = useRef<string | null>(null)

  const { data: subjects, isLoading: subjectsLoading } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiFetch<Subject[]>('/subjects/'),
    enabled: open,
  })

  const { data: polled } = useQuery({
    queryKey: ['documents', uploaded?.id],
    queryFn: () => documentApi.get(uploaded!.id),
    enabled: !!uploaded && !isFinalStatus(uploaded.status),
    refetchInterval: (query) =>
      isFinalStatus(query.state.data?.status) ? false : 2000,
  })

  const latest = polled ?? uploaded
  const uploading = uploadMutation.isPending
  const processing = !!latest && !isFinalStatus(latest.status)
  const final = !!latest && isFinalStatus(latest.status)

  useEffect(() => {
    if (!open) return
    setSubjectId(preselectedSubjectId ?? '')
    setFiles([])
    setError(null)
    setUploaded(null)
    finalizedId.current = null
  }, [open, preselectedSubjectId])

  useEffect(() => {
    if (!latest || !isFinalStatus(latest.status)) return
    if (finalizedId.current === latest.id) return
    finalizedId.current = latest.id
    queryClient.invalidateQueries({ queryKey: ['documents'] })
  }, [latest, queryClient])

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? [])
    const validationError = validateSelection(selected)
    if (uploadMutation.isError) uploadMutation.reset()
    setFiles(validationError ? [] : selected)
    setError(validationError)
    event.target.value = ''
  }

  const resetUpload = () => {
    setFiles([])
    setUploaded(null)
    setError(null)
    uploadMutation.reset()
    finalizedId.current = null
  }

  const moveFile = (index: number, direction: -1 | 1) => {
    setFiles((current) => {
      const target = index + direction
      const item = current[index]
      const swap = current[target]
      if (!item || !swap || target < 0 || target >= current.length) return current
      const next = [...current]
      next[index] = swap
      next[target] = item
      return next
    })
  }

  const removeFile = (index: number) => {
    const next = files.filter((_, itemIndex) => itemIndex !== index)
    setFiles(next)
    setError(next.length === 0 ? null : validateSelection(next))
  }

  const handleUpload = () => {
    if (!subjectId) {
      setError('Choose a subject before uploading.')
      return
    }

    const validationError = validateSelection(files)
    if (validationError) {
      setError(validationError)
      return
    }

    const docType = files.length === 1 ? 'pdf' : 'multi_image'
    setError(null)
    uploadMutation.mutate(
      { files, subjectId, docType },
      { onSuccess: (document) => setUploaded(document) }
    )
  }

  const displayError = error ?? uploadMutation.error?.message ?? null
  const hasNoSubjects = !subjectsLoading && subjects?.length === 0

  const statusLabel = (status: DocumentStatus) => {
    if (status === 'uploaded') return 'Queued'
    if (status === 'processing') return 'Processing'
    if (status === 'ready') return 'Ready'
    return 'Failed'
  }

  const statusClass = (status: DocumentStatus) => {
    if (status === 'uploaded') return 'bg-blue-100 text-blue-800'
    if (status === 'processing') return 'bg-yellow-100 text-yellow-800'
    if (status === 'ready') return 'bg-green-100 text-green-800'
    return 'bg-red-100 text-red-800'
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Upload document</DialogTitle>
          <DialogDescription>
            Upload one PDF or 2-20 page images. Images can be reordered before uploading.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="upload-subject">Subject</Label>
            <Select
              value={subjectId}
              onValueChange={(value) => {
                setSubjectId(value ?? '')
                setError(null)
                if (uploadMutation.isError) uploadMutation.reset()
              }}
              items={subjects?.map((subject) => ({ value: subject.id, label: subject.name }))}
              disabled={uploading || processing}
            >
              <SelectTrigger id="upload-subject" className="w-full" aria-required="true">
                <SelectValue placeholder={subjectsLoading ? 'Loading subjects...' : 'Select a subject'} />
              </SelectTrigger>
              <SelectContent>
                {subjects?.map((subject) => (
                  <SelectItem key={subject.id} value={subject.id}>
                    {subject.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasNoSubjects && (
              <p className="text-sm text-muted-foreground">
                You need a subject first.{' '}
                <Link
                  to="/subjects"
                  className="underline underline-offset-4 hover:text-foreground"
                  onClick={() => onOpenChange(false)}
                >
                  Create a subject
                </Link>
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="upload-files">Files</Label>
            <Input
              id="upload-files"
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
              onChange={handleFileChange}
              disabled={uploading || processing || !!latest}
              aria-describedby="upload-files-help upload-error"
              aria-invalid={!!error}
            />
            <p id="upload-files-help" className="text-sm text-muted-foreground">
              One PDF, or 2-20 JPG, PNG, or WebP images. Maximum 50 MB per file.
            </p>
          </div>

          {files.length > 0 && (
            <div className="space-y-2" aria-label="Selected files">
              <p className="text-sm font-medium">Upload order</p>
              <ol className="space-y-2">
                {files.map((file, index) => (
                  <li
                    key={`${file.name}-${file.size}-${file.lastModified}`}
                    className="flex items-center gap-2 rounded-lg border p-2"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                      {index + 1}
                    </span>
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{file.name}</span>
                      <span className="block text-xs text-muted-foreground">{formatBytes(file.size)}</span>
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => moveFile(index, -1)}
                      disabled={index === 0 || uploading || processing}
                      aria-label={`Move ${file.name} earlier`}
                    >
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => moveFile(index, 1)}
                      disabled={index === files.length - 1 || uploading || processing}
                      aria-label={`Move ${file.name} later`}
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => removeFile(index)}
                      disabled={uploading || processing}
                      aria-label={`Remove ${file.name}`}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {displayError && (
            <p id="upload-error" role="alert" className="text-sm text-destructive">
              {displayError}
            </p>
          )}

          {latest && (
            <div className="space-y-3 rounded-lg border p-4" aria-live="polite">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">Upload status</p>
                <Badge className={statusClass(latest.status)}>
                  {statusLabel(latest.status)}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {latest.name} · {latest.page_count} {latest.page_count === 1 ? 'page' : 'pages'}
              </p>
              {processing && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Processing document. The list updates automatically.
                </p>
              )}
              {latest.status === 'ready' && (
                <p className="text-sm text-green-700">Document uploaded and ready.</p>
              )}
              {latest.status === 'failed' && (
                <p role="alert" className="text-sm text-destructive">
                  {latest.error_message || 'Processing failed. Please try again.'}
                </p>
              )}
            </div>
          )}

          <div
            role="note"
            aria-label="Upload privacy and OCR notice"
            className="space-y-1 text-sm text-muted-foreground"
          >
            <p>Handwriting recognition is not 100% accurate. Review the text after upload.</p>
            <p>Uploaded files and page images are sent to Google Gemini for processing.</p>
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={uploading}
          >
            {latest ? 'Close' : 'Cancel'}
          </Button>
          {final ? (
            <Button type="button" onClick={resetUpload}>
              <Upload className="mr-2 h-4 w-4" />
              Upload another
            </Button>
          ) : (
            <Button
              type="button"
              onClick={handleUpload}
              disabled={uploading || processing || !!latest || !subjectId || files.length === 0}
            >
              {uploading || processing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {uploading ? 'Uploading...' : 'Processing...'}
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
