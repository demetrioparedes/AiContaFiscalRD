// AiContaFiscalRD - Premium SaaS UI Logic
const uploadedFiles = {
    '606': [], '607': [], 'TSS': [], 'Terceros': [], 'IR2Anterior': []
};

let isProcessing = false;
let apiResuelta = false;
let dataApi = null;
let currentEngineUI = 1;

const API_KEY = 'AiConta_Secure_Key_2026_RD'; // Llave industrial por defecto

async function safeFetch(url, options = {}) {
    if (!options.headers) options.headers = {};
    options.headers['X-API-KEY'] = API_KEY;
    
    try {
        const resp = await fetch(url, options);
        if (resp.status === 403) {
            console.error("Acceso denegado: API Key inválida.");
            return resp; // Devolvemos para que el caller maneje el error
        }
        return resp;
    } catch (e) {
        console.error("Error en safeFetch:", e);
        throw e;
    }
}

// Autoejecutable al instante de cargar el script
(async function initClientData() {
    const pathParts = window.location.pathname.split('/');
    if (pathParts[1] === 'cliente' && pathParts[2]) {
        try {
            const resp = await safeFetch(`/api/clientes/${pathParts[2]}`);
            if (resp.ok) {
                const c = await resp.json();
                const inputFormNombre = document.getElementById("empresa_nombre");
                const inputFormRnc = document.getElementById("empresa_rnc");
                if(inputFormNombre) { inputFormNombre.value = c.razon_social; inputFormNombre.classList.add('bg-gray-200', 'cursor-not-allowed'); }
                if(inputFormRnc) { inputFormRnc.value = c.rnc; inputFormRnc.classList.add('bg-gray-200', 'cursor-not-allowed'); }
                
                const headerEmpNombre = document.getElementById("header_empresa_nombre");
                const headerEmpRnc = document.getElementById("header_empresa_rnc");
                if(headerEmpNombre) { headerEmpNombre.value = c.razon_social; }
                if(headerEmpRnc) { headerEmpRnc.value = c.rnc; }
                
                const headerTitle = document.querySelector("header h1");
                if(headerTitle) { headerTitle.innerHTML = `<a href="/" class="hover:text-blue-200 transition-colors"><i class="ri-arrow-left-line mr-1"></i> Dashboard</a> &nbsp;|&nbsp; <span class="text-white font-black drop-shadow-md">${c.razon_social}</span> <span class="text-sm font-normal text-blue-200 ml-2">SaaS Premium</span>`; }
            }
        } catch(e) { console.error("Error obteniendo cliente", e); }
    }
})();

// ─── IR-2 OFICIAL DGII ─────────────────────────────────────────
// Dispara la descarga del formulario oficial DGII relleno
function descargarIR2Oficial(event) {
    event.preventDefault();
    const rnc  = document.getElementById('empresa_rnc')?.value;
    const anio = document.getElementById('empresa_anio')?.value;
    
    if (!rnc || !anio) {
        alert('Debes cargar un cliente y ejecutar el pipeline primero.');
        return;
    }
    
    const btn = document.getElementById('btnIR2Oficial');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="ri-loader-4-line animate-spin mr-2"></i> Generando IR-2 Oficial...';
    btn.style.opacity = '0.7';
    
    // Abrir en nueva ventana para que el navegador lo descargue
    const url = `/api/generar_ir2_oficial/${rnc}/${anio}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `IR2_OFICIAL_${anio}_${rnc}.xls`;
    a.click();
    
    setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.style.opacity = '1';
    }, 3000);
}

// Tabs Logic
function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));
    document.querySelectorAll('.tab-active').forEach(btn => {
        btn.classList.remove('tab-active');
        btn.classList.add('tab-inactive');
    });
    
    document.getElementById(tabName + 'Tab').classList.remove('hidden');
    event.currentTarget.classList.remove('tab-inactive');
    event.currentTarget.classList.add('tab-active');

    // Disparar animación del Radar si se abre la pestaña de riesgo y hay data
    if (tabName === 'risk' && window.ultimaDataRiesgo) {
        animarRadarVisualmente(window.ultimaDataRiesgo);
    }
}

// Upload Logic
function triggerFileUpload(fileType) {
    document.getElementById('input' + fileType).click();
}

function handleFileSelect(fileType, input) {
    if (input.files && input.files.length > 0) {
        uploadedFiles[fileType] = Array.from(input.files);
        const count = input.files.length;
        document.getElementById('file' + fileType).innerHTML = `
            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                <i class="ri-checkbox-multiple-line mr-1"></i> ${count} Archivos Confirmados
            </span>
        `;
        updateProcessButton();
        if (fileType === '606' || fileType === '607') {
            generarResumenUI(fileType, uploadedFiles[fileType]);
        } else if (fileType === 'IR2Anterior') {
            procesarMagiaIR2(uploadedFiles[fileType]);
        }
    }
}

async function procesarMagiaIR2(filesArr) {
    if(filesArr.length === 0) return;
    
    // UI Loading state
    const badge = document.getElementById('fileIR2Anterior');
    badge.innerHTML = '<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-pink-200 text-pink-800"><i class="ri-loader-4-line mr-1 animate-spin"></i> Analizando magia...</span>';
    
    const formData = new FormData();
    filesArr.forEach(f => formData.append('files', f)); // Enviamos todos los archivos
    
    try {
        const resp = await safeFetch(`/api/parse_ir2_anterior`, { method: 'POST', body: formData });
        if(resp.ok) {
            const data = await resp.json();
            if (data.status === "success") {
                // Auto-completado de inputs
                document.getElementById('inv_inicial').value = data.inventario_final_anterior || 0;
                document.getElementById('retenciones').value = data.retenciones_saldo_favor || 0;
                
                // Mostrar éxito
                badge.innerHTML = `<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200"><i class="ri-magic-line mr-1"></i> Auto-Completado: $${new Intl.NumberFormat('es-DO').format(data.inventario_final_anterior)}</span>`;
                
                // Flash animation on inputs
                ['inv_inicial', 'retenciones'].forEach(id => {
                    const el = document.getElementById(id);
                    el.classList.add('bg-green-50', 'text-green-900', 'font-black');
                    setTimeout(() => el.classList.remove('bg-green-50', 'text-green-900', 'font-black'), 2000);
                });
            } else {
                badge.innerHTML = `<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200"><i class="ri-error-warning-line mr-1"></i> Formato Ilegible</span>`;
            }
        }
    } catch(e) {
        badge.innerHTML = `<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200"><i class="ri-error-warning-line mr-1"></i> Error Red</span>`;
    }
}

async function generarResumenUI(tipo, filesArr) {
    const resumenDiv = document.getElementById("resumen" + tipo);
    if (!resumenDiv) return;
    
    resumenDiv.classList.remove('hidden');
    resumenDiv.innerHTML = '<i class="ri-loader-4-line animate-spin text-blue-500 mr-2"></i> Analizando...';
    
    const formData = new FormData();
    filesArr.forEach(f => formData.append('files', f));
    
    const anioSeleccionado = document.getElementById("empresa_anio").value || "2025";
    formData.append('anio', anioSeleccionado);
    
    try {
        const resp = await safeFetch(`/api/resumen_archivos/${tipo}`, { method: 'POST', body: formData });
        if(resp.ok) {
            const data = await resp.json();
            mostrarResumenEnHtml(tipo, data, resumenDiv);
        } else {
            resumenDiv.innerHTML = '<span class="text-red-500">Error analizando archivos</span>';
        }
    } catch(e) {
        resumenDiv.innerHTML = '<span class="text-red-500">Error de conexión</span>';
    }
}

const formatDir = new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP' });

function mostrarResumenEnHtml(tipo, data, div) {
    let mesesHtml = data.meses.map(m => `<span class="inline-block bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded text-[10px] mr-1 mb-1 font-mono">${m}</span>`).join('');
    if(data.meses.length === 0) mesesHtml = '<span class="text-[10px] text-gray-500">Ninguno detectado</span>';
    
    let desgloseHtml = '';
    if (Object.keys(data.desglose).length > 0) {
        desgloseHtml = `<div class="mt-2 border-t border-gray-200 pt-1">
            <span class="font-semibold text-gray-600 text-[10px]">Tipos de Gasto:</span><br>
            <div class="flex flex-wrap gap-1 mt-1">` + 
            Object.entries(data.desglose).map(([k,v]) => `<span class="bg-gray-200 text-gray-700 px-1 py-0.5 rounded text-[9px]">Tipo ${k}: ${v} fact.</span>`).join('') +
            `</div></div>`;
    }

    let html = `
        ${data.warning ? `<div class="bg-red-100 text-red-700 p-2 mb-2 rounded text-xs font-bold border border-red-300"><i class="ri-alert-fill mr-1"></i>${data.warning}</div>` : ''}
        <div class="border-b border-gray-200 pb-1 mb-1 flex justify-between">
            <span class="font-bold text-gray-700">Total Validado:</span>
            <span class="font-bold text-green-700">${formatDir.format(data.total)}</span>
        </div>
        <div class="mb-1">
            <span class="font-semibold text-gray-600">Meses:</span><br>
            ${mesesHtml}
        </div>
        ${desgloseHtml}
    `;
    div.innerHTML = html;
}

function updateProcessButton() {
    const btn = document.getElementById('processBtn');
    btn.disabled = isProcessing;
}

// DRAG AND DROP
document.querySelectorAll('.file-upload').forEach(dropzone => {
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('dragover'); });
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const inputId = dropzone.querySelector('input').id;
            const input = document.getElementById(inputId);
            const fileType = inputId.replace('input', '');
            input.files = files;
            handleFileSelect(fileType, input);
        }
    });
});

// START PROCESSING
function startProcessing() {
    if (isProcessing) return;
    isProcessing = true;
    apiResuelta = false;
    dataApi = null;
    
    const btn = document.getElementById('processBtn');
    btn.innerHTML = `<i class="ri-loader-4-line mr-2 animate-spin"></i> Arrancando Pipeline IA...`;
    btn.disabled = true;

    // Cambiar a Motres
    document.querySelector('button[onclick="switchTab(\'engines\')"]').click();
    document.getElementById('progressGlobal').classList.remove('hidden');

    // 1. INICIAR EL PROCESO VISUAL MOCK
    processEngineUI(1);

    // 2. INICIAR EL REQUEST REAL
    llamarAPIFiscal();
}

function llamarAPIFiscal() {
    const formData = new FormData();
    formData.append("nombre", document.getElementById("empresa_nombre").value || "XYZ SRL");
    formData.append("rnc", document.getElementById("empresa_rnc").value || "130826552");
    formData.append("anio", document.getElementById("empresa_anio").value || "2025");
    formData.append("inv_inicial", document.getElementById("inv_inicial").value || "0");
    formData.append("inv_final", document.getElementById("inv_final").value || "0");
    formData.append("retenciones", document.getElementById("retenciones").value || "0");

    let pends = [];
    ['606','607','TSS','Terceros','IR2Anterior'].forEach(t => {
        let filesArr = uploadedFiles[t];
        if (filesArr && filesArr.length > 0) {
            filesArr.forEach(f => formData.append("files", f));
        } else {
            pends.push(t); // Solo si NO hay archivos, es un "Pendiente"
        }
    });
    formData.append("pendientes_list", pends.join(","));

    safeFetch('/api/procesar', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        console.log("API RESPUESTA:", data);
        apiResuelta = true;
        dataApi = data;
    })
    .catch(err => {
        console.error("Error en API:", err);
        alert("Ocurrió un error de red o en el servidor.");
        isProcessing = false;
        document.getElementById('processBtn').disabled = false;
        document.getElementById('processBtn').innerHTML = `<i class="ri-blaze-fill text-2xl"></i> Reintentar Pipeline`;
    });
}

function processEngineUI(engineNum) {
    if (engineNum > 7) {
        completeProcessing();
        return;
    }

    const engine = document.getElementById('engine' + engineNum);
    const status = document.getElementById('status' + engineNum);
    const bar = document.getElementById('bar' + engineNum);
    const step = document.getElementById('step' + engineNum);

    engine.classList.add('active', 'border-blue-500');
    status.innerHTML = '<span class="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-700 rounded"><i class="ri-loader-4-line mr-1 animate-spin"></i> Procesando</span>';
    step.classList.add('bg-blue-500', 'text-white');

    let progressValue = 0;
    const interval = setInterval(() => {
        // Si la API ya terminó, avanzamos súper rápido al 100%
        let s = apiResuelta ? 40 : (Math.random() * 10 + 2);
        progressValue += s;
        
        if (progressValue >= 100) {
            progressValue = 100;
            clearInterval(interval);
            
            engine.classList.remove('active', 'border-blue-500');
            engine.classList.add('border-green-500');
            status.innerHTML = '<span class="inline-flex items-center px-2 py-1 bg-green-100 text-green-700 rounded"><i class="ri-check-line mr-1"></i> Completado</span>';
            step.classList.remove('bg-blue-500');
            step.classList.add('bg-green-500');
            step.innerHTML = '<i class="ri-check-line"></i>';
            
            updateOverallProgress(engineNum);
            
            setTimeout(() => { processEngineUI(engineNum + 1); }, 200);
        }
        bar.style.width = progressValue + '%';
    }, 200);
}

function updateOverallProgress(completed) {
    const p = (completed / 7) * 100;
    document.getElementById('progressBar').style.width = p + '%';
    document.getElementById('progressText').textContent = Math.round(p) + '% Procesado';
}

function completeProcessing() {
    isProcessing = false;
    document.getElementById('processBtn').innerHTML = `<i class="ri-check-circle-line mr-2"></i> Pipeline Completado`;
    
    // Si la API no falló y devolvió resultados
    if (dataApi && dataApi.status === "success") {
        poblarResultadosUI(dataApi.resultados);
        document.querySelector('button[onclick="switchTab(\'premium\')"]').click();
        renderDashboardPremium(); // Nueva visualización Premium
        
        // Setup downloads
        const dL = document.getElementById('downloadList');
        dL.innerHTML = '';
        dataApi.archivos.forEach(a => {
            dL.innerHTML += `
            <a href="${a.url}" target="_blank" class="flex items-center justify-between p-3 bg-gray-50 hover:bg-indigo-50 border border-gray-200 hover:border-indigo-300 rounded-lg transition-all group">
                <div class="flex items-center">
                    <i class="${a.nombre.includes('pdf') || a.nombre.includes('PDF') ? 'ri-file-pdf-fill text-red-500' : 'ri-file-excel-fill text-green-500'} text-2xl mr-3 group-hover:scale-110 transition-transform"></i>
                    <div>
                        <p class="font-bold text-gray-800 text-sm">${a.nombre}</p>
                        <p class="text-xs text-gray-500">Documento Generado IA</p>
                    </div>
                </div>
                <i class="ri-download-cloud-line text-indigo-500 text-xl font-bold"></i>
            </a>`;
        });

    } else {
        // En lugar de alert, inyectamos el rastro del error directamente en la vista para depurar rápido
        document.getElementById('progressGlobal').innerHTML = `
            <div class="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
                <div class="flex items-center mb-2">
                    <i class="ri-error-warning-fill text-2xl text-red-500 mr-2"></i>
                    <h3 class="font-bold text-red-800">Error Crítico en el Pipeline</h3>
                </div>
                <p class="text-sm text-red-700 mb-3">${dataApi ? (dataApi.message || dataApi.detail) : 'Fallo en la comunicación con el servidor (Posible Timeout o servidor apagado)'}</p>
                ${dataApi && dataApi.trace ? `<pre class="bg-red-900 text-red-100 p-3 rounded text-[10px] overflow-auto max-h-48 font-mono">${dataApi.trace}</pre>` : ''}
            </div>
        `;
        document.getElementById('processBtn').disabled = false;
        document.getElementById('processBtn').innerHTML = `<i class="ri-blaze-fill text-2xl"></i> Reintentar Pipeline`;
    }
}

function poblarResultadosUI(res) {
    const fCur = (val) => new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP' }).format(val || 0);
    
    // Resultados JSON del backend (Estado de Resultados)
    document.getElementById('resVentas').textContent = fCur(res.ventas || 0);
    document.getElementById('resCostos').textContent = fCur((res.costos || 0) * (-1));
    document.getElementById('resBruta').textContent = fCur((res.ventas || 0) - (res.costos || 0));
    document.getElementById('resGastos').textContent = fCur((res.gastos || 0) * (-1));
    document.getElementById('resISR').textContent = fCur(res.isr_pagar || 0);

    // Banderas (Audit List = 18 Cruces BIG4)
    const aList = document.getElementById('auditList');
    if (document.getElementById('auditSkeleton')) {
        document.getElementById('auditSkeleton').classList.add('hidden');
    }
    aList.innerHTML = '';
    
    let numAlertasCruces = 0;
    if (res.auditoria_cruces && res.auditoria_cruces.length > 0) {
        res.auditoria_cruces.forEach(cruce => {
            let isError = cruce.estado !== "OK";
            let color = isError ? "red" : "green";
            let icon = isError ? "ri-error-warning-fill" : "ri-check-double-fill";
            if (isError) numAlertasCruces++;
            
            aList.innerHTML += `
            <div class="flex items-start p-3 bg-${color}-50 border border-${color}-200 rounded-lg">
                <i class="${icon} text-${color}-500 mt-0.5 mr-2"></i>
                <div class="flex-1">
                    <p class="text-sm font-bold text-${color}-900">${cruce.id}</p>
                    <div class="text-xs text-${color}-800 mt-1 flex justify-between pr-4 font-mono">
                        <span>DGII: ${fCur(cruce.dgii)}</span>
                        <span>SISTEMA: ${fCur(cruce.sist)}</span>
                    </div>
                </div>
            </div>`;
        });
    } else {
        aList.innerHTML = `
        <div class="flex items-center justify-center p-6 bg-green-50 border border-green-200 rounded-lg">
            <div class="text-center">
                <i class="ri-shield-star-fill text-4xl text-green-500 mb-2"></i>
                <p class="text-sm font-bold text-green-900">Auditoría Limpia</p>
                <p class="text-xs text-green-700">Cruces perfectos o no ejecutados aún.</p>
            </div>
        </div>`;
    }

    if (numAlertasCruces > 0) {
        document.getElementById('crucesCriticosBadge').classList.remove('hidden');
        document.getElementById('crucesCriticosBadge').className = "bg-rose-100 text-rose-700 font-bold px-2.5 py-1 rounded text-xs";
        document.getElementById('crucesCriticosBadge').textContent = numAlertasCruces + ' ALERTAS';
    } else {
        document.getElementById('crucesCriticosBadge').classList.remove('hidden');
        document.getElementById('crucesCriticosBadge').className = "bg-green-100 text-green-700 font-bold px-2.5 py-1 rounded text-xs";
        document.getElementById('crucesCriticosBadge').textContent = '100% OK';
    }

    // Tablero de Riesgo DGII - Preparamos Variables pero No Animamos aún
    if (res.riesgo_dgii) {
        const r = res.riesgo_dgii;
        window.ultimaDataRiesgo = r; // Guardamos en cache para animarla
        
        // Reset inicial para el efecto sorpresa
        const circle = document.getElementById('riskCircle');
        circle.style.transition = 'none';
        circle.style.strokeDashoffset = 264;
        document.getElementById('riskPercent').textContent = '0%';
        window._radarAnimadoCerradura = false; // Reset lock
        
        // El resto se arma normal (texto y banderas)
        const lvl = document.getElementById('riskLevel');
        if (r.nivel === "BAJO") { 
            lvl.className = "inline-flex items-center px-5 py-2.5 rounded-full text-sm font-bold bg-green-100 text-green-800 border border-green-300 shadow-inner"; 
            lvl.innerHTML = '<i class="ri-shield-check-fill mr-2"></i> RIESGO BAJO'; 
        } else if (r.nivel === "MEDIO") { 
            lvl.className = "inline-flex items-center px-5 py-2.5 rounded-full text-sm font-bold bg-yellow-100 text-yellow-800 border border-yellow-300 shadow-inner"; 
            lvl.innerHTML = '<i class="ri-error-warning-fill mr-2"></i> RIESGO MEDIO'; 
        } else { 
            lvl.className = "inline-flex items-center px-5 py-2.5 rounded-full text-sm font-bold bg-red-100 text-red-800 border border-red-300 shadow-inner"; 
            lvl.innerHTML = '<i class="ri-alert-fill mr-2"></i> RIESGO ALTO'; 
        }

        document.getElementById('riskMessage').textContent = r.mensaje;

        // Banderas de Riesgo Extra
        const bExtra = document.getElementById('banderasExtra');
        if (r.flags && r.flags.length > 0) {
            let banderasHtml = r.flags.map(f => {
                let codigo = typeof f === 'string' ? 'Riesgo' : (f.codigo || 'R');
                let desc = typeof f === 'string' ? f : (f.descripcion || f);
                return `<div class="mt-1 pt-1 border-t border-blue-100/50"><span class="font-bold text-blue-900">[${codigo}]</span> <span class="text-blue-800">${desc}</span></div>`;
            }).join('');
            bExtra.innerHTML = banderasHtml;
            bExtra.parentElement.className = "mt-4 p-4 bg-blue-50/50 rounded-lg border border-blue-200 shadow-inner";
        } else {
            bExtra.innerHTML = '<div class="mt-2 text-sm text-green-700 font-bold"><i class="ri-check-line mr-1"></i> Perfil completamente limpio. Ningún factor de riesgo adicional detectado.</div>';
            bExtra.parentElement.className = "mt-4 p-4 bg-green-50 rounded-lg border border-green-200 shadow-inner";
        }
    }
}

// Función exclusiva para animar visualmente el Radar SVG y el contador (%)
function animarRadarVisualmente(r) {
    if(window._radarAnimadoCerradura) return; 
    window._radarAnimadoCerradura = true; // Solo animamos una vez

    const circle = document.getElementById('riskCircle');
    const label = document.getElementById('riskPercent');
    
    // Activar transiciones suaves con bezier curve (simula arrancar lento, acelerar y frenar)
    circle.style.transition = 'stroke-dashoffset 2.5s cubic-bezier(0.22, 1, 0.36, 1), stroke 1s ease';
    
    // Asignar el color dinámicamente según el nivel
    if (r.nivel === "BAJO") circle.style.stroke = "#10b981"; // success
    else if (r.nivel === "MEDIO") circle.style.stroke = "#f59e0b"; // warning
    else circle.style.stroke = "#ef4444"; // danger
    
    // Calcular relleno meta
    const finalOffset = 264 - ((r.indice_riesgo) / 100) * 264;
    
    // Disparar redibujado de CSS (forcing reflow) y luego ejecutar animacion SVG
    setTimeout(() => {
        circle.style.strokeDashoffset = finalOffset;
    }, 50);

    // Animación del texto % desde 0 hasta el numero objetivo
    let curPercent = 0;
    const meta = r.indice_riesgo;
    
    if (meta === 0) return;
    
    const countInterv = setInterval(() => {
        if(curPercent >= meta) {
            clearInterval(countInterv);
            label.textContent = meta + '%';
        } else {
            curPercent += Math.ceil(meta * 0.05) || 1; // aumentar 5% en cada frame
            if(curPercent > meta) curPercent = meta;
            label.textContent = curPercent + '%';
        }
    }, 40);
}

// ─── DASHBOARD PREMIUM (CHART.JS & ANALYTICS) ───────────────────────
let chartAccionistas = null;

async function renderDashboardPremium() {
    const pathParts = window.location.pathname.split('/');
    const clienteId = pathParts[2];
    const anio = document.getElementById('empresa_anio').value || 2025;
    
    if (!clienteId) return;

    try {
        const resp = await safeFetch(`/api/dashboard_analitico/${clienteId}/${anio}`);
        if (!resp.ok) return;
        const data = await resp.json();

        // 1. Cabecera resumida
        const fCur = (val) => new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP' }).format(val || 0);
        document.getElementById('prem_ventas').textContent = fCur(data.resumen.ingresos_brutos);
        document.getElementById('prem_costos').textContent = fCur(data.resumen.costo_ventas);
        document.getElementById('prem_utilidad').textContent = fCur(data.resumen.utilidad_neta);
        document.getElementById('prem_isr').textContent = fCur(data.resumen.isr_estimado);

        // 2. Gráfico de Accionistas (Doughnut)
        const ctx = document.getElementById('chartAccionistas').getContext('2d');
        if (chartAccionistas) chartAccionistas.destroy();

        chartAccionistas = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.accionistas.map(a => a.nombre),
                datasets: [{
                    data: data.accionistas.map(a => a.porcentaje),
                    backgroundColor: [
                        '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
                    ],
                    borderWidth: 0,
                    hoverOffset: 15
                }]
            },
            options: {
                cutout: '70%',
                plugins: {
                    legend: { display: false }
                },
                maintainAspectRatio: false
            }
        });

        // 3. Lista de Accionistas Lateral
        const listaAcc = document.getElementById('listaAccionistas');
        listaAcc.innerHTML = data.accionistas.map(a => `
            <div class="flex items-center justify-between text-sm">
                <div class="flex items-center">
                    <div class="w-3 h-3 rounded-full mr-2" style="background: ${chartAccionistas.data.datasets[0].backgroundColor[data.accionistas.indexOf(a) % 6]}"></div>
                    <span class="font-medium text-gray-700">${a.nombre}</span>
                </div>
                <span class="font-bold text-gray-900">${a.porcentaje}%</span>
            </div>
        `).join('');

        // 4. Hallazgos (Red Flags)
        const listaHal = document.getElementById('prem_lista_hallazgos');
        if (data.hallazgos.length > 0) {
            listaHal.innerHTML = data.hallazgos.map(h => {
                const color = h.estado === 'CRITICO' ? 'rose' : (h.estado === 'ADVERTENCIA' ? 'amber' : 'blue');
                const bg = h.estado === 'CRITICO' ? 'rose-50' : (h.estado === 'ADVERTENCIA' ? 'amber-50' : 'blue-50');
                const border = h.estado === 'CRITICO' ? 'rose-200' : (h.estado === 'ADVERTENCIA' ? 'amber-200' : 'blue-200');
                return `
                    <div class="p-4 rounded-xl border border-${border} bg-${bg} flex gap-4">
                        <div class="w-10 h-10 rounded-full bg-${color}-100 flex items-center justify-center flex-shrink-0">
                            <i class="ri-alert-line text-${color}-600 font-bold"></i>
                        </div>
                        <div>
                            <h4 class="font-bold text-${color}-900 text-sm">${h.tipo}</h4>
                            <p class="text-xs text-${color}-800 mt-1 leading-relaxed">${h.descripcion}</p>
                            <div class="flex gap-4 mt-2 text-[10px] font-mono text-${color}-700">
                                <span>DGII: ${fCur(h.valor_dgii)}</span>
                                <span>CONTABILIDAD: ${fCur(h.valor_auditoria)}</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            listaHal.innerHTML = '<div class="text-center py-12 text-gray-400 italic">No se han detectado hallazgos. Cumplimiento 100%.</div>';
        }

        // 5. Asientos Propuestos
        const tbody = document.getElementById('prem_asientos_body');
        const empty = document.getElementById('prem_asientos_empty');
        if (data.asientos.length > 0) {
            empty.classList.add('hidden');
            tbody.innerHTML = data.asientos.map(a => `
                <tr class="border-b border-slate-100 last:border-0">
                    <td class="py-4 pr-4">
                        <span class="block font-bold text-slate-700">${a.cuenta}</span>
                        <span class="text-[10px] text-slate-500 uppercase tracking-tighter">${a.concepto}</span>
                    </td>
                    <td class="py-4 px-4 text-right font-mono font-bold text-slate-900">${a.debito > 0 ? fCur(a.debito) : '-'}</td>
                    <td class="py-4 pl-4 text-right font-mono font-bold text-slate-900">${a.credito > 0 ? fCur(a.credito) : '-'}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '';
            empty.classList.remove('hidden');
        }

    } catch (e) {
        console.error("Error en Dashboard Premium:", e);
    }
}

/**
 * Genera y descarga archivos IR-2 (XML, Excel, PDF) - Refined User Style
 * @param {string} formato - xml, excel o pdf
 */
async function generarArchivo(formato = 'xml') {
    const pathParts = window.location.pathname.split('/');
    const cliente_id = pathParts[2];
    const periodo = document.getElementById('empresa_anio')?.value;

    if (!cliente_id || !periodo) {
        alert('Seleccione un cliente y período (año) válido antes de generar.');
        return;
    }

    console.log(`[Generador] Iniciando generación POST de ${formato.toUpperCase()}...`);
    
    // Opcional: Feedback visual en el botón si lo deseamos (Premium)
    
    try {
        const response = await safeFetch(`/api/generar_ir2/${cliente_id}/${periodo}?formato=${formato}`, {
            method: 'POST'
        });

        if (response.status === 400) {
            const errorData = await response.json();
            let msg = `❌ IR-2 BLOQUEADO\n\nMotivo: ${errorData.mensaje}`;
            if (errorData.recomendacion_socio) {
                msg += `\n\nRecomendación del Socio: ${errorData.recomendacion_socio}`;
            }
            alert(msg);
            return;
        }

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Error desconocido en el servidor');
        }

        // Descarga automática del archivo vía Blob
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Determinar extensión correcta
        const ext = formato.toLowerCase() === 'excel' ? 'xlsx' : formato.toLowerCase();
        a.download = `IR2_${periodo}_${formato.toUpperCase()}.${ext}`;
        
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        console.log(`✅ Archivo ${formato.toUpperCase()} generado exitosamente.`);

    } catch (error) {
        console.error("Error en la petición de generación:", error);
        alert('Error al generar el IR-2: ' + error.message);
    }
}

/**
 * Función para narrar el informe ejecutivo vía IA (Web Speech API)
 */
let synth = window.speechSynthesis;
let currentUtterance = null;

async function narrarInforme() {
    const pathParts = window.location.pathname.split('/');
    const cliente_id = pathParts[2];
    const periodo = document.getElementById('empresa_anio')?.value;

    if (!cliente_id || !periodo) {
        alert('Seleccione un cliente y período válido.');
        return;
    }

    if (synth.speaking) {
        console.log("[Audio] Deteniendo narración previa...");
        synth.cancel();
        return; // Click de nuevo para detener
    }

    console.log("[Audio] Obteniendo narrativa de la IA...");
    
    try {
        const resp = await safeFetch(`/api/narrativa_fiscal/${cliente_id}/${periodo}`);
        if (!resp.ok) throw new Error('No se pudo obtener la narrativa');
        
        const data = await resp.json();
        const script = data.script;
        
        currentUtterance = new SpeechSynthesisUtterance(script);
        currentUtterance.lang = 'es-DO'; // Localización preferida
        currentUtterance.rate = 0.95;   // Tono pausado y profesional
        currentUtterance.pitch = 1.0;

        // Intentar seleccionar una voz premium si existe
        const voices = synth.getVoices();
        const preferredVoice = voices.find(v => (v.name.includes('Sabina') || v.name.includes('Helena')) && v.lang.startsWith('es'));
        if (preferredVoice) currentUtterance.voice = preferredVoice;

        console.log("[Audio] Narrando Informe Ejecutivo...");
        synth.speak(currentUtterance);

        currentUtterance.onend = () => {
            console.log("[Audio] Fin de la narración.");
        };

    } catch (err) {
        console.error("Error en narración:", err);
        alert("Ocurrió un problema al intentar narrar el informe.");
    }
}

// ==========================================
// QUICK CREATE CLIENT & PADRON DGII
// ==========================================
let padronTimeout = null;
async function searchPadron(searchTerm) {
    if (searchTerm.length < 3) {
        document.getElementById('dgii-status').innerHTML = '';
        return;
    }
    
    // Debounce: previene saturar el endpoint en cada tecla
    if (padronTimeout) clearTimeout(padronTimeout);
    
    padronTimeout = setTimeout(async () => {
        const inputName = document.getElementById('new-client-name');
        const statusEl = document.getElementById('dgii-status');
        statusEl.innerHTML = '<i class="ri-loader-4-line animate-spin"></i> DGII...';
        
        try {
            const resp = await safeFetch(`/api/padron/buscar/?termino=${encodeURIComponent(searchTerm)}`);
            if (resp.ok) {
                const results = await resp.json();
                if (results && results.length > 0) {
                    const r = results[0];
                    inputName.value = r.razon_social;
                    statusEl.innerHTML = '<span style="color:#10b981"><i class="ri-check-line"></i> Validado</span>';
                } else {
                    statusEl.innerHTML = '<span style="color:#f59e0b">No encontrado</span>';
                }
            } else {
                statusEl.innerHTML = '<span style="color:#ef4444">Error DGII</span>';
            }
        } catch(e) {
            statusEl.innerHTML = '<span style="color:#ef4444">Fallo de Red</span>';
        }
    }, 600);
}

async function createClient() {
    const rnc = document.getElementById('new-client-rnc').value.replace(/-/g, '').trim();
    const name = document.getElementById('new-client-name').value.trim();
    const btn = document.getElementById('btn-create-client');
    
    if (!rnc || !name) {
        alert("Completa el RNC y la Razón Social.");
        return;
    }
    
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="ri-loader-4-line animate-spin text-lg"></i> Creando y Asignando...';
    btn.disabled = true;
    
    try {
        const payload = { rnc: rnc, razon_social: name };
        const resp = await safeFetch('/api/clientes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (resp.ok) {
            const data = await resp.json();
            // Redirigimos inmediatamente al panel de este cliente p.e. /cliente/3
            window.location.href = `/cliente/${data.id}`;
        } else {
            const error = await resp.json();
            alert("Aviso Backend: " + (error.detail || "Ya existe el RNC u ocurrió un problema."));
            // Si el RNC ya estaba registrado, quizás queramos redirigir de todos modos si el ID vino en el JSON:
            if (error.id) {
                window.location.href = `/cliente/${error.id}`;
            }
        }
    } catch(e) {
        alert("Fallo de conexión al Motor Fiscal.");
        console.error(e);
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}
