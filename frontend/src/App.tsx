import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/toast'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import Layout from '@/layouts/MainLayout'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import Subjects from '@/pages/Subjects'
import SubjectDetail from '@/pages/SubjectDetail'
import Documents from '@/pages/Documents'
import DocumentDetail from '@/pages/DocumentDetail'
import Tutor from '@/pages/Tutor'
import TutorSession from '@/pages/TutorSession'
import Notes from '@/pages/Notes'
import NotesDetail from '@/pages/NotesDetail'
import Quizzes from '@/pages/Quizzes'
import QuizTake from '@/pages/QuizTake'
import QuizResults from '@/pages/QuizResults'
import Planner from '@/pages/Planner'
import PlanDetail from '@/pages/PlanDetail'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="subjects" element={<Subjects />} />
              <Route path="subjects/:id" element={<SubjectDetail />} />
              <Route path="documents" element={<Documents />} />
              <Route path="documents/:id" element={<DocumentDetail />} />
              <Route path="tutor" element={<Tutor />} />
              <Route path="tutor/:sessionId" element={<TutorSession />} />
              <Route path="notes" element={<Notes />} />
              <Route path="notes/:id" element={<NotesDetail />} />
              <Route path="quizzes" element={<Quizzes />} />
              <Route path="quizzes/:id" element={<QuizTake />} />
              <Route path="quizzes/:id/results" element={<QuizResults />} />
              <Route path="planner" element={<Planner />} />
              <Route path="planner/:id" element={<PlanDetail />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
