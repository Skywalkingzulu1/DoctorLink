
        // ========== API CONFIG ==========
        const API_BASE = '';
        let authToken = localStorage.getItem('token');
        let currentUser = null;
        let selectedDoctor = null;

        // AUTO-LOGIN LOGIC
        async function autoLogin() {
            if (!authToken) {
                window.location.href = 'login.html';
                return;
            } else {
                // Fetch current user if token exists
                try {
                    const user = await apiCall('/api/auth/me');
                    currentUser = user;
                    showApp();
                } catch (e) {
                    logout();
                }
            }
        }

        window.onload = autoLogin;

        // ========== API HELPERS ==========
        async function apiCall(endpoint, options = {}) {
            const url = API_BASE + endpoint;
            const headers = { 'Content-Type': 'application/json' };
            if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
            
            try {
                const response = await fetch(url, { ...options, headers });
                if (response.status === 401) { logout(); throw new Error('Session expired'); }
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'API error');
                return data;
            } catch (e) {
                console.error('API Error:', e);
                throw e;
            }
        }

        // ========== AUTH ==========
        let isLogin = true;

        document.getElementById('authSwitch').onclick = e => {
            e.preventDefault();
            isLogin = !isLogin;
            document.getElementById('authSubtitle').textContent = isLogin ? 'Welcome Back' : 'Join South Africa\'s Healthcare Platform';
            document.getElementById('authBtn').textContent = isLogin ? 'Login' : 'Create Account';
            document.getElementById('authSwitchText').textContent = isLogin ? 'Don\'t have an account?' : 'Already have an account?';
            document.getElementById('authSwitch').textContent = isLogin ? 'Register' : 'Login';
            document.getElementById('nameField').style.display = isLogin ? 'none' : 'block';
            document.getElementById('roleField').style.display = isLogin ? 'none' : 'block';
        };

        document.getElementById('authForm').onsubmit = async e => {
            e.preventDefault();
            const email = document.getElementById('authEmail').value.trim();
            const password = document.getElementById('authPassword').value;
            const err = document.getElementById('authError');
            err.style.display = 'none';
            
            console.log('Form submitted, email:', email, 'isLogin:', isLogin);

            try {
                if (isLogin) {
                    const formData = new FormData();
                    formData.append('username', email);
                    formData.append('password', password);
                    
                    console.log('FormData created, entries:');
                    for (let [k, v] of formData) console.log('  ', k, '=', v);
                    
                    console.log('Fetching from:', API_BASE + '/api/auth/login');
                    
                    const response = await fetch(API_BASE + '/api/auth/login', {
                        method: 'POST',
                        body: formData
                    });
                    
                    console.log('Got response, status:', response.status);
                    
                    if (!response.ok) {
                        const data = await response.json();
                        console.log('Error response:', data);
                        err.textContent = data.detail || 'Invalid credentials';
                        err.style.display = 'block';
                        return;
                    }
                    
                    const data = await response.json();
                    console.log('Login success:', data);
                    authToken = data.access_token;
                    currentUser = data.user;
                    localStorage.setItem('token', authToken);
                    showApp();
                } else {
                    const name = document.getElementById('authName').value;
                    const role = document.getElementById('authRole').value;
                    
                    await apiCall('/api/auth/register', {
                        method: 'POST',
                        body: JSON.stringify({ email, password, name, role })
                    });
                    
                    alert('Registration successful! Please login.');
                    isLogin = true;
                    document.getElementById('authSwitch').click();
                }
            } catch (e) {
                err.textContent = 'Connection error. Please try again.';
                err.style.display = 'block';
            }
        };

        function logout() {
            authToken = null;
            currentUser = null;
            localStorage.removeItem('token');
            window.location.reload();
        }

        function showApp() {
            document.getElementById('authPage').classList.add('hidden');
            document.getElementById('appPage').classList.remove('hidden');
            document.getElementById('userName').textContent = currentUser.name;
            
            // Display Somnia Address
            if (currentUser.somnia_address) {
                const addr = currentUser.somnia_address;
                document.getElementById('userAddress').textContent = addr.substring(0, 6) + '...' + addr.substring(38);
                document.getElementById('userAddress').title = addr;
            }

            updateCredits();
            updateSomniaBalance();
            initDashboard();
            loadDoctors();
        }

        async function updateSomniaBalance() {
            try {
                const data = await apiCall('/api/somnia/escrow/wallet/balance');
                // Use balance_eth from API
                document.getElementById('userSttBalance').textContent = parseFloat(data.balance_eth).toFixed(2) + ' STT';
                
                // Also update address if not set
                if (!currentUser.somnia_address) {
                    const addr = data.address;
                    document.getElementById('userAddress').textContent = addr.substring(0, 6) + '...' + addr.substring(38);
                }
            } catch (e) {
                console.error('Failed to fetch Somnia balance');
            }
        }

        // ========== METAMASK INTEGRATION ==========
        let mmAccount = null;

        function toast(msg, type = 'info', duration = 4000) {
            const container = document.getElementById('toastContainer');
            const icons = { success: '✓', error: '✗', info: 'ℹ', warning: '⚠' };
            const el = document.createElement('div');
            el.className = 'toast ' + type;
            el.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span class="toast-msg">${msg}</span><button class="toast-close" onclick="this.parentElement.classList.add('toast-out');setTimeout(()=>this.parentElement.remove(),300)">×</button>`;
            container.appendChild(el);
            setTimeout(() => { if (el.parentElement) { el.classList.add('toast-out'); setTimeout(() => el.remove(), 300); } }, duration);
        }

        function showWalletDropdown() {
            document.getElementById('walletDropdownMenu').classList.toggle('show');
        }
        document.addEventListener('click', function(e) {
            const dd = document.getElementById('walletDropdownMenu');
            if (dd && !e.target.closest('.wallet-dropdown')) dd.classList.remove('show');
        });

        function disconnectWallet() {
            mmAccount = null;
            const btn = document.getElementById('connectMmBtn');
            btn.innerHTML = 'Connect MetaMask';
            btn.style.background = 'var(--secondary)';
            btn.disabled = false;
            document.getElementById('connectMmBtnWrapper').style.display = 'inline-block';
            document.getElementById('walletDropdownWrapper').style.display = 'none';
            document.getElementById('userAddress').textContent = '0x...';
            toast('Wallet disconnected', 'info');
        }

        async function connectMetaMask() {
            if (typeof window.ethereum === 'undefined') {
                toast('Please install MetaMask to use this feature.', 'error');
                return;
            }
            const btn = document.getElementById('connectMmBtn');
            btn.disabled = true;
            btn.innerHTML = '<svg style="width:14px;height:14px;display:inline-block;margin-right:4px;animation:spin 0.6s linear infinite" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="3"/><path d="M12 2a10 10 0 0 1 10 10" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/></svg> Connecting...';
            try {
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                mmAccount = accounts[0];
                btn.innerHTML = '<svg style="width:16px;height:16px;display:inline-block;margin-right:4px;vertical-align:middle" viewBox="0 0 35 33" xmlns="http://www.w3.org/2000/svg"><g fill="none" fill-rule="evenodd"><path d="M32.958 1l-13.134 9.718 2.442-5.767L32.958 1z" fill="#E17726" stroke="#E17726" stroke-width=".25"/><path d="M2.663 1l13.016 9.825-2.35-5.874L2.663 1z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M28.188 23.3l-3.5 5.346 7.543 2.076 2.166-7.361-6.21-.06z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M1.605 23.363l2.156 7.358 7.543-2.076-3.5-5.346-6.2.064z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M10.922 14.206l-2.083 3.145 7.482.336-.286-8.033-5.113 4.552z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M24.7 14.206l-5.202-4.556-.197 8.137 7.482-.336-2.083-3.245z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M10.569 28.646l4.543-2.204-3.91-3.043-.633 5.247z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M20.51 26.442l4.543 2.204-.633-5.247-3.91 3.043z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M25.052 28.646l-4.543-2.204.402 2.776-.058 1.182 4.199-.758z" fill="#D5BFB2" stroke="#D5BFB2" stroke-width=".25"/><path d="M10.569 28.646l4.199.758-.058-1.182.402-2.776-4.543 2.2z" fill="#D5BFB2" stroke="#D5BFB2" stroke-width=".25"/><path d="M14.86 21.734l-3.77-1.105 2.663-1.224 1.107 2.33z" fill="#233447" stroke="#233447" stroke-width=".25"/><path d="M20.762 21.734l1.107-2.33 2.663 1.224-3.77 1.106z" fill="#233447" stroke="#233447" stroke-width=".25"/><path d="M10.569 28.646l.655-5.346-4.155.063 3.5 5.283z" fill="#CC6228" stroke="#CC6228" stroke-width=".25"/><path d="M24.398 23.3l.655 5.346 3.5-5.283-4.155-.063z" fill="#CC6228" stroke="#CC6228" stroke-width=".25"/><path d="M28.188 23.3l-3.5 5.346 2.285 1.89 4.656-1.79-1.44-5.446z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M7.433 23.3l-1.44 5.446 4.656 1.79 2.285-1.89-3.5-5.346z" fill="#E27625" stroke="#E27625" stroke-width=".25"/><path d="M21.92 17.35l-3.694-1.232 1.323-2.042 2.37 3.274z" fill="#CD6116" stroke="#CD6116" stroke-width=".25"/><path d="M13.702 17.35l2.371-3.274 1.323 2.042-3.694 1.232z" fill="#CD6116" stroke="#CD6116" stroke-width=".25"/><path d="M14.86 21.734l-.705-1.873-3.06.868 3.765 1.005z" fill="#E4751F" stroke="#E4751F" stroke-width=".25"/><path d="M20.762 21.734l3.766-1.005-3.06-.868-.706 1.873z" fill="#E4751F" stroke="#E4751F" stroke-width=".25"/><path d="M25.052 28.646l-.633-5.247 1.77-2.099-4.82.07 3.683 7.276z" fill="#F5841F" stroke="#F5841F" stroke-width=".25"/><path d="M10.569 28.646l3.683-7.276-4.82-.07 1.77 2.099-.633 5.247z" fill="#F5841F" stroke="#F5841F" stroke-width=".25"/><path d="M10.202 17.35l-2.456 1.733 2.982.292-.526-2.025z" fill="#C0AC9D" stroke="#C0AC9D" stroke-width=".25"/><path d="M21.42 17.35l-.526 2.025 2.982-.292-2.456-1.733z" fill="#C0AC9D" stroke="#C0AC9D" stroke-width=".25"/><path d="M14.86 21.734l.151-2.34-2.63.283 2.479 2.057z" fill="#161616" stroke="#161616" stroke-width=".25"/><path d="M20.762 21.734l2.479-2.057-2.63-.283.151 2.34z" fill="#161616" stroke="#161616" stroke-width=".25"/><path d="M25.052 28.646l-.633-5.247 1.77-2.099-4.82.07 3.683 7.276z" fill="#F5841F" stroke="#F5841F" stroke-width=".25"/></g></svg> <span style="vertical-align:middle">' + mmAccount.substring(0, 6) + '...</span>';
                btn.style.background = 'var(--accent)';
                btn.disabled = false;
                toast('MetaMask Connected \u2713', 'success');

                // Switch to Somnia Testnet if needed
                try {
                    await window.ethereum.request({
                        method: 'wallet_switchEthereumChain',
                        params: [{ chainId: '0xC488' }],
                    });
                } catch (switchError) {
                    if (switchError.code === 4902) {
                        await window.ethereum.request({
                            method: 'wallet_addEthereumChain',
                            params: [{
                                chainId: '0xC488',
                                chainName: 'Somnia Testnet',
                                rpcUrls: ['https://api.infra.testnet.somnia.network'],
                                nativeCurrency: { name: 'Somnia Test Token', symbol: 'STT', decimals: 18 },
                                blockExplorerUrls: ['https://explorer.testnet.somnia.network']
                            }],
                        });
                    }
                }
                // Show disconnect dropdown
                document.getElementById('connectMmBtnWrapper').style.display = 'none';
                document.getElementById('walletDropdownWrapper').style.display = 'inline-block';
                document.getElementById('walletAddressDisplay').innerHTML = '<svg style="width:12px;height:12px;display:inline-block;margin-right:3px;vertical-align:middle" viewBox="0 0 35 33"><path d="M32.958 1l-13.134 9.718 2.442-5.767L32.958 1z" fill="#E17726"/><path d="M2.663 1l13.016 9.825-2.35-5.874L2.663 1z" fill="#E27625"/><path d="M28.188 23.3l-3.5 5.346 7.543 2.076 2.166-7.361-6.21-.06z" fill="#E27625"/><path d="M1.605 23.363l2.156 7.358 7.543-2.076-3.5-5.346-6.2.064z" fill="#E27625"/><path d="M10.922 14.206l-2.083 3.145 7.482.336-.286-8.033-5.113 4.552z" fill="#E27625"/><path d="M24.7 14.206l-5.202-4.556-.197 8.137 7.482-.336-2.083-3.245z" fill="#E27625"/><path d="M10.569 28.646l4.543-2.204-3.91-3.043-.633 5.247z" fill="#E27625"/><path d="M20.51 26.442l4.543 2.204-.633-5.247-3.91 3.043z" fill="#E27625"/><path d="M25.052 28.646l-4.543-2.204.402 2.776-.058 1.182 4.199-.758z" fill="#D5BFB2"/><path d="M10.569 28.646l4.199.758-.058-1.182.402-2.776-4.543 2.2z" fill="#D5BFB2"/><path d="M14.86 21.734l-3.77-1.105 2.663-1.224 1.107 2.33z" fill="#233447"/><path d="M20.762 21.734l1.107-2.33 2.663 1.224-3.77 1.106z" fill="#233447"/><path d="M10.569 28.646l.655-5.346-4.155.063 3.5 5.283z" fill="#CC6228"/><path d="M24.398 23.3l.655 5.346 3.5-5.283-4.155-.063z" fill="#CC6228"/><path d="M28.188 23.3l-3.5 5.346 2.285 1.89 4.656-1.79-1.44-5.446z" fill="#E27625"/><path d="M7.433 23.3l-1.44 5.446 4.656 1.79 2.285-1.89-3.5-5.346z" fill="#E27625"/><path d="M21.92 17.35l-3.694-1.232 1.323-2.042 2.37 3.274z" fill="#CD6116"/><path d="M13.702 17.35l2.371-3.274 1.323 2.042-3.694 1.232z" fill="#CD6116"/><path d="M14.86 21.734l-.705-1.873-3.06.868 3.765 1.005z" fill="#E4751F"/><path d="M20.762 21.734l3.766-1.005-3.06-.868-.706 1.873z" fill="#E4751F"/><path d="M25.052 28.646l-.633-5.247 1.77-2.099-4.82.07 3.683 7.276z" fill="#F5841F"/><path d="M10.569 28.646l3.683-7.276-4.82-.07 1.77 2.099-.633 5.247z" fill="#F5841F"/></svg> <span style="vertical-align:middle">' + mmAccount.substring(0, 6) + '...' + mmAccount.slice(-4) + '</span>';
            } catch (e) {
                console.error('MetaMask connection failed:', e);
                toast('MetaMask connection cancelled or failed', 'error');
                btn.disabled = false;
                btn.innerHTML = 'Connect MetaMask';
            }
        }

        function copyAddress() {
            if (mmAccount) {
                navigator.clipboard.writeText(mmAccount).then(() => toast('Address copied ✓', 'success'));
            }
        }

        // ========== SKELETON HELPERS ==========
        function showSkeleton(id, rows = 3) {
            const el = document.getElementById(id);
            if (!el) return;
            let html = '';
            for (let i = 0; i < rows; i++) {
                html += '<div class="skeleton-row"><div class="skeleton skeleton-avatar"></div><div style="flex:1"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div></div></div>';
            }
            el.innerHTML = html;
        }
        function showSkeletonTable(id, cols = 4, rows = 4) {
            const el = document.getElementById(id);
            if (!el) return;
            let html = '';
            for (let i = 0; i < rows; i++) {
                html += '<tr><td colspan="' + cols + '"><div class="skeleton skeleton-line" style="height:16px;margin:8px 0;"></div></td></tr>';
            }
            el.innerHTML = html;
        }

        function updateCredits() {
            // Fetch fresh credits from API
            apiCall('/api/credits/balance').then(data => {
                currentUser.credits = data.credits;
                document.getElementById('userCredits').textContent = data.credits + ' Credits';
                document.getElementById('statCredits').textContent = data.credits;
            }).catch(() => {});
            
            // Update appointment badge
            apiCall('/api/appointments').then(appts => {
                const pending = appts.filter(a => a.status === 'SCHEDULED').length;
                document.getElementById('apptBadge').textContent = pending;
            }).catch(() => {});
        }

        // ========== NAVIGATION ==========
        document.querySelectorAll('.menu-item[data-page]').forEach(item => {
            item.onclick = () => navTo(item.dataset.page);
        });

        function navTo(page) {
            document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
            document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
            const prevPage = document.querySelector('[id^="page-"]:not(.hidden)');
            document.querySelectorAll('[id^="page-"]').forEach(p => p.classList.add('hidden'));
            const nextPage = document.getElementById('page-' + page);
            if (nextPage) {
                nextPage.classList.remove('hidden');
                nextPage.classList.remove('page-enter');
                void nextPage.offsetWidth; // force reflow
                nextPage.classList.add('page-enter');
            }
            document.getElementById('pageTitle').textContent = page.charAt(0).toUpperCase() + page.slice(1).replace(/-/g,' ');
            
            if (page === 'appointments') loadAppointments();
            if (page === 'records') loadRecords();
            if (page === 'prescriptions') loadPrescriptions();
            if (page === 'health-tools') loadCreditCosts();
            if (page === 'payments') { loadPayments(); loadEscrow(); }
            if (page === 'profile') loadProfile();
        }

        // ========== DASHBOARD ==========
        async function initDashboard() {
            try {
                const [appts, doctors, records] = await Promise.all([
                    apiCall('/api/appointments'),
                    apiCall('/api/doctors'),
                    apiCall('/api/records')
                ]);
                
                document.getElementById('statAppointments').textContent = appts.length;
                document.getElementById('statCredits').textContent = currentUser.credits;
                document.getElementById('statDoctors').textContent = doctors.length;
                document.getElementById('statRecords').textContent = records.length;
                
                // Upcoming appointments
                const upcoming = appts.filter(a => a.status === 'SCHEDULED' || a.status === 'ACTIVE').slice(0, 3);
                const apptsContainer = document.getElementById('dashboardAppts');
                if (upcoming.length === 0) {
                    apptsContainer.innerHTML = '<div class="empty"><p>No upcoming appointments</p></div>';
                } else {
                    apptsContainer.innerHTML = upcoming.map(a => `
                        <div style="padding:0.8rem;border-bottom:1px solid var(--border)">
                            <strong>${a.doctor_name || 'Doctor'}</strong><br>
                            <small>${new Date(a.timestamp).toLocaleString()}</small><br>
                            <span class="status status-${a.status.toLowerCase()}">${a.status}</span>
                        </div>
                    `).join('');
                }
                
                // Recent records
                const recordsContainer = document.getElementById('dashboardRecords');
                if (records.length === 0) {
                    recordsContainer.innerHTML = '<div class="empty"><p>No medical records</p></div>';
                } else {
                    recordsContainer.innerHTML = records.slice(0, 3).map(r => `
                        <div style="padding:0.8rem;border-bottom:1px solid var(--border)">
                            <strong>Visit Summary</strong><br>
                            <small>${r.summary.substring(0, 50)}...</small>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error('Dashboard error:', e);
            }
        }

        // ========== DOCTORS ==========
        async function loadDoctors() {
            try {
                const doctors = await apiCall('/api/doctors');
                renderDoctors(doctors);
                
                // Populate specialty dropdown
                const specialties = [...new Set(doctors.map(d => d.specialty))];
                const select = document.getElementById('docSpecialty');
                select.innerHTML = '<option value="">All Specialties</option>' + 
                    specialties.map(s => `<option value="${s}">${s}</option>`).join('');
            } catch (e) {
                console.error('Load doctors error:', e);
            }
        }

        async function searchDoctors() {
            const query = document.getElementById('docSearch').value;
            const specialty = document.getElementById('docSpecialty').value;
            showSkeleton('doctorsGrid', 3);
            try {
                const params = new URLSearchParams();
                if (query) params.set('q', query);
                if (specialty) params.set('specialty', specialty);
                const doctors = await apiCall('/api/doctors?' + params);
                
                const grid = document.getElementById('doctorsGrid');
                if (!doctors.length) {
                    grid.innerHTML = '<div class="empty">No doctors found</div>';
                    return;
                }
                
                grid.innerHTML = doctors.map(d => {
                // Verification badge
                let badge = '';
                if (d.verification_status === 'verified') {
                    badge = '<div style="color:#36b37e;font-size:0.8rem;font-weight:bold">★ Verified Doctor</div>';
                } else if (d.verification_status === 'basic') {
                    badge = '<div style="color:#0052cc;font-size:0.8rem;font-weight:bold">✓ Verified</div>';
                } else {
                    badge = '<div style="color:#6b778c;font-size:0.8rem">Pending Verification</div>';
                }
                
                return `
                <div class="card">
                    <div style="text-align:center;padding:1rem"><i class="fas fa-user-md" style="font-size:3rem;color:var(--text-light)"></i></div>
                    ${badge}
                    <h3 style="margin:0.5rem 0">${d.name}</h3>
                    <div class="meta"><i class="fas fa-stethoscope"></i> ${d.specialty}</div>
                    <div class="meta"><i class="fas fa-map-marker-alt"></i> ${d.area}</div>
                    <div class="meta"><i class="fas fa-star"></i> ${d.rating} (${d.review_count} reviews)</div>
                    <div class="meta"><i class="fas fa-coins"></i> ${d.consultation_fee} credits <span style="background:#059669;color:white;padding:1px 6px;border-radius:3px;font-weight:bold;font-size:0.7rem">≈ ${d.consultation_fee * 10} T800</span></div>
                    <button class="btn btn-primary" style="width:100%;margin-top:1rem" onclick="openBookModal(${d.id})">Book Appointment</button>
                </div>
            `}).join('');
            } catch (e) {
                console.error('Search doctors error:', e);
            }
        }

        // ========== APPOINTMENTS ==========
        async function loadAppointments(filter = 'all') {
            showSkeletonTable('appointmentsTable', 5);
            try {
                const url = filter === 'all' ? '/api/appointments' : `/api/appointments?status_filter=${filter}`;
                const appts = await apiCall(url);
                
                const tbody = document.getElementById('appointmentsTable');
                if (!appts.length) {
                    tbody.innerHTML = '<tr><td colspan="5" class="empty">No appointments</td></tr>';
                    return;
                }
                
                tbody.innerHTML = appts.map(a => {
                    const isScheduled = a.status === 'SCHEDULED';
                    const isActive = a.status === 'ACTIVE';
                    const isCompleted = a.status === 'COMPLETED';
                    
                    let actionButtons = '';
                    if (isActive) {
                        actionButtons = '<button class="btn btn-sm btn-accent" onclick="joinCall(' + a.id + ')">Join Call</button>';
                    } else if (isScheduled) {
                        actionButtons = '<button class="btn btn-sm btn-secondary" onclick="joinWaitingRoom(' + a.id + ')">Join Waiting Room</button>' +
                                        '<button class="btn btn-sm btn-danger" style="margin-left:0.5rem" onclick="cancelAppt(' + a.id + ')">Cancel</button>';
                    } else if (isCompleted) {
                        actionButtons = '<span style="color:var(--text-light)">Completed</span>';
                    }
                    
                    return '<tr>' +
                        '<td>' + (a.doctor_name || 'Doctor') + '</td>' +
                        '<td>' + new Date(a.timestamp).toLocaleDateString() + '</td>' +
                        '<td>' + a.appointment_type + '</td>' +
                        '<td><span class="status status-' + a.status.toLowerCase() + '">' + a.status + '</span></td>' +
                        '<td>' + actionButtons + '</td>' +
                    '</tr>';
                }).join('');
            } catch (e) {
                console.error('Load appointments error:', e);
            }
        }

        function filterAppts(status, tab) {
            document.querySelectorAll('#page-appointments .tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            loadAppointments(status);
        }

        async function cancelAppt(id) {
            if (!confirm('Cancel this appointment?')) return;
            try {
                await apiCall(`/api/appointments/${id}`, { method: 'DELETE' });
                loadAppointments();
            } catch (e) {
                alert('Failed to cancel');
            }
        }

        function joinCall(id) {
            const frame = document.getElementById('consultationFrame');
            frame.src = `room.html?appointment_id=${id}`;
            document.getElementById('menu-consultation').style.display = 'flex';
            navTo('consultation');
        }
        
        let waitingRoomInterval = null;
        let currentWaitingApptId = null;

        async function joinWaitingRoom(id) {
            currentWaitingApptId = id;
            try {
                const result = await apiCall(`/api/waiting-room/join/${id}`, { method: 'POST' });
                
                // Show modal
                const modal = document.getElementById('waitingRoomModal');
                const status = document.getElementById('waitingRoomStatus');
                const posCard = document.getElementById('waitingPositionCard');
                const posText = document.getElementById('waitingPosition');
                
                modal.classList.add('active');
                
                if (result.waiting) {
                    status.textContent = 'You are in the queue. Please wait for the doctor to admit you.';
                    posCard.style.display = 'block';
                    posText.textContent = result.position;
                    
                    // Start polling
                    startWaitingRoomPolling(id);
                } else {
                    status.textContent = result.message || 'Appointment not ready yet.';
                    posCard.style.display = 'none';
                    
                    // Even if not "waiting" yet (e.g. too early), we can poll or just let them stay
                    startWaitingRoomPolling(id);
                }
            } catch (e) {
                toast('Error: ' + e.message, 'error');
            }
        }

        function startWaitingRoomPolling(id) {
            if (waitingRoomInterval) clearInterval(waitingRoomInterval);
            
            waitingRoomInterval = setInterval(async () => {
                try {
                    const appt = await apiCall(`/api/appointments/${id}`);
                    
                    if (appt.status === 'ACTIVE') {
                        clearInterval(waitingRoomInterval);
                        document.getElementById('waitingRoomStatus').textContent = 'Doctor is ready! Redirecting...';
                        toast('Doctor is ready! Joining call...', 'success');
                        setTimeout(() => {
                            joinCall(id);
                        }, 1500);
                    } else if (appt.status === 'CANCELLED') {
                        clearInterval(waitingRoomInterval);
                        alert('This appointment was cancelled.');
                        closeModal('waitingRoomModal');
                        loadAppointments();
                    } else {
                        // Update position by re-joining (which is idempotent and returns current position)
                        const result = await apiCall(`/api/waiting-room/join/${id}`, { method: 'POST' });
                        if (result.waiting) {
                            document.getElementById('waitingPosition').textContent = result.position;
                        }
                    }
                } catch (e) {
                    console.error('Polling error:', e);
                }
            }, 5000);
        }

        async function leaveWaitingRoom() {
            if (waitingRoomInterval) clearInterval(waitingRoomInterval);
            if (currentWaitingApptId) {
                try {
                    await apiCall(`/api/waiting-room/leave/${currentWaitingApptId}`, { method: 'POST' });
                } catch(e) {}
            }
            closeModal('waitingRoomModal');
            currentWaitingApptId = null;
        }

        // ========== RECORDS ==========
        async function loadRecords() {
            try {
                const records = await apiCall('/api/records');
                const tbody = document.getElementById('recordsTable');
                
                if (!records.length) {
                    tbody.innerHTML = '<tr><td colspan="3" class="empty">No medical records</td></tr>';
                    return;
                }
                
                tbody.innerHTML = records.map(r => `
                    <tr>
                        <td>${new Date(r.created_at).toLocaleDateString()}</td>
                        <td>Doctor</td>
                        <td>${r.summary.substring(0, 50)}...</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('Load records error:', e);
            }
        }

        // ========== PRESCRIPTIONS ==========
        async function loadPrescriptions() {
            try {
                const scripts = await apiCall('/api/prescriptions');
                const tbody = document.getElementById('prescriptionsTable');
                
                if (!scripts.length) {
                    tbody.innerHTML = '<tr><td colspan="4" class="empty">No prescriptions</td></tr>';
                    return;
                }
                
                tbody.innerHTML = scripts.map(p => `
                    <tr>
                        <td>${new Date(p.created_at).toLocaleDateString()}</td>
                        <td>${p.medication}</td>
                        <td>${p.dosage}</td>
                        <td>${p.instructions || '-'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('Load prescriptions error:', e);
            }
        }

        // ========== PAYMENTS ==========
        async function loadPayments() {
            try {
                const balance = await apiCall('/api/credits/balance');
                document.getElementById('creditBalance').textContent = balance.credits;
                
                const txns = await apiCall('/api/credits/transactions');
                const tbody = document.getElementById('transactionsTable');
                
                if (!txns.length) {
                    tbody.innerHTML = '<tr><td colspan="4" class="empty">No transactions</td></tr>';
                } else {
                    tbody.innerHTML = txns.map(t => `
                        <tr>
                            <td>${new Date(t.created_at).toLocaleDateString()}</td>
                            <td>${t.description || t.transaction_type}</td>
                            <td style="color:${t.payment_status === 'completed' ? 'var(--accent)' : 'var(--text-light)'}">${t.amount}</td>
                            <td>${t.payment_status}</td>
                        </tr>
                    `).join('');
                }

                // Load T800 balance
                ['t800Balance','t800FeeDisplay'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.textContent = '...';
                });
                try {
                    const t800 = await apiCall('/api/somnia/agent/t800/balance');
                    document.getElementById('t800Balance').textContent = Number(t800.t800_balance).toFixed(2);
                    document.getElementById('t800FeeDisplay').textContent = t800.t800_fee_per_invocation || 10;
                } catch(e) {
                    document.getElementById('t800Balance').textContent = 'N/A';
                }

                try {
                    const t800info = await apiCall('/api/somnia/agent/t800/info');
                    if (t800info.t800_contract) document.getElementById('t800ContractDisplay').textContent = t800info.t800_contract;
                    if (t800info.router_contract) document.getElementById('t800RouterDisplay').textContent = t800info.router_contract;
                } catch(e) {
                    // fallback addresses already in HTML
                }

            } catch (e) {
                console.error('Load payments error:', e);
            }
        }

        async function purchaseCredits(amount) {
            if (!confirm(`Purchase ${amount} credits for R${amount}?`)) return;
            const btns = document.querySelectorAll('.purchase-btn[data-amount="' + amount + '"]');
            btns.forEach(b => { b.classList.add('loading'); b.disabled = true; });
            try {
                const result = await apiCall('/api/credits/purchase', {
                    method: 'POST',
                    body: JSON.stringify({ amount })
                });
                currentUser.credits = result.new_balance;
                updateCredits();
                loadPayments();
                toast(`Successfully purchased ${amount} credits ✓`, 'success');
            } catch (e) {
                toast('Purchase failed: ' + e.message, 'error');
            }
            btns.forEach(b => { b.classList.remove('loading'); b.disabled = false; });
        }

        async function claimT800() {
            const btn = document.getElementById('claimT800Btn');
            btn.classList.add('loading'); btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span><span class="btn-text">Claiming...</span>';
            try {
                const result = await apiCall('/api/somnia/agent/t800/faucet', { method: 'POST' });
                document.getElementById('claimT800Result').style.display = 'block';
                document.getElementById('claimT800Result').innerHTML =
                    `<span style="color:var(--accent)">✓ ${result.message}</span> Balance: ${result.t800_balance} T800`;
                document.getElementById('t800Balance').textContent = Number(result.t800_balance).toFixed(2);
                btn.textContent = 'Claimed ✓';
            } catch (e) {
                document.getElementById('claimT800Result').style.display = 'block';
                document.getElementById('claimT800Result').innerHTML =
                    `<span style="color:var(--danger)">✗ ${e.message}</span>`;
                btn.classList.remove('loading'); btn.disabled = false; btn.innerHTML = '<span class="spinner"></span><span class="btn-text">Claim T800</span>';
            }
        }

        // ========== HEALTH TOOLS ==========
        async function loadCreditCosts() {
            showSkeleton('creditCostsList', 3);
            try {
                const costs = await apiCall('/api/somnia/agent/credit-costs');
                const list = document.getElementById('creditCostsList');
                list.innerHTML = '<table class="table"><thead><tr><th>Feature</th><th>Credits</th></tr></thead><tbody>' +
                    Object.entries(costs).map(([k, v]) =>
                        `<tr><td>${k.replace(/_/g, ' ')}</td><td><strong>${v}</strong></td></tr>`
                    ).join('') +
                    '</tbody></table>';
            } catch (e) {
                document.getElementById('creditCostsList').innerHTML = '<div class="empty">Could not load costs</div>';
            }
            // Load STT cost independently (don't block credit costs on STT)
            try {
                const stt = await apiCall('/api/somnia/agent/stt/cost');
                document.getElementById('sttCostBadge').style.display = 'block';
                document.getElementById('sttCostText').textContent =
                    `~${Number(stt.total_stt).toFixed(4)} STT per invocation (1 STT = 30 T800)`;
            } catch (e) {
                document.getElementById('sttCostBadge').style.display = 'block';
                document.getElementById('sttCostText').textContent = '~0.57 STT per invocation (1 STT = 30 T800)';
            }
        }

        let pollInterval = null;

        async function runSymptomCheck() {
            const input = document.getElementById('symptomInput').value.trim();
            if (!input) { toast('Please describe your symptoms', 'warning'); return; }
            const resultDiv = document.getElementById('symptomResult');
            resultDiv.classList.remove('hidden');
            resultDiv.innerHTML = '<div class="poll-progress"><div class="poll-progress-fill" style="width:5%"></div></div><div style="font-size:0.85rem;color:var(--text-light);margin-top:4px;">Submitting to Somnia LLM Agent...</div>';
            try {
                const resp = await apiCall('/api/somnia/agent/symptom-check', {
                    method: 'POST',
                    body: JSON.stringify({ symptoms: input })
                });
                resultDiv.textContent = 'Request submitted (ID: ' + resp.request_id + '). Polling for result...';
                let pollStart = Date.now();
                pollInterval = setInterval(async () => {
                    if (Date.now() - pollStart > 120000) {
                        clearInterval(pollInterval);
                        resultDiv.textContent = 'Timed out waiting for agent response. Please try again.';
                        return;
                    }
                    try {
                        const status = await apiCall('/api/somnia/agent/result/' + resp.request_id);
                        if (status.status === 'success') {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Result:</strong><br>' + status.result;
                        } else if (['failed', 'timedout', 'archived'].includes(status.status)) {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Agent ' + status.status + ':</strong> ' + (status.result || 'No result available');
                        } else {
                            resultDiv.textContent = 'Waiting for agent response (ID: ' + resp.request_id + ')...';
                        }
                    } catch(e) {
                        resultDiv.textContent = 'Polling: ' + e.message;
                    }
                }, 3000);
            } catch (e) {
                if (e.message.includes('402') || e.message.includes('insufficient credits')) {
                    resultDiv.textContent = 'Insufficient credits. Please purchase more credits.';
                } else {
                    resultDiv.textContent = 'Error: ' + e.message;
                }
            }
        }

        async function runDrugCheck() {
            const input = document.getElementById('drugInput').value.trim();
            if (!input) { toast('Enter medications separated by commas', 'warning'); return; }
            const resultDiv = document.getElementById('drugResult');
            resultDiv.classList.remove('hidden');
            resultDiv.textContent = 'Submitting to Somnia LLM Agent...';
            try {
                const medications = input.split(',').map(m => m.trim()).filter(Boolean);
                const resp = await apiCall('/api/somnia/agent/drug-interaction', {
                    method: 'POST',
                    body: JSON.stringify({ medications })
                });
                resultDiv.textContent = 'Request submitted (ID: ' + resp.request_id + '). Polling for result...';
                let pollStart = Date.now();
                pollInterval = setInterval(async () => {
                    if (Date.now() - pollStart > 120000) {
                        clearInterval(pollInterval);
                        resultDiv.textContent = 'Timed out waiting for agent response. Please try again.';
                        return;
                    }
                    try {
                        const status = await apiCall('/api/somnia/agent/result/' + resp.request_id);
                        if (status.status === 'success') {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Interaction Result:</strong><br>' + status.result;
                        } else if (['failed', 'timedout', 'archived'].includes(status.status)) {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Agent ' + status.status + ':</strong> ' + (status.result || 'No result');
                        } else {
                            resultDiv.textContent = 'Waiting for response...';
                        }
                    } catch(e) {
                        resultDiv.textContent = 'Polling: ' + e.message;
                    }
                }, 3000);
            } catch (e) {
                if (e.message.includes('402')) {
                    resultDiv.textContent = 'Insufficient credits.';
                } else {
                    resultDiv.textContent = 'Error: ' + e.message;
                }
            }
        }

        async function _pollResult(resp, resultDiv) {
            resultDiv.innerHTML = '<div class="poll-progress"><div class="poll-progress-fill" style="width:5%"></div></div><div class="poll-status" style="font-size:0.85rem;color:var(--text-light);margin-top:4px;">Submitted (ID: ' + resp.request_id + '). Polling...</div>';
            let pollStart = Date.now();
            const maxPoll = 120000;
            const interval = setInterval(async () => {
                const elapsed = Date.now() - pollStart;
                const pct = Math.min(95, (elapsed / maxPoll) * 100);
                const bar = resultDiv.querySelector('.poll-progress-fill');
                const status = resultDiv.querySelector('.poll-status');
                if (bar) bar.style.width = pct + '%';
                if (status) status.textContent = 'Waiting for agent response... (' + Math.floor(elapsed / 1000) + 's)';
                if (elapsed > maxPoll) {
                    clearInterval(interval);
                    resultDiv.innerHTML = '<strong>Timed out</strong> — no response after 120s. Please try again.';
                    return;
                }
                try {
                    const st = await apiCall('/api/somnia/agent/result/' + resp.request_id);
                    if (st.status === 'success') {
                        clearInterval(interval);
                        if (bar) bar.style.width = '100%';
                        resultDiv.innerHTML = '<strong>Result:</strong><br>' + st.result;
                    } else if (['failed', 'timedout', 'archived'].includes(st.status)) {
                        clearInterval(interval);
                        resultDiv.innerHTML = '<strong>Agent ' + st.status + ':</strong> ' + (st.result || 'No result');
                    }
                } catch(e) {
                    if (status) status.textContent = 'Polling... (' + Math.floor(elapsed / 1000) + 's)';
                }
            }, 3000);
        }

        async function runSymptomCheckStt() {
            const input = document.getElementById('symptomInput').value.trim();
            if (!input) { toast('Please describe your symptoms', 'warning'); return; }
            const resultDiv = document.getElementById('symptomResult');
            resultDiv.classList.remove('hidden');
            resultDiv.textContent = 'Submitting via STT...';
            try {
                const resp = await apiCall('/api/somnia/agent/stt/invoke', {
                    method: 'POST',
                    body: JSON.stringify({ agent_type: 'llm', prompt: 'Patient symptoms: ' + input + '. Provide triage assessment.', system_prompt: 'You are a medical triage assistant.' })
                });
                _pollResult(resp, resultDiv);
            } catch (e) {
                resultDiv.textContent = 'Error: ' + e.message;
            }
        }

        async function runDrugCheckStt() {
            const input = document.getElementById('drugInput').value.trim();
            if (!input) { toast('Enter medications', 'warning'); return; }
            const resultDiv = document.getElementById('drugResult');
            resultDiv.classList.remove('hidden');
            resultDiv.textContent = 'Submitting via STT...';
            try {
                const medications = input.split(',').map(m => m.trim()).filter(Boolean);
                const resp = await apiCall('/api/somnia/agent/stt/invoke', {
                    method: 'POST',
                    body: JSON.stringify({ agent_type: 'llm', prompt: 'Check interactions between these medications: ' + medications.join(', '), system_prompt: 'You are a clinical pharmacist.' })
                });
                _pollResult(resp, resultDiv);
            } catch (e) {
                resultDiv.textContent = 'Error: ' + e.message;
            }
        }

        async function runHealthTips() {
            const input = document.getElementById('tipsInput').value.trim();
            if (!input) { toast('Enter a health topic', 'warning'); return; }
            const resultDiv = document.getElementById('tipsResult');
            resultDiv.classList.remove('hidden');
            resultDiv.innerHTML = '<div class="poll-progress"><div class="poll-progress-fill" style="width:5%"></div></div><div style="font-size:0.85rem;color:var(--text-light);margin-top:4px;">Submitting to Somnia LLM Agent...</div>';
            try {
                const resp = await apiCall('/api/somnia/agent/health-tips', {
                    method: 'POST',
                    body: JSON.stringify({ topic: input })
                });
                resultDiv.textContent = 'Request submitted (ID: ' + resp.request_id + '). Polling...';
                let pollStart = Date.now();
                pollInterval = setInterval(async () => {
                    if (Date.now() - pollStart > 120000) {
                        clearInterval(pollInterval);
                        resultDiv.textContent = 'Timed out waiting for agent response. Please try again.';
                        return;
                    }
                    try {
                        const status = await apiCall('/api/somnia/agent/result/' + resp.request_id);
                        if (status.status === 'success') {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Health Tips:</strong><br>' + status.result;
                        } else if (['failed', 'timedout', 'archived'].includes(status.status)) {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Agent ' + status.status + ':</strong> ' + (status.result || 'No result');
                        }
                    } catch(e) {
                        resultDiv.textContent = 'Polling: ' + e.message;
                    }
                }, 3000);
            } catch (e) {
                if (e.message.includes('402')) {
                    resultDiv.textContent = 'Insufficient credits.';
                } else {
                    resultDiv.textContent = 'Error: ' + e.message;
                }
            }
        }

        async function runGenerateSummary() {
            const input = document.getElementById('summaryInput').value.trim();
            if (!input) { toast('Enter consultation notes', 'warning'); return; }
            const resultDiv = document.getElementById('summaryResult');
            resultDiv.classList.remove('hidden');
            resultDiv.innerHTML = '<div class="poll-progress"><div class="poll-progress-fill" style="width:5%"></div></div><div style="font-size:0.85rem;color:var(--text-light);margin-top:4px;">Submitting to Somnia LLM Agent...</div>';
            try {
                const resp = await apiCall('/api/somnia/agent/generate-summary', {
                    method: 'POST',
                    body: JSON.stringify({ consultation_notes: input })
                });
                resultDiv.textContent = 'Request submitted (ID: ' + resp.request_id + '). Polling...';
                let pollStart = Date.now();
                pollInterval = setInterval(async () => {
                    if (Date.now() - pollStart > 120000) {
                        clearInterval(pollInterval);
                        resultDiv.textContent = 'Timed out waiting for agent response. Please try again.';
                        return;
                    }
                    try {
                        const status = await apiCall('/api/somnia/agent/result/' + resp.request_id);
                        if (status.status === 'success') {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Summary:</strong><br>' + status.result;
                        } else if (['failed', 'timedout', 'archived'].includes(status.status)) {
                            clearInterval(pollInterval);
                            resultDiv.innerHTML = '<strong>Agent ' + status.status + ':</strong> ' + (status.result || 'No result');
                        }
                    } catch(e) {
                        resultDiv.textContent = 'Polling: ' + e.message;
                    }
                }, 3000);
            } catch (e) {
                if (e.message.includes('402')) {
                    resultDiv.textContent = 'Insufficient credits.';
                } else {
                    resultDiv.textContent = 'Error: ' + e.message;
                }
            }
        }

        // ========== PROFILE ==========
        function loadProfile() {
            document.getElementById('profileName').value = currentUser.name;
            document.getElementById('profileEmail').value = currentUser.email;
            document.getElementById('profilePhone').value = currentUser.phone || '';
            document.getElementById('profileRole').value = currentUser.role;
        }

        function saveProfile() {
            toast('Profile saved ✓', 'success');
        }

        // ========== BOOKING ==========
        function toggleBookingLocation() {
            const type = document.getElementById('bookType').value;
            const group = document.getElementById('bookLocationGroup');
            group.style.display = (type === 'INPERSON') ? 'block' : 'none';
        }

        async function openBookModal(docId) {
            try {
                const doctor = await apiCall(`/api/doctors/${docId}`);
                selectedDoctor = doctor;
                document.getElementById('bookDoctorInfo').innerHTML = `
                    <div style="background:var(--light);padding:1rem;border-radius:8px;margin-bottom:1rem">
                        <strong>${doctor.name}</strong><br>
                        <span>${doctor.specialty} - ${doctor.area}</span>
                    </div>
                `;
                const bookCostEl = document.getElementById('bookCost');
                if (bookCostEl) bookCostEl.textContent = doctor.consultation_fee;
                
                const t800Cost = doctor.consultation_fee * 10;
                const bookCostT800El = document.getElementById('bookCostT800');
                if (bookCostT800El) bookCostT800El.textContent = t800Cost;

                // Check user's T800 balance and update checkbox state
                let t800Bal = 0;
                try {
                    const t800 = await apiCall('/api/somnia/agent/t800/balance');
                    t800Bal = Number(t800.t800_balance) || 0;
                } catch(e) {}
                const payWithT800 = document.getElementById('payWithT800');
                const t800Hint = document.getElementById('t800BookHint');
                if (payWithT800) payWithT800.checked = false;
                
                if (t800Bal >= t800Cost) {
                    if (payWithT800) {
                        payWithT800.disabled = false;
                        payWithT800.title = `You have ${t800Bal.toFixed(0)} T800 — enough to pay`;
                    }
                    if (t800Hint) {
                        t800Hint.textContent = `✓ You have ${t800Bal.toFixed(0)} T800`;
                        t800Hint.style.color = 'var(--accent)';
                    }
                } else {
                    if (payWithT800) {
                        payWithT800.disabled = true;
                        payWithT800.title = `Need ${t800Cost} T800, you have ${t800Bal.toFixed(0)}. Claim free T800 from Payments page`;
                    }
                    if (t800Hint) {
                        t800Hint.textContent = `Need ${t800Cost} T800 — you have ${t800Bal.toFixed(0)} (get free T800 in Payments)`;
                        t800Hint.style.color = 'var(--text-light)';
                    }
                }

                document.getElementById('bookModal').classList.add('active');
            } catch(e) {
                toast('Error loading doctor: ' + e.message, 'error');
            }
        }

    async function confirmBooking() {
        const type = document.getElementById('bookType').value;
        const datetime = document.getElementById('bookDateTime').value;
        const reason = document.getElementById('bookReason').value;
        const location = document.getElementById('bookLocation').value;
        
        const payMethod = document.querySelector('input[name="payMethod"]:checked')?.id;
        
        if (!datetime) { toast('Please select date and time', 'warning'); return; }
        if (type === 'INPERSON' && !location.trim()) { toast('Please enter a meeting address for in-person visit', 'warning'); return; }

        const bookBtn = document.querySelector('#bookModal .btn-primary');
        if (bookBtn) { bookBtn.classList.add('loading'); bookBtn.disabled = true; }
        
        try {
            const appt = await apiCall('/api/appointments', {
                method: 'POST',
                body: JSON.stringify({
                    doctor_id: selectedDoctor.id,
                    timestamp: new Date(datetime).toISOString(),
                    appointment_type: type,
                    reason: reason,
                    location: location,
                    payment_method: payMethod === 'payWithYoco' ? 'yoco' : 
                                    payMethod === 'payWithSomnia' ? 'somnia' : 
                                    payMethod === 'payWithT800' ? 't800' : 'credits',
                    triage_data: JSON.stringify({
                        duration: document.getElementById('bookDuration').value,
                        severity: document.getElementById('bookSeverity').value
                    })
                })
            });

            // 1. Give T800 Reward
            toast('Booking reward: T800 tokens sent to your wallet! 🎁', 'success');

            // 2. Handle Selected Payment Method
            if (payMethod === 'payWithYoco') {
                const yoco = await apiCall('/api/yoco/initiate', {
                    method: 'POST',
                    body: JSON.stringify({
                        appointment_id: appt.id,
                        amount_zar: selectedDoctor.consultation_fee
                    })
                });
                toast('Redirecting to Yoco Checkout...', 'info');
                
                // Redirect immediately. Whether it's a live Yoco URL or our fallback ?mock_yoco URL,
                // we must redirect to break this flow, otherwise it falls through to the SOAP redirect below.
                if (yoco.checkout_url) {
                    window.location.href = yoco.checkout_url;
                    return; // Crucial: Stop execution here!
                }

            } else if (payMethod === 'payWithSomnia') {
                toast('Initiating Somnia On-Chain Escrow...', 'info');
                const escrowResult = await apiCall(`/api/appointments/${appt.id}/pay-with-somnia`, {
                    method: 'POST'
                });
                toast('STT payment deposited on-chain ✓', 'success');

            } else if (payMethod === 'payWithT800') {
                toast('Initiating T800 token payment...', 'info');
                await apiCall(`/api/appointments/${appt.id}/pay-with-t800`, {
                    method: 'POST'
                });
                toast('T800 payment sent successfully ✓', 'success');

            } else {
                toast('Appointment booked successfully ✓', 'success');
            }
            
            // 3. Cleanup UI
            closeModal('bookModal');
            document.getElementById('bookDateTime').value = '';
            document.getElementById('bookReason').value = '';
            document.getElementById('bookLocation').value = '';
            
            // 4. Redirect to Questionnaire (SOAP)
            setTimeout(() => {
                window.location.href = `patient_questionnaire.html?appointment_id=${appt.id}&return=index.html`;
            }, 1000);

            // 5. Update State
            updateCredits();
            updateSomniaBalance();
            initDashboard();
            if (typeof loadPayments === 'function') loadPayments();
            if (typeof loadEscrow === 'function') loadEscrow();

        } catch (e) {
            toast('Booking failed: ' + e.message, 'error');
        }
        if (bookBtn) { bookBtn.classList.remove('loading'); bookBtn.disabled = false; }
    }

        async function loadEscrow() {
            const container = document.getElementById('escrowList');
            container.innerHTML = '<div class="skeleton-card" style="padding:12px"><div class="skeleton skeleton-line" style="width:100%"></div><div class="skeleton skeleton-line med"></div><div class="skeleton skeleton-line short"></div><div class="skeleton skeleton-line med"></div></div>';
            try {
                const appts = await apiCall('/api/appointments');
                const somniaAppts = appts.filter(a => a.escrow_status && a.escrow_status !== 'NONE');
                
                if (somniaAppts.length === 0) {
                    container.innerHTML = '<div class="empty"><i class="fas fa-link" style="font-size:2rem;margin-bottom:0.5rem;opacity:0.3"></i><br>No on-chain escrow transactions</div>';
                    return;
                }
                
                container.innerHTML = `
                    <div style="overflow-x:auto">
                    <table class="table">
                        <thead><tr><th>ID</th><th>Doctor</th><th>Amount</th><th>Method</th><th>Status</th></tr></thead>
                        <tbody>
                            ${somniaAppts.map(a => {
                                const status = (a.escrow_status || '').toLowerCase();
                                const fee = a.consultation_fee || a.base_price || a.price_credits || 0;
                                const method = a.payment_method || 'stt';
                                const amountDisplay = method === 't800' ? fee * 10 + ' T800' : fee + ' STT';
                                const statusClass = status === 'released' ? 'status-released' : status === 'funded' ? 'status-funded' : status === 'pending' ? 'status-pending' : 'status-' + status;
                                return `<tr>
                                    <td>#${a.id}</td>
                                    <td>${a.doctor_name || '—'}</td>
                                    <td>${amountDisplay}</td>
                                    <td><span style="font-size:0.75rem;padding:2px 6px;border-radius:4px;background:${method==='t800'?'#05966920':'#0052cc20'};color:${method==='t800'?'#059669':'var(--primary)'};font-weight:600">${method.toUpperCase()}</span></td>
                                    <td><span class="status ${statusClass}">${a.escrow_status}</span></td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                    </div>
                `;
            } catch (e) {
                container.innerHTML = '<div class="empty">Failed to load escrow data</div>';
            }
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }

        // Message listener for iframe communication
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'navTo') {
                navTo(event.data.page);
            }
            if (event.data && event.data.type === 'callEnded') {
                document.getElementById('consultationFrame').src = 'about:blank';
                document.getElementById('menu-consultation').style.display = 'none';
                navTo('dashboard');
                loadAppointments();
            }
        });

        // Check session on load
        if (authToken) {
            apiCall('/api/auth/me').then(user => {
                currentUser = user;
                showApp();
            }).catch(() => {
                localStorage.removeItem('token');
            });
        }
    