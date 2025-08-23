const state = {
    active_label: 'text',
    printer_ready: false,
    units: 'metric' // 'metric' or 'imperial'
}

function onload() {
    update_config()
    set_label('text')
    
    // Set initial values after config is loaded
    setTimeout(() => {
        if ($('#tape').val() === null || $('#tape').val() === '') {
            $('#tape').val('12mm')
        }
        if ($('#printer').val() === null || $('#printer').val() === '') {
            $('#printer').val($('#printer option:first').val())
        }
        if ($('#fontname').val() === null || $('#fontname').val() === '') {
            $('#fontname').val('mono')
        }
        if ($('#id').val() === null || $('#id').val() === '') {
            $('#id').val('0')
        }
        
        // Update printer status after everything is loaded
        update_printer_status()
        
        // Set up periodic status updates (every 30 seconds)
        setInterval(update_printer_status, 30000)
    }, 100)
}

function set_label(what) {
    var elements = {
        text: {
            lines: true,
            label: false,
            qrtext: false,
            length: false,
            id: false,
            dictionary: false,
        },
        qr: {
            lines: true,
            label: false,
            qrtext: true,
            length: false,
            id: false,
            dictionary: false,
        },
        wrap: {
            lines: false,
            label: true,
            qrtext: false,
            length: true,
            id: false,
            dictionary: false,
        },
        flag: {
            lines: false,
            label: true,
            qrtext: false,
            length: false,
            id: false,
            dictionary: false,
        },
        aruco: {
            lines: true,
            label: false,
            qrtext: false,
            length: false,
            id: true,
            dictionary: true,

        }
    }

    for (const [k, v] of Object.entries(elements[what])) {
        const divname = '#' + k + "_div"

        if(v) {
            $(divname).show()
        } else {
            $(divname).hide()
        }
    }

    const keys = Object.keys(elements)
    for(let index = 0; index < keys.length; index++) {
        if (keys[index] != what) {
            $('#' + keys[index] + "_nav").removeClass('active')
        } else {
            $('#' + keys[index] + "_nav").addClass('active')
        }
    }

    state.active_label = what
    
    // Ensure default values are set when switching labels
    if ($('#tape').val() === null || $('#tape').val() === '') {
        $('#tape').val('24mm')
    }
    if ($('#id').val() === null || $('#id').val() === '') {
        $('#id').val('0')
    }
    
    update_preview()
}

function update_printer_status() {
    const printer = $('#printer').val()
    if (!printer) return
    
    $.ajax({
        type: "GET",
        dataType: "json",
        url: "/status",
        timeout: 5000,
        async: true
    }).done(function(data) {
        if (data && data[printer]) {
            const ready = data[printer]["ready"]
            const error = data[printer]["error"] 
            
            if (error) {
                // Error state - red
                $('#printer_dot').removeClass('bg-secondary bg-success bg-warning')
                $('#printer_dot').addClass('bg-danger')
                $('#printer_dot').attr('title', `Fehler: ${error}`)
            } else if (ready) {
                // Online and ready - green  
                $('#printer_dot').removeClass('bg-secondary bg-danger bg-warning')
                $('#printer_dot').addClass('bg-success')
                $('#printer_dot').attr('title', 'Online und bereit')
            } else {
                // Online but not ready - yellow
                $('#printer_dot').removeClass('bg-secondary bg-success bg-danger')
                $('#printer_dot').addClass('bg-warning')
                $('#printer_dot').attr('title', 'Online, nicht bereit')
            }
        } else {
            // No valid response - gray
            $('#printer_dot').removeClass('bg-success bg-danger bg-warning')
            $('#printer_dot').addClass('bg-secondary')
            $('#printer_dot').attr('title', 'Status unbekannt')
        }
    }).fail(function() {
        // Connection failed - gray
        $('#printer_dot').removeClass('bg-success bg-danger bg-warning')
        $('#printer_dot').addClass('bg-secondary')
        $('#printer_dot').attr('title', 'Offline oder nicht erreichbar')
    })
}

function update_config() {
    $.ajax({
        type: "GET",
        dataType: "json",
        url: "/config",
        async: true,  // Make async to prevent UI blocking
        timeout: 5000  // 5 second timeout
    }).done(function(data) {
        const tapes = data["tapes"]

        // Clear existing options first
        $('#tape').empty()
        for(let index = 0; index < tapes.length; index++) {
            $('#tape').append('<option value="' + tapes[index] + '">' + tapes[index] + '</option>')
        }
        $('#tape').val('12mm') // Set default to 12mm since that's what's in the printer

        const printers = data["printers"]
        // Clear existing printer options first
        $('#printer').empty()
        for(let index = 0; index < printers.length; index++) {
            $('#printer').append('<option value="' + printers[index] + '">' + printers[index] + '</option>')
        }
        $('#printer').val(printers[0]) // Set default printer

        const fonts = data["fonts"]
        // Clear existing font options first
        $('#fontname').empty()
        for(let index = 0; index < fonts.length; index++) {
            const opt = '<option value="' + fonts[index] + '">' + fonts[index] + '</option>'
            $('#fontname').append(opt)
        }

        const dictionaries = data["dictionaries"]
        // Clear existing dictionary options first
        $('#dictionary').empty()
        for(let index = 0; index < dictionaries.length; index++) {
            const opt = '<option value="' + dictionaries[index] + '">' + dictionaries[index] + '</option>'
            $('#dictionary').append(opt)
        }


    }).fail(function(jqXHR) {
        $('#warning_div').removeClass('alert-success')
        $('#warning_div').addClass('alert-danger')
        $('#warning_div').html('Failure: ' + jqXHR.responseText)
    })
}

function get_request_json() {
    var fields = {
        text: ['printer', 'tape', 'fontname', 'size', 'align', 'lines'],
        qr: ['printer', 'tape', 'fontname', 'size', 'align', 'qrtext', 'lines'],
        wrap: ['printer', 'tape', 'fontname', 'label', 'length'],
        flag: ['printer', 'tape', 'fontname', 'size', 'label'],
	aruco: ['printer', 'tape', 'fontname', 'size', 'align', 'lines', 'id', 'dictionary']
    }

    const request = {
        'label_type': state.active_label
    }

    const flist = fields[state.active_label]
    for(let index = 0; index < flist.length; index++) {
        if (flist[index] == 'align') {
            const checked = $('input[name=align]:checked', '#text-form').val()
            request['align'] = checked
        } else if (flist[index] == 'lines') {
            const linearray = $('#lines').val().split('\n')
            request['lines'] = linearray
        } else {
            request[flist[index]] = $('#' + flist[index]).val()
            if(flist[index] == 'length') {
                request['length'] = 128 * Number(request['length'])
            }
        }
    }

    request['label_type'] = state.active_label

    const fullRequest = {
        'label': request,
        'count': 1
    }

    const jsonRequest = JSON.stringify(fullRequest)

    return jsonRequest
}

function print() {
    const request = get_request_json()

    $('#warning_div').removeClass('alert-danger')
    $('#warning_div').addClass('alert-success')
    $('#warning_div').html('Printing...')

    $.ajax({
        type: "PUT",
        dataType: "json",
        url: "/print",
        contentType: "application/json",
        data: request
    }).done(function(data) {
        $('#warning_div').removeClass('alert-danger')
        $('#warning_div').addClass('alert-success')
        $('#warning_div').html('Printed')
    }).fail(function(jqXHR) {
        $('#warning_div').removeClass('alert-success')
        $('#warning_div').addClass('alert-danger')
        $('#warning_div').html('Failure: ' + jqXHR.responseText)
    })
}

// Debounce function for performance
let previewTimeout;
function update_preview() {
    // Clear previous timeout to debounce rapid calls
    clearTimeout(previewTimeout)
    
    previewTimeout = setTimeout(() => {
        const request = get_request_json()
        const max_size = Math.trunc($('#preview_div').width())

        $.ajax({
            type: "PUT",
            dataType: "json", 
            url: "/preview?max_width="+max_size,
            contentType: "application/json",
            data: request,
            timeout: 8000  // 8 second timeout
        }).done(function(data) {
            const height = parseFloat(data["height"])
            const width = parseFloat(data["width"])
        
        let heightText, widthText, unitText
        
        if (state.units === 'imperial') {
            // Convert from inches to inches (already in inches from backend)
            heightText = height.toFixed(2)
            widthText = width.toFixed(2)
            unitText = "in"
        } else {
            // Convert from inches to millimeters
            const heightMm = (height * 25.4).toFixed(1)
            const widthMm = (width * 25.4).toFixed(1)
            heightText = heightMm
            widthText = widthMm
            unitText = "mm"
        }
        
        const new_label = `${heightText}${unitText} × ${widthText}${unitText}`
        $('#preview_label').html(new_label)
        $('#preview').attr('src', 'data:image/png;base64,' + data["preview"])
        $('#warning_div').removeClass('alert-danger')
        $('#warning_div').addClass('alert-success')
        $('#warning_div').html('Ok')
    }).fail(function(jqXHR) {
        $('#warning_div').removeClass('alert-success')
        $('#warning_div').addClass('alert-danger')
        $('#warning_div').html('Failure: ' + jqXHR.responseText)
    })
    }, 150) // 150ms debounce delay
}

function toggle_units() {
    state.units = state.units === 'metric' ? 'imperial' : 'metric'
    
    // Update button text
    const button = $('#units_toggle')
    if (state.units === 'metric') {
        button.text('mm')
        button.attr('title', 'Auf Imperial (Zoll) umschalten')
    } else {
        button.text('in')
        button.attr('title', 'Auf Metrisch (mm) umschalten')
    }
    
    // Update preview with new units
    update_preview()
}

function detect_tape_from_printer() {
    // Show loading state
    $('#warning_div').removeClass('alert-danger alert-success')
    $('#warning_div').addClass('alert-info')
    $('#warning_div').html('Tape-Größe wird erkannt...')
    
    $.ajax({
        type: "GET",
        dataType: "json",
        url: "/status",
        timeout: 10000  // 10 second timeout
    }).done(function(data) {
        const printer = $('#printer').val()
        
        if (data && data[printer] && data[printer]["media"]) {
            const detectedTape = data[printer]["media"]
            $('#tape').val(detectedTape)
            $('#warning_div').removeClass('alert-danger alert-info')
            $('#warning_div').addClass('alert-success')
            $('#warning_div').html('Tape-Größe erkannt: ' + detectedTape)
            update_preview()
        } else {
            $('#warning_div').removeClass('alert-success alert-info')
            $('#warning_div').addClass('alert-warning')
            $('#warning_div').html('Tape-Größe konnte nicht automatisch erkannt werden')
        }
    }).fail(function(jqXHR) {
        $('#warning_div').removeClass('alert-success alert-info')
        $('#warning_div').addClass('alert-danger')
        if (jqXHR.status === 0) {
            $('#warning_div').html('Verbindung zum Drucker fehlgeschlagen (Timeout)')
        } else {
            $('#warning_div').html('Fehler beim Abrufen der Drucker-Info: ' + jqXHR.responseText)
        }
    })
}

function show_font_manager() {
    // Load font data and show modal
    $.ajax({
        type: "GET",
        url: "/config",
        dataType: "json"
    }).done(function(data) {
        // Populate cached fonts only (no more suggested fonts)
        let cachedHtml = ''
        if (data.cached_fonts && data.cached_fonts.length > 0) {
            data.cached_fonts.forEach(function(font) {
                cachedHtml += `<div class="d-flex justify-content-between align-items-center mb-2 p-2 border rounded">
                    <span class="fw-bold">${font}</span>
                    <button class="btn btn-outline-danger btn-sm" onclick="remove_font('${font}')">
                        <i class="bi-trash"></i> Löschen
                    </button>
                </div>`
            })
        } else {
            cachedHtml = '<div class="text-muted text-center py-3"><em>Keine Custom Fonts installiert</em></div>'
        }
        $('#cached_fonts').html(cachedHtml)
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('fontModal'))
        modal.show()
    }).fail(function() {
        $('#warning_div').removeClass('alert-success')
        $('#warning_div').addClass('alert-danger')
        $('#warning_div').html('Fehler beim Laden der Font-Konfiguration')
    })
}

// Download functions removed - only file upload allowed

function upload_font_file() {
    const fileInput = $('#font_file')[0]
    const file = fileInput.files[0]
    const name = $('#font_name').val() || (file ? file.name.split('.')[0] : '')
    
    if (!file) {
        alert('Bitte Font-Datei auswählen')
        return
    }
    
    // Validate file type (only TTF/OTF now)
    const fileName = file.name.toLowerCase()
    if (!fileName.endsWith('.ttf') && !fileName.endsWith('.otf')) {
        alert('Nur .ttf und .otf Dateien unterstützt')
        return
    }
    
    // Show loading state
    const uploadBtn = $('button[onclick="upload_font_file()"]')
    const originalText = uploadBtn.html()
    uploadBtn.html('<i class="bi-arrow-clockwise spin"></i> Lädt hoch...').prop('disabled', true)
    
    // Create FormData for file upload
    const formData = new FormData()
    formData.append('file', file)
    if (name) formData.append('name', name)
    
    $.ajax({
        type: "POST",
        url: "/fonts/upload",
        data: formData,
        processData: false,
        contentType: false
    }).done(function(data) {
        $('#warning_div').removeClass('alert-danger')
        $('#warning_div').addClass('alert-success')
        $('#warning_div').html('Font erfolgreich hochgeladen!')
        
        // Clear inputs
        $('#font_file').val('')
        $('#font_name').val('')
        
        // Update font list
        update_config()
        
        // Close modal properly and remove backdrop
        const modalElement = document.getElementById('fontModal')
        const modal = bootstrap.Modal.getInstance(modalElement)
        if (modal) {
            modal.hide()
        }
        
        // Force remove backdrop if it exists
        setTimeout(() => {
            const backdrop = document.querySelector('.modal-backdrop')
            if (backdrop) {
                backdrop.remove()
            }
            document.body.classList.remove('modal-open')
            document.body.style.removeProperty('overflow')
            document.body.style.removeProperty('padding-right')
        }, 100)
        
    }).fail(function(jqXHR) {
        $('#warning_div').removeClass('alert-success')
        $('#warning_div').addClass('alert-danger')
        const errorMsg = jqXHR.responseText || 'Unbekannter Fehler'
        $('#warning_div').html('Fehler beim Upload: ' + errorMsg)
    }).always(function() {
        // Reset button state
        uploadBtn.html(originalText).prop('disabled', false)
    })
}

function remove_font(fontName) {
    if (!confirm(`Font "${fontName}" wirklich löschen?`)) return
    
    $.ajax({
        type: "DELETE",
        url: `/fonts/${fontName}`
    }).done(function(data) {
        $('#warning_div').removeClass('alert-danger')
        $('#warning_div').addClass('alert-success')
        $('#warning_div').html(`Font "${fontName}" erfolgreich entfernt!`)
        
        // Update font list
        update_config()
        
        // Close modal properly and remove backdrop
        const modalElement = document.getElementById('fontModal')
        const modal = bootstrap.Modal.getInstance(modalElement)
        if (modal) {
            modal.hide()
        }
        
        // Force remove backdrop if it exists
        setTimeout(() => {
            const backdrop = document.querySelector('.modal-backdrop')
            if (backdrop) {
                backdrop.remove()
            }
            document.body.classList.remove('modal-open')
            document.body.style.removeProperty('overflow')
            document.body.style.removeProperty('padding-right')
        }, 100)
        
    }).fail(function(jqXHR) {
        $('#warning_div').removeClass('alert-success')
        $('#warning_div').addClass('alert-danger')
        $('#warning_div').html(`Fehler beim Entfernen von "${fontName}": ` + jqXHR.responseText)
    })
}
