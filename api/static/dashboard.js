// AiContaFiscalRD - Dashboard Logic
// Extraído automáticamente de index.html

const API_URL = (window.API_URL || window.location.origin) + '/api';
    let hasData = false;
    let hasDataFromPipeline = false;

    /* ── Navigation ── */
    function switchTab(tab) {
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        document.getElementById('tab-' + tab).classList.add('active');
        document.querySelectorAll('.nav-item').forEach(l => l.classList.remove('active'));
        document.getElementById('nav-' + tab).classList.add('active');
    }

    /* ── Client Modal ── */
    function toggleClientModal() {
        const m = document.getElementById('client-modal');
        const isOpen = m.classList.contains('open');
        m.classList.toggle('open', !isOpen);
        if (!isOpen) loadClients();
    }
    
    async function createClient() {
        const rnc = document.getElementById('new-client-rnc').value.trim();
        const name = document.getElementById('new-client-name').value.trim();
        const btn = document.getElementById('btn-create-client');

        if (!rnc || !name) return alert("Por favor complete RNC y Razón Social");

        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-rounded animate-spin">cyclone</span> Guardando...`;

        try {
            const resp = await safeFetch(`${API_URL}/clientes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rnc, razon_social: name })
            });
            const data = await resp.json();

            if (resp.ok) {
                // Seleccionar al nuevo cliente y recargar
                selectClient(data.id, name, rnc);
            } else if (resp.status === 400 && data.id) {
                // El cliente ya existe, lo seleccionamos directamente
                selectClient(data.id, data.razon_social || name, rnc);
            } else {
                alert("Error: " + (data.detail || data.message || "No se pudo registrar"));
            }
        } catch (e) {
            console.error(e);
            alert("Error de red al registrar cliente");
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<span class="material-symbols-rounded">save</span> Guardar y Seleccionar`;
        }
    }

    async function loadClients() {
        const list = document.getElementById('client-list');
        list.innerHTML = '<div class="table-empty">Cargando...</div>';
        try {
            const resp = await safeFetch(`${API_URL}/clientes`);
            const data = await resp.json();
            list.innerHTML = data.clientes.map(c => `
                <div class="client-item" onclick="selectClient('${c.id}', '${c.razon_social}', '${c.rnc}')">
                    <div>
                        <div class="client-name">${c.razon_social}</div>
                        <div class="client-rnc">RNC: ${c.rnc}</div>
                    </div>
                    <span class="material-symbols-rounded">arrow_forward</span>
                </div>`).join('');
        } catch(e) {
            list.innerHTML = '<div class="table-empty">Error al cargar clientes.</div>';
        }
    }

    function selectClient(id, name, rnc) {
        localStorage.setItem('cid', id);
        localStorage.setItem('cname', name);
        localStorage.setItem('crnc', rnc);
        window.location.reload();
    }

    /* ── Init ── */
    window.onload = () => {
        const id = localStorage.getItem('cid');
        if (id) {
            document.getElementById('current-client-name').textContent = localStorage.getItem('cname');
            // Show dashboard, load data
            document.getElementById('empty-state').style.display    = 'none';
            document.getElementById('dashboard-real').style.display = 'block';
            updateDashboard();
        } else {
            // Show empty state
            document.getElementById('empty-state').style.display    = 'flex';
            document.getElementById('dashboard-real').style.display = 'none';
        }

        // Auto first message from bot
        appendBotMessage('Hola. Sube tu 606 y te digo qué riesgo tienes antes de enviarlo a la DGII.');

        // Enter to send
        document.getElementById('chat-input').addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
        });

        // Drag & Drop dropzone
        const dz = document.getElementById('dropzone');
        if (dz) {
            dz.addEventListener('dragover',  e => { e.preventDefault(); dz.style.borderColor = 'var(--primary)'; });
            dz.addEventListener('dragleave', () => dz.style.borderColor = '');
            dz.addEventListener('drop', e => {
                e.preventDefault(); dz.style.borderColor = '';
                if (e.dataTransfer.files.length) handleFiles({ files: e.dataTransfer.files });
            });
        }
    };

    /* ══════════════════════════════════════════════
       Dashboard (Cambio 3: render honesto)
    ══════════════════════════════════════════════ */
    async function updateDashboard() {
        const rnc = localStorage.getItem('crnc');
        if (!rnc) return;
        const anio = document.getElementById('display-period').textContent.trim();
        try {
            // /api/riesgo devuelve: {indice_riesgo, nivel, semaforo, mensaje, total_flags, flags[]}
            const resp = await safeFetch(`${API_URL}/riesgo?rnc=${encodeURIComponent(rnc)}&anio=${anio}`);
            const data = await resp.json();

            if (data && !data.error) {
                hasData = true;

                const indice  = data.indice_riesgo ?? null;
                const semaf   = data.semaforo || '';
                const flags   = data.flags || [];
                const nFlags  = data.total_flags || 0;

                // KPI 1: Alertas Críticas = banderas de riesgo ALTO/MUY_ALTO
                const flagsAltos = flags.filter(f => f.nivel === 'ALTO' || f.nivel === 'MUY_ALTO').length;
                setKPI('stat-alerts',
                    flagsAltos > 0 ? flagsAltos.toString() : '0',
                    flagsAltos > 0 ? 'danger' : 'success');

                // KPI 2: Integridad / Semáforo de Riesgo
                const colorSemaf = { VERDE: 'success', AMARILLO: 'amber', NARANJA: 'danger', ROJO: 'danger' };
                setKPI('stat-cruces',
                    indice !== null ? `${indice}% riesgo` : '—',
                    colorSemaf[semaf] || null);

                // KPI 3: ISR — no disponible en /api/riesgo, mantener estado honesto si no hay pipeline
                if (!hasDataFromPipeline) {
                    document.getElementById('stat-isr').textContent = 'Pendiente de archivo';
                }

                // KPI 4: NCFs — no disponible en /api/riesgo
                if (!hasDataFromPipeline) {
                    document.getElementById('stat-ncfs').textContent = '—';
                }

                // Tabla de auditoría: mostrar flags de riesgo
                renderRiskFlags(flags, data.mensaje);
            }
        } catch(e) {
            // Mantener estado honesto
        }
        // Cargar planificador luego del dashboard
        renderPlanificador(rnc, anio);
    }

    async function renderPlanificador(rnc, anio) {
        try {
            // 1. Buscar cliente_id para este RNC
            const clResp = await safeFetch(`${API_URL}/clientes`);
            const clData = await clResp.json();
            const cliente = (clData.clientes || []).find(c => c.rnc === rnc);
            if (!cliente) return;

            // 2. Obtener planificacion desde dashboard analitico
            const dpResp = await safeFetch(`${API_URL}/dashboard_analitico/${cliente.id}/${anio}`);
            const dpData = await dpResp.json();
            if (!dpData || dpData.error) return;

            const plan = dpData.planificacion || {};
            const list = document.getElementById('planificador-list');
            if (!list) return;

            if (!plan.ventas_proyectadas && !plan.anticipo_sugerido) {
                list.innerHTML = '<div class="table-empty">Sin datos de planificación. Ejecutá el pipeline primero.</div>';
                return;
            }

            const fmt = (v) => new Intl.NumberFormat('es-DO', { style:'currency', currency:'DOP', minimumFractionDigits:0 }).format(v || 0);
            list.innerHTML = `
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;padding:12px;">
                    <div style="background:var(--bg-card);border-radius:8px;padding:10px;text-align:center;">
                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Ventas Proyectadas</div>
                        <div style="font-size:18px;font-weight:800;color:var(--text-primary);margin-top:4px;">${fmt(plan.ventas_proyectadas)}</div>
                    </div>
                    <div style="background:var(--bg-card);border-radius:8px;padding:10px;text-align:center;">
                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">ISR Estimado</div>
                        <div style="font-size:18px;font-weight:800;color:var(--accent-amber);margin-top:4px;">${fmt(plan.isr_estimado_anual)}</div>
                    </div>
                    <div style="background:var(--bg-card);border-radius:8px;padding:10px;text-align:center;">
                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Anticipo Sugerido (Art. 314)</div>
                        <div style="font-size:18px;font-weight:800;color:var(--accent-emerald);margin-top:4px;">${fmt(plan.anticipo_sugerido)}</div>
                    </div>
                </div>
                <div style="padding:0 12px 10px;font-size:10px;color:var(--text-muted);display:flex;justify-content:space-between;">
                    <span>Crecimiento: ${(plan.factor_crecimiento || 1.0).toFixed(2)}x</span>
                    <span>Períodos históricos: ${plan.periodos_historicos || 0}</span>
                    ${plan.generado ? `<span>${new Date(plan.generado).toLocaleDateString('es-DO')}</span>` : ''}
                </div>`;
        } catch(e) {
            // Silent fail — no bloquea el dashboard
        }
    }

    function renderRiskFlags(flags, mensaje) {
        const list = document.getElementById('audit-list');
        if (!flags || flags.length === 0) {
            list.innerHTML = `<div class="table-empty">${mensaje || 'Sin banderas de riesgo para este periodo.'}</div>`;
            return;
        }
        const colorNivel = { MUY_ALTO: 'error', ALTO: 'error', MEDIO: 'ok', BAJO: 'ok', INFORMATIVO: 'ok' };
        const colorBadge = { MUY_ALTO: 'danger', ALTO: 'danger', MEDIO: 'loading', BAJO: 'success', INFORMATIVO: 'success' };
        list.innerHTML = flags.map(f => {
            const rowData = JSON.stringify(f).replace(/"/g, '&quot;');
            return `
            <div class="audit-item" onclick="explainAuditItem(${rowData})">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div class="status-dot-inline ${colorNivel[f.nivel] || 'ok'}"></div>
                    <span class="audit-id">[${f.codigo}]</span>
                    <span class="badge ${colorBadge[f.nivel] || 'loading'}">${f.nivel}</span>
                    <span style="font-size:12px;color:var(--text-secondary);flex:1;padding-right:30px;">${f.descripcion}</span>
                </div>
                <span class="audit-diff ${f.puntos > 0 ? 'error' : 'ok'}">+${f.puntos} pts</span>
            </div>`;
        }).join('');
    }

    /* Helper: actualiza una KPI card limpiando clases de color */
    function setKPI(id, value, colorClass) {
        const el = document.getElementById(id);
        if (!el) return;
        el.className = 'kpi-value' + (colorClass ? ' ' + colorClass : '');
        el.textContent = value;
    }

    function renderAudit(cruces) {
        const list = document.getElementById('audit-list');
        if (!cruces || cruces.length === 0) {
            list.innerHTML = '<div class="table-empty">Sin hallazgos para este periodo.</div>';
            return;
        }
        list.innerHTML = cruces.map(c => {
            const ok   = c.estado === 'OK';
            const diff = Math.abs(c.sist - c.dgii).toFixed(2);
            const rowData = JSON.stringify(c).replace(/"/g, '&quot;');
            return `<div class="audit-item" onclick="explainAuditItem(${rowData}, 'cruce')">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div class="status-dot-inline ${ok ? 'ok' : 'error'}"></div>
                    <span class="audit-id">${c.id}</span>
                    <span class="badge ${ok ? 'success' : 'danger'}">${c.estado}</span>
                </div>
                <span class="audit-diff ${ok ? 'ok' : 'error'}">RD$ ${diff}</span>
            </div>`;
        }).join('');
    }

    /* ══════════════════════════════════════════════
       CHAT
    ══════════════════════════════════════════════ */
    function appendBotMessage(text) {
        const hist = document.getElementById('chat-history');
        const div  = document.createElement('div');
        div.className = 'message bot';
        
        // Crear contenedor para el botón de repetir (Play)
        const replayHtml = `<button class="replay-btn" onclick="speakText(\`${text.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)" title="Escuchar nuevamente">
            <span class="material-symbols-rounded" style="font-size:18px;">volume_up</span>
        </button>`;

        div.innerHTML = `<div class="message-bubble">${text}${replayHtml}</div>`;
        hist.appendChild(div);
        hist.scrollTop = hist.scrollHeight;
    }

    async function sendChat() {
        const input = document.getElementById('chat-input');
        const hist  = document.getElementById('chat-history');
        const val   = input.value.trim();
        if (!val) return;

        // User bubble
        const userDiv = document.createElement('div');
        userDiv.className = 'message user';
        userDiv.innerHTML = `<div class="message-bubble">${val}</div>`;
        hist.appendChild(userDiv);
        input.value = '';
        hist.scrollTop = hist.scrollHeight;

        // Typing indicator
        const typing = document.createElement('div');
        typing.className = 'message bot'; typing.id = 'typing';
        typing.innerHTML = `<div class="typing-indicator">
            <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
        </div>`;
        hist.appendChild(typing);
        hist.scrollTop = hist.scrollHeight;

        // Preparar payload — cliente_id debe ser número (int), no string
        const cidRaw  = localStorage.getItem('cid');
        const cid     = cidRaw ? parseInt(cidRaw, 10) : null;
        const periodo = document.getElementById('display-period')?.textContent?.trim() || '2025';

        // Si no hay cliente seleccionado, responder localmente
        if (!cid) {
            document.getElementById('typing')?.remove();
            appendBotMessage('Selecciona un contribuyente primero para consultas personalizadas.');
            return;
        }

        try {
            const resp = await safeFetch(`${API_URL}/chat_fiscal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cliente_id: cid, periodo, pregunta: val })
            });
            const data = await resp.json();
            document.getElementById('typing')?.remove();

            // respuesta puede ser string o indefinida — nunca crashear
            appendBotMessage(data.respuesta || 'Sin respuesta del motor.');

            // costo y fuente son opcionales según la ruta del backend
            const fuente = data.fuente || 'sistema';
            const costo  = data.costo != null ? Number(data.costo).toFixed(5) : '0.00000';
            document.getElementById('chat-source').textContent = 'Source: ' + fuente;
            document.getElementById('chat-cost').textContent   = 'RD$ ' + costo;

        } catch(e) {
            document.getElementById('typing')?.remove();
            appendBotMessage('<span style="color:var(--danger)">⚠ Sin conexión con el servidor. Verifica que el motor esté activo.</span>');
        }
    }

    /* Auditoría */
    async function startAudit() {
        const id     = localStorage.getItem('cid');
        const period = document.getElementById('display-period').textContent;
        if (!id) return;
        await safeFetch(`${API_URL}/procesar_rapido/${id}/${period}`, { method: 'POST' });
        updateDashboard();
    }

    /* ══════════════════════════════════════════════
       ENTREGABLES INDUSTRIALES (XML/EXCEL/PDF)
    ══════════════════════════════════════════════ */
    async function generarEntregablesIndustriales() {
        const rnc = localStorage.getItem('crnc');
        const anio = document.getElementById('display-period').textContent.trim();
        const btn = document.getElementById('btn-generar-final');
        const container = document.getElementById('entregables-list');
        const empty = document.getElementById('entregables-empty');

        if (!rnc) return alert("Selecciona un cliente primero.");

        // UI Feedback
        const originalBtnHTML = btn.innerHTML;
        btn.innerHTML = `<span class="material-symbols-rounded animate-spin">cyclone</span> Generando...`;
        btn.disabled = true;
        
        const fd = new FormData();
        fd.append('rnc', rnc);
        fd.append('anio', anio);

        try {
            const resp = await safeFetch(`${API_URL}/generar_ir2_final`, {
                method: 'POST',
                body: fd
            });
            const data = await resp.json();

            if (data.status === 'success') {
                empty.classList.add('hidden');
                empty.style.display = 'none';
                container.classList.remove('hidden');
                container.style.display = 'grid';
                
                container.innerHTML = data.archivos.map(a => {
                    let icon = 'description';
                    let color = 'var(--text-secondary)';
                    if (a.nombre.includes('XML')) { icon = 'code'; color = '#6366f1'; }
                    else if (a.nombre.includes('Excel')) { icon = 'table_chart'; color = '#10b981'; }
                    else if (a.nombre.includes('PDF')) { icon = 'picture_as_pdf'; color = '#f43f5e'; }

                    return `
                    <a href="${a.url}" target="_blank" class="card" style="padding:16px; display:flex; align-items:center; gap:12px; text-decoration:none; transition:var(--transition); border: 1px solid var(--border-subtle); background: var(--bg-card);">
                        <span class="material-symbols-rounded" style="color:${color}; font-size:28px;">${icon}</span>
                        <div style="flex:1;">
                            <div style="font-size:12px; font-weight:700; color:var(--text-primary);">${a.nombre}</div>
                            <div style="font-size:10px; color:var(--text-secondary);">Validado por IA</div>
                        </div>
                        <span class="material-symbols-rounded" style="font-size:20px; color:var(--primary);">download</span>
                    </a>`;
                }).join('');

                // Trigger Premium Success Effect
                const panel = document.getElementById('panel-entregables');
                if (panel) panel.classList.add('success-glow');

                speakText("Paquete legal generado con éxito. Los archivos XML, Excel y la constancia PDF están disponibles para su descarga.");
            } else {
                alert("Error al generar entregables: " + data.message);
            }
        } catch (e) {
            console.error(e);
            alert("Error de conexión al generar entregables.");
        } finally {
            btn.innerHTML = originalBtnHTML;
            btn.disabled = false;
        }
    }

    /* Upload — parámetros corregidos para /api/procesar (backend lines 288-296)
       Requiere: rnc (Form), nombre (Form), anio (int Form), files (File)
    */
    async function handleFiles(input) {
        const status  = document.getElementById('upload-status');
        const results = document.getElementById('upload-results');

        const rnc   = localStorage.getItem('crnc') || '';
        const name  = localStorage.getItem('cname') || 'Sin nombre';
        const anio  = (document.getElementById('display-period')?.textContent?.trim()) || '2025';

        if (!rnc) {
            alert('Selecciona un contribuyente antes de cargar archivos.');
            return;
        }

        const fd = new FormData();
        fd.append('rnc',    rnc);
        fd.append('nombre', name);   // ← campo requerido por el backend
        fd.append('anio',   anio);   // ← el backend lo parsea como int
        Array.from(input.files).forEach(f => fd.append('files', f));

        status.style.display = 'block';
        results.innerHTML = '<tr><td colspan="3" style="padding:16px;text-align:center;"><span class="badge loading">⚙ Procesando archivos...</span></td></tr>';

        try {
            const resp = await safeFetch(`${API_URL}/procesar`, { method: 'POST', body: fd });
            const data = await resp.json();

            if (data.status === 'error') {
                results.innerHTML = `<tr><td colspan="3" style="padding:16px;text-align:center;"><span class="badge danger">⚠ ${data.message}</span></td></tr>`;
                return;
            }

            // Actualizar KPIs con resultados del pipeline
            if (data.resultados) {
                const res = data.resultados;
                hasData = true;
                hasDataFromPipeline = true;
                const cruces  = res.auditoria_cruces || [];
                const alerts  = cruces.filter(c => c.estado !== 'OK').length;
                const crucePct = alerts === 0 ? '100%' : (100 - alerts * 5) + '%';
                const yields   = res.riesgo_dgii || {};
                const isr_val  = res.isr_pagar || 0;
                const isr     = new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP' }).format(isr_val);
                
                setKPI('stat-ncfs',   '—', null);
                setKPI('stat-alerts', alerts.toString(),  alerts > 0 ? 'danger' : 'success');
                setKPI('stat-cruces', crucePct,           alerts === 0 ? 'success' : 'danger');
                setKPI('stat-isr',    isr,                'amber');
                if (cruces.length > 0) renderAudit(cruces);

                // PROACTIVE AUDIO SUMMARY — Phase 2
                const levelMsg = yields.nivel === 'BAJO' ? 'Riesgo bajo.' : `¡Riesgo ${yields.nivel}!`;
                const summary = `Carga completada de ${input.files.length} archivos. ${levelMsg} El impuesto proyectado es de ${isr}. ¿Qué deseas analizar ahora?`;
                setTimeout(() => speakText(summary), 1000);
            }

            results.innerHTML = Array.from(input.files).map(f => `
                <tr>
                    <td>${f.name}</td>
                    <td><span class="badge success">✓ Procesado</span></td>
                    <td class="mono">${anio}</td>
                </tr>`).join('');

        } catch(e) {
            results.innerHTML = '<tr><td colspan="3" style="padding:16px;text-align:center;"><span class="badge danger">Error de conexión con el motor</span></td></tr>';
        }
    }

    /* ══════════════════════════════════════════════
       VOICE INTEGRATION (STT + TTS)
    ══════════════════════════════════════════════ */
    let recognition;
    let isRecording = false;

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRec();
        recognition.lang = 'es-DO'; // Localización Dominicana para "NCF", "IR2", etc.
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            isRecording = true;
            document.getElementById('btn-mic').classList.add('recording');
            startMicTimer();
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('chat-input').value = transcript;
            
            // VOICE COMMANDS — Phase 2
            if (!processVoiceCommand(transcript)) {
                resetMicTimer(); 
            }
        };

        function processVoiceCommand(text) {
            const cmd = text.toLowerCase();
            console.log('Testing voice command:', cmd);
            
            if (cmd.includes('ir a') || cmd.includes('ver') || cmd.includes('abrir')) {
                if (cmd.includes('riesgo') || cmd.includes('dashboard') || cmd.includes('inicio')) {
                    switchTab('dashboard');
                } else if (cmd.includes('auditoría') || cmd.includes('cruces') || cmd.includes('hallazgos')) {
                    switchTab('auditoria');
                } else if (cmd.includes('archivos') || cmd.includes('subir') || cmd.includes('carga')) {
                    switchTab('archivos');
                } else if (cmd.includes('cliente') || cmd.includes('contribuyente')) {
                    toggleClientModal();
                } else if (cmd.includes('declaración') || cmd.includes('ir-2')) {
                    // Acción especial: descargar si es posible
                    showVoiceAlert('Abriendo panel de descarga...');
                } else {
                    return false; // No es un comando de navegación reconocido
                }
                
                // Si llegamos aquí, fue un comando exitoso
                stopVoiceUI();
                if (recognition) recognition.stop();
                showVoiceAlert('Comando ejecutado: ' + text);
                return true;
            }
            return false;
        }

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'not-allowed') {
                showVoiceAlert('Permiso de micrófono denegado por el navegador.');
            } else if (event.error !== 'no-speech') {
                showVoiceAlert('Error en el reconocimiento de voz: ' + event.error);
            }
            stopVoiceUI();
        };

        recognition.onend = () => {
            stopVoiceUI();
        };
    }

    let micTimer = null;
    function startMicTimer() {
        if (micTimer) clearTimeout(micTimer);
        micTimer = setTimeout(() => {
            if (isRecording) {
                console.log('Voice interaction: 8s inactivity timeout.');
                recognition.stop();
            }
        }, 8000);
    }

    function resetMicTimer() {
        if (isRecording) startMicTimer();
    }

    function toggleMic() {
        if (!recognition) {
            showVoiceAlert('Tu navegador no soporta reconocimiento de voz.');
            return;
        }
        if (isRecording) {
            recognition.stop();
        } else {
            try {
                recognition.start();
            } catch(e) {
                console.error(e);
            }
        }
    }

    function stopVoiceUI() {
        isRecording = false;
        document.getElementById('btn-mic').classList.remove('recording');
    }

    function showVoiceAlert(msg) {
        const alert = document.getElementById('voice-alert');
        document.getElementById('voice-alert-text').textContent = msg;
        alert.style.display = 'flex';
        setTimeout(() => { alert.style.display = 'none'; }, 5000);
    }

    /* Audio Unlock Utility */
    let audioUnlocked = false;
    function unlockAudio() {
        if (audioUnlocked) return;
        const silent = new SpeechSynthesisUtterance("");
        silent.volume = 0;
        window.speechSynthesis.speak(silent);
        audioUnlocked = true;
        console.log('Audio Context Unlocked via Click');
    }
    document.addEventListener('click', unlockAudio, { once: true });
    document.addEventListener('keydown', unlockAudio, { once: true });

    /* Text to Speech (TTS) logic */
    function speakText(text) {
        if (!window.speechSynthesis) return;
        
        // Detener cualquier lectura previa y apagar micrófono para evitar eco
        speechSynthesis.cancel();
        if (isRecording) recognition.stop();

        const cleanText = cleanTextForTTS(text);
        const utterance = new SpeechSynthesisUtterance(cleanText);
        
        // Búsqueda inteligente de voz en español
        const voices = window.speechSynthesis.getVoices();
        const preferred = ['es-DO', 'es-MX', 'es-ES', 'es-US'];
        let selectedVoice = null;
        
        for (let lang of preferred) {
            selectedVoice = voices.find(v => v.lang.includes(lang));
            if (selectedVoice) break;
        }
        
        if (selectedVoice) utterance.voice = selectedVoice;
        utterance.lang = selectedVoice ? selectedVoice.lang : 'es-ES';
        utterance.rate = 1.05;

        utterance.onstart = () => {
            document.getElementById('btn-stop-voice').classList.add('speaking');
        };
        utterance.onend = () => {
            document.getElementById('btn-stop-voice').classList.remove('speaking');
            
            // AUTOMATIC MIC ACTIVATION
            setTimeout(() => {
                if (!isRecording && recognition) {
                    try { recognition.start(); } catch(e) {}
                }
            }, 500);
        };

        speechSynthesis.speak(utterance);
    }

    function stopSpeaking() {
        if (window.speechSynthesis) {
            speechSynthesis.cancel();
            document.getElementById('btn-stop-voice').classList.remove('speaking');
        }
    }

    function explainAuditItem(item, type = 'flag') {
        let msg = "";
        if (type === 'flag') {
            msg = `Hallazgo de tipo ${item.codigo}. Nivel de riesgo ${item.nivel}. ${item.descripcion}. `;
            if (item.nivel === 'ALTO' || item.nivel === 'MUY_ALTO') {
                msg += "Te sugiero revisar este documento de inmediato para evitar multas de la DGII.";
            } else {
                msg += "Este es un hallazgo preventivo, considera ajustarlo en tu próxima declaración.";
            }
        } else {
            const diff = Math.abs(item.sist - item.dgii).toFixed(2);
            msg = `Discrepancia en el cruce ${item.id}. Hay una diferencia de ${diff} pesos entre el sistema y la base de datos oficial. `;
            if (item.estado === 'ERROR' || item.estado === 'ROJO') {
                msg += "Esto podría activar una fiscalización. Debes conciliar estos montos antes de enviar el envío oficial.";
            }
        }
        speakText(msg);
        showVoiceAlert('Explicando hallazgo: ' + (item.codigo || item.id));
    }

    function cleanTextForTTS(text) {
        let clean = text;
        // 1. Eliminar negritas, cursivas y otros markdown
        clean = clean.replace(/\*\*/g, '').replace(/__/g, '');
        clean = clean.replace(/#/g, '');
        clean = clean.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1'); // Mantener texto de links, quitar URLs
        
        // 2. Normalizar términos financieros dominicanos
        clean = clean.replace(/RD\$/g, 'pesos dominicanos');
        clean = clean.replace(/NCF/g, 'N C F'); 
        clean = clean.replace(/DGII/g, 'D G I I');
        clean = clean.replace(/IT-1/g, 'I T uno');
        clean = clean.replace(/IR-2/g, 'I R dos');
        clean = clean.replace(/ISR/g, 'I S R');
        clean = clean.replace(/RNC/g, 'Renecé');
        clean = clean.replace(/ITBIS/g, 'Itbis');
        clean = clean.replace(/IR-3/g, 'I R tres');
        clean = clean.replace(/IR-13/g, 'I R trece');
        clean = clean.replace(/TSS/g, 'T S S');
        
        return clean;
    }

    // Sobrescribimos la función original para integrar voz
    const originalAppendBotMessage = appendBotMessage;
    appendBotMessage = function(text, shouldSpeak = true) {
        originalAppendBotMessage(text);
        if (shouldSpeak) speakText(text);
    };

    /* ============================================================
       VISUALIZER ANIMATION — Phase 2
    ============================================================ */
    const canvas = document.getElementById('voice-vis');
    const ctx = canvas.getContext('2d');
    let animationFrame;

    function renderVis() {
        animationFrame = requestAnimationFrame(renderVis);
        const w = canvas.width = canvas.offsetWidth;
        const h = canvas.height = canvas.offsetHeight;
        
        ctx.clearRect(0, 0, w, h);
        
        const isActive = isRecording || (window.speechSynthesis && speechSynthesis.speaking);
        const visEl = document.getElementById('voice-vis');
        visEl.classList.toggle('active', isActive);
        
        if (!isActive) return;

        const time = Date.now() / 1000;
        const bars = 40;
        const barW = w / bars;
        
        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim();
        
        for (let i = 0; i < bars; i++) {
            // Generar una onda sinusoide "viva" con algo de ruido aleatorio para realismo
            const amplitude = isRecording ? 15 : 10;
            const freq = i * 0.2 + time * 10;
            const noise = Math.random() * 5;
            const barH = Math.abs(Math.sin(freq) * amplitude) + 2 + noise;
            
            ctx.globalAlpha = 0.3 + (Math.sin(freq) * 0.2);
            ctx.fillRect(i * barW, h - barH, barW - 2, barH);
        }
    }
    renderVis();