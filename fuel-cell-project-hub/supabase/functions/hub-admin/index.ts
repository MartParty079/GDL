import { createClient } from 'npm:@supabase/supabase-js@2.99.1';

// Credentials remain in Supabase-managed secrets, never in the desktop client.
const url = Deno.env.get('SUPABASE_URL')!;
const service = createClient(url, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
  auth: { persistSession: false, autoRefreshToken: false },
});
const reply = (body: unknown, status = 200) => Response.json(body, { status });
Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return reply({ message: 'Method unavailable' }, 405);
  const token = req.headers.get('Authorization')?.match(/^Bearer (.+)$/)?.[1];
  if (!token) return reply({ message: 'Sign in required' }, 401);
  const { data: { user }, error: authError } = await service.auth.getUser(token);
  if (authError || !user) return reply({ message: 'Sign in required' }, 401);
  const { data: actor } = await service.from('profiles').select('id,role,active').eq('id',user.id).single();
  if (!actor?.active || actor.role !== 'admin') return reply({ message: 'Administrator access required' }, 403);
  try {
    const raw = await req.text();
    if (raw.length > 4096) return reply({ message: 'Request too large' }, 413);
    const body = JSON.parse(raw);
    const { action } = body;
    if (action === 'overview' || action === 'users' || action === 'activity' || action === 'installations') {
      if (action === 'overview') {
        const since = new Date(Date.now()-7*86400000).toISOString();
        const [users, installs, logins, recent] = await Promise.all([
          service.from('profiles').select('id',{count:'exact',head:true}).eq('active',true),
          service.from('installations').select('id',{count:'exact',head:true}).gte('last_seen_at',since),
          service.from('activity_events').select('id',{count:'exact',head:true}).eq('event_type','LOGIN').gte('created_at',since),
          service.from('activity_events').select('*').order('created_at',{ascending:false}).limit(12),
        ]);
        if ([users,installs,logins,recent].some(x=>x.error)) throw Error('Query failed');
        return reply({ active_users: users.count, recent_installations: installs.count, logins_7_days: logins.count, recent: recent.data });
      }
      const table = action === 'users' ? 'profiles' : action === 'activity' ? 'activity_events' : 'installations';
      const offset = Math.max(0,Math.min(100000,Number(body.offset)||0));
      let query = service.from(table).select('*',{count:'exact'}).order(action==='installations'?'last_seen_at':'created_at',{ascending:false}).range(offset,offset+99);
      if (action==='activity') {
        for (const field of ['user_id','event_type','entity_type','app_version']) {
          if (body[field]) query = query.eq(field,String(body[field]).slice(0,120));
        }
        if (body.date_from && /^\d{4}-\d{2}-\d{2}$/.test(body.date_from)) query=query.gte('created_at',body.date_from);
      }
      const { data, error, count } = await query;
      if (error) throw error;
      // Users include installation and usage summaries, without Auth internals.
      if (action==='users' && data?.length) {
        const ids=data.map(x=>x.id);
        const {data: installs,error: installError}=await service.from('installations').select('user_id,app_version,last_seen_at').in('user_id',ids).order('last_seen_at',{ascending:false});
        if(installError) throw installError;
        for(const row of data) {
          const owned=(installs||[]).filter(x=>x.user_id===row.id);
          row.installations=owned.length; row.last_app_version=owned[0]?.app_version||''; row.last_activity=owned[0]?.last_seen_at||row.last_login||'';
        }
      }
      return reply({ rows: data, count });
    }
    if (action==='invite') {
      const email=String(body.email||'').trim();
      if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return reply({message:'Enter a valid email'},400);
      const name=String(body.display_name||'').slice(0,120);
      const {data,error}=await service.auth.admin.inviteUserByEmail(email,{data:{display_name:name}});
      if(error || !data.user) return reply({message:'Invitation unavailable. Check the address or existing account.'},400);
      const {error: insertError}=await service.from('profiles').insert({id:data.user.id,email,display_name:name,role:'user',active:true});
      if(insertError) throw insertError;
      const {error: auditError}=await service.from('activity_events').insert({user_id:user.id,event_type:'USER_INVITED',entity_type:'user',entity_id:data.user.id,entity_name:email});
      if(auditError) throw auditError;
      return reply({message:'Invitation sent'});
    }
    if(action==='set_role' || action==='set_active') {
      if(!/^[0-9a-f-]{36}$/i.test(body.user_id||'')) return reply({message:'Select a user'},400);
      const values=action==='set_role'? {role:body.role}: {active:body.active};
      if(action==='set_role' && !['admin','user'].includes(body.role)) return reply({message:'Invalid role'},400);
      if(action==='set_active' && typeof body.active!=='boolean') return reply({message:'Invalid status'},400);
      const {data,error}=await service.from('profiles').update(values).eq('id',body.user_id).select('id').single();
      if(error || !data) return reply({message:'Change unavailable. At least one active administrator must remain.'},409);
      const {error: auditError}=await service.from('activity_events').insert({user_id:user.id,event_type:action==='set_role'?'ROLE_CHANGED':body.active?'USER_ENABLED':'USER_DISABLED',entity_type:'user',entity_id:body.user_id,details:values});
      if(auditError) throw auditError;
      return reply({message:'Account updated'});
    }
    return reply({message:'Action unavailable'},400);
  } catch {
    return reply({message:'Account action unavailable. Please try again.'},500);
  }
});
