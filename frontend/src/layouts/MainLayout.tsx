import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/use-auth'
import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import {
  BookOpen,
  LayoutDashboard,
  LogOut,
  Folder,
  MessageSquare,
  PenLine,
  CircleHelp,
  CalendarDays,
  Settings as SettingsIcon,
} from 'lucide-react'

export default function Layout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  const getHeading = () => {
    const p = location.pathname
    if (p === '/') return 'Dashboard'
    if (p === '/tutor') return 'AI Tutor'
    if (p === '/subjects') return 'Subjects'
    if (p.startsWith('/subjects/')) return 'Subject Details'
    if (p === '/notes' || p.startsWith('/notes/')) return 'Notes'
    if (p === '/quizzes' || p.startsWith('/quizzes/')) return 'Quizzes'
    if (p === '/planner' || p.startsWith('/planner/')) return 'Study Planner'
    if (p === '/settings') return 'Settings'
    return 'Study Assistant'
  }

  return (
    <SidebarProvider>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:shadow"
      >
        Skip to main content
      </a>
      <div className="flex h-screen w-full">
        <Sidebar>
          <SidebarHeader className="border-b px-6 py-4">
            <Link to="/" className="flex items-center gap-2 font-semibold">
              <BookOpen className="h-5 w-5 text-primary" />
              <span>Study Assistant</span>
            </Link>
          </SidebarHeader>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Dashboard">
                  <Link to="/" className="flex items-center gap-3">
                    <LayoutDashboard className="h-4 w-4" />
                    <span>Dashboard</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Tutor">
                  <Link to="/tutor" className="flex items-center gap-3">
                    <MessageSquare className="h-4 w-4" />
                    <span>Tutor</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Notes">
                  <Link to="/notes" className="flex items-center gap-3">
                    <PenLine className="h-4 w-4" />
                    <span>Notes</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Quizzes">
                  <Link to="/quizzes" className="flex items-center gap-3">
                    <CircleHelp className="h-4 w-4" />
                    <span>Quizzes</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Subjects">
                  <Link to="/subjects" className="flex items-center gap-3">
                    <Folder className="h-4 w-4" />
                    <span>Subjects</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Study Planner">
                  <Link to="/planner" className="flex items-center gap-3">
                    <CalendarDays className="h-4 w-4" />
                    <span>Planner</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Settings">
                  <Link to="/settings" className="flex items-center gap-3">
                    <SettingsIcon className="h-4 w-4" />
                    <span>Settings</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
          <SidebarFooter className="border-t p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground truncate max-w-[180px]">
                {user?.email?.split('@')[0]}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSignOut}
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </SidebarFooter>
        </Sidebar>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex min-w-0 items-center gap-4 border-b px-4 py-3 sm:px-6">
            <SidebarTrigger />
            <h1 className="truncate text-lg font-semibold">{getHeading()}</h1>
          </header>
          <main id="main-content" tabIndex={-1} className="flex-1 overflow-auto p-4 sm:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}
