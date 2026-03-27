// ---- INICIALIZAR SIGNATURE PAD ----
const canvasFirma = document.getElementById('firmaUsuario');
const firmaUsuario = new SignaturePad(canvasFirma);

canvasFirma.style.height = '150px';

function ajustarCanvas(canvas) {
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = canvas.offsetWidth * ratio;
    canvas.height = 150 * ratio;
    canvas.getContext('2d').scale(ratio, ratio);
}
ajustarCanvas(canvasFirma);

function limpiarFirma() {
    firmaUsuario.clear();
}

// ---- MARCA SELECT ----
document.querySelector('.marca-select').addEventListener('change', function() {
    const otroInput = this.parentElement.querySelector('.marca-otro');
    const btnVolver = this.parentElement.querySelector('.btn-volver-marca');
    if (this.value === 'Otro') {
        this.style.display = 'none';
        otroInput.style.display = 'inline-block';
        btnVolver.style.display = 'inline-block';
        otroInput.focus();
    } else {
        this.style.display = 'inline-block';
        otroInput.style.display = 'none';
        btnVolver.style.display = 'none';
    }
});

document.querySelector('.btn-volver-marca').addEventListener('click', function() {
    const parent = this.parentElement;
    const select = parent.querySelector('.marca-select');
    const otroInput = parent.querySelector('.marca-otro');
    select.value = '';
    select.style.display = 'inline-block';
    otroInput.style.display = 'none';
    otroInput.value = '';
    this.style.display = 'none';
});

// ---- HELPERS PDF ----
function linea(doc, y, M, W) {
    doc.setDrawColor(180, 180, 180);
    doc.setLineWidth(0.2);
    doc.line(M, y, M + W, y);
}

function campoConLinea(doc, label, valor, x, y, w, labelFs, valFs) {
    if (label) {
        doc.setFontSize(labelFs);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(80, 80, 80);
        doc.text(label, x, y);
        x += doc.getTextWidth(label) + 1.5;
        w -= doc.getTextWidth(label) + 1.5;
    }
    doc.setFontSize(valFs);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(0, 0, 0);
    doc.text(valor || '', x + 1, y);
    doc.setDrawColor(100, 100, 100);
    doc.setLineWidth(0.3);
    doc.line(x, y + 0.8, x + w, y + 0.8);
    doc.setFont('helvetica', 'normal');
}

// ---- GENERAR PDF ----
function generarPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');
    const PW = doc.internal.pageSize.getWidth();
    const PH = doc.internal.pageSize.getHeight();
    const M  = 18;  // margen amplio para este doc tipo carta
    const W  = PW - M * 2;
    let y = M;

    // ==============================
    // CABECERA: logo centrado
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
            logoH = 10;
            const logoW = logoH * (logoImg.naturalWidth / logoImg.naturalHeight);
            doc.addImage(logoData, 'PNG', PW/2 - logoW/2, y, logoW, logoH);
        } catch(e) {
            doc.setFontSize(9); doc.setFont('helvetica','bold');
            doc.setTextColor(0,122,51);
            doc.text('Junta de Andalucía — SANDETEL', PW/2, y+7, {align:'center'});
            doc.setTextColor(0,0,0);
            logoH = 8;
        }
    }
    y += logoH + 3;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.7);
    doc.line(M, y, M+W, y);
    y += 7;

    // ==============================
    // TÍTULO
    // ==============================
    doc.setFontSize(9.5);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(0, 0, 0);
    const tituloTexto = 'COMPROMISO DE RESPONSABILIDAD EN LA CESIÓN Y USO DE MATERIAL TIC\nTITULARIDAD DE SOCIEDAD ANDALUZA PARA EL DESARROLLO DE LAS TELECOMUNICACIONES, S.A.';
    const tituloLines = doc.splitTextToSize(tituloTexto, W);
    doc.text(tituloLines, PW/2, y, {align:'center'});
    // Subrayado
    const tituloH = tituloLines.length * 5;
    doc.setDrawColor(100,100,100); doc.setLineWidth(0.3);
    doc.line(M + W*0.1, y + tituloH - 1, M + W*0.9, y + tituloH - 1);
    y += tituloH + 28;

    // ==============================
    // CUERPO: "Yo,"
    // ==============================
    const FS  = 9;    // fuente cuerpo
    const FSB = 9.5;  // fuente valores
    const LH  = 5.5;  // interlineado

    doc.setFontSize(FS); doc.setFont('helvetica','normal'); doc.setTextColor(0,0,0);
    doc.text('Yo,', M, y);
    y += LH * 0.5;

    // Nombre — línea completa
    const nombreVal = document.getElementById('nombreUsuario').value.trim();
    doc.setFontSize(FSB); doc.setFont('helvetica','bold');
    doc.text(nombreVal || '', M + 1, y + LH);
    doc.setDrawColor(100,100,100); doc.setLineWidth(0.3);
    doc.line(M, y + LH + 1, M + W, y + LH + 1);
    y += LH * 2;

    // "con DNI _____ declaro..."
    const dniVal = document.getElementById('dniUsuario').value.trim();
    const textoAntesDNI = 'con DNI ';
    const textoPostDNI  = ' declaro haber recibido la cesión del siguiente terminal/dispositivo móvil titularidad de';
    const textoPost2    = 'SOCIEDAD ANDALUZA PARA EL DESARROLLO DE LAS TELECOMUNICACIONES, S.A. para su uso como apoyo';
    const textoPost3    = 'a mis funciones y tareas en la empresa:';

    doc.setFontSize(FS); doc.setFont('helvetica','normal');
    let lineText = textoAntesDNI;
    doc.text(lineText, M, y);
    const xDni = M + doc.getTextWidth(lineText);
    // valor DNI en negrita con subrayado
    doc.setFont('helvetica','bold');
    doc.text(dniVal || '', xDni + 1, y);
    doc.setDrawColor(100,100,100); doc.setLineWidth(0.3);
    doc.line(xDni, y+0.8, xDni + 35, y+0.8);
    const xPostDni = xDni + 36;
    doc.setFont('helvetica','normal');
    // Texto que sigue en la misma línea
    const restoPrimerLinea = doc.splitTextToSize(textoPostDNI, M + W - xPostDni);
    doc.text(restoPrimerLinea[0], xPostDni, y);
    y += LH;
    // Resto del párrafo
    const parrafo1Lines = doc.splitTextToSize(
        restoPrimerLinea.slice(1).join(' ') + ' ' + textoPost2 + ' ' + textoPost3,
        W
    );
    doc.text(parrafo1Lines, M, y);
    y += parrafo1Lines.length * LH + 4;

    // ==============================
    // CAMPOS: Marca, Modelo, IMEI, Fecha
    // ==============================
    const marcaSelect = document.querySelector('.marca-select');
    const marcaOtro   = document.querySelector('.marca-otro');
    const marcaVal    = marcaSelect.value === 'Otro' ? marcaOtro.value : marcaSelect.value;
    const modeloVal   = document.getElementById('modelo').value.trim();
    const imeiVal     = document.getElementById('imei').value.trim();
    const fechaRaw    = document.getElementById('fechaEntrega').value;
    const fechaVal    = fechaRaw ? fechaRaw.split('-').reverse().join('/') : '';

    const campos = [
        { label: 'Marca:', valor: marcaVal },
        { label: 'Modelo:', valor: modeloVal },
        { label: 'Código de IMEI:', valor: imeiVal },
        { label: 'Fecha de Entrega:', valor: fechaVal },
    ];

    campos.forEach(c => {
        doc.setFontSize(FS); doc.setFont('helvetica','normal'); doc.setTextColor(80,80,80);
        doc.text(c.label, M, y);
        const xVal = M + doc.getTextWidth(c.label) + 2;
        doc.setFontSize(FSB); doc.setFont('helvetica','bold'); doc.setTextColor(0,0,0);
        doc.text(c.valor || '', xVal, y);
        doc.setDrawColor(100,100,100); doc.setLineWidth(0.25);
        doc.line(xVal, y+0.8, M+W, y+0.8);
        y += LH + 1.5;
    });
    y += 4;

    // ==============================
    // TEXTO LEGAL (del DOM)
    // ==============================
    const parrafosLegal = document.querySelectorAll('.texto-legal-compromiso p');
    const FS_LEGAL = 7.5;
    const LH_LEGAL = FS_LEGAL * 0.50;

    // Calcular altura
    doc.setFontSize(FS_LEGAL); doc.setFont('helvetica','normal');
    let legalH = 4;
    parrafosLegal.forEach(p => {
        const lines = doc.splitTextToSize(p.textContent.trim(), W - 6);
        legalH += lines.length * LH_LEGAL + 1.5;
    });

    doc.setFillColor(249,249,249); doc.setDrawColor(0,122,51); doc.setLineWidth(0.4);
    doc.rect(M, y, W, legalH, 'FD');
    // Borde izquierdo verde más grueso
    doc.setFillColor(0,122,51);
    doc.rect(M, y, 2, legalH, 'F');

    let ly = y + 3;
    doc.setTextColor(60,60,60);
    parrafosLegal.forEach(p => {
        const lines = doc.splitTextToSize(p.textContent.trim(), W - 8);
        doc.text(lines, M + 4, ly);
        ly += lines.length * LH_LEGAL + 1.5;
    });
    doc.setTextColor(0,0,0);
    y += legalH + 8;

    // ==============================
    // FECHA DE FIRMA — anclada al fondo
    // ==============================
    const ciudadVal = document.getElementById('ciudad').value.trim();
    const diaVal    = document.getElementById('dia').value.trim();
    const mesVal    = document.getElementById('mes').value.trim();
    const anioVal   = document.getElementById('anio').value.trim();

    const firmaW  = W * 0.55;
    const firmaX  = M + (W - firmaW) / 2;
    const firmaH  = 38;
    const labelH  = 10;
    const fechaH  = 8;
    // Todo anclado: fecha + label + firma + margen inferior
    const bloqueY = PH - M - fechaH - labelH - firmaH - 2;

    // Línea separadora
    doc.setDrawColor(200,200,200); doc.setLineWidth(0.3);
    doc.line(M, bloqueY - 5, M+W, bloqueY - 5);

    // Fecha centrada
    doc.setFontSize(9); doc.setFont('helvetica','normal'); doc.setTextColor(0,0,0);
    const fechaFirmaTexto = `En ${ciudadVal || '_______________'}, a ${diaVal || '__'} de ${mesVal || '___________'} de 20${anioVal || '__'}`;
    doc.text(fechaFirmaTexto, PW/2, bloqueY, {align:'center'});

    // Etiqueta firma
    const yLabel = bloqueY + fechaH;
    doc.setFontSize(8.5); doc.setFont('helvetica','bold');
    doc.text('Firma del usuario', firmaX + firmaW/2, yLabel, {align:'center'});

    // Recuadro firma
    const yFirma = yLabel + 3;
    doc.setDrawColor(0,122,51); doc.setLineWidth(0.5);
    doc.rect(firmaX, yFirma, firmaW, firmaH);

    if (!firmaUsuario.isEmpty()) {
        const ratio = (canvasFirma.offsetWidth || 400) / 150;
        let iw = firmaW * 0.78, ih = iw / ratio;
        if (ih > firmaH * 0.78) { ih = firmaH * 0.78; iw = ih * ratio; }
        const ix = firmaX + (firmaW - iw) / 2;
        const iy = yFirma + (firmaH - ih) / 2;
        doc.addImage(firmaUsuario.toDataURL('image/png'), 'PNG', ix, iy, iw, ih);
    }

    // ==============================
    // NOMBRE DEL ARCHIVO
    // ==============================
    const dniArchivo   = dniVal.replace(/\s/g,'') || 'SinDNI';
    const nombrePartes = document.getElementById('nombreUsuario').value.trim().split(/\s+/);
    const inicialN     = nombrePartes[0] ? nombrePartes[0][0].toUpperCase() : '';
    const apellidoN    = nombrePartes[1] || '';
    const nombreArchivo = (inicialN + apellidoN) || 'SinNombre';
    const fechaArch    = fechaRaw ? fechaRaw.split('-').reverse().join('') : 'SinFecha';

    doc.save(`${dniArchivo}_${nombreArchivo}_Cesion_${fechaArch}.pdf`);
}