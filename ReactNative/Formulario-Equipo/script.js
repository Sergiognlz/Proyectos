// ---- INICIALIZAR SIGNATURE PAD ----
const canvasAreaTI = document.getElementById('firmaAreaTI');
const canvasOtraParte = document.getElementById('firmaOtraParte');

const firmaTI = new SignaturePad(canvasAreaTI);
const firmaOtra = new SignaturePad(canvasOtraParte);

document.querySelectorAll('input[name="modalidad"]').forEach(radio => {
    radio.addEventListener('change', () => {
        const otroTexto = document.getElementById('modalidadOtroTexto');
        otroTexto.style.display = radio.value === 'Otro' && radio.checked ? 'block' : 'none';
    });
});

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

function limpiarFirma(id) {
    if (id === 'firmaAreaTI') firmaTI.clear();
    if (id === 'firmaOtraParte') firmaOtra.clear();
}

function getRadioValue(name) {
    const selected = document.querySelector(`input[name="${name}"]:checked`);
    if (!selected) return '';
    if (selected.value === 'Otro' && name === 'modalidad') {
        const texto = document.getElementById('modalidadOtroTexto').value;
        return texto ? `Otro: ${texto}` : 'Otro';
    }
    return selected.value;
}

function getDatosTabla() {
    const filas = document.querySelectorAll('#tablaEquipamiento tbody tr');
    const datos = [];
    filas.forEach(fila => {
        const celdas = fila.querySelectorAll('td');
        const fila_datos = Array.from(celdas).map(celda => {
            const select = celda.querySelector('.marca-select');
            if (select) return select.value === 'Otro' ? celda.querySelector('.marca-otro').value : select.value;
            const input = celda.querySelector('input');
            return input ? input.value : '';
        });
        datos.push(fila_datos);
    });
    return datos;
}

// ---- HELPERS PDF ----
function seccionTitulo(doc, texto, x, y, w, fs, bh) {
    doc.setFillColor(0, 122, 51);
    doc.rect(x, y, w, bh, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(fs);
    doc.setFont('helvetica', 'bold');
    doc.text(texto, x + 1.5, y + bh * 0.72);
    doc.setTextColor(0, 0, 0);
    doc.setFont('helvetica', 'normal');
}

function campo(doc, label, valor, x, y, w, labelFs, valFs, fh) {
    doc.setFontSize(labelFs);
    doc.setFont('helvetica', 'bold');
    doc.text(label, x, y);
    doc.setFont('helvetica', 'normal');
    doc.setDrawColor(180, 180, 180);
    doc.setLineWidth(0.2);
    doc.rect(x, y + 0.8, w, fh);
    doc.setFontSize(valFs);
    doc.text(valor || '', x + 1, y + fh * 0.72 + 0.8);
}

function radio(doc, label, marcado, x, y, fs, r) {
    doc.setDrawColor(80, 80, 80);
    doc.setLineWidth(0.25);
    doc.circle(x + r, y, r);
    if (marcado) {
        doc.setFillColor(0, 122, 51);
        doc.circle(x + r, y, r * 0.55, 'F');
        doc.setFillColor(255, 255, 255);
    }
    doc.setFontSize(fs);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(0, 0, 0);
    doc.text(label, x + r * 2 + 1, y + r * 0.7);
    return x + r * 2 + 1 + doc.getTextWidth(label) + 2.5;
}

// ---- GENERAR PDF ----
function generarPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');
    const PW = doc.internal.pageSize.getWidth();   // 210
    const PH = doc.internal.pageSize.getHeight();  // 297
    const M = 7;
    const W = PW - M * 2;  // 196

    // Tamaños fijos calibrados para A4
    const FS_LABEL  = 6.5;   // etiquetas de campo
    const FS_VAL    = 7;     // valores de campo
    const FS_RADIO  = 6.5;   // texto radio
    const FS_SEC    = 7;     // título sección
    const FS_LEGAL  = 5.2;   // texto legal
    const FS_FIRMA  = 7.5;   // etiqueta firmas
    const R_RADIO   = 1.3;   // radio del círculo
    const BH        = 4.5;   // altura barra sección
    const FH        = 5;     // altura campo input
    const ROW_H     = 5.2;   // altura fila tabla
    const GAP       = 1.2;   // espacio entre elementos

    let y = M;

    // ==============================
    // CABECERA
    // ==============================
    const logoImg = document.querySelector('.cabecera-logo-completo');
    let logoOk = false;
    if (logoImg && logoImg.complete && logoImg.naturalWidth > 0) {
        try {
            const tmp = document.createElement('canvas');
            tmp.width = logoImg.naturalWidth;
            tmp.height = logoImg.naturalHeight;
            tmp.getContext('2d').drawImage(logoImg, 0, 0);
            const logoData = tmp.toDataURL('image/png');
            const logoH = 10;
            const logoW = logoH * (logoImg.naturalWidth / logoImg.naturalHeight);
            // Centrar logo
            doc.addImage(logoData, 'PNG', PW/2 - logoW/2, y, logoW, logoH);
            logoOk = true;
            y += logoH + 2;
        } catch(e) {}
    }
    if (!logoOk) {
        doc.setFontSize(9); doc.setFont('helvetica','bold');
        doc.setTextColor(0,122,51);
        doc.text('Junta de Andalucía — SANDETEL', PW/2, y+6, {align:'center'});
        doc.setTextColor(0,0,0);
        y += 9;
    }
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.7);
    doc.line(M, y, M+W, y);
    y += 3.5;

    // ==============================
    // TÍTULO
    // ==============================
    doc.setFontSize(9.5); doc.setFont('helvetica','bold');
    doc.setTextColor(0,122,51);
    doc.text('Formulario de Entrega o Recogida de Equipamiento Informático', PW/2, y, {align:'center'});
    doc.setTextColor(0,0,0);
    y += 4.5;

    // ==============================
    // SECCIÓN 1: DATOS GENERALES
    // ==============================
    const operacion = getRadioValue('operacion');
    const fechaRaw  = document.getElementById('fecha').value;
    const fechaMostrar = fechaRaw ? fechaRaw.split('-').reverse().join('/') : '';
    const modalidad = getRadioValue('modalidad');

    const sec1Y = y;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    // Altura: barra + operacion+radios + modalidad+radios + gap
    const sec1H = BH + 3 + (FH+1.5) + 3 + (FH+1.5) + 2.5;
    doc.rect(M, y, W, sec1H);
    seccionTitulo(doc, '1. Datos Generales', M, y, W, FS_SEC, BH);
    y += BH + 1.5;

    // Fila: Operación | N.º Tique | Fecha
    const col3 = W / 3;
    doc.setFontSize(FS_LABEL); doc.setFont('helvetica','bold');
    doc.text('Operación', M+1, y);
    y += 2.8;
    let rx = M+1;
    rx = radio(doc, 'Entrega',  operacion==='Entrega',  rx, y, FS_RADIO, R_RADIO);
    rx = radio(doc, 'Recogida', operacion==='Recogida', rx, y, FS_RADIO, R_RADIO);

    campo(doc, 'N.º Tique', document.getElementById('nTique').value, M+col3+1,   y-2.8, col3-2, FS_LABEL, FS_VAL, FH);
    campo(doc, 'Fecha',     fechaMostrar,                             M+col3*2+1, y-2.8, col3-2, FS_LABEL, FS_VAL, FH);
    y += FH - 1;

    // Modalidad
    y += GAP;
    doc.setFontSize(FS_LABEL); doc.setFont('helvetica','bold');
    doc.text('Modalidad', M+1, y);
    y += 2.8;
    let mx = M+1;
    mx = radio(doc, 'Dotación', modalidad==='Dotación',        mx, y, FS_RADIO, R_RADIO);
    mx = radio(doc, 'Préstamo', modalidad==='Préstamo',        mx, y, FS_RADIO, R_RADIO);
    mx = radio(doc, 'Otro',     modalidad.startsWith('Otro'),  mx, y, FS_RADIO, R_RADIO);
    if (modalidad.startsWith('Otro:')) {
        doc.setFontSize(FS_RADIO); doc.setFont('helvetica','normal');
        doc.text(modalidad.replace('Otro: ',''), mx, y + R_RADIO*0.7);
    }
    y += 3.5;

    // ==============================
    // SECCIÓN 2: PERSONA QUE ENTREGA
    // ==============================
    y += GAP;
    const sec2H = BH + 3 + (FH+1.5)*2 + 5;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, sec2H);
    seccionTitulo(doc, '2. Datos de la persona que entrega', M, y, W, FS_SEC, BH);
    y += BH + 1.5;

    const tipoEntrega = getRadioValue('tipoEntrega');
    let ex = M+1;
    ex = radio(doc, 'Área TI',       tipoEntrega==='Área TI',       ex, y, FS_RADIO, R_RADIO);
    ex = radio(doc, 'Pers. Interno', tipoEntrega==='Pers. Interno', ex, y, FS_RADIO, R_RADIO);
    ex = radio(doc, 'Pers. Externo', tipoEntrega==='Pers. Externo', ex, y, FS_RADIO, R_RADIO);
    ex = radio(doc, 'Proveedor',     tipoEntrega==='Proveedor',     ex, y, FS_RADIO, R_RADIO);
    y += 3.5;

    const hW = W/2 - 1.5;
    campo(doc, 'Nombre',   document.getElementById('entNombre').value,  M+1,      y, hW, FS_LABEL, FS_VAL, FH);
    campo(doc, 'DNI',      document.getElementById('entDNI').value,     M+hW+2.5, y, hW, FS_LABEL, FS_VAL, FH);
    y += FH + 2.5;
    campo(doc, 'Empresa',  document.getElementById('entEmpresa').value, M+1,      y, hW, FS_LABEL, FS_VAL, FH);
    campo(doc, 'Teléfono', document.getElementById('entTelf').value,    M+hW+2.5, y, hW, FS_LABEL, FS_VAL, FH);
    y += FH + 2;

    // ==============================
    // SECCIÓN 3: PERSONA QUE RECOGE
    // ==============================
    y += GAP;
    const sec3H = BH + 3 + (FH+1.5)*2 + 5;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, sec3H);
    seccionTitulo(doc, '3. Datos de la persona que recoge', M, y, W, FS_SEC, BH);
    y += BH + 1.5;

    const tipoRecoge = getRadioValue('tipoRecoge');
    let rx2 = M+1;
    rx2 = radio(doc, 'Área TI',       tipoRecoge==='Área TI',       rx2, y, FS_RADIO, R_RADIO);
    rx2 = radio(doc, 'Pers. Interno', tipoRecoge==='Pers. Interno', rx2, y, FS_RADIO, R_RADIO);
    rx2 = radio(doc, 'Pers. Externo', tipoRecoge==='Pers. Externo', rx2, y, FS_RADIO, R_RADIO);
    rx2 = radio(doc, 'Proveedor',     tipoRecoge==='Proveedor',     rx2, y, FS_RADIO, R_RADIO);
    y += 3.5;

    campo(doc, 'Nombre',   document.getElementById('recNombre').value,  M+1,      y, hW, FS_LABEL, FS_VAL, FH);
    campo(doc, 'DNI',      document.getElementById('recDNI').value,     M+hW+2.5, y, hW, FS_LABEL, FS_VAL, FH);
    y += FH + 2.5;
    campo(doc, 'Empresa',  document.getElementById('recEmpresa').value, M+1,      y, hW, FS_LABEL, FS_VAL, FH);
    campo(doc, 'Teléfono', document.getElementById('recTelf').value,    M+hW+2.5, y, hW, FS_LABEL, FS_VAL, FH);
    y += FH + 2;

    // ==============================
    // TABLA EQUIPAMIENTO
    // ==============================
    y += GAP;
    const datosTabla = getDatosTabla();
    const colHeaders = ['Nombre', 'Marca', 'Modelo', 'N.º de serie', 'CRIHJA / IMEI'];
    const colWidths  = [W*0.26, W*0.12, W*0.22, W*0.20, W*0.20];
    const tablaH     = BH + ROW_H + ROW_H * datosTabla.length + 1;

    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, tablaH);
    seccionTitulo(doc, 'Datos del equipamiento informático entregado o recogido', M, y, W, FS_SEC, BH);
    y += BH;

    // Cabecera tabla
    doc.setFillColor(30,30,30);
    doc.rect(M, y, W, ROW_H, 'F');
    doc.setTextColor(255,255,255);
    doc.setFontSize(6); doc.setFont('helvetica','bold');
    let cx = M;
    colHeaders.forEach((h, i) => {
        doc.text(h, cx+1.5, y + ROW_H*0.72);
        cx += colWidths[i];
    });
    doc.setTextColor(0,0,0);
    y += ROW_H;

    // Filas
    doc.setFont('helvetica','normal'); doc.setFontSize(6);
    datosTabla.forEach(fila => {
        cx = M;
        doc.setDrawColor(180,180,180); doc.setLineWidth(0.15);
        doc.rect(M, y, W, ROW_H);
        fila.forEach((celda, ci) => {
            if (ci > 0) doc.line(cx, y, cx, y+ROW_H);
            doc.text(celda||'', cx+1.5, y+ROW_H*0.72);
            cx += colWidths[ci];
        });
        y += ROW_H;
    });
    y += 1.5;

    // ==============================
    // TEXTO LEGAL
    // ==============================
    y += GAP;
    const parrafosLegal = document.querySelectorAll('.texto-legal p');
    doc.setFontSize(FS_LEGAL); doc.setFont('helvetica','normal');
    let legalH = 2;
    parrafosLegal.forEach(p => {
        const lines = doc.splitTextToSize(p.textContent.trim(), W-3);
        legalH += lines.length * (FS_LEGAL * 0.42) + 0.8;
    });

    doc.setFillColor(249,249,249); doc.setDrawColor(200,200,200); doc.setLineWidth(0.2);
    doc.rect(M, y, W, legalH, 'FD');
    let ly = y + 1.8;
    parrafosLegal.forEach(p => {
        const lines = doc.splitTextToSize(p.textContent.trim(), W-3);
        doc.text(lines, M+1.5, ly);
        ly += lines.length * (FS_LEGAL * 0.42) + 0.8;
    });
    y += legalH + GAP;

    // ==============================
    // FIRMAS
    // ==============================
    // Calcular espacio restante
    const espacioRestante = PH - M - y;
    const firmaH = Math.max(espacioRestante - 7, 14);
    const firmaW = W/2 - 3;

    doc.setFontSize(FS_FIRMA); doc.setFont('helvetica','bold');
    doc.text('Firma del Área TI',      M + firmaW/2,          y+3, {align:'center'});
    doc.text('Firma de la otra parte', M + firmaW+6+firmaW/2, y+3, {align:'center'});
    y += 4.5;

    doc.setDrawColor(0,122,51); doc.setLineWidth(0.4);
    doc.rect(M,            y, firmaW, firmaH);
    doc.rect(M+firmaW+6,   y, firmaW, firmaH);

    if (!firmaTI.isEmpty())
        doc.addImage(firmaTI.toDataURL('image/png'),   'PNG', M+1,          y+1, firmaW-2, firmaH-2);
    if (!firmaOtra.isEmpty())
        doc.addImage(firmaOtra.toDataURL('image/png'), 'PNG', M+firmaW+7,   y+1, firmaW-2, firmaH-2);

    // ==============================
    // NOMBRE DEL ARCHIVO
    // ==============================
    const operacionFinal  = getRadioValue('operacion') || 'SinOperacion';
    const esPrestamo      = document.getElementById('modPrestamo').checked;
    const esEntrega       = operacionFinal === 'Entrega';
    const dniId           = esEntrega ? 'recDNI'    : 'entDNI';
    const nombreId        = esEntrega ? 'recNombre' : 'entNombre';
    const dni             = document.getElementById(dniId).value.trim() || 'SinDNI';
    const nombreCompleto  = document.getElementById(nombreId).value.trim();
    const partes          = nombreCompleto.split(/\s+/);
    const inicialNombre   = partes[0] ? partes[0][0].toUpperCase() : '';
    const apellido        = partes[1] || '';
    const nombreArchivo   = (inicialNombre + apellido) || 'SinNombre';
    const fechaFormateada = fechaRaw ? fechaRaw.split('-').reverse().join('') : 'SinFecha';
    const partesPrestamo  = esPrestamo ? ['Prestamo'] : [];
    const segmentos       = [dni, nombreArchivo, operacionFinal, ...partesPrestamo, fechaFormateada];

    doc.save(segmentos.join('_') + '.pdf');
}