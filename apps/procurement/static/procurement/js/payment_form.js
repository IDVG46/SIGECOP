(function () {
    const form = document.getElementById('payment-form');
    if (!form) return;
    form.setAttribute('novalidate', 'novalidate');

    const numberUtils = window.SIGECOPNumbers || {};
    const formErrors = window.SIGECOPFormErrors || {};
    const addButton = document.getElementById('add-allocation-button');
    const totalFormsInput = document.getElementById('id_allocations-TOTAL_FORMS') || document.getElementById('id_paymentallocation_set-TOTAL_FORMS');
    const tableBody = form.querySelector('table tbody');
    const rowTemplate = document.getElementById('allocation-row-template');
    const urlTemplate = form.dataset.orderBudgetsUrlTemplate || '';
    const contractField = document.getElementById('id_contract');
    const contractOrdersUrlTemplate = form.dataset.contractOrdersUrlTemplate || '';
    const feedbackBox = document.getElementById('payment-form-feedback');
    const allocationsWidget = document.getElementById('payment-allocations-widget');
    let currentContractOrderOptions = [];

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

    function validateHeaderRequiredFields() {
        const requiredFields = [
            { key: 'contract', message: 'Debe seleccionar un contrato.' },
            { key: 'payment_number', message: 'Debe completar el número de pago.' },
            { key: 'payment_date', message: 'Debe completar la fecha del pago.' },
            { key: 'amount_total', message: 'Debe completar el monto total.' },
        ];

        requiredFields.forEach(function(entry) {
            const field = document.getElementById('id_' + entry.key);
            if (!field) return;
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(field);
            }
        });

        for (const entry of requiredFields) {
            const field = document.getElementById('id_' + entry.key);
            if (!field) {
                continue;
            }

            const value = String(field.value || '').trim();
            if (value !== '') {
                continue;
            }

            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(field, entry.message);
            }
            return field;
        }

        return null;
    }

    function parseMoneyValue(rawValue) {
        if (numberUtils.parseQuantity) {
            return numberUtils.parseQuantity(rawValue);
        }
        return parseFloat(String(rawValue || '').replace(/\./g, '').replace(',', '.')) || 0;
    }

    function rowIsDeleted(row) {
        const deleteCheckbox = row ? row.querySelector('input[type="checkbox"][name$="-DELETE"]') : null;
        return !!(deleteCheckbox && deleteCheckbox.checked);
    }

    function clearRowInvalidState(row) {
        if (!row) return;
        row.classList.remove('danger');
        if (formErrors.clearInvalidInContainer) {
            formErrors.clearInvalidInContainer(row);
        }
        const amountError = row.querySelector('.amount-error');
        if (amountError) {
            amountError.textContent = '';
        }
    }

    function markRowInvalid(row) {
        if (!row) return;
        row.classList.add('danger');
    }

    function getFirstFocusableInvalidField(row) {
        if (!row) return null;
        return row.querySelector('select[name$="-purchase_order"], select[name$="-contract_budget"], input[name$="-amount"]');
    }

    function validateAllocationRow(row, options) {
        const showErrors = !!(options && options.showErrors);
        const requireCompleted = !!(options && options.requireCompleted);
        if (!row) {
            return { ok: true, field: null };
        }

        if (rowIsDeleted(row)) {
            clearRowInvalidState(row);
            return { ok: true, field: null };
        }

        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const budgetSelect = row.querySelector('select[name$="-contract_budget"]');
        const amountInput = row.querySelector('input[name$="-amount"]');
        const amountError = row.querySelector('.amount-error');

        const orderValue = String(orderSelect && orderSelect.value || '').trim();
        const budgetValue = String(budgetSelect && budgetSelect.value || '').trim();
        const amountRawValue = String(amountInput && amountInput.value || '').trim();
        const amountValue = parseMoneyValue(amountRawValue);
        const hasAnyValue = orderValue !== '' || budgetValue !== '' || amountRawValue !== '';

        function fail(field, message) {
            if (showErrors) {
                markRowInvalid(row);
                if (field && formErrors.markFieldInvalid) {
                    formErrors.markFieldInvalid(field, message);
                }
            } else {
                clearRowInvalidState(row);
            }
            return { ok: false, field: field || getFirstFocusableInvalidField(row) };
        }

        if (!hasAnyValue) {
            if (requireCompleted) {
                return fail(orderSelect, 'Debe seleccionar una orden de compra.');
            }
            clearRowInvalidState(row);
            return { ok: true, field: null };
        }

        if (!orderValue) {
            return fail(orderSelect, 'Debe seleccionar una orden de compra.');
        }

        if (!budgetValue) {
            return fail(budgetSelect, 'Debe seleccionar un presupuesto.');
        }

        if (!(amountValue > 0)) {
            return fail(amountInput, 'Debe indicar un monto mayor a cero.');
        }

        const selectedBudget = budgetSelect && budgetSelect.selectedIndex >= 0
            ? budgetSelect.options[budgetSelect.selectedIndex]
            : null;
        const availableAmount = parseFloat(selectedBudget && selectedBudget.dataset.availableAmount || '0') || 0;
        if (availableAmount > 0 && amountValue > availableAmount) {
            if (amountError) {
                amountError.textContent = 'Excede el saldo disponible del presupuesto (Gs. ' + availableAmount.toLocaleString('es-PY', { maximumFractionDigits: 0 }) + ').';
            }
            return fail(amountInput, 'El monto excede el saldo disponible del presupuesto.');
        }

        if (amountError) {
            amountError.textContent = '';
        }
        clearRowInvalidState(row);
        return { ok: true, field: null };
    }

    function clearAllocationTableErrorState() {
        if (allocationsWidget) {
            allocationsWidget.classList.remove('js-client-invalid-block');
        }
        if (!tableBody) return;
        tableBody.querySelectorAll('tr.line-row').forEach(function (row) {
            clearRowInvalidState(row);
        });
    }

    function validateAllocationTable() {
        clearAllocationTableErrorState();
        if (!tableBody) {
            return { ok: true, field: null, kind: null };
        }

        const activeRows = Array.from(tableBody.querySelectorAll('tr.line-row')).filter(function (row) {
            return !rowIsDeleted(row);
        });

        if (activeRows.length === 0) {
            if (allocationsWidget) {
                allocationsWidget.classList.add('js-client-invalid-block');
            }
            return { ok: false, kind: 'no-rows', field: null };
        }

        for (const row of activeRows) {
            const result = validateAllocationRow(row, { showErrors: true, requireCompleted: true });
            if (!result.ok) {
                if (allocationsWidget) {
                    allocationsWidget.classList.add('js-client-invalid-block');
                }
                return { ok: false, kind: 'invalid-row', field: result.field };
            }
        }

        return { ok: true, field: null, kind: null };
    }

    function applyDeleteRowState(row) {
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
        const del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
        row.classList.toggle('line-row-deleted', !!(del && del.checked));
    }

    function initSelect2In(container) {
        if (window.SIGECOPUI && window.SIGECOPUI.enhanceSelects) {
            window.SIGECOPUI.enhanceSelects(container || form);
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
    }

    function buildUrl(template, orderId) {
        if (!orderId || !template) return '';
        return template
            .replace('__ORDER_ID__', encodeURIComponent(orderId))
            .replace('%5F%5FORDER_ID%5F%5F', encodeURIComponent(orderId));
    }

    function setOptions(select, options, selectedValue) {
        if (!select) return;

        const normalizedSelected = selectedValue ? String(selectedValue) : String(select.value || '');
        const normalizedOptions = (options || []).map(function (opt) {
            return {
                value: String(opt.id),
                text: opt.text,
                availableAmount: String(opt.available_amount || '0'),
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
            option.dataset.availableAmount = opt.availableAmount;
            select.appendChild(option);
        });

        if (normalizedSelected) {
            select.value = normalizedSelected;
        }
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function getSelectedBudgetAvailableAmount(budgetSelect) {
        if (!budgetSelect) return 0;

        const selectedValue = String(budgetSelect.value || '').trim();
        if (!selectedValue) return 0;

        if (budgetSelect.tomselect && budgetSelect.tomselect.options) {
            const tsOption = budgetSelect.tomselect.options[selectedValue];
            if (tsOption && tsOption.availableAmount !== undefined) {
                return parseFloat(tsOption.availableAmount || '0') || 0;
            }
        }

        const selected = budgetSelect.selectedIndex >= 0
            ? budgetSelect.options[budgetSelect.selectedIndex]
            : null;
        return parseFloat(selected && selected.dataset.availableAmount || '0') || 0;
    }

    async function refreshBudgetsForRow(row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        const budgetSelect = row.querySelector('select[name$="-contract_budget"]');
        if (!orderSelect || !budgetSelect) return;

        const orderId = orderSelect.value;
        if (!orderId) {
            setOptions(budgetSelect, []);
            return;
        }

        const url = buildUrl(urlTemplate, orderId);
        if (!url) {
            setOptions(budgetSelect, []);
            return;
        }

        const resp = await fetch(url, { credentials: 'same-origin' });
        if (!resp.ok) {
            setOptions(budgetSelect, []);
            return;
        }

        const payload = await resp.json();
        const budgets = payload.budgets || [];
        setOptions(budgetSelect, budgets);
    }

    function validateAmountInput(input) {
        const row = input.closest('tr');
        if (!row) return;

        const budgetSelect = row.querySelector('select[name$="-contract_budget"]');
        const errorEl = row.querySelector('.amount-error');
        if (!budgetSelect || !String(budgetSelect.value || '').trim()) {
            if (errorEl) errorEl.textContent = '';
            return;
        }

        const entered = numberUtils.parseQuantity
            ? numberUtils.parseQuantity(input.value)
            : (parseFloat(String(input.value).replace(/\./g, '').replace(',', '.')) || 0);

        const available = getSelectedBudgetAvailableAmount(budgetSelect);
        if (!errorEl) return;

        if (Number.isFinite(entered) && available > 0 && entered > available) {
            errorEl.textContent = 'Excede el saldo disponible del presupuesto (Gs. ' + available.toLocaleString('es-PY', { maximumFractionDigits: 0 }) + ').';
        } else {
            errorEl.textContent = '';
        }
    }

    function setupOrderSelectListener(orderSelect) {
        if (!orderSelect) return;
        bindSelectChangeEvents(orderSelect, function () {
            const row = orderSelect.closest('tr');
            if (row) refreshBudgetsForRow(row);
        });
    }

    function refreshRowIndexes() {
        if (!tableBody) return;
        let index = 1;
        tableBody.querySelectorAll('tr.line-row').forEach(function (row) {
            const cell = row.querySelector('.js-line-index');
            if (cell) {
                cell.textContent = String(index);
                index += 1;
            }
        });
    }

    function addRow() {
        if (!rowTemplate || !tableBody || !totalFormsInput) return;

        const index = Number(totalFormsInput.value || '0');
        const html = rowTemplate.innerHTML.replace(/__prefix__/g, String(index));
        const temp = document.createElement('tbody');
        temp.innerHTML = html.trim();
        const row = temp.firstElementChild;
        if (!row) return;

        tableBody.appendChild(row);
        totalFormsInput.value = String(index + 1);

        initSelect2In(row);

        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        if (orderSelect) {
            setSelectPlaceholder(orderSelect, 'Buscar orden...');
            if (contractField && contractField.value) {
                setOptions(orderSelect, currentContractOrderOptions);
            } else {
                setOptions(orderSelect, []);
            }
            setupOrderSelectListener(orderSelect);
        }

        const budgetSelect = row.querySelector('select[name$="-contract_budget"]');
        if (budgetSelect) {
            setSelectPlaceholder(budgetSelect, 'Buscar presupuesto...');
            setOptions(budgetSelect, []);
        }

        row.querySelectorAll('input[name$="-amount"]').forEach(function (input) {
            if (numberUtils.bindInputFormatting) {
                numberUtils.bindInputFormatting(input, {
                    kind: 'money',
                    currency: 'Gs.',
                    precision: 0,
                    locale: 'es-PY',
                });
            }
        });

        applyDeleteRowState(row);
        refreshRowIndexes();
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
                onRemoved: function () {
                    refreshRowIndexes();
                },
            });
            if (!result.removed) {
                applyDeleteRowState(row);
            }
        } else {
            const deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (deleteCheckbox) {
                deleteCheckbox.checked = !deleteCheckbox.checked;
                applyDeleteRowState(row);
            } else {
                row.remove();
                refreshRowIndexes();
            }
        }

        recalculateTotal();
    }

    function recalculateTotal() {
        let sum = 0;
        form.querySelectorAll('input[name$="-amount"]').forEach(function (input) {
            const row = input.closest('tr');
            if (!row) return;

            const deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (deleteCheckbox && deleteCheckbox.checked) return;

            const val = numberUtils.parseQuantity
                ? numberUtils.parseQuantity(input.value)
                : (parseFloat(input.value.replace(/\./g, '').replace(',', '.')) || 0);
            if (Number.isFinite(val)) sum += val;
        });

        const totalInput = document.getElementById('id_amount_total');
        if (totalInput && numberUtils.setMoneyInputValue) {
            numberUtils.setMoneyInputValue(totalInput, sum, {
                currency: 'Gs.',
                precision: 0,
                locale: 'es-PY',
            });
        }
    }

    async function loadOrdersForContract(contractId, options) {
        const clearBudgets = !(options && options.clearBudgets === false);

        if (!contractOrdersUrlTemplate || !contractId) {
            currentContractOrderOptions = [];
            form.querySelectorAll('select[name$="-purchase_order"]').forEach(function (orderSelect) {
                setOptions(orderSelect, []);
            });
            form.querySelectorAll('select[name$="-contract_budget"]').forEach(function (budgetSelect) {
                setOptions(budgetSelect, []);
            });
            return;
        }

        const url = contractOrdersUrlTemplate.replace('__CONTRACT_ID__', encodeURIComponent(contractId));
        try {
            const resp = await fetch(url, { credentials: 'same-origin' });
            if (!resp.ok) {
                currentContractOrderOptions = [];
                form.querySelectorAll('select[name$="-purchase_order"]').forEach(function (orderSelect) {
                    setOptions(orderSelect, []);
                });
                if (clearBudgets) {
                    form.querySelectorAll('select[name$="-contract_budget"]').forEach(function (budgetSelect) {
                        setOptions(budgetSelect, []);
                    });
                }
                return;
            }

            const payload = await resp.json();
            const orders = payload.orders || [];
            currentContractOrderOptions = orders;

            form.querySelectorAll('select[name$="-purchase_order"]').forEach(function (orderSelect) {
                setOptions(orderSelect, orders);
            });

            if (clearBudgets) {
                form.querySelectorAll('select[name$="-contract_budget"]').forEach(function (budgetSelect) {
                    setOptions(budgetSelect, []);
                });
            }
        } catch (_error) {
            return;
        }
    }

    form.querySelectorAll('input[name$="-amount"]').forEach(function (input) {
        if (numberUtils.bindInputFormatting) {
            numberUtils.bindInputFormatting(input, {
                kind: 'money',
                currency: 'Gs.',
                precision: 0,
                locale: 'es-PY',
            });
        }
    });

    // Asegura que los selects existentes (primera fila incluida) estén inicializados
    // antes de sincronizar opciones dinámicas.
    initSelect2In(form);

    if (addButton) {
        addButton.addEventListener('click', addRow);
    }

    form.addEventListener('click', function (e) {
        const btn = e.target.closest('.js-delete-line-btn');
        if (btn) removeRow(btn);
    });

    form.addEventListener('input', function (e) {
        if (e.target && e.target.matches('input[name$="-amount"]')) {
            recalculateTotal();
            const row = e.target.closest('tr.line-row');
            if (row && formErrors.clearFieldError) {
                formErrors.clearFieldError(e.target);
                row.classList.remove('danger');
            }
            if (allocationsWidget) {
                allocationsWidget.classList.remove('js-client-invalid-block');
            }
        }
    });

    form.addEventListener('change', function (e) {
        if (e.target && e.target.matches('select[name$="-purchase_order"], select[name$="-contract_budget"], input[name$="-amount"]')) {
            const row = e.target.closest('tr.line-row');
            if (row) {
                if (formErrors.clearFieldError) {
                    formErrors.clearFieldError(e.target);
                }
                row.classList.remove('danger');
            }
            if (allocationsWidget) {
                allocationsWidget.classList.remove('js-client-invalid-block');
            }
            showFormFeedback('', 'danger');
        }

        if (e.target && e.target.matches('select[name$="-contract_budget"], input[name$="-amount"]')) {
            const row = e.target.closest('tr');
            if (row) {
                const amountInput = row.querySelector('input[name$="-amount"]');
                if (amountInput) validateAmountInput(amountInput);
            }
        }
    });

    form.addEventListener('submit', function (e) {
        const invalidHeaderField = validateHeaderRequiredFields();
        if (invalidHeaderField) {
            e.preventDefault();
            showFormFeedback('Complete los campos requeridos en la seccion superior.', 'danger');
            invalidHeaderField.focus();
            return false;
        }

        const allocationValidation = validateAllocationTable();
        if (!allocationValidation.ok) {
            e.preventDefault();
            if (allocationValidation.kind === 'no-rows') {
                showFormFeedback('Debe agregar al menos una linea de asignacion.', 'danger');
                if (allocationsWidget && allocationsWidget.scrollIntoView) {
                    allocationsWidget.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            } else {
                showFormFeedback('Complete los campos obligatorios de las lineas de asignacion.', 'danger');
                const wrapper = allocationValidation.field ? allocationValidation.field.closest('tr') : null;
                if (wrapper && wrapper.scrollIntoView) {
                    wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
            return false;
        }

        form.querySelectorAll('input[name$="-amount"]').forEach(function (input) {
            if (numberUtils.normalizeInputForSubmit) {
                numberUtils.normalizeInputForSubmit(input, {
                    kind: 'money',
                    currency: 'Gs.',
                    precision: 0,
                    locale: 'es-PY',
                });
            }
        });

        const totalInput = document.getElementById('id_amount_total');
        if (totalInput && numberUtils.normalizeInputForSubmit) {
            numberUtils.normalizeInputForSubmit(totalInput, {
                kind: 'money',
                currency: 'Gs.',
                precision: 0,
                locale: 'es-PY',
            });
        }
    });

    form.querySelectorAll('tbody tr.line-row').forEach(function (row) {
        const orderSelect = row.querySelector('select[name$="-purchase_order"]');
        if (orderSelect) {
            setSelectPlaceholder(orderSelect, 'Buscar orden...');
            setupOrderSelectListener(orderSelect);
        }
        const budgetSelect = row.querySelector('select[name$="-contract_budget"]');
        if (budgetSelect) {
            setSelectPlaceholder(budgetSelect, 'Buscar presupuesto...');
        }
        applyDeleteRowState(row);
    });

    if (contractField) {
        setSelectPlaceholder(contractField, 'Buscar contrato...');
    }

    if (contractField && contractField.value) {
        contractField.style.pointerEvents = 'none';
        contractField.style.backgroundColor = '#f5f5f5';
        contractField.style.color = '#777';
        contractField.tabIndex = -1;
    }

    if (!contractField || !contractField.value) {
        loadOrdersForContract('');
        form.querySelectorAll('select[name$="-contract_budget"]').forEach(function (budgetSelect) {
            setOptions(budgetSelect, []);
        });
    } else {
        loadOrdersForContract(contractField.value, { clearBudgets: false }).then(function () {
            form.querySelectorAll('tbody tr.line-row').forEach(function (row) {
                const orderSelect = row.querySelector('select[name$="-purchase_order"]');
                if (orderSelect && orderSelect.value) {
                    refreshBudgetsForRow(row);
                }
            });
        });
    }

    if (contractField) {
        bindSelectChangeEvents(contractField, function () {
            // Limpiar errores de campos cuando cambia el contrato
            const requiredFields = [
                { key: 'contract', message: 'Debe seleccionar un contrato.' },
                { key: 'payment_number', message: 'Debe completar el número de pago.' },
                { key: 'payment_date', message: 'Debe completar la fecha del pago.' },
                { key: 'amount_total', message: 'Debe completar el monto total.' },
            ];
            
            requiredFields.forEach(function(entry) {
                const field = document.getElementById('id_' + entry.key);
                if (!field) return;
                if (formErrors.clearFieldError) {
                    formErrors.clearFieldError(field);
                }
            });

            // Limpiar errores en filas de asignaciones
            clearAllocationTableErrorState();
            showFormFeedback('', 'danger');
            
            const selectedContractId = String(contractField.value || '').trim();
            loadOrdersForContract(selectedContractId);
        });
    }

    refreshRowIndexes();
    recalculateTotal();

    // Decorar campos con errores y deshabilitar required en selects mejorados
    if (formErrors.decorateFieldsWithErrors) {
        formErrors.decorateFieldsWithErrors(form);
    }
    if (formErrors.disableNativeRequiredOnEnhancedSelects) {
        formErrors.disableNativeRequiredOnEnhancedSelects(form);
    }
})();
