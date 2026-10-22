import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing Supabase environment variables')
}

let _client: ReturnType<typeof createClient> | null = null

export function createSupabaseClient() {
  if (!_client) {
    _client = createClient(supabaseUrl!, supabaseAnonKey!, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
      },
    })
  }
  return _client
}

export async function getAccessToken(): Promise<string | null> {
  const client = createSupabaseClient()
  const { data } = await client.auth.getSession()
  return data.session?.access_token ?? null
}
