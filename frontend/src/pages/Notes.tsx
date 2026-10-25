import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useNotes, useGenerateNote, useDeleteNote } from '@/hooks/use-notes'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
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
  const { data: notes, isLoading } = useNotes(subjectId)
  const generateNote = useGenerateNote()
  const deleteNote = useDeleteNote()
  const [generateOpen, setGenerateOpen] = useState(false)
  const [generateParams, setGenerateParams] = useState<{ note_type: NoteType; title: string }>({
    note_type: 'summary',
    title: 'Generated Note',
  })

  const handleGenerate = async () => {
    const params: Record<string, string> = {
      note_type: generateParams.note_type,
      title: generateParams.title,
    }
    if (subjectId) params.subject_id = subjectId
    await generateNote.mutateAsync(params)
    setGenerateOpen(false)
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
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">
          {subjectId ? 'Notes' : 'All Notes'}
        </h2>
        <Button onClick={() => setGenerateOpen(true)}>
          <Sparkles className="mr-2 h-4 w-4" />
          Generate Note
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
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
            <Button onClick={() => setGenerateOpen(true)}>
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
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base flex-1">{note.title}</CardTitle>
                  <Badge className={noteTypeColor(note.note_type as NoteType)}>{noteTypeLabel(note.note_type as NoteType)}</Badge>
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
            <Button onClick={handleGenerate} disabled={generateNote.isPending}>
              {generateNote.isPending ? 'Generating...' : 'Generate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
