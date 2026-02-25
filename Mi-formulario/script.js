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

// Mostrar input de texto al seleccionar Otro en Marca
document.querySelectorAll('.marca-select').forEach(select => {
    select.addEventListener('change', () => {
        const otroInput = select.parentElement.querySelector('.marca-otro');
        if (select.value === 'Otro') {
            select.style.display = 'none';
            otroInput.style.display = 'block';
            otroInput.focus();
        } else {
            select.style.display = 'block';
            otroInput.style.display = 'none';
        }
    });
});

// Ajustar tamaño del canvas al tamaño real en pantalla
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
                if (select.value === 'Otro') {
                    return celda.querySelector('.marca-otro').value;
                }
                return select.value;
            }
            const input = celda.querySelector('input');
            return input ? input.value : '';
        });
        datos.push(fila_datos);
    });
    return datos;
}

// ---- GENERAR PDF ----
function generarPDF() {
    const elemento = document.querySelector('.container');
    const boton = document.getElementById('botonPDF');
    const btnLimpiarTI = document.getElementById('btnLimpiarTI');
    const btnLimpiarOtra = document.getElementById('btnLimpiarOtra');

    const firmaTIData = !firmaTI.isEmpty() ? firmaTI.toDataURL('image/png') : null;
    const firmaOtraData = !firmaOtra.isEmpty() ? firmaOtra.toDataURL('image/png') : null;

    const canvasWrapper1 = canvasAreaTI.parentElement;
    const canvasWrapper2 = canvasOtraParte.parentElement;

    const placeholder1 = document.createElement('div');
    placeholder1.style.cssText = 'width:100%; height:100px; border:1px solid #007A33; background:#fff; display:block;';
    if (firmaTIData) {
        const img = document.createElement('img');
        img.src = firmaTIData;
        img.style.cssText = 'width:100%; height:100px; object-fit:contain;';
        placeholder1.appendChild(img);
    }

    const placeholder2 = document.createElement('div');
    placeholder2.style.cssText = 'width:100%; height:100px; border:1px solid #007A33; background:#fff; display:block;';
    if (firmaOtraData) {
        const img = document.createElement('img');
        img.src = firmaOtraData;
        img.style.cssText = 'width:100%; height:100px; object-fit:contain;';
        placeholder2.appendChild(img);
    }

    // Sustituir selects de marca por spans de texto plano
    const selectsInfo = [];
    document.querySelectorAll('.marca-select').forEach(select => {
        const valor = select.value === 'Otro'
            ? select.parentElement.querySelector('.marca-otro').value
            : select.value;
        const span = document.createElement('span');
        span.textContent = valor;
        span.style.cssText = 'font-size:11px; display:block; padding:2px 4px;';
        select.parentElement.insertBefore(span, select);
        selectsInfo.push({ select, span });
        select.style.display = 'none';
        const otroInput = select.parentElement.querySelector('.marca-otro');
        if (otroInput) otroInput.style.display = 'none';
    });

    canvasAreaTI.style.display = 'none';
    canvasOtraParte.style.display = 'none';
    canvasWrapper1.insertBefore(placeholder1, canvasAreaTI);
    canvasWrapper2.insertBefore(placeholder2, canvasOtraParte);
    btnLimpiarTI.style.display = 'none';
    btnLimpiarOtra.style.display = 'none';
    boton.style.display = 'none';

    html2canvas(elemento, {
        scale: 1.5,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff'
    }).then(canvas => {
        // Restaurar selects
        selectsInfo.forEach(({ select, span }) => {
            select.style.display = '';
            const otroInput = select.parentElement.querySelector('.marca-otro');
            if (otroInput && select.value === 'Otro') otroInput.style.display = 'block';
            select.parentElement.removeChild(span);
        });

        canvasAreaTI.style.display = 'block';
        canvasOtraParte.style.display = 'block';
        canvasWrapper1.removeChild(placeholder1);
        canvasWrapper2.removeChild(placeholder2);
        btnLimpiarTI.style.display = '';
        btnLimpiarOtra.style.display = '';
        boton.style.display = '';

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF('p', 'mm', 'a4');

        const pageWidth = doc.internal.pageSize.getWidth();
        const pageHeight = doc.internal.pageSize.getHeight();
        const pdfHeight = (canvas.height * pageWidth) / canvas.width;

        if (pdfHeight <= pageHeight) {
            doc.addImage(canvas.toDataURL('image/jpeg', 0.85), 'JPEG', 0, 0, pageWidth, pdfHeight);
        } else {
            const escala = pageWidth / canvas.width;
            const alturaCorte = Math.floor(pageHeight / escala);
            let posicion = 0;
            let primeraPagina = true;

            while (posicion < canvas.height) {
                const alturaTrozo = Math.min(alturaCorte, canvas.height - posicion);
                if (alturaTrozo <= 0) break;

                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = canvas.width;
                tempCanvas.height = alturaTrozo;
                const ctx = tempCanvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
                ctx.drawImage(canvas, 0, posicion, canvas.width, alturaTrozo, 0, 0, canvas.width, alturaTrozo);

                if (!primeraPagina) doc.addPage();
                doc.addImage(tempCanvas.toDataURL('image/jpeg', 0.85), 'JPEG', 0, 0, pageWidth, (alturaTrozo * pageWidth) / canvas.width);

                posicion += alturaTrozo;
                primeraPagina = false;
            }
        }

        doc.save('formulario_equipamiento.pdf');

    }).catch(err => {
        console.error('Error al generar PDF:', err);
        selectsInfo.forEach(({ select, span }) => {
            select.style.display = '';
            select.parentElement.removeChild(span);
        });
        canvasAreaTI.style.display = 'block';
        canvasOtraParte.style.display = 'block';
        canvasWrapper1.removeChild(placeholder1);
        canvasWrapper2.removeChild(placeholder2);
        btnLimpiarTI.style.display = '';
        btnLimpiarOtra.style.display = '';
        boton.style.display = '';
    });
}