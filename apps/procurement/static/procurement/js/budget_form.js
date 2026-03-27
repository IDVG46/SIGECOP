(function () {
    const form = document.getElementById('budget-form');
    if (!form) return;
    form.setAttribute('novalidate', 'novalidate');

    const formErrors = window.SIGECOPFormErrors || {};
    const contractSelect = document.getElementById('id_contract');
    const expenseObjectSelect = document.getElementById('id_expense_object');
    const fiscalYearInput = document.getElementById('id_fiscal_year');
    const financialCodeSelect = document.getElementById('id_financial_code');
    const fundingSourceInput = document.getElementById('id_funding_source');
    const statusSelect = document.getElementById('id_status');
    const assignedAmountInput = document.getElementById('id_assigned_amount');
    const feedbackBox = document.getElementById('budget-form-feedback');
    const financialCodesUrlTemplate = form.dataset.financialCodesUrlTemplate || '';

    if (window.SIGECOPUI && window.SIGECOPUI.enhanceSelects) {
        window.SIGECOPUI.enhanceSelects(form);
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

    function setOptions(select, options, selectedValue) {
        if (!select) return;

        const normalizedSelected = selectedValue ? String(selectedValue) : String(select.value || '');
        const normalizedOptions = (options || []).map(function (item) {
            return {
                value: String(item.value),
                text: item.label,
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
        const blank = document.createElement('option');
        blank.value = '';
        blank.textContent = '';
        select.appendChild(blank);

        normalizedOptions.forEach(function (opt) {
            const option = document.createElement('option');
            option.value = opt.value;
            option.textContent = opt.text;
            select.appendChild(option);
        });

        select.value = normalizedSelected;
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function validateRequiredFields() {
        const requiredFields = [
            { field: contractSelect, message: 'Debe seleccionar un contrato.' },
            { field: expenseObjectSelect, message: 'Debe seleccionar un objeto de gasto.' },
            { field: fiscalYearInput, message: 'Debe completar el año fiscal.' },
            { field: fundingSourceInput, message: 'Debe completar la fuente de financiamiento.' },
            { field: statusSelect, message: 'Debe seleccionar un estado.' },
            { field: assignedAmountInput, message: 'Debe completar el monto asignado.' },
        ];

        requiredFields.forEach(function (entry) {
            if (!entry.field) return;
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(entry.field);
            }
        });

        for (const entry of requiredFields) {
            if (!entry.field) continue;
            const value = String(entry.field.value || '').trim();
            if (value !== '') continue;

            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(entry.field, entry.message);
            }
            return entry.field;
        }

        return null;
    }

    function buildFinancialCodesUrl(contractId) {
        if (!contractId || !financialCodesUrlTemplate) return '';
        return financialCodesUrlTemplate.replace('__CONTRACT_ID__', encodeURIComponent(contractId));
    }

    async function refreshFinancialCodes() {
        if (!contractSelect || !financialCodeSelect) return;

        const contractId = contractSelect.value;
        const previousValue = financialCodeSelect.value || '';

        if (!contractId) {
            setOptions(financialCodeSelect, []);
            return;
        }

        try {
            const url = buildFinancialCodesUrl(contractId);
            if (!url) return;

            const response = await fetch(url, { credentials: 'same-origin' });
            if (!response.ok) return;

            const payload = await response.json();
            const items = payload.financial_codes || [];

            const knownCodes = items.slice();
            if (previousValue) {
                const exists = knownCodes.some(function (item) {
                    return String(item.value) === String(previousValue);
                });
                if (!exists) {
                    knownCodes.push({ value: previousValue, label: previousValue });
                }
            }

            setOptions(financialCodeSelect, knownCodes, previousValue);
        } catch (error) {
            if (window.console) {
                console.warn('No se pudieron cargar financial codes', error);
            }

            if (previousValue) {
                setOptions(financialCodeSelect, [{ value: previousValue, label: previousValue }], previousValue);
            } else {
                setOptions(financialCodeSelect, []);
            }
        }
    }

    const numberUtils = window.SIGECOPNumbers || {};
    const moneyInputs = ['id_assigned_amount', 'id_committed_amount', 'id_executed_amount']
        .map(function (id) { return document.getElementById(id); })
        .filter(Boolean);

    moneyInputs.forEach(function (input) {
        if (numberUtils.bindInputFormatting) {
            numberUtils.bindInputFormatting(input, {
                kind: 'money',
                currency: 'Gs.',
                precision: 0,
                locale: 'es-PY',
            });
        }
    });

    setSelectPlaceholder(contractSelect, 'Buscar contrato...');
    setSelectPlaceholder(expenseObjectSelect, 'Buscar objeto de gasto...');
    setSelectPlaceholder(financialCodeSelect, 'Buscar código financiero...');
    setSelectPlaceholder(statusSelect, 'Buscar estado...');

    if (contractSelect) {
        bindSelectChangeEvents(contractSelect, function () {
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(contractSelect);
            }
            if (formErrors.clearFieldError && financialCodeSelect) {
                formErrors.clearFieldError(financialCodeSelect);
            }
            showFormFeedback('', 'danger');
            refreshFinancialCodes();
        });
    }

    [expenseObjectSelect, fiscalYearInput, fundingSourceInput, statusSelect, assignedAmountInput].forEach(function (field) {
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

    refreshFinancialCodes();

    form.addEventListener('submit', function (e) {
        const invalidField = validateRequiredFields();
        if (invalidField) {
            e.preventDefault();
            showFormFeedback('Complete los campos requeridos del presupuesto.', 'danger');
            invalidField.focus();
            return false;
        }

        moneyInputs.forEach(function (input) {
            if (numberUtils.normalizeInputForSubmit) {
                numberUtils.normalizeInputForSubmit(input, {
                    kind: 'money',
                    currency: 'Gs.',
                    precision: 0,
                    locale: 'es-PY',
                });
            }
        });
    });

    if (formErrors.decorateFieldsWithErrors) {
        formErrors.decorateFieldsWithErrors(form);
    }
    if (formErrors.disableNativeRequiredOnEnhancedSelects) {
        formErrors.disableNativeRequiredOnEnhancedSelects(form);
    }
    showFormFeedback('', 'danger');
})();
