
        const BASE_URL = window.API_BASE || '';
        let authToken = localStorage.getItem('token');
        let currentAppointments = [];

        // ========== AUTH & INIT ==========
        async function init() {
            if (!authToken) { window.location.href = 'login.html'; return; }
            try {
                const user = await apiCall('/api/auth/me');
                if (user.role !== 'DOCTOR') { window.location.href = 'index.html'; return; }
                document.getElementById('displayDocName').textContent = user.name;
                
                // Set doc details in document generator
                document.getElementById('docHeaderName').textContent = user.name;
                document.getElementById('docSignature').textContent = user.name;
                
                loadStats();
                loadProfile();
                updateBalance();
            } catch (e) { handleLogout(); }
        }

        function handleLogout() { localStorage.removeItem('token'); window.location.href = 'login.html'; }

        async function apiCall(endpoint, options = {}) {
            const headers = { 'Content-Type': 'application/json' };
            if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
            const res = await fetch(BASE_URL + endpoint, { ...options, headers });
            if (res.status === 401) { handleLogout(); throw new Error('Session Expired'); }
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'API Error');
            return data;
        }

        // ========== DATA LOADERS ==========
        async function loadStats() {
            try {
                const appts = await apiCall('/api/appointments');
                currentAppointments = appts;
                const earnings = await apiCall('/api/credits/doctor/earnings');
                
                document.getElementById('countPending').textContent = appts.filter(a => a.status === 'SCHEDULED').length;
                document.getElementById('countActive').textContent = appts.filter(a => a.status === 'ACTIVE').length;
                document.getElementById('countCompleted').textContent = appts.filter(a => a.status === 'COMPLETED').length;
                document.getElementById('countCredits').textContent = 'R ' + (earnings.total_earnings);

                renderPending(appts.filter(a => a.status === 'SCHEDULED'));
                renderAppointments(appts);
            } catch (e) { console.error(e); }
        }

        function renderPending(list) {
            const container = document.getElementById('pendingList');
            if (!list.length) { container.innerHTML = '<div style="padding:2rem; text-align:center; color:var(--em-text-muted);">Queue Empty</div>'; return; }
            container.innerHTML = `<table class="em-table">` + list.map(a => `
                <tr>
                    <td><strong>${a.patient_name}</strong><br><small>${a.reason || 'General Consult'}</small></td>
                    <td style="text-align:right;">
                        <button class="btn btn-sm btn-ghost" onclick="viewTriageById(${a.id})">Triage</button>
                        <button class="btn btn-sm btn-primary" onclick="acceptAppointment(${a.id})">Accept</button>
                    </td>
                </tr>
            `).join('') + `</table>`;
        }

        function renderAppointments(list) {
            const tbody = document.querySelector('#appointmentsTable tbody');
            tbody.innerHTML = list.map(a => `
                <tr>
                    <td><strong>${a.patient_name}</strong></td>
                    <td><span class="script-badge">${a.appointment_type}</span> ${a.location || ''}</td>
                    <td><span style="font-weight:700; font-size:0.7rem;">${a.status}</span></td>
                    <td><button class="btn btn-sm btn-ghost" onclick="viewTriageById(${a.id})">Review</button></td>
                </tr>
            `).join('');
        }

        function viewTriageById(id) {
            const appt = currentAppointments.find(a => a.id === id);
            if (!appt) return;
            document.getElementById('triageOverlay').classList.remove('hidden');
            document.getElementById('emailTriageBtn').onclick = () => triggerEmail(`Report: ${appt.patient_name}`, "Summary...");
            
            const rawDiv = document.getElementById('triageRawData');
            if (appt.triage_data) {
                const d = JSON.parse(appt.triage_data);
                rawDiv.innerHTML = Object.entries(d).map(([k,v]) => {
                    if (k === 'questionnaire' && typeof v === 'object' && v !== null) {
                        // Calculate age if DOB is present
                        let ageHtml = '';
                        if (v.dob) {
                            const dob = new Date(v.dob);
                            const diff = Date.now() - dob.getTime();
                            const age = new Date(diff).getUTCFullYear() - 1970;
                            ageHtml = `<div style="margin-bottom:0.5rem; color:var(--em-blue); font-weight:700;">Age: ${age} years</div>`;
                        }

                        let qHtml = '<div style="background:var(--em-bg); padding:1rem; border-radius:8px; border:1px solid var(--em-border);">';
                        qHtml += ageHtml;
                        qHtml += Object.entries(v).map(([qk, qv]) => `<div style="margin-bottom:0.5rem"><strong>${qk.replace(/_/g, ' ')}:</strong> ${qv}</div>`).join('');
                        qHtml += '</div>';
                        return `<div style="margin-bottom:1.5rem;"><strong style="font-size:0.7rem; text-transform:uppercase; color:var(--em-blue);">📋 Full Medical Questionnaire</strong>${qHtml}</div>`;
                    }
                    return `<div style="margin-bottom:0.75rem;"><strong style="font-size:0.7rem; text-transform:uppercase; color:var(--em-text-muted);">${k.replace(/_/g, ' ')}</strong><p>${v}</p></div>`;
                }).join('');
            }
            
            const aiDiv = document.getElementById('triageAiResults');
            if (appt.triage_tools_results) {
                const res = JSON.parse(appt.triage_tools_results);
                aiDiv.innerHTML = Object.entries(res).map(([k,v]) => `<div style="border-left:3px solid var(--em-blue); padding-left:1rem; margin-bottom:1rem;"><strong>${k}</strong><p style="font-size:0.85rem;">${v}</p></div>`).join('');
            }

            // Add button to open medical tools
            const actionContainer = document.createElement('div');
            actionContainer.style.marginTop = '2rem';
            actionContainer.innerHTML = `<button class="btn btn-primary" onclick="openTools(${id})"><i class="fas fa-file-medical"></i> Issue Document (Note/Script/Referral)</button>`;
            aiDiv.appendChild(actionContainer);
        }

        function closeTriage() { document.getElementById('triageOverlay').classList.add('hidden'); }

        // ========== MEDICAL TOOLS (Notes, Scripts, Referrals) ==========
        let activeAppointmentId = null;

        function openTools(appointmentId) {
            activeAppointmentId = appointmentId;
            const appt = currentAppointments.find(a => a.id === appointmentId);
            document.getElementById('toolsModal').classList.remove('hidden');
            document.getElementById('docDate').textContent = new Date().toLocaleDateString('en-ZA');
            document.getElementById('documentPreview').classList.add('hidden');
            document.getElementById('scribeContext').value = appt ? `Consultation for ${appt.patient_name} regarding ${appt.reason || 'medical assessment'}.` : '';
        }

        function closeTools() {
            document.getElementById('toolsModal').classList.add('hidden');
        }

        async function generateDocument(type) {
            const context = document.getElementById('scribeContext').value;
            const appt = currentAppointments.find(a => a.id === activeAppointmentId);
            const patientName = appt ? appt.patient_name : "[Patient Name]";
            
            // Get doctor profile details for credentials
            const profile = await apiCall('/api/profile/doctor');
            document.getElementById('docSpecialty').textContent = profile.specialty || "Medical Practitioner";
            document.getElementById('docHpcsa').textContent = profile.hpcsa_number || "Verified";
            document.getElementById('docPr').textContent = profile.practice_number || "Registered";
            
            notify(`Generating ${type}...`, 'info');
            
            let content = "";
            const today = new Date().toLocaleDateString('en-ZA');
            document.getElementById('docTitle').textContent = type;

            if (type === 'Sick Note') {
                content = `TO WHOM IT MAY CONCERN,\n\nThis is to certify that I have examined ${patientName} on ${today}.\n\nBased on my clinical findings, it is my professional opinion that the patient is unfit for work/school duties from ${today} to ${new Date(Date.now() + 172800000).toLocaleDateString('en-ZA')} inclusive.\n\nThe patient is expected to be fit to resume duties on ${new Date(Date.now() + 259200000).toLocaleDateString('en-ZA')}.\n\nNature of illness: Medical Condition (Consultation Confidentiality Maintained).\n\nClinical Context: ${context}`;
            } else if (type === 'Prescription') {
                content = `PATIENT: ${patientName}\nDATE: ${today}\n\nRx\n\n1. Medication A (e.g. Amoxicillin 500mg)\n   Sig: 1 tab PO TID x 5 days\n   Mitte: 15 tabs\n\n2. Medication B (e.g. Paracetamol 500mg)\n   Sig: 2 tabs PO QID PRN for pain\n   Mitte: 20 tabs\n\nRefills: 0\n\nNotes: ${context}`;
            } else if (type === 'Referral Letter') {
                content = `RE: REFERRAL FOR ${patientName.toUpperCase()}\n\nDear Colleague,\n\nI am referring this patient to your specialized care for further evaluation and management.\n\nSummary of Findings:\n- Patient presented with symptoms as described in the consultation.\n- Initial assessment suggests specialized intervention may be required.\n\nContext & Notes: ${context}\n\nThank you for your assistance in the ongoing care of this patient.`;
            }

            document.getElementById('documentContent').textContent = content;
            document.getElementById('documentPreview').classList.remove('hidden');
        }

        async function updateBalance() {
            try {
                const bal = await apiCall('/api/somnia/escrow/wallet/balance');
                document.getElementById('sttBalance').textContent = parseFloat(bal.balance_eth).toFixed(2) + ' STT';
            } catch (e) {}
        }

        async function loadProfile() {
            try {
                const profile = await apiCall('/api/profile/doctor');
                const btn = document.getElementById('gigToggleBtn');
                btn.textContent = profile.is_online ? 'Disable Home Visits' : 'Enable Home Visits';
                btn.className = profile.is_online ? 'btn btn-danger' : 'btn btn-primary';
            } catch (e) {}
        }

        async function toggleOnline() {
            try {
                const profile = await apiCall('/api/profile/doctor');
                await apiCall('/api/profile/doctor/gig-mode', { method: 'POST', body: JSON.stringify({ is_online: !profile.is_online }) });
                loadProfile();
            } catch (e) { notify(e.message, 'error'); }
        }

        const CLINICAL_SCRIPTS = [
            { id: 1, title: "Triage Classification", source: "NICE CKS", content: "Acuity: Red (Emergent), Yellow (Urgent), Green (Routine)." },
            { id: 2, title: "NEWS2 Scoring", source: "RCP", content: "National Early Warning Score for acute illness assessment." },
            { id: 3, title: "WHO IMAI Care", source: "WHO", content: "Integrated Management of Adult Illness for primary settings." }
        ];

        function loadScripts() {
            const container = document.getElementById('scriptsContainer');
            container.innerHTML = CLINICAL_SCRIPTS.map(s => `
                <div class="em-card" style="margin-bottom:0;">
                    <div class="card-body">
                        <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;"><span class="script-badge">${s.source}</span><i class="fas fa-envelope" style="cursor:pointer;" onclick="triggerEmail('${s.title}','${s.content}')"></i></div>
                        <h4 style="margin-bottom:0.5rem;">${s.title}</h4>
                        <p style="font-size:0.85rem; color:var(--em-text-muted);">${s.content}</p>
                    </div>
                </div>
            `).join('');
        }

        function filterScripts() {
            const q = document.getElementById('scriptSearch').value.toLowerCase();
            const filtered = CLINICAL_SCRIPTS.filter(s => s.title.toLowerCase().includes(q));
            // ... (Simple filter logic)
        }

        async function triggerEmail(sub, body) {
            const email = prompt("Email Address:", "doctor@example.com");
            if (!email) return;
            try {
                notify("Transmitting...", "info");
                await apiCall('/api/somnia/agent/email', { method: 'POST', body: JSON.stringify({ recipient: email, subject: sub, body: body }) });
                notify("Email Sent", "success");
            } catch (e) { notify("Failed", "error"); }
        }

        function notify(msg, type) {
            const t = document.createElement('div');
            t.style.cssText = `padding:1rem 1.5rem; background:white; border-left:4px solid ${type==='error'?'red':'var(--em-blue)'}; border-radius:8px; box-shadow:0 10px 30px rgba(0,0,0,0.1); margin-top:0.5rem; font-weight:600; font-size:0.85rem;`;
            t.textContent = msg;
            document.getElementById('toastContainer').appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }

        function navigateTo(t) {
            document.querySelectorAll('section[id^="view-"]').forEach(s => s.classList.add('hidden'));
            document.getElementById('view-' + t).classList.remove('hidden');
            document.querySelectorAll('.nav-item').forEach(m => m.classList.remove('active'));
            document.querySelector(`[data-target="${t}"]`)?.classList.add('active');
            if (t === 'scripts') loadScripts();
        }

        document.querySelectorAll('.nav-item[data-target]').forEach(i => i.onclick = () => navigateTo(i.dataset.target));

        init();
    