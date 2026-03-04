// ---- FIRMA ----
const canvasFirma = document.getElementById('firmaUsuario');
const firmaUsuario = new SignaturePad(canvasFirma);

canvasFirma.style.height = '100px';

function ajustarCanvas(canvas) {
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = canvas.offsetWidth * ratio;
    canvas.height = 100 * ratio;
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

// ---- GENERAR PDF ----
function generarPDF() {
    const elemento = document.getElementById('documentoCompleto');
    const boton = document.getElementById('botonPDF');
    const btnLimpiar = document.getElementById('btnLimpiarFirma');

    const firmaData = !firmaUsuario.isEmpty() ? firmaUsuario.toDataURL('image/png') : null;
    const canvasWrapper = canvasFirma.parentElement;

    // Placeholder para la firma
    const placeholder = document.createElement('div');
    placeholder.style.cssText = 'width:100%; height:100px; border:1px solid #007A33; background:#fff; display:block;';
    if (firmaData) {
        const img = document.createElement('img');
        img.src = firmaData;
        img.style.cssText = 'width:100%; height:100px; object-fit:contain;';
        placeholder.appendChild(img);
    }

    // Sustituir todos los inputs por spans de texto plano
    const inputsInfo = [];
    document.querySelectorAll('input[type="text"], input[type="date"]').forEach(input => {
        const span = document.createElement('span');
        span.textContent = input.value;
        span.style.cssText = 'font-size:13px; padding:2px 4px; display:inline-block; border-bottom:1px solid #333; word-break:break-word; white-space:normal;';
        input.parentElement.insertBefore(span, input);
        input.style.display = 'none';
        inputsInfo.push({ input, span });
    });

    // Sustituir select de marca por texto plano
    const marcaSelect = document.querySelector('.marca-select');
    const marcaOtro = document.querySelector('.marca-otro');
    const marcaValor = marcaSelect.value === 'Otro' ? marcaOtro.value : marcaSelect.value;
    const marcaSpan = document.createElement('span');
    marcaSpan.textContent = marcaValor;
    marcaSpan.style.cssText = 'font-size:13px; padding:2px 4px;';
    marcaSelect.parentElement.insertBefore(marcaSpan, marcaSelect);
    marcaSelect.style.display = 'none';
    marcaOtro.style.display = 'none';

    // Ocultar canvas y botones
    canvasFirma.style.display = 'none';
    canvasWrapper.insertBefore(placeholder, canvasFirma);
    btnLimpiar.style.display = 'none';
    boton.style.display = 'none';

    html2canvas(elemento, {
        scale: 1.5,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff'
    }).then(canvas => {

        // Restaurar inputs
        inputsInfo.forEach(({ input, span }) => {
            input.style.display = '';
            input.parentElement.removeChild(span);
        });

        // Restaurar marca
        marcaSelect.style.display = '';
        marcaSelect.parentElement.removeChild(marcaSpan);
        if (marcaSelect.value === 'Otro') marcaOtro.style.display = 'inline-block';

        // Restaurar firma y botones
        canvasFirma.style.display = 'block';
        canvasWrapper.removeChild(placeholder);
        btnLimpiar.style.display = '';
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

        doc.save('compromiso_material_tic.pdf');

    }).catch(err => {
        console.error('Error al generar PDF:', err);

        // Restaurar todo en caso de error
        inputsInfo.forEach(({ input, span }) => {
            input.style.display = '';
            input.parentElement.removeChild(span);
        });
        marcaSelect.style.display = '';
        marcaSelect.parentElement.removeChild(marcaSpan);
        canvasFirma.style.display = 'block';
        canvasWrapper.removeChild(placeholder);
        btnLimpiar.style.display = '';
        boton.style.display = '';
    });
}