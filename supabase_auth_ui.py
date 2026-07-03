from __future__ import annotations

import os
from html import escape
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

SUPABASE_AUTH_UI_ENABLED = os.getenv("SUPABASE_AUTH_UI_ENABLED", "1").lower() not in {"0", "false", "no"}
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_ANON_KEY", "")).strip()
SUPABASE_AUTH_TITLE = os.getenv("SUPABASE_AUTH_TITLE", "ClaimRadar BG Account")
SUPABASE_AUTH_HOME_PATH = os.getenv("SUPABASE_AUTH_HOME_PATH", "/")
SUPABASE_AUTH_ACCOUNT_PATH = os.getenv("SUPABASE_AUTH_ACCOUNT_PATH", "/account")
SUPABASE_AUTH_LOGIN_PATH = os.getenv("SUPABASE_AUTH_LOGIN_PATH", "/login")
SUPABASE_AUTH_SIGNUP_PATH = os.getenv("SUPABASE_AUTH_SIGNUP_PATH", "/signup")
SUPABASE_JS_URL = os.getenv("SUPABASE_JS_URL", "https://esm.sh/@supabase/supabase-js@2")


def supabase_auth_config() -> Dict[str, object]:
    return {
        "enabled": SUPABASE_AUTH_UI_ENABLED,
        "configured": bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY),
        "supabase_url": SUPABASE_URL,
        "supabase_publishable_key": SUPABASE_PUBLISHABLE_KEY,
        "home_path": SUPABASE_AUTH_HOME_PATH,
        "account_path": SUPABASE_AUTH_ACCOUNT_PATH,
        "login_path": SUPABASE_AUTH_LOGIN_PATH,
        "signup_path": SUPABASE_AUTH_SIGNUP_PATH,
        "supabase_js_url": SUPABASE_JS_URL,
    }


def _base_html(page: str, title: str, body: str, script: str = "") -> str:
    safe_title = escape(title)
    return f"""<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin:0; font-family:Arial, sans-serif; color:#e5e7eb; background:#020617; }}
    .shell {{ min-height:100vh; display:grid; place-items:center; padding:28px; background:radial-gradient(circle at 20% 0, rgba(34,211,238,.18), transparent 34%), radial-gradient(circle at 85% 10%, rgba(168,85,247,.18), transparent 30%); }}
    .card {{ width:min(760px, 100%); border:1px solid rgba(34,211,238,.25); border-radius:24px; padding:24px; background:rgba(15,23,42,.86); box-shadow:0 24px 80px rgba(0,0,0,.35); }}
    .kicker {{ color:#67e8f9; font-size:12px; letter-spacing:.14em; text-transform:uppercase; font-weight:800; }}
    h1 {{ margin:10px 0 6px; font-size:28px; }}
    p {{ color:#cbd5e1; line-height:1.55; }}
    label {{ display:block; margin-top:14px; color:#94a3b8; font-size:13px; }}
    input {{ box-sizing:border-box; width:100%; margin-top:6px; padding:12px; border:1px solid rgba(34,211,238,.28); border-radius:14px; background:rgba(2,6,23,.68); color:#fff; }}
    button, .button {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; margin-top:16px; padding:12px 16px; border:0; border-radius:14px; background:linear-gradient(90deg,#0891b2,#7c3aed); color:#fff; font-weight:700; cursor:pointer; text-decoration:none; }}
    .secondary {{ background:rgba(15,23,42,.9); border:1px solid rgba(34,211,238,.25); }}
    .danger {{ background:rgba(127,29,29,.8); border:1px solid rgba(248,113,113,.45); }}
    .row {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
    .status {{ margin-top:14px; padding:12px; border-radius:14px; background:rgba(2,6,23,.65); color:#e0f2fe; white-space:pre-wrap; }}
    .muted {{ color:#94a3b8; font-size:13px; }}
    .profile {{ margin-top:16px; display:grid; gap:10px; }}
    .field {{ border:1px solid rgba(34,211,238,.18); border-radius:14px; padding:12px; background:rgba(2,6,23,.45); }}
    .field b {{ color:#fff; }}
    code {{ color:#67e8f9; }}
  </style>
</head>
<body data-supabase-auth-page="{escape(page)}">
  <main class="shell"><section class="card">
    <div class="kicker">Supabase Auth · ClaimRadar BG</div>
    {body}
  </section></main>
  {script}
</body>
</html>"""


def _supabase_module_script(inner: str) -> str:
    return f"""<script type="module">
import {{ createClient }} from '{SUPABASE_JS_URL}';
const configResponse = await fetch('/api/auth/supabase/config', {{ credentials: 'same-origin' }});
const config = await configResponse.json();
const statusBox = document.querySelector('#status');
function setStatus(message) {{ if (statusBox) statusBox.textContent = message; }}
function escapeHtml(value) {{ return String(value ?? '').replace(/[&<>\"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[ch])); }}
if (!config.configured) {{
  setStatus('Supabase не е конфигуриран. Добави SUPABASE_URL и SUPABASE_PUBLISHABLE_KEY в Hugging Face Variables.');
}} else {{
  const supabase = createClient(config.supabase_url, config.supabase_publishable_key, {{
    auth: {{ persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }}
  }});
  {inner}
}}
</script>"""


def signup_page() -> HTMLResponse:
    body = """
    <h1>Създай акаунт</h1>
    <p>Регистрация през Supabase Auth. Профилът автоматично получава роля <code>viewer</code>, а RLS пази личните записи.</p>
    <form id="signupForm">
      <label>Име / псевдоним</label>
      <input id="displayName" autocomplete="name" placeholder="Yordan" />
      <label>Email</label>
      <input id="email" type="email" autocomplete="email" required placeholder="you@example.com" />
      <label>Password</label>
      <input id="password" type="password" autocomplete="new-password" minlength="8" required placeholder="минимум 8 символа" />
      <button type="submit">Създай акаунт</button>
      <a class="button secondary" href="/login">Вече имам акаунт</a>
    </form>
    <div id="status" class="status muted">Готово за регистрация.</div>
    """
    script = _supabase_module_script(
        """
  const form = document.querySelector('#signupForm');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    setStatus('Създавам акаунт...');
    const email = document.querySelector('#email').value.trim();
    const password = document.querySelector('#password').value;
    const displayName = document.querySelector('#displayName').value.trim();
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { display_name: displayName },
        emailRedirectTo: `${window.location.origin}/account`
      }
    });
    if (error) { setStatus(`Грешка: ${error.message}`); return; }
    if (data?.session) { window.location.href = '/account'; return; }
    setStatus('Акаунтът е създаден. Провери email-а си за confirmation link, ако Supabase го изисква.');
  });
"""
    )
    return HTMLResponse(_base_html("signup", "ClaimRadar BG — Signup", body, script))


def login_page() -> HTMLResponse:
    body = """
    <h1>Вход</h1>
    <p>Влез със Supabase Auth, за да получиш user JWT и RLS-scoped достъп до профила и записите си.</p>
    <form id="loginForm">
      <label>Email</label>
      <input id="email" type="email" autocomplete="email" required placeholder="you@example.com" />
      <label>Password</label>
      <input id="password" type="password" autocomplete="current-password" required placeholder="password" />
      <button type="submit">Вход</button>
      <a class="button secondary" href="/signup">Нов акаунт</a>
    </form>
    <div id="status" class="status muted">Готово за вход.</div>
    """
    script = _supabase_module_script(
        """
  const existing = await supabase.auth.getSession();
  if (existing?.data?.session) setStatus('Вече имаш активна сесия. Можеш да отвориш /account.');
  document.querySelector('#loginForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    setStatus('Влизам...');
    const email = document.querySelector('#email').value.trim();
    const password = document.querySelector('#password').value;
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) { setStatus(`Грешка: ${error.message}`); return; }
    if (data?.session) window.location.href = '/account';
  });
"""
    )
    return HTMLResponse(_base_html("login", "ClaimRadar BG — Login", body, script))


def logout_page() -> HTMLResponse:
    body = """
    <h1>Изход</h1>
    <p>Изчистване на Supabase Auth сесията от браузъра.</p>
    <div id="status" class="status muted">Излизам...</div>
    <div class="row">
      <a class="button secondary" href="/login">Към вход</a>
      <a class="button secondary" href="/">Към приложението</a>
    </div>
    """
    script = _supabase_module_script(
        """
  const { error } = await supabase.auth.signOut();
  setStatus(error ? `Грешка при изход: ${error.message}` : 'Излезе успешно.');
"""
    )
    return HTMLResponse(_base_html("logout", "ClaimRadar BG — Logout", body, script))


def account_page() -> HTMLResponse:
    body = """
    <h1>Моят акаунт</h1>
    <p>Тази страница използва publishable key + Supabase user session. Данните от <code>claimradar_profiles</code> минават през RLS.</p>
    <div id="accountBox" class="profile"></div>
    <form id="profileForm" style="display:none">
      <label>Display name</label>
      <input id="displayName" autocomplete="name" />
      <button type="submit">Запази профила</button>
      <a class="button danger" href="/logout">Logout</a>
      <a class="button secondary" href="/">Към приложението</a>
    </form>
    <div id="status" class="status muted">Зареждам профила...</div>
    """
    script = _supabase_module_script(
        """
  const accountBox = document.querySelector('#accountBox');
  const profileForm = document.querySelector('#profileForm');
  const displayNameInput = document.querySelector('#displayName');
  const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
  if (sessionError || !sessionData?.session) {
    accountBox.innerHTML = '<div class="field">Няма активна сесия. <a class="button" href="/login">Вход</a></div>';
    setStatus('Не си логнат.');
  } else {
    const user = sessionData.session.user;
    const { data: profile, error: profileError } = await supabase
      .from('claimradar_profiles')
      .select('user_id,email,display_name,claimradar_role,created_at,updated_at')
      .eq('user_id', user.id)
      .maybeSingle();
    const safeProfile = profile || {};
    displayNameInput.value = safeProfile.display_name || user.user_metadata?.display_name || '';
    accountBox.innerHTML = `
      <div class="field"><b>User ID:</b><br>${escapeHtml(user.id)}</div>
      <div class="field"><b>Email:</b><br>${escapeHtml(user.email)}</div>
      <div class="field"><b>Role:</b><br>${escapeHtml(safeProfile.claimradar_role || 'viewer')}</div>
      <div class="field"><b>JWT session:</b><br>${sessionData.session.access_token ? 'active' : 'missing'}</div>
      <div class="field"><b>Profile source:</b><br>${profileError ? escapeHtml(profileError.message) : 'claimradar_profiles via RLS'}</div>`;
    profileForm.style.display = 'block';
    setStatus('Профилът е зареден.');
    profileForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      setStatus('Записвам профила...');
      const { error } = await supabase
        .from('claimradar_profiles')
        .update({ display_name: displayNameInput.value.trim(), updated_at: new Date().toISOString() })
        .eq('user_id', user.id);
      setStatus(error ? `Грешка: ${error.message}` : 'Профилът е обновен.');
    });
  }
"""
    )
    return HTMLResponse(_base_html("account", "ClaimRadar BG — Account", body, script))


def register_supabase_auth_ui_routes(app: FastAPI) -> None:
    @app.get("/api/auth/supabase/config")
    def api_supabase_auth_config():
        return JSONResponse(supabase_auth_config())

    @app.get("/auth/supabase/config")
    def supabase_auth_config_alias():
        return JSONResponse(supabase_auth_config())

    @app.get("/signup")
    def route_signup():
        if not SUPABASE_AUTH_UI_ENABLED:
            return JSONResponse({"ok": False, "error": "supabase_auth_ui_disabled"}, status_code=404)
        return signup_page()

    @app.get("/login")
    def route_login():
        if not SUPABASE_AUTH_UI_ENABLED:
            return JSONResponse({"ok": False, "error": "supabase_auth_ui_disabled"}, status_code=404)
        return login_page()

    @app.get("/logout")
    def route_logout():
        if not SUPABASE_AUTH_UI_ENABLED:
            return RedirectResponse(SUPABASE_AUTH_HOME_PATH)
        return logout_page()

    @app.get("/account")
    def route_account():
        if not SUPABASE_AUTH_UI_ENABLED:
            return JSONResponse({"ok": False, "error": "supabase_auth_ui_disabled"}, status_code=404)
        return account_page()
