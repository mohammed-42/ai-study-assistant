
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useDocuments } from '@/hooks/use-documents'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { UploadDialog } from '@/components/upload-dialog'
import { Upload, FileText } from 'lucide-react'

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
  const { data: documents, isLoading } = useDocuments()

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

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : !documents || documents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Upload className="h-12 w-12 text-muted-foreground" />
          <h2 className="mt-4 text-xl font-semibold">No documents yet</h2>
          <p className="mt-2 text-muted-foreground">Upload your first PDF or images to get started</p>
          <Button onClick={() => setUploadOpen(true)} className="mt-4">
            <Upload className="mr-2 h-4 w-4" />
            Upload Document
          </Button>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Your Documents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table aria-label="Your documents" className="min-w-[640px]">
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
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">{doc.name}</TableCell>
                    <TableCell>
                      <Badge className={statusColors[doc.status]}>
                        {doc.status.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>{doc.page_count}</TableCell>
                    <TableCell>
                      {new Date(doc.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/documents/${doc.id}`)}
                      >
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  )
}
