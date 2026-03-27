(function () {
    const form = document.getElementById('memo-form');
    if (!form) return;
    form.setAttribute('novalidate', 'novalidate');

    const contractSelect = document.getElementById('id_contract');
    const memoNumberInput = document.getElementById('id_memo_number');
    const memoDateInput = document.getElementById('id_memo_date');
    const beneficiarySectorInput = document.getElementById('id_beneficiary_sector');
    const receivedByInput = document.getElementById('id_received_by');
    const senderPositionInput = document.getElementById('id_sender_position');
    const ordersUrlTemplate = form.dataset.contractOrdersUrlTemplate || '';
    const orderLinesUrlTemplate = form.dataset.orderLinesUrlTemplate || '';
    const memoId = form.dataset.memoId || '';

    const addOrderBtn = document.getElementById('add-memo-line-button');
    const addPartialBtn = document.getElementById('add-partial-line-button');
    const feedbackBox = document.getElementById('memo-form-feedback');

    const orderTotalForms = document.getElementById('id_lines-TOTAL_FORMS') || document.getElementById('id_fulfillmentmemoline_set-TOTAL_FORMS');
    const partialTotalForms = document.getElementById('id_partials-TOTAL_FORMS');

    const orderTemplate = document.getElementById('memo-line-row-template');
    const partialTemplate = document.getElementById('memo-partial-row-template');

    const orderBody = document.querySelector('#orders-table tbody');
    const partialBody = document.querySelector('#partials-table tbody');
    const orderWidget = document.getElementById('memo-lines-widget');
    const partialWidget = document.getElementById('memo-partials-widget');

    const numberUtils = window.SIGECOPNumbers || {};
    const formErrors = window.SIGECOPFormErrors || {};

    let currentOrderOptions = [];
    const currentOrderLineOptions = {};

    const detailPlaceholders = {
        order: 'Buscar orden...',
        mode: 'Buscar modo...',
        line: 'Buscar linea...'
    };

    function getModeValue(modeSelect) {
        if (!modeSelect) return 'total';

        let value = String(modeSelect.value || '').trim();
        if (!value && modeSelect.tomselect && typeof modeSelect.tomselect.getValue === 'function') {
            value = String(modeSelect.tomselect.getValue() || '').trim();
        }

        return value || 'total';
    }

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

    function validateHeaderRequiredFields() {
        const requiredHeaderFields = [
            { field: contractSelect, message: 'Debe seleccionar un contrato.' },
            { field: memoNumberInput, message: 'Debe indicar el numero de memorandum.' },
            { field: memoDateInput, message: 'Debe indicar la fecha del memorandum.' },
            { field: beneficiarySectorInput, message: 'Debe indicar el sector beneficiario.' },
            { field: receivedByInput, message: 'Debe indicar quien recibe.' },
            { field: senderPositionInput, message: 'Debe indicar el cargo del remitente.' }
        ];

        requiredHeaderFields.forEach(function (item) {
            if (!item.field) return;
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(item.field);
            }
        });

        for (const item of requiredHeaderFields) {
            if (!item.field) continue;
            const value = String(item.field.value || '').trim();
            if (value !== '') continue;

            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(item.field, item.message);
            }
            return item.field;
        }

        return null;
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

    function applyOrderRowPlaceholders(row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const modeSelect = row.querySelector('select[name$="-line_mode"]');
        setSelectPlaceholder(orderSelect, detailPlaceholders.order);
        setSelectPlaceholder(modeSelect, detailPlaceholders.mode);
    }

    function applyPartialRowPlaceholders(row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const lineSelect = row.querySelector('select[name$="-purchase_order_line"]');
        setSelectPlaceholder(orderSelect, detailPlaceholders.order);
        setSelectPlaceholder(lineSelect, detailPlaceholders.line);
    }

    function buildUrl(template, key, value) {
        if (!value || !template) return '';
        return template
            .replace(key, encodeURIComponent(value))
            .replace(encodeURIComponent(key), encodeURIComponent(value));
    }

    async function fetchContractOrders(contractId) {
        const url = buildUrl(ordersUrlTemplate, '__CONTRACT_ID__', contractId);
        if (!url) return [];
        try {
            const resp = await fetch(url, { credentials: 'same-origin' });
            if (!resp.ok) return null;
            const payload = await resp.json();
            return payload.orders || [];
        } catch (_e) {
            return null;
        }
    }

    async function fetchOrderLines(orderId) {
        let url = buildUrl(orderLinesUrlTemplate, '__ORDER_ID__', orderId);
        if (!url) return [];
        if (memoId) {
            url += (url.includes('?') ? '&' : '?') + 'memo_id=' + encodeURIComponent(memoId);
        }
        try {
            const resp = await fetch(url, { credentials: 'same-origin' });
            if (!resp.ok) return [];
            const payload = await resp.json();
            return payload.lines || [];
        } catch (_e) {
            return [];
        }
    }

    function setOptions(select, options, selectedValue) {
        if (!select) return;

        const normalizedSelected = selectedValue ? String(selectedValue) : '';
        const normalizedOptions = (options || []).map(function (opt) {
            return {
                value: String(opt.id),
                text: opt.text,
                pendingQuantity: String(opt.pending_quantity || '0')
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
            option.dataset.pendingQuantity = opt.pendingQuantity;
            select.appendChild(option);
        });

        select.value = normalizedSelected;
    }

    async function refreshPartialOrderLines(row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const lineSelect = row.querySelector('select[name$="-purchase_order_line"]');
        if (!orderSelect || !lineSelect) return;

        if (!orderSelect.value) {
            setOptions(lineSelect, [], '');
            return;
        }

        const oid = String(orderSelect.value);
        if (!currentOrderLineOptions[oid]) {
            const lines = await fetchOrderLines(oid);
            currentOrderLineOptions[oid] = lines || [];
        }
        setOptions(lineSelect, currentOrderLineOptions[oid], lineSelect.value);
    }

    function setupOrderRow(row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const modeSelect = row.querySelector('select[name$="-line_mode"]');
        applyOrderRowPlaceholders(row);

        if (modeSelect && String(modeSelect.value || '').trim() === '') {
            modeSelect.value = 'total';
            if (modeSelect.tomselect && typeof modeSelect.tomselect.setValue === 'function') {
                modeSelect.tomselect.setValue('total', true);
            }
        }

        if (orderSelect && currentOrderOptions.length) {
            setOptions(orderSelect, currentOrderOptions, orderSelect.value);
        }

        if (modeSelect && modeSelect.dataset.memoBound !== '1') {
            bindSelectChangeEvents(modeSelect, function () {
                syncPartialSectionVisibility();
                showFormFeedback('', 'danger');
            });
            modeSelect.dataset.memoBound = '1';
        }
    }

    function setupPartialRow(row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const lineSelect = row.querySelector('select[name$="-purchase_order_line"]');
        const qtyInput = row.querySelector('input[name$="-fulfilled_quantity"]');

        applyPartialRowPlaceholders(row);

        if (orderSelect && currentOrderOptions.length) {
            setOptions(orderSelect, currentOrderOptions, orderSelect.value);
        }

        if (orderSelect && orderSelect.dataset.memoBound !== '1') {
            const onChange = function () {
                refreshPartialOrderLines(row);
                showFormFeedback('', 'danger');
            };
            bindSelectChangeEvents(orderSelect, onChange);
            orderSelect.dataset.memoBound = '1';
        }

        if (qtyInput && numberUtils.bindInputFormatting) {
            numberUtils.bindInputFormatting(qtyInput, {
                kind: 'quantity',
                locale: 'es-PY',
                precision: 0,
            });
        }

        if (currentOrderOptions.length) {
            refreshPartialOrderLines(row);
        } else if (lineSelect) {
            setSelectPlaceholder(lineSelect, detailPlaceholders.line);
        }
    }

    function addRow(template, body, totalFormsInput, setupFn) {
        if (!template || !body || !totalFormsInput) return;

        const index = Number(totalFormsInput.value || '0');
        const html = template.innerHTML.replace(/__prefix__/g, String(index));
        const tmp = document.createElement('tbody');
        tmp.innerHTML = html.trim();
        const row = tmp.firstElementChild;
        if (!row) return;

        body.appendChild(row);
        totalFormsInput.value = String(index + 1);
        initSelects(row);
        setupFn(row);
        updateDeleteRowState(row);
        refreshRowIndexes(body);
    }

    function refreshRowIndexes(body) {
        if (!body) return;
        let index = 1;
        body.querySelectorAll('tr[data-row-kind]').forEach(function (row) {
            const indexCell = row.querySelector('.js-line-index');
            if (indexCell) {
                indexCell.textContent = String(index++);
            }
        });
    }

    function rowElements(row) {
        return {
            del: row.querySelector('input[name$="-DELETE"]'),
            deleteBtn: row.querySelector('.js-delete-line-btn'),
            deleteLabel: row.querySelector('.js-delete-line-label')
        };
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

    function removeRow(btn) {
        const row = btn.closest('tr');
        if (!row) return;

        if (window.SIGECOPLineDelete && typeof window.SIGECOPLineDelete.toggleRow === 'function') {
            const result = window.SIGECOPLineDelete.toggleRow(row, {
                hideNextErrorRow: true,
                labels: {
                    deleteText: 'Eliminar detalle',
                    restoreText: 'Restaurar detalle',
                },
            });
            if (result.removed) {
                refreshRowIndexes(row.parentElement);
            }
        } else {
            const del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (del) {
                del.checked = !del.checked;
                updateDeleteRowState(row);
            } else {
                const body = row.parentElement;
                row.remove();
                refreshRowIndexes(body);
            }
        }

        syncPartialSectionVisibility();
    }

    function rowVisible(row) {
        if (!row || row.style.display === 'none') return false;
        const del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
        return !(del && del.checked);
    }

    function clearRowInvalidState(row) {
        if (!row) return;
        row.classList.remove('danger');
    }

    function markRowInvalid(row) {
        if (!row) return;
        row.classList.add('danger');
    }

    function clearPartialCoverageErrorState() {
        if (partialWidget) {
            partialWidget.classList.remove('js-client-invalid-block');
        }
    }

    function syncPartialSectionVisibility() {
        if (!partialWidget) return;

        let hasPartialMode = false;
        orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(function (row) {
            if (!rowVisible(row)) return;
            const modeSelect = row.querySelector('select[name$="-line_mode"]');
            if (!modeSelect) return;

            if (getModeValue(modeSelect) === 'partial') {
                hasPartialMode = true;
            }
        });

        partialWidget.classList.toggle('memo-partials-collapsed', !hasPartialMode);
        if (addPartialBtn) {
            addPartialBtn.disabled = !hasPartialMode;
            addPartialBtn.classList.toggle('disabled', !hasPartialMode);
            if (!hasPartialMode) {
                addPartialBtn.setAttribute('title', 'Disponible solo cuando exista al menos una linea en modo parcial.');
            } else {
                addPartialBtn.removeAttribute('title');
            }
        }
        if (!hasPartialMode) {
            clearPartialCoverageErrorState();
        }

        return hasPartialMode;
    }

    function clearPartialLineErrors() {
        partialBody.querySelectorAll('tr[data-row-kind="partial"]').forEach(function (row) {
            clearRowInvalidState(row);

            const orderSelect = row.querySelector('select[name$="-purchase_order"]');
            const lineSelect = row.querySelector('select[name$="-purchase_order_line"]');
            const qtyInput = row.querySelector('input[name$="-fulfilled_quantity"]');

            [orderSelect, lineSelect, qtyInput].forEach(function (field) {
                if (!field || !formErrors.clearFieldError) return;
                formErrors.clearFieldError(field);
            });
        });
    }

    function validatePartialCoverage() {
        clearPartialCoverageErrorState();
        clearPartialLineErrors();

        const partialOrderIds = new Set();
        const hasDetailByOrder = new Map();
        let firstInvalidPartialField = null;
        let firstBlankPartialOrderSelect = null;

        orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(function (row) {
            if (!rowVisible(row)) return;

            const mode = row.querySelector('select[name$="-line_mode"]');
            const order = row.querySelector('select[name$="-purchase_order"]');
            if (!mode || !order || !order.value) return;

            if (mode.value === 'partial') {
                const orderId = String(order.value);
                partialOrderIds.add(orderId);
                hasDetailByOrder.set(orderId, false);
            }
        });

        partialBody.querySelectorAll('tr[data-row-kind="partial"]').forEach(function (row) {
            if (!rowVisible(row)) return;

            const order = row.querySelector('select[name$="-purchase_order"]');
            const line = row.querySelector('select[name$="-purchase_order_line"]');
            const qty = row.querySelector('input[name$="-fulfilled_quantity"]');
            if (!order || !line || !qty) return;

            const orderValue = String(order.value || '').trim();
            const lineValue = String(line.value || '').trim();
            const qtyValue = String(qty.value || '').trim();

            const hasAnyValue = orderValue !== '' || lineValue !== '' || qtyValue !== '';
            const isComplete = orderValue !== '' && lineValue !== '' && qtyValue !== '';

            if (!hasAnyValue) {
                if (!firstBlankPartialOrderSelect) {
                    firstBlankPartialOrderSelect = order;
                }
                return;
            }

            if (!isComplete) {
                markRowInvalid(row);

                if (orderValue === '' && formErrors.markFieldInvalid) {
                    formErrors.markFieldInvalid(order, 'Debe seleccionar una orden de compra.');
                    if (!firstInvalidPartialField) firstInvalidPartialField = order;
                }
                if (lineValue === '' && formErrors.markFieldInvalid) {
                    formErrors.markFieldInvalid(line, 'Debe seleccionar una linea de orden.');
                    if (!firstInvalidPartialField) firstInvalidPartialField = line;
                }
                if (qtyValue === '' && formErrors.markFieldInvalid) {
                    formErrors.markFieldInvalid(qty, 'Debe indicar la cantidad cumplida.');
                    if (!firstInvalidPartialField) firstInvalidPartialField = qty;
                }
                return;
            }

            const key = orderValue;
            if (hasDetailByOrder.has(key)) {
                hasDetailByOrder.set(key, true);
            }
        });

        if (firstInvalidPartialField) {
            if (partialWidget) {
                partialWidget.classList.add('js-client-invalid-block');
            }
            return {
                ok: false,
                kind: 'empty-partial-field',
                field: firstInvalidPartialField,
            };
        }

        for (const oid of partialOrderIds) {
            if (!hasDetailByOrder.get(oid)) {
                if (firstBlankPartialOrderSelect && formErrors.markFieldInvalid) {
                    const firstBlankRow = firstBlankPartialOrderSelect.closest('tr[data-row-kind="partial"]');
                    markRowInvalid(firstBlankRow);

                    formErrors.markFieldInvalid(firstBlankPartialOrderSelect, 'Debe seleccionar una orden de compra.');
                    if (partialWidget) {
                        partialWidget.classList.add('js-client-invalid-block');
                    }
                    return {
                        ok: false,
                        kind: 'empty-partial-field',
                        field: firstBlankPartialOrderSelect,
                    };
                }

                if (partialWidget) {
                    partialWidget.classList.add('js-client-invalid-block');
                }
                return {
                    ok: false,
                    kind: 'missing-partial-detail',
                    field: null,
                };
            }
        }

        return { ok: true };
    }

    function clearEmptyMemoErrorState() {
        if (orderWidget) {
            orderWidget.classList.remove('js-client-invalid-block');
        }
    }

    function clearOrderLineErrors() {
        orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(function (row) {
            clearRowInvalidState(row);

            const orderSelect = row.querySelector('select[name$="-purchase_order"]');
            if (!orderSelect) return;
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(orderSelect);
            }
        });
    }

    function validateAtLeastOneOrderLine() {
        clearEmptyMemoErrorState();
        clearOrderLineErrors();

        let hasAtLeastOneOrder = false;
        let visibleRows = 0;
        let firstEmptyOrderSelect = null;
        orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(function (row) {
            if (!rowVisible(row)) return;
            visibleRows += 1;

            const orderSelect = row.querySelector('select[name$="-purchase_order"]');
            if (!orderSelect) return;

            if (String(orderSelect.value || '').trim() !== '') {
                hasAtLeastOneOrder = true;
                return;
            }

            if (!firstEmptyOrderSelect) {
                firstEmptyOrderSelect = orderSelect;
            }
        });

        if (hasAtLeastOneOrder) {
            return { ok: true };
        }

        if (visibleRows > 0 && firstEmptyOrderSelect) {
            const firstEmptyRow = firstEmptyOrderSelect.closest('tr[data-row-kind="order"]');
            markRowInvalid(firstEmptyRow);

            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(firstEmptyOrderSelect, 'Debe seleccionar una orden de compra.');
            }
            if (orderWidget) {
                orderWidget.classList.add('js-client-invalid-block');
            }
            return {
                ok: false,
                kind: 'empty-order-field',
                field: firstEmptyOrderSelect,
            };
        }

        if (orderWidget) {
            orderWidget.classList.add('js-client-invalid-block');
        }
        return {
            ok: false,
            kind: 'no-order-rows',
            field: null,
        };
    }

    async function refreshContractData() {
        const contractId = contractSelect ? contractSelect.value : '';
        Object.keys(currentOrderLineOptions).forEach(function (k) {
            delete currentOrderLineOptions[k];
        });

        if (!contractId) {
            currentOrderOptions = [];
            orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(setupOrderRow);
            partialBody.querySelectorAll('tr[data-row-kind="partial"]').forEach(setupPartialRow);
            return;
        }

        const fetched = await fetchContractOrders(contractId);
        if (fetched === null) {
            showFormFeedback('No se pudieron cargar las ordenes del contrato.', 'warning');
            return;
        }

        currentOrderOptions = fetched || [];
        orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(setupOrderRow);
        partialBody.querySelectorAll('tr[data-row-kind="partial"]').forEach(setupPartialRow);
    }

    function decorateFieldsWithErrors(container) {
        if (formErrors.decorateFieldsWithErrors) {
            formErrors.decorateFieldsWithErrors(container || form);
        }
    }

    orderBody.querySelectorAll('tr[data-row-kind="order"]').forEach(function (row) {
        setupOrderRow(row);
        updateDeleteRowState(row);
    });
    partialBody.querySelectorAll('tr[data-row-kind="partial"]').forEach(function (row) {
        setupPartialRow(row);
        updateDeleteRowState(row);
    });
    refreshRowIndexes(orderBody);
    refreshRowIndexes(partialBody);
    syncPartialSectionVisibility();

    form.addEventListener('click', function (e) {
        const btn = e.target.closest('.js-delete-line-btn');
        if (btn) removeRow(btn);
    });

    form.addEventListener('submit', function (e) {
        const invalidHeaderField = validateHeaderRequiredFields();
        if (invalidHeaderField) {
            e.preventDefault();
            showFormFeedback('Complete los campos obligatorios de la cabecera.', 'danger');
            const wrapper = invalidHeaderField.closest('.row') || invalidHeaderField;
            if (wrapper && wrapper.scrollIntoView) {
                wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return;
        }

        const orderValidation = validateAtLeastOneOrderLine();
        if (!orderValidation.ok) {
            e.preventDefault();
            if (orderValidation.kind === 'empty-order-field') {
                showFormFeedback('Complete los campos obligatorios de las lineas de orden.', 'danger');
                const wrapper = orderValidation.field.closest('tr') || orderValidation.field;
                if (wrapper && wrapper.scrollIntoView) {
                    wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            } else {
                showFormFeedback('Debe agregar al menos una linea de cumplimiento.', 'danger');
                if (orderWidget && orderWidget.scrollIntoView) {
                    orderWidget.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
            return;
        }

        const partialCoverageValidation = validatePartialCoverage();
        if (!partialCoverageValidation.ok) {
            e.preventDefault();
            if (partialCoverageValidation.kind === 'empty-partial-field') {
                showFormFeedback('Complete los campos obligatorios de las lineas parciales.', 'danger');
                const wrapper = partialCoverageValidation.field.closest('tr') || partialCoverageValidation.field;
                if (wrapper && wrapper.scrollIntoView) {
                    wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            } else {
                showFormFeedback('Cada orden marcada en modo parcial debe tener al menos un detalle parcial por linea.', 'danger');
                if (partialWidget && partialWidget.scrollIntoView) {
                    partialWidget.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
            return;
        }

        clearEmptyMemoErrorState();
        clearPartialCoverageErrorState();
        showFormFeedback('', 'danger');

        partialBody.querySelectorAll('input[name$="-fulfilled_quantity"]').forEach(function (input) {
            if (numberUtils.normalizeInputForSubmit) {
                numberUtils.normalizeInputForSubmit(input, {
                    kind: 'quantity',
                    precision: 0,
                });
            }
        });
    });

    if (contractSelect) {
        bindSelectChangeEvents(contractSelect, function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(contractSelect);
            }
            refreshContractData();
        });
    }

    [memoNumberInput, memoDateInput, beneficiarySectorInput, receivedByInput, senderPositionInput].forEach(function (field) {
        if (!field) return;
        field.addEventListener('input', function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(field);
            }
        });
        field.addEventListener('change', function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(field);
            }
        });
    });

    orderBody.addEventListener('change', function (e) {
        if (e.target && e.target.matches('select[name$="-purchase_order"]')) {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(e.target);
            }
            clearEmptyMemoErrorState();
            showFormFeedback('', 'danger');
        }
    });

    partialBody.addEventListener('change', function (e) {
        if (!e.target) return;
        if (
            e.target.matches('select[name$="-purchase_order"]') ||
            e.target.matches('select[name$="-purchase_order_line"]')
        ) {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(e.target);
            }
            clearPartialCoverageErrorState();
            showFormFeedback('', 'danger');
        }
    });

    partialBody.addEventListener('input', function (e) {
        if (!e.target || !e.target.matches('input[name$="-fulfilled_quantity"]')) return;
        if (formErrors.clearFieldError) {
            formErrors.clearFieldError(e.target);
        }
        clearPartialCoverageErrorState();
        showFormFeedback('', 'danger');
    });

    if (addOrderBtn) {
        addOrderBtn.addEventListener('click', function () {
            addRow(orderTemplate, orderBody, orderTotalForms, setupOrderRow);
            syncPartialSectionVisibility();
        });
    }

    if (addPartialBtn) {
        addPartialBtn.addEventListener('click', function () {
            const canAddPartialRows = syncPartialSectionVisibility();
            if (!canAddPartialRows) {
                return;
            }
            addRow(partialTemplate, partialBody, partialTotalForms, setupPartialRow);
        });
    }

    decorateFieldsWithErrors(form);
    disableNativeRequiredOnEnhancedSelects(form);
    showFormFeedback('', 'danger');
    refreshContractData();
    syncPartialSectionVisibility();
})();
