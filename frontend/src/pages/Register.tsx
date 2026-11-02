import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/hooks/use-auth'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Brain,
  CalendarDays,
  CheckCircle2,
  Eye,
  EyeOff,
  GraduationCap,
  Lock,
  Mail,
  PenLine,
  Sparkles,
  User,
} from 'lucide-react'

const registerSchema = z.object({
  fullName: z.string().min(1, 'Full name is required'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ['confirmPassword'],
})

type RegisterFormData = z.infer<typeof registerSchema>

const features = [
  {
    icon: Brain,
    title: 'AI tutor on demand',
    description: 'Ask questions and get answers grounded in your own material.',
  },
  {
    icon: Sparkles,
    title: 'Instant quizzes',
    description: 'Generate practice questions from any document or note.',
  },
  {
    icon: CalendarDays,
    title: 'Smart study planner',
    description: 'Build a realistic schedule and track every session.',
  },
  {
    icon: PenLine,
    title: 'Organized notes',
    description: 'Keep everything tidy, searchable, and always in sync.',
  },
]

export default function Register() {
  const { signUp, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { fullName: '', email: '', password: '', confirmPassword: '' },
  })

  async function onSubmit(data: RegisterFormData) {
    setError(null)
    setSubmitting(true)
    try {
      await signUp(data.email, data.password, data.fullName)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-background">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-32 h-96 w-96 rounded-full bg-chart-4/20 blur-3xl" />
      </div>

      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-gradient-to-br from-primary via-primary to-primary/80 p-12 text-primary-foreground lg:flex">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
          <div className="absolute -bottom-32 -left-20 h-80 w-80 rounded-full bg-white/10 blur-2xl" />
        </div>

        <div className="relative z-10 flex items-center gap-2 text-lg font-semibold">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 ring-1 ring-white/25 backdrop-blur">
            <GraduationCap className="h-5 w-5" />
          </span>
          Study Assistant
        </div>

        <div className="relative z-10 space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium ring-1 ring-white/20 backdrop-blur">
            <Sparkles className="h-3.5 w-3.5" />
            Everything in one place
          </div>

          <div className="space-y-4">
            <h2 className="text-4xl font-bold leading-tight tracking-tight">
              Your whole semester,
              <br />
              organized.
            </h2>
            <p className="max-w-sm text-sm leading-relaxed text-primary-foreground/80">
              Join students who use Study Assistant to learn faster, stay
              consistent, and walk into every exam prepared.
            </p>
          </div>

          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {features.map(({ icon: Icon, title, description }) => (
              <li key={title} className="flex items-start gap-3">
                <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/15 ring-1 ring-white/20">
                  <Icon className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold">{title}</p>
                  <p className="text-xs leading-relaxed text-primary-foreground/70">
                    {description}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative z-10 flex items-center gap-2 text-xs text-primary-foreground/70">
          <CheckCircle2 className="h-4 w-4" />
          Free to start. No credit card required.
        </div>
      </aside>

      <main className="relative flex w-full flex-col items-center justify-center px-4 py-10 sm:px-8 lg:w-1/2">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center justify-center gap-2 text-lg font-semibold lg:hidden">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
              <GraduationCap className="h-5 w-5" />
            </span>
            Study Assistant
          </div>

          <Card className="w-full border-0 bg-card/90 shadow-2xl shadow-primary/10 ring-1 ring-border backdrop-blur-xl [--card-spacing:1.75rem]">
            <CardHeader>
              <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary ring-1 ring-primary/20">
                <Sparkles className="h-5 w-5" />
              </div>
              <CardTitle className="text-2xl font-bold tracking-tight">
                Create your account
              </CardTitle>
              <CardDescription>
                Start learning smarter in less than a minute.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                  {error && (
                    <div className="flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}
                  <FormField
                    control={form.control}
                    name="fullName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Full name</FormLabel>
                        <div className="relative">
                          <FormControl>
                            <Input
                              placeholder="John Doe"
                              autoComplete="name"
                              className="h-11 pl-10"
                              {...field}
                            />
                          </FormControl>
                          <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email</FormLabel>
                        <div className="relative">
                          <FormControl>
                            <Input
                              placeholder="you@example.com"
                              autoComplete="email"
                              className="h-11 pl-10"
                              {...field}
                              type="email"
                            />
                          </FormControl>
                          <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Password</FormLabel>
                        <div className="relative">
                          <FormControl>
                            <Input
                              placeholder="••••••••"
                              autoComplete="new-password"
                              className="h-11 pl-10 pr-11"
                              {...field}
                              type={showPassword ? 'text' : 'password'}
                            />
                          </FormControl>
                          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                          <button
                            type="button"
                            onClick={() => setShowPassword((value) => !value)}
                            className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground"
                            aria-label={showPassword ? 'Hide password' : 'Show password'}
                          >
                            {showPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Use at least 6 characters.
                        </p>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="confirmPassword"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Confirm password</FormLabel>
                        <div className="relative">
                          <FormControl>
                            <Input
                              placeholder="••••••••"
                              autoComplete="new-password"
                              className="h-11 pl-10 pr-11"
                              {...field}
                              type={showConfirmPassword ? 'text' : 'password'}
                            />
                          </FormControl>
                          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                          <button
                            type="button"
                            onClick={() => setShowConfirmPassword((value) => !value)}
                            className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground"
                            aria-label={
                              showConfirmPassword ? 'Hide password' : 'Show password'
                            }
                          >
                            {showConfirmPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button
                    type="submit"
                    className="group h-11 w-full gap-2 text-sm font-semibold shadow-lg shadow-primary/20"
                    disabled={submitting}
                  >
                    {submitting ? 'Creating account...' : 'Create account'}
                    {!submitting && (
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    )}
                  </Button>
                </form>
              </Form>
              <div className="mt-6 text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link
                  to="/login"
                  className="font-semibold text-primary hover:underline"
                >
                  Sign in
                </Link>
              </div>
            </CardContent>
          </Card>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Join thousands of students studying smarter every day.
          </p>
        </div>
      </main>
    </div>
  )
}
