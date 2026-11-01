import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useNotes, useGenerateNote, useDeleteNote } from '@/hooks/use-notes'
import { useDocuments } from '@/hooks/use-documents'
import { useSubjects } from '@/hooks/use-subjects'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/error-state'
import { Badge } from '@/components/ui/badge'
import { Plus, Sparkles, Trash2, Pencil } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Note, NoteType } from '@/types'

interface NotesProps {
  subjectId?: string
}

export default function Notes({ subjectId }: NotesProps) {
  const navigate = useNavigate()
  const { data: notes, isLoading, isError, error, refetch } = useNotes(subjectId)
  const generateNote = useGenerateNote()
  const deleteNote = useDeleteNote()
  const [generateOpen, setGenerateOpen] = useState(false)
  const [selectedSubjectId, setSelectedSubjectId] = useState(subjectId ?? '')
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const { data: subjects, isLoading: subjectsLoading } = useSubjects(generateOpen)
  const { data: documents, isLoading: documentsLoading } = useDocuments(selectedSubjectId || undefined)
  const readyDocuments = (documents ?? []).filter((document) => document.status === 'ready')
  const hasNoSubjects = !subjectsLoading && (subjects?.length ?? 0) === 0
  const hasNoReadyDocuments =
    !!selectedSubjectId && !documentsLoading && readyDocuments.length === 0
  const [generateParams, setGenerateParams] = useState<{ note_type: NoteType; title: string }>({
    note_type: 'summary',
    title: 'Generated Note',
  })

  const handleGenerate = async () => {
    const params: {
      subject_id?: string
      document_id?: string
      note_type: NoteType
      title: string
    } = {
      note_type: generateParams.note_type,
      title: generateParams.title,
    }
    if (selectedSubjectId) params.subject_id = selectedSubjectId
    if (selectedDocumentId) params.document_id = selectedDocumentId
    try {
      await generateNote.mutateAsync(params)
      setGenerateOpen(false)
    } catch {
      // The mutation hook shows the readable error toast.
    }
  }

  const noteTypeLabel = (t: NoteType) => {
    const map: Record<NoteType, string> = { summary: 'Summary', key_concepts: 'Key Concepts', definitions: 'Definitions', revision: 'Revision' }
    return map[t] || t
  }

  const noteTypeColor = (t: NoteType) => {
    const map: Record<NoteType, string> = { summary: 'bg-blue-100 text-blue-700', key_concepts: 'bg-green-100 text-green-700', definitions: 'bg-purple-100 text-purple-700', revision: 'bg-orange-100 text-orange-700' }
    return map[t] || 'bg-gray-100'
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold tracking-tight">
          {subjectId ? 'Notes' : 'All Notes'}
        </h1>
        <Button onClick={() => setGenerateOpen(true)} className="shrink-0">
          <Sparkles className="mr-2 h-4 w-4" />
          Generate Note
        </Button>
      </div>

      {isError ? (
        <ErrorState
          title="Failed to load notes"
          message={error instanceof Error ? error.message : undefined}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : !notes || notes.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No notes yet</CardTitle>
            <CardDescription>
              Generate AI-powered notes from your study materials.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button onClick={() => setGenerateOpen(true)} className="shrink-0">
              <Plus className="mr-2 h-4 w-4" />
              Generate First Note
            </Button>
          </CardFooter>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {notes.map((note: Note) => (
            <Card key={note.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="min-w-0 flex-1 break-words text-base">{note.title}</CardTitle>
                  <Badge className={`shrink-0 ${noteTypeColor(note.note_type as NoteType)}`}>{noteTypeLabel(note.note_type as NoteType)}</Badge>
                </div>
                <CardDescription className="line-clamp-2">
                  {note.content.slice(0, 120)}...
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1">
                <p className="text-xs text-muted-foreground">
                  {new Date(note.created_at).toLocaleDateString()}
                </p>
              </CardContent>
              <CardFooter className="gap-2">
                <Button variant="outline" size="sm" className="flex-1" onClick={() => navigate(`/notes/${note.id}`)}>
                  <Pencil className="mr-1 h-3 w-3" /> View
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete note ${note.title}`}
                  disabled={deleteNote.isPending}
                  onClick={() => {
                    if (confirm(`Delete note "${note.title}"?`)) {
                      deleteNote.mutate(note.id)
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Note</DialogTitle>
            <DialogDescription>
              Create an AI-generated note from your study materials.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="note-subject">Subject</Label>
              <Select
                value={selectedSubjectId}
                onValueChange={(value) => {
                  setSelectedSubjectId(value ?? '')
                  setSelectedDocumentId('')
                }}
                items={subjects?.map((subject) => ({ value: subject.id, label: subject.name }))}
                disabled={generateNote.isPending}
              >
                <SelectTrigger id="note-subject" className="w-full" aria-required="true">
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
                    onClick={() => setGenerateOpen(false)}
                  >
                    Create a subject
                  </Link>
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="note-document">Document (optional)</Label>
              <Select
                value={selectedDocumentId || 'all'}
                onValueChange={(value) => setSelectedDocumentId(value === 'all' ? '' : (value ?? ''))}
                items={[
                  { value: 'all', label: 'All ready documents in subject' },
                  ...readyDocuments.map((document) => ({ value: document.id, label: document.name })),
                ]}
                disabled={generateNote.isPending || !selectedSubjectId || documentsLoading}
              >
                <SelectTrigger id="note-document" className="w-full">
                  <SelectValue placeholder={documentsLoading ? 'Loading documents...' : 'All ready documents in subject'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All ready documents in subject</SelectItem>
                  {readyDocuments.map((document) => (
                    <SelectItem key={document.id} value={document.id}>
                      {document.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {hasNoReadyDocuments && (
                <p className="text-sm text-muted-foreground">
                  No ready documents in this subject.{' '}
                  <Link
                    to={`/subjects/${selectedSubjectId}`}
                    className="underline underline-offset-4 hover:text-foreground"
                    onClick={() => setGenerateOpen(false)}
                  >
                    Upload or check documents
                  </Link>
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="note-type">Note Type</Label>
              <Select value={generateParams.note_type} onValueChange={(v) => setGenerateParams(p => ({ ...p, note_type: v as NoteType }))}>
                <SelectTrigger id="note-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="summary">Summary</SelectItem>
                  <SelectItem value="key_concepts">Key Concepts</SelectItem>
                  <SelectItem value="definitions">Definitions</SelectItem>
                  <SelectItem value="revision">Revision Note</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="note-title">Title</Label>
              <Input
                id="note-title"
                value={generateParams.title}
                onChange={(e) => setGenerateParams(p => ({ ...p, title: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenerateOpen(false)}>Cancel</Button>
            <Button onClick={handleGenerate} disabled={generateNote.isPending || !selectedSubjectId}>
              {generateNote.isPending ? 'Generating...' : 'Generate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
