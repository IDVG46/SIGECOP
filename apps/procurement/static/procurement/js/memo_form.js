(function () {
    const form = document.getElementById('memo-form');
    if (!form) return;

    form.setAttribute('novalidate', 'novalidate');

    const contractSelect = document.getElementById('id_contract');
    const memoNumberInput = document.getElementById('id_memo_number');
    const memoDateInput = document.getElementById('id_memo_date');
    const applicationScopeInput = document.getElementById('id_application_scope');
    const applicationDetailInput = document.getElementById('id_application_detail');
    const receivedByInput = document.getElementById('id_received_by');
    const senderPositionInput = document.getElementById('id_sender_position');
    const ordersUrlTemplate = form.dataset.contractOrdersUrlTemplate || '';
    const orderLinesUrlTemplate = form.dataset.orderLinesUrlTemplate || '';
    const applicationScopeCreateUrl = form.dataset.applicationScopeCreateUrl || '';
    const memoId = form.dataset.memoId || '';

    const addLineButton = document.getElementById('add-memo-line-button');
    const feedbackBox = document.getElementById('memo-form-feedback');
    const linesWidget = document.getElementById('memo-lines-widget');
    const totalFormsInput = document.getElementById('id_lines-TOTAL_FORMS') || document.getElementById('id_fulfillmentmemoline_set-TOTAL_FORMS');
    const lineTemplate = document.getElementById('memo-line-row-template');
    const linesBody = document.querySelector('#orders-table tbody');

    const scopeModal = document.getElementById('application-scope-modal');
    const scopeNameInput = document.getElementById('application-scope-name-input');
    const scopeTypeInput = document.getElementById('application-scope-type-input');
    const scopeSaveBtn = document.getElementById('application-scope-modal-save-btn');

    const numberUtils = window.SIGECOPNumbers || {};
    const formErrors = window.SIGECOPFormErrors || {};

    let currentOrderOptions = [];
    const currentOrderLineOptions = {};
    let pendingScopeTargetField = null;

    function showFormFeedback(message, level) {
        if (formErrors.showFloatingFeedback) {
            formErrors.showFloatingFeedback(feedbackBox, message, level);
            return;
        }

        if (!feedbackBox) return;
        if (!message) {
            feedbackBox.style.display = 'none';
            feedbackBox.textContent = '';
            feedbackBox.className = 'alert alert-danger form-feedback';
            return;
        }

        feedbackBox.style.display = '';
        feedbackBox.textContent = message;
        feedbackBox.className = `alert alert-${level || 'danger'} form-feedback`;
    }

    function getCsrfToken() {
        const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput && csrfInput.value) {
            return csrfInput.value;
        }

        const cookie = document.cookie || '';
        const match = cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function initSelects(container) {
        if (window.SIGECOPUI && window.SIGECOPUI.enhanceSelects) {
            window.SIGECOPUI.enhanceSelects(container || form);
        }
    }

    function disableNativeRequiredOnEnhancedSelects(container) {
        if (formErrors.disableNativeRequiredOnEnhancedSelects) {
            formErrors.disableNativeRequiredOnEnhancedSelects(container || form);
        }
    }

    function bindSelectChangeEvents(field, handler) {
        if (!field || typeof handler !== 'function') return;
        field.addEventListener('change', handler);
        if (field.tomselect && typeof field.tomselect.on === 'function') {
            field.tomselect.off('change');
            field.tomselect.on('change', handler);
        }
    }

    function setSelectPlaceholder(select, placeholderText) {
        if (!select || !placeholderText) return;
        select.setAttribute('placeholder', placeholderText);
        select.dataset.placeholder = placeholderText;

        if (!select.tomselect) return;
        const ts = select.tomselect;
        ts.settings.placeholder = placeholderText;
        if (ts.control_input) {
            ts.control_input.setAttribute('placeholder', placeholderText);
        }
        if (!select.value) {
            ts.clear(true);
        }
    }

    function setOptions(select, options, selectedValue) {
        if (!select) return;

        const normalizedSelected = selectedValue ? String(selectedValue) : '';
        const normalizedOptions = (options || []).map(function (opt) {
            return {
                value: String(opt.id),
                text: opt.text,
            };
        });

        if (select.tomselect) {
            const ts = select.tomselect;
            ts.clearOptions();
            ts.addOption({ value: '', text: '' });
            normalizedOptions.forEach(function (opt) {
                ts.addOption(opt);
            });
            ts.refreshOptions(false);
            if (normalizedSelected) {
                ts.setValue(normalizedSelected, true);
            } else {
                ts.clear(true);
            }
            return;
        }

        select.innerHTML = '';
        const first = document.createElement('option');
        first.value = '';
        first.textContent = '';
        select.appendChild(first);

        normalizedOptions.forEach(function (opt) {
            const option = document.createElement('option');
            option.value = opt.value;
            option.textContent = opt.text;
            select.appendChild(option);
        });

        select.value = normalizedSelected;
    }

    function refreshIndexes() {
        Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]')).forEach(function (row, index) {
            const indexCell = row.querySelector('.js-line-index');
            if (indexCell) {
                indexCell.textContent = String(index + 1);
            }
        });
    }

    function rowElements(row) {
        return {
            order: row.querySelector('select[name$="-purchase_order"]'),
            orderLine: row.querySelector('select[name$="-purchase_order_line"]'),
            fulfilledQuantity: row.querySelector('input[name$="-fulfilled_quantity"]'),
            applicationScope: row.querySelector('select[name$="-application_scope"]'),
            applicationDetail: row.querySelector('input[name$="-application_detail"]'),
            observations: row.querySelector('input[name$="-observations"]'),
            del: row.querySelector('input[name$="-DELETE"]'),
            deleteBtn: row.querySelector('.js-delete-line-btn'),
            fillOrderBtn: row.querySelector('.js-fill-order-lines-btn'),
        };
    }

    function updateFillBtnVisibility(row) {
        const els = rowElements(row);
        if (!els.fillOrderBtn) return;
        els.fillOrderBtn.style.display = (els.order && els.order.value) ? '' : 'none';
    }

    async function fillOrderLines(sourceRow) {
        const els = rowElements(sourceRow);
        if (!els.order || !els.order.value) return;

        const orderId = String(els.order.value);
        if (!currentOrderLineOptions[orderId]) {
            currentOrderLineOptions[orderId] = await fetchOrderLines(orderId);
        }

        const allLines = currentOrderLineOptions[orderId] || [];
        const pendingLines = allLines.filter(function (l) {
            return parseFloat(l.pending_quantity || '0') > 0;
        });

        if (!pendingLines.length) {
            showFormFeedback('La orden seleccionada no tiene líneas con cantidad pendiente.', 'warning');
            return;
        }

        // Completar la fila actual con la primera línea pendiente
        setOptions(els.orderLine, allLines, String(pendingLines[0].id));
        if (els.fulfilledQuantity) {
            els.fulfilledQuantity.value = pendingLines[0].pending_quantity;
            els.fulfilledQuantity.dispatchEvent(new Event('blur'));
        }
        clearRowInvalidState(sourceRow);

        // Agregar una fila nueva por cada línea pendiente adicional
        for (let i = 1; i < pendingLines.length; i++) {
            const lineDef = pendingLines[i];
            addRow();
            const allRows = Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]'));
            const newRow = allRows[allRows.length - 1];
            if (!newRow) continue;
            const newEls = rowElements(newRow);
            setOptions(newEls.order, currentOrderOptions, orderId);
            setOptions(newEls.orderLine, allLines, String(lineDef.id));
            if (newEls.fulfilledQuantity) {
                newEls.fulfilledQuantity.value = lineDef.pending_quantity;
                newEls.fulfilledQuantity.dispatchEvent(new Event('blur'));
            }
            updateFillBtnVisibility(newRow);
            clearRowInvalidState(newRow);
        }

        refreshIndexes();
        const n = pendingLines.length;
        showFormFeedback(
            n === 1
                ? 'Se agregó 1 línea pendiente de la orden.'
                : 'Se agregaron ' + n + ' líneas pendientes de la orden.',
            'success'
        );
    }

    function clearRowInvalidState(row) {
        if (!row) return;
        row.classList.remove('danger');
        if (formErrors.clearInvalidInContainer) {
            formErrors.clearInvalidInContainer(row);
        }
        const next = row.nextElementSibling;
        if (next && next.classList.contains('js-line-error-row')) {
            next.remove();
        }
    }

    function markRowFieldInvalid(row, field, message) {
        row.classList.add('danger');
        if (formErrors.markFieldInvalid) {
            formErrors.markFieldInvalid(field, message || '');
        }
    }

    function updateDeleteRowState(row) {
        if (window.SIGECOPLineDelete && typeof window.SIGECOPLineDelete.applyState === 'function') {
            window.SIGECOPLineDelete.applyState(row, {
                hideNextErrorRow: true,
                labels: {
                    deleteText: 'Eliminar detalle',
                    restoreText: 'Restaurar detalle',
                },
            });
            return;
        }

        const els = rowElements(row);
        const isDeleted = !!(els.del && els.del.checked);
        row.classList.toggle('line-row-deleted', isDeleted);
    }

    async function fetchContractOrders(contractId) {
        if (!contractId || !ordersUrlTemplate) return [];
        const url = ordersUrlTemplate.replace('__CONTRACT_ID__', encodeURIComponent(contractId));
        try {
            const response = await fetch(url, { credentials: 'same-origin' });
            if (!response.ok) return null;
            const payload = await response.json();
            return payload.orders || [];
        } catch (_error) {
            return null;
        }
    }

    async function fetchOrderLines(orderId) {
        if (!orderId || !orderLinesUrlTemplate) return [];
        let url = orderLinesUrlTemplate.replace('__ORDER_ID__', encodeURIComponent(orderId));
        if (memoId) {
            url += (url.includes('?') ? '&' : '?') + 'memo_id=' + encodeURIComponent(memoId);
        }

        try {
            const response = await fetch(url, { credentials: 'same-origin' });
            if (!response.ok) return [];
            const payload = await response.json();
            return payload.lines || [];
        } catch (_error) {
            return [];
        }
    }

    async function refreshRowOrderLines(row) {
        const els = rowElements(row);
        if (!els.order || !els.orderLine) return;

        if (!els.order.value) {
            setOptions(els.orderLine, [], '');
            return;
        }

        const orderId = String(els.order.value);
        if (!currentOrderLineOptions[orderId]) {
            currentOrderLineOptions[orderId] = await fetchOrderLines(orderId);
        }

        setOptions(els.orderLine, currentOrderLineOptions[orderId], els.orderLine.value);
        setSelectPlaceholder(els.orderLine, 'Buscar línea...');
    }

    function validateHeaderRequiredFields() {
        const requiredFields = [
            { field: contractSelect, message: 'Debe seleccionar un contrato.' },
            { field: memoNumberInput, message: 'Debe indicar el número de memorándum.' },
            { field: memoDateInput, message: 'Debe indicar la fecha del memorándum.' },
            { field: receivedByInput, message: 'Debe indicar quién recibe.' },
            { field: senderPositionInput, message: 'Debe indicar el cargo del remitente.' },
        ];

        requiredFields.forEach(function (item) {
            if (item.field && formErrors.clearFieldError) {
                formErrors.clearFieldError(item.field);
            }
        });

        for (const item of requiredFields) {
            if (!item.field) continue;
            if (String(item.field.value || '').trim() !== '') continue;
            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(item.field, item.message);
            }
            return item.field;
        }

        const scopeValue = String((applicationScopeInput && applicationScopeInput.value) || '').trim();
        const detailValue = String((applicationDetailInput && applicationDetailInput.value) || '').trim();
        if (!scopeValue && !detailValue) {
            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(applicationScopeInput, 'Debe seleccionar un ámbito o especificar un detalle.');
            }
            return applicationScopeInput;
        }

        return null;
    }

    function rowHasAnyData(row) {
        const els = rowElements(row);
        return [
            els.order && els.order.value,
            els.orderLine && els.orderLine.value,
            els.fulfilledQuantity && els.fulfilledQuantity.value,
            els.applicationScope && els.applicationScope.value,
            els.applicationDetail && els.applicationDetail.value,
            els.observations && els.observations.value,
        ].some(Boolean);
    }

    function validateRow(row, options) {
        const requireCompleted = !!(options && options.requireCompleted);
        const els = rowElements(row);
        clearRowInvalidState(row);

        if (els.del && els.del.checked) {
            return true;
        }

        if (!rowHasAnyData(row)) {
            if (!requireCompleted) {
                return true;
            }
            row.classList.add('danger');
            markRowFieldInvalid(row, els.order, 'Debe seleccionar una orden.');
            return false;
        }

        if (!els.order || !els.order.value) {
            markRowFieldInvalid(row, els.order, 'Debe seleccionar una orden.');
            return false;
        }
        if (!els.orderLine || !els.orderLine.value) {
            markRowFieldInvalid(row, els.orderLine, 'Debe seleccionar una línea.');
            return false;
        }
        if (!els.fulfilledQuantity || String(els.fulfilledQuantity.value || '').trim() === '') {
            markRowFieldInvalid(row, els.fulfilledQuantity, 'Debe indicar la cantidad cumplida.');
            return false;
        }

        return true;
    }

    function hasActiveRows() {
        return Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]')).some(function (row) {
            const els = rowElements(row);
            return !(els.del && els.del.checked);
        });
    }

    function setupRow(row) {
        const els = rowElements(row);
        if (!els.order) return;

        if (row.dataset.bound === '1') {
            if (currentOrderOptions.length) {
                setOptions(els.order, currentOrderOptions, els.order.value);
            }
            refreshRowOrderLines(row);
            updateFillBtnVisibility(row);
            return;
        }

        row.dataset.bound = '1';

        setSelectPlaceholder(els.order, 'Buscar orden...');
        setSelectPlaceholder(els.orderLine, 'Buscar línea...');
        setSelectPlaceholder(els.applicationScope, 'Buscar ámbito...');

        if (currentOrderOptions.length) {
            setOptions(els.order, currentOrderOptions, els.order.value);
        }

        if (els.fulfilledQuantity && numberUtils.bindInputFormatting) {
            numberUtils.bindInputFormatting(els.fulfilledQuantity, {
                kind: 'quantity',
                locale: 'es-PY',
                precision: 0,
            });
        }

        bindSelectChangeEvents(els.order, function () {
            refreshRowOrderLines(row);
            validateRow(row, { requireCompleted: false });
            showFormFeedback('', 'danger');
            updateFillBtnVisibility(row);
        });

        bindSelectChangeEvents(els.orderLine, function () {
            validateRow(row, { requireCompleted: false });
            showFormFeedback('', 'danger');
        });

        [els.fulfilledQuantity, els.applicationDetail, els.observations].forEach(function (field) {
            if (!field) return;
            field.addEventListener('input', function () {
                if (formErrors.clearFieldError) {
                    formErrors.clearFieldError(field);
                }
                showFormFeedback('', 'danger');
            });
        });

        if (els.fillOrderBtn) {
            els.fillOrderBtn.addEventListener('click', function (e) {
                e.preventDefault();
                fillOrderLines(row);
            });
        }

        updateFillBtnVisibility(row);

        updateDeleteRowState(row);
        refreshRowOrderLines(row);
    }

    function addRow() {
        if (!lineTemplate || !linesBody || !totalFormsInput) return;
        const index = Number(totalFormsInput.value || '0');
        const html = lineTemplate.innerHTML.replace(/__prefix__/g, String(index));
        const temp = document.createElement('tbody');
        temp.innerHTML = html.trim();
        const row = temp.firstElementChild;
        if (!row) return;

        linesBody.appendChild(row);
        totalFormsInput.value = String(index + 1);
        initSelects(row);
        setupRow(row);
        refreshIndexes();
    }

    async function refreshContractData() {
        const contractId = contractSelect ? String(contractSelect.value || '') : '';
        Object.keys(currentOrderLineOptions).forEach(function (key) {
            delete currentOrderLineOptions[key];
        });

        if (!contractId) {
            currentOrderOptions = [];
            Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]')).forEach(function (row) {
                const els = rowElements(row);
                setOptions(els.order, [], '');
                setOptions(els.orderLine, [], '');
            });
            return;
        }

        const fetched = await fetchContractOrders(contractId);
        if (fetched === null) {
            showFormFeedback('No se pudieron cargar las órdenes del contrato.', 'warning');
            return;
        }

        currentOrderOptions = fetched || [];
        if (!currentOrderOptions.length) {
            showFormFeedback('El contrato seleccionado no tiene órdenes de compra disponibles.', 'warning');
        } else {
            showFormFeedback('', 'danger');
        }
        Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]')).forEach(function (row) {
            setupRow(row);
        });
    }

    function resolveScopeTargetField(button) {
        if (!button) return null;
        const group = button.closest('.input-group');
        if (group) {
            const inGroup = group.querySelector('select[name$="application_scope"]');
            if (inGroup) return inGroup;
        }
        const row = button.closest('tr');
        if (row) {
            const inRow = row.querySelector('select[name$="application_scope"]');
            if (inRow) return inRow;
        }
        return applicationScopeInput;
    }

    function openScopeModal() {
        if (!scopeModal) {
            showFormFeedback('No se encontró el modal para crear ámbito.', 'warning');
            return;
        }

        if (scopeNameInput) scopeNameInput.value = '';
        if (scopeTypeInput && !scopeTypeInput.value) scopeTypeInput.value = 'sector';

        if (window.jQuery && window.jQuery.fn && window.jQuery.fn.modal) {
            window.jQuery(scopeModal).modal('show');
            window.setTimeout(function () {
                if (scopeNameInput) scopeNameInput.focus();
            }, 220);
            return;
        }

        scopeModal.style.display = 'block';
        scopeModal.classList.add('in');
        if (scopeNameInput) scopeNameInput.focus();
    }

    function closeScopeModal() {
        if (!scopeModal) return;
        if (window.jQuery && window.jQuery.fn && window.jQuery.fn.modal) {
            window.jQuery(scopeModal).modal('hide');
            return;
        }
        scopeModal.style.display = 'none';
        scopeModal.classList.remove('in');
    }

    async function createApplicationScopeQuick(targetField) {
        if (!applicationScopeCreateUrl || !targetField) {
            showFormFeedback('No se pudo inicializar la creación del ámbito.', 'warning');
            return;
        }

        const name = scopeNameInput ? String(scopeNameInput.value || '').trim() : '';
        const scopeType = scopeTypeInput ? String(scopeTypeInput.value || 'sector').trim() : 'sector';
        if (!name) {
            if (scopeNameInput) scopeNameInput.focus();
            return;
        }

        if (scopeSaveBtn) scopeSaveBtn.disabled = true;

        let response;
        try {
            response = await fetch(applicationScopeCreateUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ name: name, scope_type: scopeType }),
            });
        } catch (_error) {
            showFormFeedback('No se pudo crear el ámbito por un error de conexión.', 'danger');
            if (scopeSaveBtn) scopeSaveBtn.disabled = false;
            return;
        }

        if (!response.ok) {
            showFormFeedback('No se pudo crear el ámbito.', 'danger');
            if (scopeSaveBtn) scopeSaveBtn.disabled = false;
            return;
        }

        const payload = await response.json();
        const scope = payload.scope;
        if (!scope || !scope.id) {
            showFormFeedback('Respuesta inválida al crear ámbito.', 'danger');
            if (scopeSaveBtn) scopeSaveBtn.disabled = false;
            return;
        }

        const value = String(scope.id);
        if (targetField.tomselect) {
            if (!targetField.tomselect.options[value]) {
                targetField.tomselect.addOption({ value: value, text: scope.name });
            }
            targetField.tomselect.setValue(value, true);
        } else {
            let option = Array.from(targetField.options || []).find(function (opt) {
                return String(opt.value) === value;
            });
            if (!option) {
                option = document.createElement('option');
                option.value = value;
                option.textContent = scope.name;
                targetField.appendChild(option);
            }
            targetField.value = value;
        }

        targetField.dispatchEvent(new Event('change', { bubbles: true }));
        if (scopeSaveBtn) scopeSaveBtn.disabled = false;
        pendingScopeTargetField = null;
        closeScopeModal();
        showFormFeedback('Ámbito agregado correctamente.', 'success');
    }

    form.addEventListener('click', function (event) {
        const deleteButton = event.target.closest('.js-delete-line-btn');
        if (deleteButton) {
            const row = deleteButton.closest('tr[data-row-kind="order"]');
            if (!row) return;
            if (window.SIGECOPLineDelete && typeof window.SIGECOPLineDelete.toggleRow === 'function') {
                window.SIGECOPLineDelete.toggleRow(row, {
                    hideNextErrorRow: true,
                    labels: {
                        deleteText: 'Eliminar detalle',
                        restoreText: 'Restaurar detalle',
                    },
                });
            }
            updateDeleteRowState(row);
            return;
        }

        const scopeButton = event.target.closest('.js-add-scope-btn');
        if (scopeButton) {
            event.preventDefault();
            pendingScopeTargetField = resolveScopeTargetField(scopeButton);
            openScopeModal();
        }
    });

    if (scopeSaveBtn) {
        scopeSaveBtn.addEventListener('click', function () {
            createApplicationScopeQuick(pendingScopeTargetField);
        });
    }

    if (scopeNameInput) {
        scopeNameInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                if (scopeSaveBtn) scopeSaveBtn.click();
            }
        });
    }

    form.addEventListener('submit', function (event) {
        const invalidHeaderField = validateHeaderRequiredFields();
        if (invalidHeaderField) {
            event.preventDefault();
            showFormFeedback('Complete los campos obligatorios de la cabecera.', 'danger');
            const wrapper = invalidHeaderField.closest('.row') || invalidHeaderField;
            if (wrapper && wrapper.scrollIntoView) {
                wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return;
        }

        if (!hasActiveRows()) {
            event.preventDefault();
            showFormFeedback('Debe agregar al menos una línea de cumplimiento.', 'danger');
            if (linesWidget && linesWidget.scrollIntoView) {
                linesWidget.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return;
        }

        const rows = Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]'));
        for (const row of rows) {
            if (!validateRow(row, { requireCompleted: true })) {
                event.preventDefault();
                showFormFeedback('Complete los campos obligatorios de cada línea.', 'danger');
                row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
        }

        Array.from(linesBody.querySelectorAll('input[name$="-fulfilled_quantity"]')).forEach(function (input) {
            if (numberUtils.normalizeInputForSubmit) {
                numberUtils.normalizeInputForSubmit(input, {
                    kind: 'quantity',
                    precision: 0,
                });
            }
        });
    });

    [memoNumberInput, memoDateInput, applicationScopeInput, applicationDetailInput, receivedByInput, senderPositionInput].forEach(function (field) {
        if (!field) return;
        field.addEventListener('input', function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(field);
            }
            showFormFeedback('', 'danger');
        });
        field.addEventListener('change', function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(field);
            }
            showFormFeedback('', 'danger');
        });
    });

    if (addLineButton) {
        addLineButton.addEventListener('click', addRow);
    }

    initSelects(form);
    disableNativeRequiredOnEnhancedSelects(form);

    if (contractSelect) {
        bindSelectChangeEvents(contractSelect, function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(contractSelect);
            }
            refreshContractData();
        });
    }

    Array.from(linesBody.querySelectorAll('tr[data-row-kind="order"]')).forEach(function (row) {
        setupRow(row);
    });

    refreshIndexes();
    showFormFeedback('', 'danger');
    refreshContractData();
})();