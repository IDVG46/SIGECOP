(function () {
    function getFieldContainer(field) {
        if (!field) return null;
        return field.closest('td') || field.closest('.col-sm-1, .col-sm-2, .col-sm-3, .col-sm-4, .col-sm-5, .col-sm-6, .col-sm-7, .col-sm-8, .col-sm-9, .col-sm-10, .col-sm-11, .col-sm-12');
    }

    function getTomSelectControl(field) {
        if (!field) return null;
        if (field.tomselect && field.tomselect.control) {
            return field.tomselect.control;
        }
        const siblingWrapper = field.nextElementSibling;
        if (siblingWrapper && siblingWrapper.classList && siblingWrapper.classList.contains('ts-wrapper')) {
            return siblingWrapper.querySelector('.ts-control');
        }
        const container = getFieldContainer(field);
        return container ? container.querySelector('.ts-control') : null;
    }

    function markFieldInvalid(field, message, options) {
        if (!field) return;
        const cfg = options || {};
        const container = cfg.container || getFieldContainer(field);

        field.classList.add('js-client-invalid');

        const tsControl = getTomSelectControl(field);
        if (tsControl) {
            tsControl.classList.add('js-client-invalid-control');
        }

        if (!message || !container) return;

        const errorNode = document.createElement('small');
        errorNode.className = 'text-danger js-inline-field-error';
        errorNode.textContent = message;
        container.appendChild(errorNode);
    }

    function clearFieldError(field, options) {
        if (!field) return;
        const cfg = options || {};
        const container = cfg.container || getFieldContainer(field);

        field.classList.remove('js-client-invalid');

        const tsControl = getTomSelectControl(field);
        if (tsControl) {
            tsControl.classList.remove('js-client-invalid-control');
        }

        if (container) {
            container.querySelectorAll('.js-inline-field-error').forEach(function (errorNode) {
                errorNode.remove();
            });
        }
    }

    function clearInvalidInContainer(container) {
        if (!container) return;

        container.querySelectorAll('.js-client-invalid').forEach(function (field) {
            field.classList.remove('js-client-invalid');
        });

        container.querySelectorAll('.ts-control.js-client-invalid-control').forEach(function (control) {
            control.classList.remove('js-client-invalid-control');
        });

        container.querySelectorAll('.js-inline-field-error').forEach(function (errorNode) {
            errorNode.remove();
        });
    }

    function decorateFieldsWithErrors(container) {
        const root = container || document;
        root.querySelectorAll('.errorlist').forEach(function (errorList) {
            const control = errorList.previousElementSibling;
            if (!control || !control.matches('input, textarea, select')) return;
            if (control.type === 'hidden' || control.type === 'checkbox' || control.type === 'radio') return;

            const firstError = errorList.querySelector('li');
            const errorMessage = firstError ? firstError.textContent.trim() : errorList.textContent.trim();

            markFieldInvalid(control, errorMessage);
            errorList.remove();
        });
    }

    function disableNativeRequiredOnEnhancedSelects(container) {
        const root = container || document;
        root.querySelectorAll('select.select2[required]').forEach(function (select) {
            select.removeAttribute('required');
            select.dataset.requiredManaged = '1';
        });
    }

    function ensureFeedbackCloseButton(feedbackBox) {
        if (!feedbackBox) return;
        if (feedbackBox.querySelector('.js-feedback-close')) return;

        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'js-feedback-close form-feedback-close';
        closeButton.setAttribute('aria-label', 'Cerrar mensaje');
        closeButton.innerHTML = '&times;';
        closeButton.addEventListener('click', function () {
            feedbackBox.style.display = 'none';
            feedbackBox.textContent = '';
            feedbackBox.className = 'alert alert-danger form-feedback floating-form-feedback';
            ensureFeedbackCloseButton(feedbackBox);
        });

        feedbackBox.appendChild(closeButton);
    }

    function showFloatingFeedback(feedbackBox, message, level) {
        if (!feedbackBox) return;

        if (!message) {
            feedbackBox.style.display = 'none';
            feedbackBox.textContent = '';
            feedbackBox.className = 'alert alert-danger form-feedback floating-form-feedback';
            ensureFeedbackCloseButton(feedbackBox);
            return;
        }

        feedbackBox.style.display = '';
        feedbackBox.textContent = message;
        feedbackBox.className = `alert alert-${level || 'danger'} form-feedback floating-form-feedback`;
        ensureFeedbackCloseButton(feedbackBox);
    }

    window.SIGECOPFormErrors = {
        markFieldInvalid: markFieldInvalid,
        clearFieldError: clearFieldError,
        clearInvalidInContainer: clearInvalidInContainer,
        decorateFieldsWithErrors: decorateFieldsWithErrors,
        disableNativeRequiredOnEnhancedSelects: disableNativeRequiredOnEnhancedSelects,
        showFloatingFeedback: showFloatingFeedback,
    };
})();
