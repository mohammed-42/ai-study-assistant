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
import { BookOpen, LayoutDashboard, LogOut, Folder } from 'lucide-react'

export default function Layout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  return (
    <SidebarProvider>
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
                <SidebarMenuButton tooltip="Subjects">
                  <Link to="/subjects" className="flex items-center gap-3">
                    <Folder className="h-4 w-4" />
                    <span>Subjects</span>
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
              <Button variant="ghost" size="sm" onClick={handleSignOut} title="Sign out">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </SidebarFooter>
        </Sidebar>
        <div className="flex flex-1 flex-col">
          <header className="border-b px-6 py-3 flex items-center gap-4">
            <SidebarTrigger />
            <h1 className="text-lg font-semibold">
              {location.pathname === '/' ? 'Dashboard' :
               location.pathname === '/subjects' ? 'Subjects' :
               location.pathname.startsWith('/subjects/') ? 'Subject Details' : ''}
            </h1>
          </header>
          <main className="flex-1 overflow-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}
