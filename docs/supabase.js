// Supabase Client for DoctorLink
// Include this in HTML files that need authentication

const SUPABASE_URL = 'https://jvsfhrekkkhijneqngax.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_nFnWeQyQCy47pZVhyIXrlA_PiGYK36I';

// Supabase auth state
let currentUser = null;
let supabaseSession = null;

// Initialize Supabase (mock for static HTML - will be replaced by real client)
class DoctorLinkSupabase {
    constructor() {
        this.authState = null;
    }

    async signUp(email, password, options = {}) {
        // For static HTML demo - store in localStorage
        // In production, this would call actual Supabase
        const users = JSON.parse(localStorage.getItem('dl_users') || '[]');
        
        if (users.find(u => u.email === email)) {
            throw new Error('Email already registered');
        }
        
        const newUser = {
            id: 'user_' + Date.now(),
            email,
            password: btoa(password), // Simple encoding (NOT secure - demo only)
            name: options.name || email.split('@')[0],
            role: options.role || 'PATIENT',
            credits: options.role === 'DOCTOR' ? 0 : 500
        };
        
        users.push(newUser);
        localStorage.setItem('dl_users', JSON.stringify(users));
        
        // Auto login after signup
        return this.signIn(email, password);
    }

    async signIn(email, password) {
        const users = JSON.parse(localStorage.getItem('dl_users') || '[]');
        const user = users.find(u => u.email === email);
        
        if (!user) {
            throw new Error('Invalid email or password');
        }
        
        if (atob(user.password) !== password) {
            throw new Error('Invalid email or password');
        }
        
        this.currentUser = user;
        this.authState = {
            user: user,
            session: {
                access_token: 'demo_token_' + user.id,
                user: user
            }
        };
        
        localStorage.setItem('dl_current_user', JSON.stringify(user));
        
        return { data: this.authState, error: null };
    }

    async signOut() {
        this.currentUser = null;
        this.authState = null;
        localStorage.removeItem('dl_current_user');
        return { error: null };
    }

    getUser() {
        return this.currentUser;
    }

    getSession() {
        return this.authState;
    }

    async getProfile() {
        return this.currentUser;
    }

    // Mock database operations
    async from(table) {
        const storageKey = 'dl_' + table;
        
        return {
            select: () => ({
                eq: (field, value) => ({
                    order: (field, options = {}) => {
                        let data = JSON.parse(localStorage.getItem(storageKey) || '[]');
                        data = data.filter(item => item[field] === value);
                        if (options.desc) {
                            data.reverse();
                        }
                        return {
                            execute: () => ({ data, error: null })
                        };
                    },
                    execute: () => {
                        const data = JSON.parse(localStorage.getItem(storageKey) || '[]');
                        return { data, error: null };
                    }
                }),
                execute: () => {
                    const data = JSON.parse(localStorage.getItem(storageKey) || '[]');
                    return { data, error: null };
                }
            }),
            insert: (data) => ({
                execute: () => {
                    const existing = JSON.parse(localStorage.getItem(storageKey) || '[]');
                    const newData = Array.isArray(data) ? data : [data];
                    const inserted = newData.map(item => ({
                        ...item,
                        id: Date.now() + Math.random(),
                        created_at: new Date().toISOString()
                    }));
                    localStorage.setItem(storageKey, JSON.stringify([...existing, ...inserted]));
                    return { data: inserted, error: null };
                }
            }),
            update: (data) => ({
                eq: (field, value) => ({
                    execute: () => {
                        const existing = JSON.parse(localStorage.getItem(storageKey) || '[]');
                        const updated = existing.map(item => 
                            item[field] === value ? { ...item, ...data } : item
                        );
                        localStorage.setItem(storageKey, JSON.stringify(updated));
                        return { data: updated, error: null };
                    }
                })
            })
        };
    }
}

// Create global instance
const supabase = new DoctorLinkSupabase();

// Check for existing session
const savedUser = localStorage.getItem('dl_current_user');
if (savedUser) {
    supabase.currentUser = JSON.parse(savedUser);
    supabase.authState = {
        user: JSON.parse(savedUser),
        session: { access_token: 'demo', user: JSON.parse(savedUser) }
    };
    currentUser = supabase.currentUser;
}

// Helper to check auth
function isAuthenticated() {
    return currentUser !== null;
}

// Helper to get current user
function getCurrentUser() {
    return currentUser;
}

// Helper to logout
async function logout() {
    await supabase.signOut();
    currentUser = null;
    window.location.reload();
}