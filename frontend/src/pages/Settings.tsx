import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, LogOut, Save, Trash2, User } from 'lucide-react'

import { useAuth } from '@/hooks/use-auth'
import { useDeleteAccount, useProfile, useUpdateProfile } from '@/hooks/use-profile'
import { toast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
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

export default function Settings() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const { data: profile, isLoading, isError, error, refetch } = useProfile()
  const updateProfile = useUpdateProfile()
  const deleteAccount = useDeleteAccount()

  const [fullName, setFullName] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    setFullName(profile?.full_name ?? '')
  }, [profile?.full_name])

  const trimmedName = fullName.trim()
  const canSave =
    !!profile &&
    trimmedName.length > 0 &&
    trimmedName.length <= 255 &&
    trimmedName !== (profile.full_name ?? '')

  const handleSave = async () => {
    setSaveError(null)
    try {
      await updateProfile.mutateAsync(trimmedName)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not update profile')
    }
  }

  const handleSignOut = async () => {
    setLoggingOut(true)
    try {
      await signOut()
      navigate('/login', { replace: true })
    } catch (err) {
      toast({
        title: 'Sign out failed',
        description: err instanceof Error ? err.message : 'Please try again.',
        variant: 'destructive',
      })
    } finally {
      setLoggingOut(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (confirmText !== 'DELETE') return
    setDeleteError(null)
    try {
      await deleteAccount.mutateAsync()
      try {
        await signOut()
      } catch {
        // The auth user may already be gone; still leave the protected app.
      }
      toast({ title: 'Account deleted' })
      navigate('/login', { replace: true })
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : 'Account deletion failed'
      )
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-6">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle>Could not load settings</CardTitle>
            <CardDescription>
              {error instanceof Error ? error.message : 'Please try again.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => refetch()}>Try again</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage your profile and account.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Profile
          </CardTitle>
          <CardDescription>Your email address cannot be changed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="settings-email">Email</Label>
            <Input
              id="settings-email"
              type="email"
              value={profile?.email ?? user?.email ?? ''}
              readOnly
              disabled
              aria-describedby="settings-email-help"
            />
            <p id="settings-email-help" className="text-xs text-muted-foreground">
              Contact support if you need to change your email.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="settings-full-name">Full name</Label>
            <Input
              id="settings-full-name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              maxLength={255}
              autoComplete="name"
              aria-describedby={saveError ? 'settings-name-error' : undefined}
            />
            {saveError && (
              <p id="settings-name-error" role="alert" className="text-sm text-destructive">
                {saveError}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={handleSave}
              disabled={!canSave || updateProfile.isPending}
            >
              {updateProfile.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              {updateProfile.isPending ? 'Saving...' : 'Save changes'}
            </Button>
            <Button
              variant="outline"
              onClick={handleSignOut}
              disabled={loggingOut}
              aria-label="Log out"
            >
              <LogOut className="mr-2 h-4 w-4" />
              {loggingOut ? 'Logging out...' : 'Log out'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive">Delete account</CardTitle>
          <CardDescription>
            This permanently deletes your profile, subjects, documents, notes,
            quizzes, planner data, and stored files.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="mr-2 h-4 w-4" />
            Delete my account and data
          </Button>
        </CardContent>
      </Card>

      <AlertDialog
        open={deleteOpen}
        onOpenChange={(open) => {
          if (deleteAccount.isPending) return
          setDeleteOpen(open)
          if (!open) {
            setConfirmText('')
            setDeleteError(null)
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete your account?</AlertDialogTitle>
            <AlertDialogDescription>
              This cannot be undone. Type DELETE to confirm that you want to
              permanently remove your account and all associated data.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-2">
            <Label htmlFor="delete-confirm">Confirmation</Label>
            <Input
              id="delete-confirm"
              value={confirmText}
              onChange={(event) => setConfirmText(event.target.value)}
              placeholder="DELETE"
              autoComplete="off"
              disabled={deleteAccount.isPending}
              aria-describedby="delete-confirm-help"
            />
            <p id="delete-confirm-help" className="text-xs text-muted-foreground">
              Enter DELETE in uppercase.
            </p>
            {deleteError && (
              <p role="alert" className="text-sm text-destructive">
                {deleteError}
              </p>
            )}
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteAccount.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={confirmText !== 'DELETE' || deleteAccount.isPending}
              onClick={handleDeleteAccount}
            >
              {deleteAccount.isPending ? 'Deleting...' : 'Delete account'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
