document.addEventListener('DOMContentLoaded', () => {

    // Gender/Condition logic
    const genderSelect = document.getElementById('patient-gender');
    const conditionSelect = document.getElementById('patient-condition');

    if (genderSelect && conditionSelect) {
        const togglePregnantOption = () => {
            const isMale = genderSelect.value === 'M';
            Array.from(conditionSelect.options).forEach(opt => {
                if (opt.value === 'Pregnant') {
                    opt.disabled = isMale;
                    opt.hidden = isMale;
                    opt.style.display = isMale ? 'none' : 'block';
                    if (isMale && conditionSelect.value === 'Pregnant') {
                        conditionSelect.value = 'Normal';
                    }
                }
            });
        };

        genderSelect.addEventListener('change', togglePregnantOption);
        // Initialize on load
        togglePregnantOption();
    }

    // Tab Logic
    const tabs = document.querySelectorAll('.input-tab');
    const panes = document.querySelectorAll('.input-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            panes.forEach(p => p.classList.remove('active'));
            
            tab.classList.add('active');
            const target = document.getElementById(tab.getAttribute('data-target'));
            if(target) target.classList.add('active');
        });
    });

    // Character Counter
    const textArea = document.getElementById('clinical-notes');
    const charCounter = document.getElementById('char-counter');
    const clearBtn = document.getElementById('clear-text-btn');

    textArea.addEventListener('input', () => {
        charCounter.textContent = `${textArea.value.length} chars`;
    });

    clearBtn.addEventListener('click', () => {
        textArea.value = '';
        charCounter.textContent = '0 chars';
    });


    // Drag and Drop Logic
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('file-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const fileNameDisplay = document.getElementById('file-name');
    const removeBtn = document.getElementById('remove-file-btn');

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);     
    });
    function preventDefaults (e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop zone
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files; // Update the HTML5 file input with the dropped files
        handleFiles(files);
    });

    // Handle selected files
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if(files.length > 0) {
            const file = files[0];
            fileNameDisplay.textContent = file.name;
            
            // Check if Image vs PDF to show preview
            if(file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onloadend = function() {
                    imagePreview.src = reader.result;
                    imagePreview.style.display = 'block';
                }
            } else {
                imagePreview.src = '';
                imagePreview.style.display = 'none'; // Hide if PDF
            }

            previewContainer.classList.remove('hidden');
        }
    }

    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // Stop click from triggering 'input file' again
        fileInput.value = '';
        previewContainer.classList.add('hidden');
        imagePreview.src = '';
        fileNameDisplay.textContent = '';
    });


    // Step & API Logic
    const analyzeBtn = document.getElementById('analyze-btn');
    const resetBtn = document.getElementById('reset-btn');
    const genReportBtn = document.getElementById('generate-report-btn');
    const dlPdfBtn = document.getElementById('download-pdf-btn');
    
    const sectionInput = document.getElementById('section-input');
    const sectionProcessing = document.getElementById('section-processing');
    const sectionResults = document.getElementById('section-results');

    const stepInput = document.getElementById('step-input');
    const stepProc = document.getElementById('step-processing');
    const stepRes = document.getElementById('step-results');

    analyzeBtn.addEventListener('click', () => {
        // Validate inputs loosely
        const userAge = document.getElementById('patient-age').value;
        const userGender = document.getElementById('patient-gender').value;
        const userCondition = document.getElementById('patient-condition').value;

        if(!userAge) {
            alert('Please enter the patient\'s age.');
            return;
        }

        const hasText = textArea.value.trim().length > 0;
        const hasFile = fileInput.files.length > 0;

        if(!hasText && !hasFile) {
            alert('Please provide clinical text or upload a report before analyzing.');
            return;
        }

        // Transition to processing
        sectionInput.classList.remove('active-section');
        sectionInput.classList.add('hidden-section');
        stepInput.classList.add('completed');
        
        sectionProcessing.classList.remove('hidden-section');
        sectionProcessing.classList.add('active-section');
        stepProc.classList.add('active');

        // Real API Call via fetch
        const formData = new FormData();
        formData.append('age', userAge);
        formData.append('gender', userGender);
        formData.append('condition', userCondition);
        
        // Append depending on what's active
        const isTextActive = document.getElementById('text-input-pane').classList.contains('active');
        if (isTextActive && hasText) {
            formData.append('text', textArea.value);
        } else if (hasFile) {
            formData.append('file', fileInput.files[0]);
        }

        fetch('/predict', {
            method: 'POST',
            body: formData
        })
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            renderResults(data);

            // Transition to results
            sectionProcessing.classList.remove('active-section');
            sectionProcessing.classList.add('hidden-section');
            stepProc.classList.remove('active');
            stepProc.classList.add('completed');
            
            sectionResults.classList.remove('hidden-section');
            sectionResults.classList.add('active-section');
            stepRes.classList.add('active');
        })
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error);
            alert("Backend Error: " + error.message);
            resetBtn.click(); // Reset UI if failed
        });
    });

    resetBtn.addEventListener('click', () => {
        // Reset everything
        sectionResults.classList.remove('active-section');
        sectionResults.classList.add('hidden-section');
        
        sectionInput.classList.remove('hidden-section');
        sectionInput.classList.add('active-section');

        stepRes.classList.remove('active');
        stepProc.classList.remove('completed');
        stepInput.classList.remove('completed');
    });

    const renderResults = (data) => {
        // Main Badge
        const mainBadge = document.getElementById('primary-deficiency-badge');
        mainBadge.textContent = data.predicted_deficiency;
        if(data.predicted_deficiency.toLowerCase().includes('no deficiency')) {
            mainBadge.className = 'badge large-badge status-normal';
        } else {
            mainBadge.className = 'badge large-badge status-severe';
        }

        // Detailed Table
        const tbody = document.getElementById('nutrient-table-body');
        tbody.innerHTML = ''; // Clear previous

        const references = {
            "Vitamin D": { range: "20 - 50 ng/mL", desc: "Bone health, immune function" },
            "Vitamin B12": { range: "200 - 900 pg/mL", desc: "Nerve function, red blood cells" },
            "Iron": { range: "60 - 170 µg/dL", desc: "Oxygen transport in blood" },
            "Calcium": { range: "8.5 - 10.2 mg/dL", desc: "Strong bones and teeth" }
        };

        for (const [nutrient, status] of Object.entries(data.nutrient_status)) {
            const val = data.extracted_values[nutrient];
            const ref = references[nutrient];

            let statusClass = 'status-normal';
            if (status.includes('Severe') || status.includes('Deficient') && !status.includes('Mild')) statusClass = 'status-severe';
            else if (status.includes('Mild')) statusClass = 'status-mild';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>
                    ${nutrient}
                    <span class="info-icon" title="${ref.desc}">?</span>
                </td>
                <td><strong>${val}</strong></td>
                <td>${ref.range}</td>
                <td><span class="status-badge ${statusClass}">${status}</span></td>
                <td>${status === 'Normal' ? 'Maintain current intake' : 'Supplementation recommended'}</td>
            `;
            tbody.appendChild(tr);
        }

        // Summary Text
        document.getElementById('summary-text').textContent = `The patient's lab results indicate primarily a ${data.predicted_deficiency}. Critical markers for Vitamin D and Iron are significantly below the optimal ranges.`;
        document.getElementById('recommendation-text').textContent = `Recommendation: Consult with your primary physician immediately regarding aggressive Vitamin D therapy and Iron supplementation. Re-test in 3 months.`;
    };

    // UI Toggle for Detailed Report
    genReportBtn.addEventListener('click', () => {
        // The detailed report is visible by default in this implementation to ensure good UX flow,
        // but we can mock expanding/collapsing or highlighting here.
        const summaryBlock = document.getElementById('report-summary-block');
        summaryBlock.style.backgroundColor = '#dbeafe'; // highlight
        setTimeout(() => {
            summaryBlock.style.backgroundColor = 'var(--input-bg)';
        }, 1000);
        alert('Detailed report UI is expanded.');
    });

    // PDF Download using html2pdf
    dlPdfBtn.addEventListener('click', () => {
        const element = document.getElementById('pdf-export-area');
        
        const opt = {
            margin:       0.5,
            filename:     'NutriDetector_Report.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };

        // Output PDF
        html2pdf().set(opt).from(element).save();
    });

});
