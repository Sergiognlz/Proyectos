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
function drawSeccionHeader(doc, texto, x, y, w) {
    const h = 5;
    doc.setFillColor(0, 122, 51);
    doc.rect(x, y, w, h, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(7.5);
    doc.setFont('helvetica', 'bold');
    doc.text(texto, x + 2, y + h * 0.72);
    doc.setTextColor(0, 0, 0);
    doc.setFont('helvetica', 'normal');
    return y + h;
}

function drawCampo(doc, label, valor, x, y, w) {
    const pad = 3;
    doc.setFontSize(6);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(80, 80, 80);
    doc.text(label, x + pad, y + 2.5);
    doc.setDrawColor(180, 180, 180);
    doc.setLineWidth(0.2);
    doc.rect(x, y + 3.2, w, 5.5);
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(0, 0, 0);
    doc.text(valor || '', x + pad, y + 3.2 + 4);
    return y + 3.2 + 5.5 + 1;
}

function drawRadio(doc, label, marcado, x, y) {
    const r = 1.4;
    doc.setDrawColor(100, 100, 100);
    doc.setLineWidth(0.25);
    doc.circle(x + r, y + r, r);
    if (marcado) {
        doc.setFillColor(0, 122, 51);
        doc.circle(x + r, y + r, r * 0.55, 'F');
        doc.setFillColor(255, 255, 255);
    }
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(0, 0, 0);
    doc.text(label, x + r * 2 + 1.5, y + r * 1.5);
    return x + r * 2 + 1.5 + doc.getTextWidth(label) + 3;
}

// ---- GENERAR PDF ----
function generarPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');
    const PW = doc.internal.pageSize.getWidth();
    const PH = doc.internal.pageSize.getHeight();
    const M = 8;
    const W = PW - M * 2;
    let y = M;

    // ==============================
    // CABECERA: logo izquierda
    // ==============================
    const logoImg = document.querySelector('.cabecera-logo-completo');
    let logoH = 0;
    if (logoImg && logoImg.complete && logoImg.naturalWidth > 0) {
        try {
            const tmp = document.createElement('canvas');
            tmp.width = logoImg.naturalWidth;
            tmp.height = logoImg.naturalHeight;
            tmp.getContext('2d').drawImage(logoImg, 0, 0);
            const logoData = tmp.toDataURL('image/png');
            logoH = 9;
            const logoW = logoH * (logoImg.naturalWidth / logoImg.naturalHeight);
            doc.addImage(logoData, 'PNG', M, y, logoW, logoH);
        } catch(e) {
            doc.setFontSize(8); doc.setFont('helvetica','bold');
            doc.setTextColor(0,122,51);
            doc.text('Junta de Andalucía — SANDETEL', M, y+6);
            doc.setTextColor(0,0,0);
            logoH = 7;
        }
    }
    y += logoH + 2;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.6);
    doc.line(M, y, M+W, y);
    y += 4;

    // ==============================
    // TÍTULO centrado, subrayado
    // ==============================
    doc.setFontSize(10); doc.setFont('helvetica','bold');
    doc.setTextColor(0,122,51);
    const titulo = 'Formulario de Entrega o Recogida de Equipamiento Informático';
    doc.text(titulo, PW/2, y, {align:'center'});
    const tW = doc.getTextWidth(titulo);
    doc.setLineWidth(0.3);
    doc.line(PW/2 - tW/2, y+0.8, PW/2 + tW/2, y+0.8);
    doc.setTextColor(0,0,0);
    y += 5;

    const operacion = getRadioValue('operacion');
    const fechaRaw  = document.getElementById('fecha').value;
    const fechaMostrar = fechaRaw ? fechaRaw.split('-').reverse().join('/') : '';
    const modalidad = getRadioValue('modalidad');

    // ==============================
    // SECCIÓN 1
    // ==============================
    // Calcular altura sección 1
    // barra + fila operacion/tique/fecha + fila modalidad + padding
    const s1H = 5 + 2.5 + 3 + 9.7 + 2 + 3 + 3 + 2;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, s1H);
    const afterSec1Header = drawSeccionHeader(doc, '1. Datos Generales', M, y, W);
    let sy = afterSec1Header + 2;

    // Fila: Operación (col1) | N.º Tique (col2) | Fecha (col3)
    const col3W = W / 3;
    doc.setFontSize(6); doc.setFont('helvetica','normal'); doc.setTextColor(80,80,80);
    doc.text('Operación', M+1, sy+2.5);
    let rx = M+1;
    sy += 3.2;
    rx = drawRadio(doc, 'Entrega',  operacion==='Entrega',  rx, sy);
    rx = drawRadio(doc, 'Recogida', operacion==='Recogida', rx, sy);

    // Tique y Fecha en misma fila
    drawCampo(doc, 'N.º Tique', document.getElementById('nTique').value, M+col3W,   afterSec1Header+2, col3W-1);
    drawCampo(doc, 'Fecha',     fechaMostrar,                             M+col3W*2, afterSec1Header+2, col3W-1);
    sy += 5.5;

    // Modalidad
    doc.setFontSize(6); doc.setFont('helvetica','normal'); doc.setTextColor(80,80,80);
    doc.text('Modalidad', M+1, sy+2.5);
    sy += 3.2;
    let mx = M+1;
    mx = drawRadio(doc, 'Dotación', modalidad==='Dotación',       mx, sy);
    mx = drawRadio(doc, 'Préstamo', modalidad==='Préstamo',       mx, sy);
    mx = drawRadio(doc, 'Otro',     modalidad.startsWith('Otro'), mx, sy);
    if (modalidad.startsWith('Otro:')) {
        doc.setFontSize(7); doc.setFont('helvetica','normal'); doc.setTextColor(0,0,0);
        doc.text(modalidad.replace('Otro: ',''), mx, sy+2.5);
    }
    y += s1H + 1.5;

    // ==============================
    // SECCIÓN 2
    // ==============================
    const hW = W/2 - 1;
    const s2H = 5 + 2.5 + 3 + (9.7*2) + 5;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, s2H);
    const afterS2 = drawSeccionHeader(doc, '2. Datos de la persona que entrega', M, y, W);
    sy = afterS2 + 2;

    const tipoEntrega = getRadioValue('tipoEntrega');
    let ex = M+1;
    ex = drawRadio(doc, 'Área TI',       tipoEntrega==='Área TI',       ex, sy);
    ex = drawRadio(doc, 'Pers. Interno', tipoEntrega==='Pers. Interno', ex, sy);
    ex = drawRadio(doc, 'Pers. Externo', tipoEntrega==='Pers. Externo', ex, sy);
    ex = drawRadio(doc, 'Proveedor',     tipoEntrega==='Proveedor',     ex, sy);
    sy += 5;

    drawCampo(doc, 'Nombre',   document.getElementById('entNombre').value,  M+0.5,    sy, hW-0.5);
    drawCampo(doc, 'DNI',      document.getElementById('entDNI').value,     M+hW+1,   sy, hW);
    sy += 9.7;
    drawCampo(doc, 'Empresa',  document.getElementById('entEmpresa').value, M+0.5,    sy, hW-0.5);
    drawCampo(doc, 'Teléfono', document.getElementById('entTelf').value,    M+hW+1,   sy, hW);
    y += s2H + 1.5;

    // ==============================
    // SECCIÓN 3
    // ==============================
    const s3H = 5 + 2.5 + 3 + (9.7*2) + 5;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, s3H);
    const afterS3 = drawSeccionHeader(doc, '3. Datos de la persona que recoge', M, y, W);
    sy = afterS3 + 2;

    const tipoRecoge = getRadioValue('tipoRecoge');
    let rx2 = M+1;
    rx2 = drawRadio(doc, 'Área TI',       tipoRecoge==='Área TI',       rx2, sy);
    rx2 = drawRadio(doc, 'Pers. Interno', tipoRecoge==='Pers. Interno', rx2, sy);
    rx2 = drawRadio(doc, 'Pers. Externo', tipoRecoge==='Pers. Externo', rx2, sy);
    rx2 = drawRadio(doc, 'Proveedor',     tipoRecoge==='Proveedor',     rx2, sy);
    sy += 5;

    drawCampo(doc, 'Nombre',   document.getElementById('recNombre').value,  M+0.5,    sy, hW-0.5);
    drawCampo(doc, 'DNI',      document.getElementById('recDNI').value,     M+hW+1,   sy, hW);
    sy += 9.7;
    drawCampo(doc, 'Empresa',  document.getElementById('recEmpresa').value, M+0.5,    sy, hW-0.5);
    drawCampo(doc, 'Teléfono', document.getElementById('recTelf').value,    M+hW+1,   sy, hW);
    y += s3H + 1.5;

    // ==============================
    // TABLA EQUIPAMIENTO
    // ==============================
    const datosTabla = getDatosTabla();
    const colHeaders = ['Nombre', 'Marca', 'Modelo', 'N.º de serie', 'CRIHJA / IMEI'];
    const colWidths  = [W*0.26, W*0.12, W*0.22, W*0.20, W*0.20];
    const rowH = 5;
    const tablaH = 5 + rowH + rowH * datosTabla.length + 0.5;

    doc.setDrawColor(0,122,51); doc.setLineWidth(0.3);
    doc.rect(M, y, W, tablaH);
    const afterTablaH = drawSeccionHeader(doc, 'Datos del equipamiento informático entregado o recogido', M, y, W);
    sy = afterTablaH;

    // Cabecera tabla oscura
    doc.setFillColor(33,37,41);
    doc.rect(M, sy, W, rowH, 'F');
    doc.setTextColor(255,255,255);
    doc.setFontSize(6.5); doc.setFont('helvetica','bold');
    let cx = M;
    colHeaders.forEach((h,i) => {
        doc.text(h, cx+1.5, sy+rowH*0.72);
        cx += colWidths[i];
    });
    doc.setTextColor(0,0,0);
    sy += rowH;

    doc.setFont('helvetica','normal'); doc.setFontSize(6.5);
    datosTabla.forEach(fila => {
        cx = M;
        doc.setDrawColor(180,180,180); doc.setLineWidth(0.15);
        doc.rect(M, sy, W, rowH);
        fila.forEach((celda, ci) => {
            if (ci > 0) doc.line(cx, sy, cx, sy+rowH);
            doc.text(celda||'', cx+1.5, sy+rowH*0.72);
            cx += colWidths[ci];
        });
        sy += rowH;
    });
    y += tablaH + 1.5;

    // ==============================
    // TEXTO LEGAL
    // ==============================
    const parrafosLegal = document.querySelectorAll('.texto-legal p');
    const FS_LEGAL = 5.2;
    const LINE_H   = FS_LEGAL * 0.43;
    doc.setFontSize(FS_LEGAL); doc.setFont('helvetica','normal');
    let legalH = 2.5;
    parrafosLegal.forEach(p => {
        const lines = doc.splitTextToSize(p.textContent.trim(), W-3);
        legalH += lines.length * LINE_H + 0.8;
    });

    doc.setFillColor(249,249,249); doc.setDrawColor(190,190,190); doc.setLineWidth(0.2);
    doc.rect(M, y, W, legalH, 'FD');
    let ly = y + 2;
    parrafosLegal.forEach(p => {
        const lines = doc.splitTextToSize(p.textContent.trim(), W-3);
        doc.text(lines, M+1.5, ly);
        ly += lines.length * LINE_H + 0.8;
    });
    y += legalH + 1.5;

    // ==============================
    // FIRMAS — ocupan el espacio restante
    // ==============================
    const espacioRestante = PH - M - y;
    const labelH = 5;
    const firmaH = Math.max(espacioRestante - labelH - 1, 12);
    const firmaW = W/2 - 3;

    doc.setFontSize(7.5); doc.setFont('helvetica','bold');
    doc.text('Firma del Área TI',      M + firmaW/2,          y+3.5, {align:'center'});
    doc.text('Firma de la otra parte', M + firmaW+6+firmaW/2, y+3.5, {align:'center'});
    y += labelH;

    doc.setDrawColor(0,122,51); doc.setLineWidth(0.4);
    doc.rect(M,          y, firmaW, firmaH);
    doc.rect(M+firmaW+6, y, firmaW, firmaH);

    // Insertar firmas preservando aspect ratio
    const insertarFirma = (dataURL, srcCanvas, fx, fy, fw, fh) => {
        const ratio = srcCanvas.width / srcCanvas.height;
        let iw = fw * 0.85, ih = iw / ratio;
        if (ih > fh * 0.85) { ih = fh * 0.85; iw = ih * ratio; }
        const ix = fx + (fw - iw) / 2;
        const iy = fy + (fh - ih) / 2;
        doc.addImage(dataURL, 'PNG', ix, iy, iw, ih);
    };

    if (!firmaTI.isEmpty())
        insertarFirma(firmaTI.toDataURL('image/png'),    canvasAreaTI,    M+1,        y+1, firmaW-2, firmaH-2);
    if (!firmaOtra.isEmpty())
        insertarFirma(firmaOtra.toDataURL('image/png'),  canvasOtraParte, M+firmaW+7, y+1, firmaW-2, firmaH-2);

    // ==============================
    // NOMBRE ARCHIVO
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