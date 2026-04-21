(function () {
    const form = document.getElementById('amendment-form');
    if (!form) return;

    form.setAttribute('novalidate', 'novalidate');

    const feedbackBox = document.getElementById('amendment-form-feedback');
    const formErrors = window.SIGECOPFormErrors || {};
    const numberUtils = window.SIGECOPNumbers || {};
    const contractSelect = document.getElementById('id_contract');
    const amendmentNumberInput = document.getElementById('id_amendment_number');
    const amendmentTypeSelect = document.getElementById('id_amendment_type');
    const financialCodeInput = document.getElementById('id_financial_code');
    const amountDeltaInput = document.getElementById('id_amount_delta');
    const periodExtensionInput = document.getElementById('id_period_extension_days');
    const newEndDateInput = document.getElementById('id_new_end_date');
    const effectiveDateInput = document.getElementById('id_effective_date');
    const statusSelect = document.getElementById('id_status');
    const isCreateMode = form.dataset.isCreate === '1';

    if (window.SIGECOPUI && window.SIGECOPUI.enhanceSelects) {
        window.SIGECOPUI.enhanceSelects(form);
    }

    if (formErrors.disableNativeRequiredOnEnhancedSelects) {
        formErrors.disableNativeRequiredOnEnhancedSelects(form);
    }

    if (formErrors.decorateFieldsWithErrors) {
        formErrors.decorateFieldsWithErrors(form);
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

    function clearFieldError(field) {
        if (!field || !formErrors.clearFieldError) return;
        formErrors.clearFieldError(field);
    }

    function clearPeriodErrors() {
        clearFieldError(periodExtensionInput);
        clearFieldError(newEndDateInput);
    }

    function focusField(field) {
        if (!field) return;
        const wrapper = field.closest('.col-sm-4, .col-sm-12');
        if (wrapper && wrapper.scrollIntoView) {
            wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        if (field.tomselect) {
            if (field.tomselect.control_input && typeof field.tomselect.control_input.focus === 'function') {
                field.tomselect.control_input.focus();
                return;
            }
            if (field.tomselect.control && typeof field.tomselect.control.focus === 'function') {
                field.tomselect.control.focus();
                return;
            }
        }

        field.focus();
    }

    function focusSelectWithoutDropdown(field) {
        if (!field) return;
        const wrapper = field.closest('.col-sm-4, .col-sm-12');
        if (wrapper && wrapper.scrollIntoView) {
            wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        if (!field.tomselect) {
            field.focus();
            return;
        }

        const tomselect = field.tomselect;
        const previousOpenOnFocus = tomselect.settings.openOnFocus;
        tomselect.settings.openOnFocus = false;

        if (tomselect.control_input && typeof tomselect.control_input.focus === 'function') {
            tomselect.control_input.focus();
        } else if (tomselect.control && typeof tomselect.control.focus === 'function') {
            tomselect.control.focus();
        } else {
            field.focus();
        }

        window.setTimeout(function () {
            tomselect.close();
            tomselect.settings.openOnFocus = previousOpenOnFocus;
        }, 0);
    }

    function amendmentTypeValue() {
        return String(amendmentTypeSelect?.value || '').trim();
    }

    function validateRequiredFields() {
        const requiredFields = [
            { field: contractSelect, message: 'Debe seleccionar un contrato.' },
            { field: amendmentNumberInput, message: 'Debe completar el número de adenda.' },
            { field: amendmentTypeSelect, message: 'Debe seleccionar el tipo de adenda.' },
            { field: financialCodeInput, message: 'Debe completar el código financiero.' },
            { field: effectiveDateInput, message: 'Debe completar la fecha de vigencia.' },
            { field: statusSelect, message: 'Debe seleccionar un estado.' },
        ];

        requiredFields.forEach(function (entry) {
            clearFieldError(entry.field);
        });
        clearFieldError(financialCodeInput);
        clearFieldError(amountDeltaInput);
        clearPeriodErrors();

        for (const entry of requiredFields) {
            if (!entry.field) continue;
            const value = String(entry.field.value || '').trim();
            if (value !== '') continue;

            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(entry.field, entry.message);
            }
            return entry.field;
        }

        const type = amendmentTypeValue();
        const needsAmount = type === 'amount' || type === 'mixed';
        const needsPeriod = type === 'period' || type === 'mixed';
        const amountValue = String(amountDeltaInput?.value || '').trim();
        const periodValue = String(periodExtensionInput?.value || '').trim();
        const endDateValue = String(newEndDateInput?.value || '').trim();

        if (needsAmount && amountDeltaInput && amountValue === '') {
            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(amountDeltaInput, 'Debe completar el monto de la adenda.');
            }
            return amountDeltaInput;
        }

        if (needsPeriod && periodExtensionInput && newEndDateInput && periodValue === '' && endDateValue === '') {
            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(periodExtensionInput, 'Ingrese días de prórroga o nueva fecha fin.');
                formErrors.markFieldInvalid(newEndDateInput, 'Ingrese días de prórroga o nueva fecha fin.');
            }
            return periodExtensionInput;
        }

        return null;
    }

    if (amountDeltaInput && numberUtils.bindInputFormatting) {
        numberUtils.bindInputFormatting(amountDeltaInput, {
            kind: 'money',
            currency: 'Gs.',
            precision: 0,
            locale: 'es-PY',
        });
    }

    [amendmentNumberInput, financialCodeInput, periodExtensionInput, newEndDateInput, effectiveDateInput].forEach(function (field) {
        if (!field) return;
        field.addEventListener('input', function () {
            clearFieldError(field);
            if (field === periodExtensionInput || field === newEndDateInput) {
                clearPeriodErrors();
            }
            showFormFeedback('', 'danger');
        });
        field.addEventListener('change', function () {
            clearFieldError(field);
            if (field === periodExtensionInput || field === newEndDateInput) {
                clearPeriodErrors();
            }
            showFormFeedback('', 'danger');
        });
    });

    bindSelectChangeEvents(contractSelect, function () {
        clearFieldError(contractSelect);
        showFormFeedback('', 'danger');
    });
    bindSelectChangeEvents(amendmentTypeSelect, function () {
        clearFieldError(amendmentTypeSelect);
        clearFieldError(financialCodeInput);
        clearFieldError(amountDeltaInput);
        clearPeriodErrors();
        showFormFeedback('', 'danger');
    });
    bindSelectChangeEvents(statusSelect, function () {
        clearFieldError(statusSelect);
        showFormFeedback('', 'danger');
    });

    form.addEventListener('submit', function (event) {
        const invalidField = validateRequiredFields();
        if (invalidField) {
            event.preventDefault();
            showFormFeedback('Revise los campos requeridos de la adenda antes de guardar.', 'danger');
            focusField(invalidField);
            return false;
        }

        if (amountDeltaInput && numberUtils.normalizeInputForSubmit) {
            numberUtils.normalizeInputForSubmit(amountDeltaInput, {
                kind: 'money',
                currency: 'Gs.',
                precision: 0,
                locale: 'es-PY',
            });
        }
    });

    const hasFieldErrors = !!form.querySelector('.js-client-invalid, .js-inline-field-error');
    const hasNonFieldErrors = !!form.querySelector('.alert.alert-danger');

    if (hasFieldErrors && formErrors.showFloatingFeedback) {
        formErrors.showFloatingFeedback(
            feedbackBox,
            'Revise los campos marcados en rojo antes de guardar la adenda.',
            'danger'
        );
    } else if (!hasNonFieldErrors) {
        showFormFeedback('', 'danger');
    }

    if (isCreateMode) {
        window.setTimeout(function () {
            focusSelectWithoutDropdown(contractSelect || amendmentTypeSelect || statusSelect || amendmentNumberInput);
        }, 0);
    }
})();