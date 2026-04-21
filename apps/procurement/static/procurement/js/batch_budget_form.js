/**
 * batch_budget_form.js
 * Maneja el editor batch de presupuestos por contrato:
 *  - Redirige a la URL del contrato seleccionado al cambiar el selector
 *  - Formato de montos (SIGECOPNumbers) en campo assigned_amount
 *  - Decorar errores del servidor con estilos js-client-invalid (SIGECOPFormErrors)
 *  - Agregar nueva fila (clonar empty form, incrementar management form)
 *  - Eliminar / marcar para DELETE una fila existente
 */
(function () {
    "use strict";

    var TOTAL_FORMS_INPUT = null;
    var batchUrlTemplate = "";
    var feedbackBox = null;
    var budgetLinesWidget = null;

    var nu = window.SIGECOPNumbers || {};
    var fe = window.SIGECOPFormErrors || {};

    function showBatchFeedback(message, level) {
        if (fe.showFloatingFeedback) {
            fe.showFloatingFeedback(feedbackBox, message, level);
            return;
        }

        if (!feedbackBox) return;
        if (!message) {
            feedbackBox.style.display = "none";
            feedbackBox.textContent = "";
            feedbackBox.className = "alert alert-danger form-feedback";
            return;
        }

        feedbackBox.style.display = "";
        feedbackBox.textContent = message;
        feedbackBox.className = "alert alert-" + (level || "danger") + " form-feedback";
    }

    function clearCellError(field, cell) {
        if (!field || !fe.clearFieldError) return;
        fe.clearFieldError(field, { container: cell || field.closest("td") });
    }

    function getRowField(row, fieldNamePart) {
        if (!row) return null;
        return row.querySelector('[name*="' + fieldNamePart + '"]');
    }

    function activeBudgetRows() {
        return Array.from(document.querySelectorAll("#budget-batch-tbody .budget-line-row")).filter(function (row) {
            var deleteInput = row.querySelector('input[name$="-DELETE"]');
            return !(deleteInput && deleteInput.checked);
        });
    }

    function rowHasAnyData(row) {
        if (!row) return false;

        var visibleFields = [
            getRowField(row, "expense_object"),
            getRowField(row, "fiscal_year"),
            getRowField(row, "financial_code"),
            getRowField(row, "funding_source"),
            getRowField(row, "cdp_number"),
            getRowField(row, "assigned_amount"),
            getRowField(row, "status")
        ];

        return visibleFields.some(function (field) {
            return !!String(field && field.value || "").trim();
        });
    }

    function clearRowErrors(row) {
        if (!row) return;
        [
            "expense_object",
            "financial_code",
            "cdp_number",
            "fiscal_year",
            "funding_source",
            "assigned_amount",
            "status"
        ].forEach(function (fieldNamePart) {
            var field = getRowField(row, fieldNamePart);
            if (!field) return;
            clearCellError(field, field.closest("td"));
        });
    }

    function clearRowInvalidState(row) {
        if (!row) return;
        row.classList.remove("danger");
        clearRowErrors(row);
    }

    function markRequiredError(field, message) {
        if (!field || !fe.markFieldInvalid) return;
        fe.markFieldInvalid(field, message, { container: field.closest("td") });
    }

    function validateRow(row, options) {
        var requireCompleted = !!(options && options.requireCompleted);
        if (!row) return true;

        clearRowInvalidState(row);

        var deleteInput = row.querySelector('input[name$="-DELETE"]');
        if (deleteInput && deleteInput.checked) {
            return true;
        }

        if (!rowHasAnyData(row)) {
            if (!requireCompleted) {
                return true;
            }
            return true;
        }

        var validations = [
            { field: getRowField(row, "expense_object"), message: "Seleccione el objeto de gasto." },
            { field: getRowField(row, "fiscal_year"), message: "Complete el año fiscal." },
            { field: getRowField(row, "funding_source"), message: "Complete la fuente de financiamiento." },
            { field: getRowField(row, "assigned_amount"), message: "Complete el monto asignado." },
            { field: getRowField(row, "status"), message: "Seleccione el estado." }
        ];

        for (var i = 0; i < validations.length; i++) {
            var entry = validations[i];
            if (!entry.field) continue;
            var value = String(entry.field.value || "").trim();
            if (value !== "") continue;

            row.classList.add("danger");
            markRequiredError(entry.field, entry.message);
            return false;
        }

        return true;
    }

    function validateAllRows(options) {
        return activeBudgetRows().every(function (row) {
            return validateRow(row, options);
        });
    }

    function firstInvalidRow() {
        return activeBudgetRows().find(function (row) {
            return row.classList.contains("danger");
        }) || null;
    }

    function validateActiveRows() {
        var rows = activeBudgetRows();

        if (budgetLinesWidget) {
            budgetLinesWidget.classList.remove("js-client-invalid-block");
        }

        rows.forEach(function (row) {
            clearRowInvalidState(row);
        });

        validateAllRows({ requireCompleted: true });

        var invalidRow = firstInvalidRow();
        var firstInvalidField = invalidRow
            ? invalidRow.querySelector(".js-client-invalid, select, input, textarea")
            : null;

        if (firstInvalidField && budgetLinesWidget) {
            budgetLinesWidget.classList.add("js-client-invalid-block");
        }

        return firstInvalidField;
    }

    function focusInvalidField(field) {
        if (!field) return;
        var row = field.closest("tr");
        if (row && row.scrollIntoView) {
            row.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        if (field.tomselect) {
            if (field.tomselect.control_input && typeof field.tomselect.control_input.focus === "function") {
                field.tomselect.control_input.focus();
                return;
            }
            if (field.tomselect.control && typeof field.tomselect.control.focus === "function") {
                field.tomselect.control.focus();
                return;
            }
        }

        field.focus();
    }

    function bindRowValidation(row) {
        if (!row) return;
        [
            "expense_object",
            "fiscal_year",
            "funding_source",
            "assigned_amount",
            "status"
        ].forEach(function (fieldNamePart) {
            var field = getRowField(row, fieldNamePart);
            if (!field) return;

            var handler = function () {
                clearCellError(field, field.closest("td"));
                row.classList.remove("danger");
                if (!document.querySelector("#budget-batch-table .js-client-invalid")) {
                    if (budgetLinesWidget) {
                        budgetLinesWidget.classList.remove("js-client-invalid-block");
                    }
                    showBatchFeedback("", "danger");
                }
            };

            field.addEventListener("input", handler);
            field.addEventListener("change", handler);

            if (field.tomselect && typeof field.tomselect.on === "function") {
                field.tomselect.off("change");
                field.tomselect.on("change", handler);
            }
        });
    }

    // ── Formato de montos (assigned_amount) ─────────────────────────
    function bindAmountInput(input) {
        if (!input || !nu.bindInputFormatting) return;
        nu.bindInputFormatting(input, { kind: "money", currency: "Gs" });
    }

    function bindAmountInputsInRow(row) {
        row.querySelectorAll('input[name*="assigned_amount"]').forEach(bindAmountInput);
    }

    function normalizeAmountsForSubmit(form) {
        if (!nu.normalizeInputForSubmit) return;
        form.querySelectorAll('input[name*="assigned_amount"]').forEach(function (input) {
            nu.normalizeInputForSubmit(input, { kind: "money", currency: "Gs" });
        });
    }

    // ── Decorar errores del servidor en la tabla ─────────────────────
    // Transforma <ul class="errorlist"> en estilos js-client-invalid
    // sobre el campo correspondiente, para unificar visualmente con
    // la validacion cliente de otros formularios.
    function decorateServerErrors() {
        var table = document.getElementById("budget-batch-table");
        if (!table || !fe.markFieldInvalid) return;

        var hasErrors = false;

        if (budgetLinesWidget) {
            budgetLinesWidget.classList.remove("js-client-invalid-block");
        }

        table.querySelectorAll(".errorlist").forEach(function (errorList) {
            var td = errorList.closest("td");
            if (!td) return;
            var msg = "";
            var firstLi = errorList.querySelector("li");
            if (firstLi) msg = firstLi.textContent.trim();
            hasErrors = true;

            // Buscar el campo visible de la celda (excluir hidden y DELETE)
            var field = null;
            var candidates = Array.from(td.querySelectorAll("input, textarea, select"));
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                if (el.type === "hidden") continue;
                if (el.name && el.name.endsWith("-DELETE")) continue;
                if (el.name && el.name.endsWith("-id")) continue;
                field = el;
                break;
            }
            if (!field) return;

            fe.markFieldInvalid(field, msg, { container: td });
            errorList.remove();
        });

        if (table.querySelector(".budget-error-row")) {
            hasErrors = true;
        }

        if (hasErrors && budgetLinesWidget) {
            budgetLinesWidget.classList.add("js-client-invalid-block");
            showBatchFeedback("Revise las filas de presupuesto marcadas en rojo antes de guardar.", "danger");
        }
    }

    // ── Selector de contrato: redirige al cambiar ────────────────────
    function initContractSelector() {
        var form = document.getElementById("budget-batch-form");
        if (!form) return;
        batchUrlTemplate = form.dataset.batchUrlTemplate || "";

        var sel = document.getElementById("id_batch_contract");
        if (!sel) return;

        function handleChange(value) {
            if (!value || !batchUrlTemplate) return;
            window.location.href = batchUrlTemplate.replace("__CONTRACT_ID__", encodeURIComponent(value));
        }

        sel.addEventListener("change", function () { handleChange(sel.value); });

        function bindTomSelect() {
            if (sel.tomselect) {
                sel.tomselect.on("change", handleChange);
                return true;
            }
            return false;
        }

        if (!bindTomSelect()) {
            var observer = new MutationObserver(function () {
                if (bindTomSelect()) observer.disconnect();
            });
            observer.observe(sel.parentElement || document.body, { childList: true, subtree: true });
        }
    }

    // ── Formset: helpers ─────────────────────────────────────────────
    function getTotalForms() {
        return parseInt(TOTAL_FORMS_INPUT.value, 10);
    }

    function setTotalForms(n) {
        TOTAL_FORMS_INPUT.value = String(n);
    }

    function replacePrefix(html, index) {
        return html.replace(/__prefix__/g, String(index));
    }

    function enhanceSelects(row) {
        if (!window.TomSelect) return;
        row.querySelectorAll("select.select2, select.select2-sm").forEach(function (sel) {
            if (sel.tomselect) return;
            try {
                new TomSelect(sel, {
                    allowEmptyOption: true,
                    maxOptions: 400,
                    plugins: [],
                    dropdownParent: "body",
                });
            } catch (e) {}
        });
    }

    // ── Formset: agregar fila ────────────────────────────────────────
    function addRow() {
        var template = document.getElementById("budget-empty-form-template");
        if (!template) return;

        var idx = getTotalForms();
        var html = replacePrefix(template.innerHTML, idx);

        var tbody = document.getElementById("budget-batch-tbody");
        var tmp = document.createElement("tbody");
        tmp.innerHTML = html.trim();
        var newRow = tmp.firstElementChild;
        if (!newRow) return;

        newRow.dataset.rowIndex = String(idx);
        tbody.appendChild(newRow);
        setTotalForms(idx + 1);

        enhanceSelects(newRow);
        bindAmountInputsInRow(newRow);
        bindRowValidation(newRow);

        var btn = newRow.querySelector(".js-budget-delete-btn");
        if (btn) btn.addEventListener("click", function () { handleDelete(newRow); });
    }

    // ── Formset: eliminar fila ───────────────────────────────────────
    function handleDelete(row) {
        var deleteInput = row.querySelector('input[name$="-DELETE"]');
        if (deleteInput) {
            // Fila existente en BD: toggle DELETE
            deleteInput.checked = !deleteInput.checked;
            row.classList.toggle("line-row-deleted", deleteInput.checked);
            if (deleteInput.checked) {
                clearRowInvalidState(row);
            }
            var icon = row.querySelector(".js-budget-delete-btn i");
            var button = row.querySelector(".js-budget-delete-btn");
            if (icon) {
                icon.className = deleteInput.checked
                    ? "ace-icon fa fa-undo bigger-130"
                    : "ace-icon fa fa-trash-o bigger-130";
            }
            if (button) {
                button.title = deleteInput.checked ? "Restaurar detalle" : "Eliminar detalle";
            }
        } else {
            // Fila nueva: quitar del DOM y decrementar contador
            row.remove();
            setTotalForms(getTotalForms() - 1);
            // Re-numerar data-row-index para mantener coherencia
            document.querySelectorAll("#budget-batch-tbody .budget-line-row").forEach(function (r, i) {
                r.dataset.rowIndex = String(i);
            });
        }
    }

    // ── Init ─────────────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", function () {
        initContractSelector();

        TOTAL_FORMS_INPUT = document.querySelector('[name$="-TOTAL_FORMS"]');

        var form = document.getElementById("budget-batch-form");
        feedbackBox = document.getElementById("batch-form-feedback");
        budgetLinesWidget = document.getElementById("budget-lines-widget");

        if (TOTAL_FORMS_INPUT) {
            var addBtn = document.getElementById("add-budget-row-btn");
            if (addBtn) addBtn.addEventListener("click", addRow);

            // Handlers delete + formato de montos en filas existentes
            document.querySelectorAll("#budget-batch-tbody .budget-line-row").forEach(function (row) {
                var del = row.querySelector('input[name$="-DELETE"]');
                if (del && del.checked) row.classList.add("line-row-deleted");
                bindAmountInputsInRow(row);
                bindRowValidation(row);

                var btn = row.querySelector(".js-budget-delete-btn");
                if (btn) btn.addEventListener("click", function () { handleDelete(row); });
            });

            // Decorar errores del servidor con estilos coherentes
            decorateServerErrors();

            // Normalizar montos antes de enviar
            if (form) {
                form.addEventListener("submit", function (event) {
                    var invalidField = validateActiveRows();
                    if (invalidField) {
                        event.preventDefault();
                        showBatchFeedback("Complete los campos requeridos de las filas marcadas antes de guardar.", "danger");
                        focusInvalidField(invalidField);
                        return false;
                    }

                    normalizeAmountsForSubmit(form);
                });
            }
        }
    });
})();