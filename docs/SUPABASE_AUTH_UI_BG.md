# ClaimRadar BG — Supabase Auth UI

Този слой добавя browser-facing Supabase Auth страници, които работят с public publishable key и user session.

## Routes

```text
/signup
/login
/logout
/account
/api/auth/supabase/config
/auth/supabase/config
```

## Public variables

```bash
SUPABASE_AUTH_UI_ENABLED=1
SUPABASE_URL=https://rsknkjmzjpewhebwfffz.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable-key>
SUPABASE_AUTH_TITLE=ClaimRadar BG Account
SUPABASE_AUTH_HOME_PATH=/
SUPABASE_AUTH_ACCOUNT_PATH=/account
SUPABASE_AUTH_LOGIN_PATH=/login
SUPABASE_AUTH_SIGNUP_PATH=/signup
SUPABASE_JS_URL=https://esm.sh/@supabase/supabase-js@2
```

## Как работи

- `/signup` използва `supabase.auth.signUp(...)`.
- `/login` използва `supabase.auth.signInWithPassword(...)`.
- `/logout` използва `supabase.auth.signOut()`.
- `/account` използва `supabase.auth.getSession()` и чете `claimradar_profiles` през user session и RLS.
- `/account` позволява update само на собствен `display_name`.

## Security model

- Използва се само public publishable key във frontend.
- Повишени backend credentials не се показват в browser страниците.
- User-level достъпът се пази чрез Supabase Auth session + RLS policies.
- Профилите са в `public.claimradar_profiles`.
- Всеки нов `auth.users` запис автоматично получава profile с роля `viewer`.

## Supabase dashboard настройки

В Supabase Auth settings добави allowed redirect URLs:

```text
https://dyrakarmy-claimradar-bg.hf.space/account
https://claimradar.dyrakarmy.eu/account
```

Ако custom domain още не е активен, използвай първо `hf.space` URL.

## Проверка

```bash
curl https://dyrakarmy-claimradar-bg.hf.space/api/auth/supabase/config
```

Browser flow:

```text
/signup → email/password → Supabase Auth → /account
/login → email/password → /account
/logout → clear browser session
```

## Tests

```bash
pytest tests/test_supabase_auth_ui.py
```
