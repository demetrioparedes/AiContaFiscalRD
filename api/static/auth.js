/* AiContaFiscalRD — Auth Session Management */
/* Guarda JWT en localStorage, maneja sesión con Supabase Auth */

const AUTH_API = window.API_URL || '';

/* ─── Login ─────────────────────────────────────────── */
async function login(email, password) {
    try {
        const resp = await fetch(`${AUTH_API}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await resp.json();
        if (resp.status !== 200) {
            return { error: data.detail || 'Error de autenticación' };
        }
        // Guardar sesión
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.profile));
        localStorage.setItem('crnc', '');
        return { ok: true, profile: data.profile };
    } catch (e) {
        return { error: 'Error de conexión con el servidor' };
    }
}

/* ─── Logout ────────────────────────────────────────── */
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('crnc');
    window.location.href = '/login';
}

/* ─── Verificar sesión activa ──────────────────────── */
function isLoggedIn() {
    return !!localStorage.getItem('token');
}

/* ─── Obtener headers de autenticación ─────────────── */
function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    } : { 'Content-Type': 'application/json' };
}

/* ─── Safe fetch con JWT ───────────────────────────── */
async function safeFetch(url, options = {}) {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        throw new Error('No autenticado');
    }
    const headers = options.headers || {};
    headers['Authorization'] = `Bearer ${token}`;

    const resp = await fetch(url, { ...options, headers });

    if (resp.status === 401) {
        // Token expirado o inválido
        localStorage.removeItem('token');
        window.location.href = '/login';
        throw new Error('Sesión expirada');
    }

    return resp;
}

/* ─── Obtener perfil actual ────────────────────────── */
function getProfile() {
    try {
        return JSON.parse(localStorage.getItem('user') || '{}');
    } catch {
        return {};
    }
}

/* ─── Proteger página (redirigir si no hay sesión) ── */
function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

/* ─── Alternar menú de usuario ─────────────────────── */
function toggleUserMenu() {
    const menu = document.getElementById('user-menu');
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

/* ─── Cerrar menú al hacer clic fuera ──────────────── */
document.addEventListener('click', function(e) {
    const menu = document.getElementById('user-menu');
    if (menu && !e.target.closest('.topbar-user')) {
        menu.style.display = 'none';
    }
});

/* ─── Inicializar en pages protegidas ──────────────── */
function initAuth() {
    if (!requireAuth()) return;
    const profile = getProfile();
    const el = document.getElementById('user-name');
    if (el && profile.nombre) {
        el.textContent = profile.nombre;
    }
    const elRole = document.getElementById('user-role');
    if (elRole && profile.role) {
        elRole.textContent = profile.role === 'admin' ? 'Administrador'
            : profile.role === 'contador' ? 'Contador' : 'Cliente';
    }
    const elEmail = document.getElementById('user-menu-email');
    if (elEmail && profile.email) {
        elEmail.textContent = profile.email;
    }
    const elInit = document.getElementById('user-initial');
    if (elInit && profile.nombre) {
        elInit.textContent = profile.nombre.charAt(0).toUpperCase();
    }
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', initAuth);
