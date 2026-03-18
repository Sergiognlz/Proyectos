// ---- INICIALIZAR SIGNATURE PAD ----
const canvasAreaTI = document.getElementById('firmaAreaTI');
const canvasOtraParte = document.getElementById('firmaOtraParte');

const firmaTI = new SignaturePad(canvasAreaTI);
const firmaOtra = new SignaturePad(canvasOtraParte);

// Mostrar campo de texto al seleccionar Otro en Modalidad
document.querySelectorAll('input[name="modalidad"]').forEach(radio => {
    radio.addEventListener('change', () => {
        const otroTexto = document.getElementById('modalidadOtroTexto');
        otroTexto.style.display = radio.value === 'Otro' && radio.checked ? 'block' : 'none';
    });
});

// ---- MARCA SELECT con botón volver ----
document.querySelectorAll('.marca-select').forEach(select => {
    select.addEventListener('change', function() {
        const otroInput = this.parentElement.querySelector('.marca-otro');
        const btnVolver = this.parentElement.querySelector('.btn-volver-marca');
        if (this.value === 'Otro') {
            this.style.display = 'none';
            otroInput.style.display = 'block';
            btnVolver.style.display = 'inline-block';
            otroInput.focus();
        } else {
            this.style.display = 'block';
            otroInput.style.display = 'none';
            btnVolver.style.display = 'none';
        }
    });
});

document.querySelectorAll('.btn-volver-marca').forEach(btn => {
    btn.addEventListener('click', function() {
        const parent = this.parentElement;
        const select = parent.querySelector('.marca-select');
        const otroInput = parent.querySelector('.marca-otro');
        select.value = '';
        select.style.display = 'block';
        otroInput.style.display = 'none';
        otroInput.value = '';
        this.style.display = 'none';
    });
});

// Ajustar tamaño del canvas
function ajustarCanvas(canvas) {
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = canvas.offsetWidth * ratio;
    canvas.height = 100 * ratio;
    canvas.getContext('2d').scale(ratio, ratio);
}

canvasAreaTI.style.height = '100px';
canvasOtraParte.style.height = '100px';
ajustarCanvas(canvasAreaTI);
ajustarCanvas(canvasOtraParte);

// ---- LIMPIAR FIRMA ----
function limpiarFirma(id) {
    if (id === 'firmaAreaTI') firmaTI.clear();
    if (id === 'firmaOtraParte') firmaOtra.clear();
}

// ---- OBTENER VALOR DE RADIO BUTTON ----
function getRadioValue(name) {
    const selected = document.querySelector(`input[name="${name}"]:checked`);
    if (!selected) return '';
    if (selected.value === 'Otro' && name === 'modalidad') {
        const texto = document.getElementById('modalidadOtroTexto').value;
        return texto ? `Otro: ${texto}` : 'Otro';
    }
    return selected.value;
}

// ---- RECOGER DATOS DE LA TABLA ----
function getDatosTabla() {
    const filas = document.querySelectorAll('#tablaEquipamiento tbody tr');
    const datos = [];
    filas.forEach(fila => {
        const celdas = fila.querySelectorAll('td');
        const fila_datos = Array.from(celdas).map(celda => {
            const select = celda.querySelector('.marca-select');
            if (select) {
                return select.value === 'Otro'
                    ? celda.querySelector('.marca-otro').value
                    : select.value;
            }
            const input = celda.querySelector('input');
            return input ? input.value : '';
        });
        datos.push(fila_datos);
    });
    return datos;
}

// ---- HELPERS PDF ----
function seccionTitulo(doc, texto, x, y, w, s) {
    doc.setFillColor(0, 122, 51);
    doc.rect(x, y, w, 4.5 * s, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(7 * s);
    doc.setFont('helvetica', 'bold');
    doc.text(texto, x + 1.5 * s, y + 3.2 * s);
    doc.setTextColor(0, 0, 0);
    doc.setFont('helvetica', 'normal');
}

function campo(doc, label, valor, x, y, w, s) {
    doc.setFontSize(6 * s);
    doc.setFont('helvetica', 'bold');
    doc.text(label, x, y);
    doc.setFont('helvetica', 'normal');
    doc.setDrawColor(180, 180, 180);
    doc.rect(x, y + 1 * s, w, 5 * s);
    doc.setFontSize(6.5 * s);
    doc.text(valor || '', x + 1 * s, y + 4.5 * s);
}

function radioDisplay(doc, label, marcado, x, y, s) {
    doc.setDrawColor(80, 80, 80);
    doc.setLineWidth(0.3);
    doc.circle(x + 1.2 * s, y, 1.2 * s);
    if (marcado) {
        doc.setFillColor(0, 122, 51);
        doc.circle(x + 1.2 * s, y, 0.7 * s, 'F');
    }
    doc.setFillColor(255, 255, 255);
    doc.setFontSize(6 * s);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(0, 0, 0);
    doc.text(label, x + 3.2 * s, y + 0.8 * s);
    return x + 3.2 * s + doc.getTextWidth(label) + 3 * s;
}

// ---- GENERAR PDF ----
function generarPDF() {
    const { jsPDF } = window.jspdf;
    const s = 0.88; // escala global

    const doc = new jsPDF('p', 'mm', 'a4');
    const PW = doc.internal.pageSize.getWidth();
    const PH = doc.internal.pageSize.getHeight();
    const M  = 8;
    const W  = PW - M * 2;

    let y = M;

    // ---- CABECERA ----
    const logoImg = document.querySelector('.cabecera-logo-completo');
    if (logoImg && logoImg.complete && logoImg.naturalWidth > 0) {
        try {
            const tmpCanvas = document.createElement('canvas');
            tmpCanvas.width  = logoImg.naturalWidth;
            tmpCanvas.height = logoImg.naturalHeight;
            tmpCanvas.getContext('2d').drawImage(logoImg, 0, 0);
            const logoData = tmpCanvas.toDataURL('image/png');
            const logoH = 12 * s;
            const logoW = logoH * (logoImg.naturalWidth / logoImg.naturalHeight);
            doc.addImage(logoData, 'PNG', M, y, logoW, logoH);
        } catch(e) {
            doc.setFontSize(9 * s);
            doc.setFont('helvetica', 'bold');
            doc.setTextColor(0, 122, 51);
            doc.text('Junta de Andalucía — SANDETEL', M, y + 8 * s);
            doc.setTextColor(0, 0, 0);
        }
    }
    y += 14 * s;
    doc.setDrawColor(0, 122, 51);
    doc.setLineWidth(0.8);
    doc.line(M, y, M + W, y);
    y += 5 * s;

    // ---- TÍTULO ----
    doc.setFontSize(10 * s);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(0, 122, 51);
    doc.text('Formulario de Entrega o Recogida de Equipamiento Informático', PW / 2, y, { align: 'center' });
    doc.setTextColor(0, 0, 0);
    y += 7 * s;

    // ---- SECCIÓN 1: DATOS GENERALES ----
    const operacion = getRadioValue('operacion');
    const fechaRaw  = document.getElementById('fecha').value;
    const fechaMostrar = fechaRaw ? fechaRaw.split('-').reverse().join('/') : '';

    doc.setDrawColor(0, 122, 51);
    doc.setLineWidth(0.3);
    doc.rect(M, y, W, 26 * s);
    seccionTitulo(doc, '1. Datos Generales', M, y, W, s);
    y += 6 * s;

    const colW = W / 3;
    doc.setFontSize(6 * s);
    doc.setFont('helvetica', 'bold');
    doc.text('Operación', M + 2, y);
    y += 3.5 * s;
    let rx = M + 2;
    rx = radioDisplay(doc, 'Entrega',  operacion === 'Entrega',  rx, y, s);
    rx = radioDisplay(doc, 'Recogida', operacion === 'Recogida', rx, y, s);

    campo(doc, 'N.º Tique', document.getElementById('nTique').value, M + colW + 2,     y - 3.5 * s, colW - 4, s);
    campo(doc, 'Fecha',     fechaMostrar,                             M + colW * 2 + 2, y - 3.5 * s, colW - 4, s);
    y += 5 * s;

    const modalidad = getRadioValue('modalidad');
    doc.setFontSize(6 * s);
    doc.setFont('helvetica', 'bold');
    doc.text('Modalidad', M + 2, y);
    y += 3.5 * s;
    let mx = M + 2;
    mx = radioDisplay(doc, 'Dotación', modalidad === 'Dotación',          mx, y, s);
    mx = radioDisplay(doc, 'Préstamo', modalidad === 'Préstamo',          mx, y, s);
    mx = radioDisplay(doc, 'Otro',     modalidad.startsWith('Otro'),      mx, y, s);
    if (modalidad.startsWith('Otro:')) {
        doc.setFontSize(6 * s);
        doc.setFont('helvetica', 'normal');
        doc.text(modalidad.replace('Otro: ', ''), mx, y + 0.8 * s);
    }
    y += 6 * s;

    // ---- SECCIÓN 2: PERSONA QUE ENTREGA ----
    doc.setDrawColor(0, 122, 51);
    doc.rect(M, y, W, 28 * s);
    seccionTitulo(doc, '2. Datos de la persona que entrega', M, y, W, s);
    y += 6 * s;

    const tipoEntrega = getRadioValue('tipoEntrega');
    let ex = M + 2;
    ex = radioDisplay(doc, 'Área TI',       tipoEntrega === 'Área TI',       ex, y, s);
    ex = radioDisplay(doc, 'Pers. Interno', tipoEntrega === 'Pers. Interno', ex, y, s);
    ex = radioDisplay(doc, 'Pers. Externo', tipoEntrega === 'Pers. Externo', ex, y, s);
    ex = radioDisplay(doc, 'Proveedor',     tipoEntrega === 'Proveedor',     ex, y, s);
    y += 4 * s;

    const halfW = W / 2 - 2;
    campo(doc, 'Nombre',   document.getElementById('entNombre').value,  M + 1,         y, halfW, s);
    campo(doc, 'DNI',      document.getElementById('entDNI').value,     M + halfW + 3, y, halfW, s);
    y += 8 * s;
    campo(doc, 'Empresa',  document.getElementById('entEmpresa').value, M + 1,         y, halfW, s);
    campo(doc, 'Teléfono', document.getElementById('entTelf').value,    M + halfW + 3, y, halfW, s);
    y += 9 * s;

    // ---- SECCIÓN 3: PERSONA QUE RECOGE ----
    doc.setDrawColor(0, 122, 51);
    doc.rect(M, y, W, 28 * s);
    seccionTitulo(doc, '3. Datos de la persona que recoge', M, y, W, s);
    y += 6 * s;

    const tipoRecoge = getRadioValue('tipoRecoge');
    let rx2 = M + 2;
    rx2 = radioDisplay(doc, 'Área TI',       tipoRecoge === 'Área TI',       rx2, y, s);
    rx2 = radioDisplay(doc, 'Pers. Interno', tipoRecoge === 'Pers. Interno', rx2, y, s);
    rx2 = radioDisplay(doc, 'Pers. Externo', tipoRecoge === 'Pers. Externo', rx2, y, s);
    rx2 = radioDisplay(doc, 'Proveedor',     tipoRecoge === 'Proveedor',     rx2, y, s);
    y += 4 * s;

    campo(doc, 'Nombre',   document.getElementById('recNombre').value,  M + 1,         y, halfW, s);
    campo(doc, 'DNI',      document.getElementById('recDNI').value,     M + halfW + 3, y, halfW, s);
    y += 8 * s;
    campo(doc, 'Empresa',  document.getElementById('recEmpresa').value, M + 1,         y, halfW, s);
    campo(doc, 'Teléfono', document.getElementById('recTelf').value,    M + halfW + 3, y, halfW, s);
    y += 9 * s;

    // ---- TABLA DE EQUIPAMIENTO ----
    const datosTabla = getDatosTabla();
    const colHeaders = ['Nombre', 'Marca', 'Modelo', 'N.º de serie', 'CRIHJA / IMEI'];
    const colWidths  = [W * 0.25, W * 0.13, W * 0.22, W * 0.20, W * 0.20];
    const rowH       = 5.5 * s;
    const headerH    = 5.5 * s;
    const tablaH     = 4.5 * s + headerH + rowH * datosTabla.length + 4 * s;

    doc.setDrawColor(0, 122, 51);
    doc.rect(M, y, W, tablaH);
    seccionTitulo(doc, 'Datos del equipamiento informático entregado o recogido', M, y, W, s);
    y += 5 * s;

    // Cabecera tabla
    doc.setFillColor(0, 122, 51);
    doc.rect(M, y, W, headerH, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(6.5 * s);
    doc.setFont('helvetica', 'bold');
    let cx = M;
    colHeaders.forEach((h, i) => {
        doc.text(h, cx + 1.5, y + 3.8 * s);
        cx += colWidths[i];
    });
    doc.setTextColor(0, 0, 0);
    y += headerH;

    // Filas tabla
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(6 * s);
    datosTabla.forEach(fila => {
        cx = M;
        doc.setDrawColor(200, 200, 200);
        doc.setLineWidth(0.2);
        doc.rect(M, y, W, rowH);
        fila.forEach((celda, ci) => {
            if (ci > 0) doc.line(cx, y, cx, y + rowH);
            doc.text(celda || '', cx + 1.5, y + 3.8 * s);
            cx += colWidths[ci];
        });
        y += rowH;
    });
    y += 5 * s;


    // ---- TEXTO LEGAL ----
const parrafosLegal = document.querySelectorAll('.texto-legal p');
doc.setFontSize(5.5 * s);
doc.setFont('helvetica', 'normal');
let legalH = 3 * s;
parrafosLegal.forEach(p => {
    const lines = doc.splitTextToSize(p.textContent.trim(), W - 4);
    legalH += lines.length * 3.0 * s + 1.0 * s;
});

doc.setFillColor(249, 249, 249);
doc.setDrawColor(200, 200, 200);
doc.setLineWidth(0.3);
doc.rect(M, y, W, legalH, 'FD');
let ly = y + 2.5 * s;
parrafosLegal.forEach(p => {
    const lines = doc.splitTextToSize(p.textContent.trim(), W - 4);
    doc.text(lines, M + 2, ly);
    ly += lines.length * 3.0 * s + 1.0 * s;
});
y += legalH + 4 * s;

    // ---- FIRMAS ----
    const firmaW = W / 2 - 4;
    const firmaH = 20 * s;

    doc.setFontSize(7 * s);
    doc.setFont('helvetica', 'bold');
    doc.text('Firma del Área TI',      M + firmaW / 2,              y + 2 * s, { align: 'center' });
    doc.text('Firma de la otra parte', M + firmaW + 8 + firmaW / 2, y + 2 * s, { align: 'center' });
    y += 5 * s;

    doc.setDrawColor(0, 122, 51);
    doc.setLineWidth(0.4);
    doc.rect(M,              y, firmaW, firmaH);
    doc.rect(M + firmaW + 8, y, firmaW, firmaH);

    if (!firmaTI.isEmpty()) {
        doc.addImage(firmaTI.toDataURL('image/png'),    'PNG', M + 1,              y + 1, firmaW - 2, firmaH - 2);
    }
    if (!firmaOtra.isEmpty()) {
        doc.addImage(firmaOtra.toDataURL('image/png'),  'PNG', M + firmaW + 9,     y + 1, firmaW - 2, firmaH - 2);
    }

    // ---- NOMBRE DEL ARCHIVO ----
    const operacionFinal  = getRadioValue('operacion') || 'SinOperacion';
    const esPrestamo      = document.getElementById('modPrestamo').checked;
    const esEntrega       = operacionFinal === 'Entrega';
    const dniId           = esEntrega ? 'recDNI'    : 'entDNI';
    const nombreId        = esEntrega ? 'recNombre' : 'entNombre';
    const dni             = document.getElementById(dniId).value.trim() || 'SinDNI';
    const nombreCompleto  = document.getElementById(nombreId).value.trim();
    const partes          = nombreCompleto.split(/\s+/);
    const inicialNombre   = partes[0] ? partes[0][0].toUpperCase() : '';
    const apellido        = partes[1] ? partes[1] : '';
    const nombreArchivo   = (inicialNombre + apellido) || 'SinNombre';
    const fechaFormateada = fechaRaw ? fechaRaw.split('-').reverse().join('') : 'SinFecha';
    const partesPrestamo  = esPrestamo ? ['Prestamo'] : [];
    const segmentos       = [dni, nombreArchivo, operacionFinal, ...partesPrestamo, fechaFormateada];

    doc.save(segmentos.join('_') + '.pdf');
}