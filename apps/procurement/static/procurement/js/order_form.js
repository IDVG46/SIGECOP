(function() {
        const form = document.getElementById('order-form');
        if (!form) return;

        const contractSelect = document.getElementById('id_contract');
        const supplierSelect = document.getElementById('id_supplier');
        const addLineButton = document.getElementById('add-line-button');
        const linesBody = document.getElementById('line-items-body');
        const lineTemplate = document.getElementById('line-row-template');
        const contractSummary = document.getElementById('contract-summary');
        const contractSummaryPlaceholder = document.getElementById('contract-summary-placeholder');
        const totalFormsInput = document.getElementById('id_lines-TOTAL_FORMS') || document.getElementById('id_purchaseorderline_set-TOTAL_FORMS');
        const urlTemplate = form.dataset.lineOptionsUrlTemplate || '';
        const supplierUrlTemplate = form.dataset.supplierOptionsUrlTemplate || '';
        const isEditMode = form.dataset.editMode === '1';
        const initialSummaryNode = document.getElementById('initial-contract-summary');
        let initialContractSummary = null;
        if (initialSummaryNode && initialSummaryNode.textContent) {
            try {
                initialContractSummary = JSON.parse(initialSummaryNode.textContent);
            } catch (error) {
                initialContractSummary = null;
            }
        }
        let lineOptions = { lots: [], items: [], subitems: [] };
        let supplierPayload = null;
        let currentCurrency = 'Gs.';
        const grandTotalElement = document.getElementById('order-grand-total');
        const feedbackBox = document.getElementById('form-feedback');
        const saveOrderButton = document.getElementById('save-order-button');
        const numberUtils = window.SIGECOPNumbers || {};

        function showFormFeedback(message, level) {
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

        function triggerSelect2Change(field) {
            if (!field || !window.jQuery) return;
            jQuery(field).trigger('change.select2');
        }

        function bindSelectChangeEvents(field, handler) {
            if (!field || typeof handler !== 'function') return;
            field.addEventListener('change', handler);
            if (window.jQuery) {
                jQuery(field).on('select2:select select2:clear', handler);
            }
        }

        function resetSelectValue(field) {
            if (!field) return;
            field.value = '';
            triggerSelect2Change(field);
        }

        function refreshRowAmounts(row, options) {
            const shouldValidate = !!(options && options.validate);
            updateRowHints(row);
            renderRowTotal(row);
            renderGrandTotal();
            if (shouldValidate) {
                validateRow(row);
            }
        }

        function refreshLineIndexes() {
            getRows().forEach(function(row, index) {
                const indexCell = row.querySelector('.js-line-index');
                if (indexCell) {
                    indexCell.textContent = String(index + 1);
                }
            });
        }

        function computeRowTotal(row) {
            const els = rowElements(row);
            if (!els || (els.del && els.del.checked)) return 0;
            const qty = parseQuantity(els.quantity?.value || '0');
            const price = parseNumber(els.unitPrice?.dataset?.normalizedValue || els.unitPrice?.value || '0');
            if (!Number.isFinite(qty) || !Number.isFinite(price) || qty <= 0 || price <= 0) return 0;
            return qty * price;
        }

        function renderRowTotal(row) {
            const els = rowElements(row);
            if (!els.lineTotal) return;
            const total = computeRowTotal(row);
            els.lineTotal.textContent = total > 0 ? formatCurrencyDisplay(total, currentCurrency, getMoneyPrecision() > 0) : '-';
        }

        function renderGrandTotal() {
            if (!grandTotalElement) return;
            const total = getRows().reduce(function(sum, row) {
                return sum + computeRowTotal(row);
            }, 0);
            grandTotalElement.textContent = total > 0 ? formatCurrencyDisplay(total, currentCurrency, getMoneyPrecision() > 0) : '-';
        }

        function refreshTotals() {
            getRows().forEach(renderRowTotal);
            renderGrandTotal();
            refreshLineIndexes();
        }

        const contractInfo = {
            id: document.getElementById('contract-info-id'),
            tender: document.getElementById('contract-info-tender'),
            tenderId: document.getElementById('contract-info-tender-id'),
            status: document.getElementById('contract-info-status'),
            amount: document.getElementById('contract-info-amount')
        };

        function initSelect2In(container) {
            if (!window.jQuery || !jQuery.fn || !jQuery.fn.select2) return;
            const $container = jQuery(container || form);
            $container.find('select.select2').each(function() {
                const $el = jQuery(this);
                if ($el.hasClass('select2-hidden-accessible')) {
                    $el.select2('destroy');
                }
                $el.select2({
                    width: '100%',
                    placeholder: 'Seleccione una opcion',
                    allowClear: true
                });
            });
        }

        function decorateFieldsWithErrors(container) {
            const root = container || form;
            root.querySelectorAll('.errorlist').forEach(function(errorList) {
                const control = errorList.previousElementSibling;
                if (!control || !control.matches('input, textarea, select')) return;
                if (control.type === 'hidden' || control.type === 'checkbox' || control.type === 'radio') return;
                if (control.parentElement && control.parentElement.classList.contains('field-error-icon-wrap')) return;

                const wrapper = document.createElement('span');
                wrapper.className = 'block input-icon input-icon-right field-error-icon-wrap';
                control.parentNode.insertBefore(wrapper, control);
                wrapper.appendChild(control);

                const icon = document.createElement('i');
                icon.className = 'ace-icon fa fa-times-circle error-icon';
                wrapper.appendChild(icon);
            });
        }

        function buildContractUrl(template, contractId, fallbackSuffix) {
            if (!contractId) return '';
            if (template && template.length > 0) {
                return template
                    .replace('__CONTRACT_ID__', encodeURIComponent(contractId))
                    .replace('%5F%5FCONTRACT_ID%5F%5F', encodeURIComponent(contractId))
                    .replace('%5f%5fCONTRACT_ID%5f%5f', encodeURIComponent(contractId));
            }

            const origin = window.location.origin;
            return `${origin}/api/contracts/${encodeURIComponent(contractId)}/${fallbackSuffix}/`;
        }

        function showLoadError(message) {
            if (!message) return;
            console.warn(message);
            showFormFeedback(message, 'warning');
        }

        function setOptions(select, options, selectedValue) {
            if (!select) return;
            const first = document.createElement('option');
            first.value = '';
            first.textContent = '---------';
            select.innerHTML = '';
            select.appendChild(first);

            options.forEach(function(opt) {
                const option = document.createElement('option');
                option.value = String(opt.id);
                option.textContent = opt.text;
                if (opt.item_definition_id !== undefined) {
                    option.dataset.itemDefinitionId = String(opt.item_definition_id);
                }
                if (opt.unit_price !== undefined) {
                    option.dataset.unitPrice = String(opt.unit_price);
                }
                if (opt.available_quantity !== undefined) {
                    option.dataset.availableQuantity = String(opt.available_quantity);
                }
                if (opt.enforce_quantity_limit !== undefined) {
                    option.dataset.enforceQuantityLimit = String(opt.enforce_quantity_limit);
                }
                if (opt.quantity_control_mode !== undefined) {
                    option.dataset.quantityControlMode = String(opt.quantity_control_mode);
                }
                if (opt.available_amount !== undefined) {
                    option.dataset.availableAmount = String(opt.available_amount);
                }
                select.appendChild(option);
            });

            if (selectedValue) {
                select.value = String(selectedValue);
            }

            if (window.jQuery) {
                jQuery(select).trigger('change.select2');
            }
        }

        function parseNumber(value) {
            if (numberUtils.parseNumber) {
                return numberUtils.parseNumber(value);
            }
            return Number(value);
        }

        function parseQuantity(value) {
            if (numberUtils.parseQuantity) {
                return numberUtils.parseQuantity(value);
            }
            return parseNumber(value);
        }

        function normalizeQuantityValue(value) {
            if (numberUtils.normalizeQuantityValue) {
                return numberUtils.normalizeQuantityValue(value, 0);
            }
            const parsed = parseQuantity(value);
            if (!Number.isFinite(parsed)) return '';
            return parsed.toFixed(0);
        }

        function coerceQuantityFromBackendPadding(input) {
            if (!input) return;
            const raw = String(input.value || '').trim().replace(/\s+/g, '');
            if (!/^\d+\.0+$/.test(raw)) return;
            const normalized = raw.replace(/\.0+$/, '');
            input.dataset.normalizedValue = normalized;
            input.value = normalized;
        }

        function formatQuantityDisplay(value) {
            if (numberUtils.formatQuantityDisplay) {
                return numberUtils.formatQuantityDisplay(value, { locale: 'es-PY', maxFractionDigits: 0 });
            }
            const parsed = parseQuantity(value);
            if (!Number.isFinite(parsed)) return '';

            const rounded = Math.round(parsed * 1000) / 1000;
            return new Intl.NumberFormat('es-PY', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
                useGrouping: true
            }).format(rounded);
        }

        function normalizeQuantityInputDisplay(input) {
            if (!input) return;
            const parsed = parseQuantity(input.value);
            const displayed = Number.isFinite(parsed) ? formatQuantityDisplay(parsed) : '';
            if (displayed !== '') {
                input.dataset.normalizedValue = String(parsed);
                input.value = displayed;
            }
        }

        function getMoneyPrecision() {
            if (numberUtils.getMoneyPrecision) {
                return numberUtils.getMoneyPrecision(currentCurrency);
            }
            return 2;
        }

        function formatAmountDisplay(value, withDecimals) {
            if (numberUtils.formatAmountDisplay) {
                return numberUtils.formatAmountDisplay(value, {
                    locale: 'es-PY',
                    withDecimals: !!withDecimals,
                    precision: withDecimals ? 2 : 0,
                });
            }
            const numberValue = parseNumber(value);
            if (!Number.isFinite(numberValue)) return '-';
            return String(numberValue);
        }

        function formatCurrencyDisplay(value, currency, withDecimals) {
            if (numberUtils.formatCurrencyDisplay) {
                return numberUtils.formatCurrencyDisplay(value, {
                    currency: currency,
                    locale: 'es-PY',
                    withDecimals: !!withDecimals,
                    precision: withDecimals ? 2 : 0,
                });
            }
            const amount = formatAmountDisplay(value, withDecimals);
            if (amount === '-') return '-';
            return `${currency || ''} ${amount}`.trim();
        }

        function normalizeMoneyValue(value) {
            if (numberUtils.normalizeMoneyValue) {
                return numberUtils.normalizeMoneyValue(value, {
                    currency: currentCurrency,
                    precision: getMoneyPrecision(),
                });
            }
            const parsed = parseNumber(value);
            if (!Number.isFinite(parsed)) return '';
            return parsed.toFixed(getMoneyPrecision());
        }

        function moneyFormatOptions() {
            return {
                currency: currentCurrency,
                locale: 'es-PY',
                precision: getMoneyPrecision(),
            };
        }

        function formatMoneyInputDisplay(input) {
            if (numberUtils.formatMoneyInputDisplay) {
                numberUtils.formatMoneyInputDisplay(input, moneyFormatOptions());
                return;
            }
        }

        function setMoneyInputValue(input, value) {
            if (numberUtils.setMoneyInputValue) {
                numberUtils.setMoneyInputValue(input, value, moneyFormatOptions());
                return;
            }
        }

        function getItemHasSubitemsForRow(row) {
            const els = rowElements(row);
            if (!els.lot || !els.lot.value || !els.item || !els.item.value) return false;

            const selectedItemOption = els.item.options[els.item.selectedIndex];
            const selectedItemDefinitionId = selectedItemOption ? selectedItemOption.dataset.itemDefinitionId : null;
            if (!selectedItemDefinitionId) return false;

            return lineOptions.subitems.some(function(sub) {
                return String(sub.lot_id) === String(els.lot.value) && String(sub.item_definition_id) === String(selectedItemDefinitionId);
            });
        }

        function renderContractInfo(contract) {
            if (!contract) {
                currentCurrency = 'Gs.';
                contractInfo.id.textContent = '-';
                contractInfo.tender.textContent = '-';
                contractInfo.tenderId.textContent = '-';
                contractInfo.status.textContent = '-';
                contractInfo.amount.textContent = '-';
                if (contractSummary) {
                    contractSummary.classList.add('is-empty');
                }
                if (contractSummaryPlaceholder) {
                    contractSummaryPlaceholder.style.display = '';
                }
                return;
            }

            contractInfo.id.textContent = contract.id || '-';
            contractInfo.tender.textContent = contract.tender || '-';
            contractInfo.tenderId.textContent = contract.tender_id || '-';
            contractInfo.status.textContent = contract.status || '-';
            currentCurrency = contract.currency || 'Gs.';
            const amountText = formatCurrencyDisplay(contract.amount || 0, contract.currency || '', false);
            contractInfo.amount.textContent = amountText || '-';
            if (contractSummary) {
                contractSummary.classList.remove('is-empty');
            }
            if (contractSummaryPlaceholder) {
                contractSummaryPlaceholder.style.display = 'none';
            }
        }

        function getRows() {
            return Array.from(form.querySelectorAll('tr.line-row'));
        }

        function rowElements(row) {
            return {
                lot: row.querySelector('select[name$="-lot"]'),
                item: row.querySelector('select[name$="-award_item"]'),
                subitem: row.querySelector('select[name$="-award_subitem"]'),
                quantity: row.querySelector('input[name$="-quantity"]'),
                unitPrice: row.querySelector('input[name$="-unit_price"]'),
                del: row.querySelector('input[name$="-DELETE"]'),
                lineTotal: row.querySelector('.js-line-total'),
                deleteBtn: row.querySelector('.js-delete-line-btn'),
                deleteLabel: row.querySelector('.js-delete-line-label')
            };
        }

        function updateDeleteRowState(row) {
            const els = rowElements(row);
            const isDeleted = !!(els.del && els.del.checked);
            row.classList.toggle('line-row-deleted', isDeleted);

            if (els.deleteLabel) {
                els.deleteLabel.textContent = 'Eliminar detalle';
            }

            if (els.deleteBtn) {
                const icon = els.deleteBtn.querySelector('i');
                if (icon) {
                    icon.className = 'ace-icon fa fa-trash-o bigger-130';
                }
                els.deleteBtn.title = isDeleted ? 'Detalle marcado para eliminar' : 'Eliminar detalle';
            }
        }

        function updateRowHints(row) {
            return row;
        }

        function setDefaultUnitPriceFromSelection(row) {
            const els = rowElements(row);
            if (!els.unitPrice) return;

            const selectedItemOpt = (els.item && els.item.value && els.item.selectedIndex >= 0) ? els.item.options[els.item.selectedIndex] : null;
            const selectedSubitemOpt = (els.subitem && els.subitem.value && els.subitem.selectedIndex >= 0) ? els.subitem.options[els.subitem.selectedIndex] : null;
            const itemHasSubitems = getItemHasSubitemsForRow(row);

            if (selectedSubitemOpt?.dataset?.unitPrice) {
                setMoneyInputValue(els.unitPrice, selectedSubitemOpt.dataset.unitPrice);
            } else if (selectedItemOpt?.dataset?.unitPrice && !itemHasSubitems) {
                setMoneyInputValue(els.unitPrice, selectedItemOpt.dataset.unitPrice);
            } else if (itemHasSubitems && !selectedSubitemOpt) {
                els.unitPrice.value = '';
                els.unitPrice.dataset.normalizedValue = '';
            }

            updateRowHints(row);
            renderRowTotal(row);
            renderGrandTotal();
        }

        function filterRowOptions(row) {
            const els = rowElements(row);
            const lotId = els.lot ? els.lot.value : '';
            const selectedItem = els.item ? els.item.value : '';
            const selectedSubitem = els.subitem ? els.subitem.value : '';
            const selectedItemOption = (els.item && els.item.selectedIndex >= 0) ? els.item.options[els.item.selectedIndex] : null;
            const selectedItemDefinitionId = selectedItemOption ? selectedItemOption.dataset.itemDefinitionId : null;
            const selectedSubitemOption = (els.subitem && els.subitem.selectedIndex >= 0) ? els.subitem.options[els.subitem.selectedIndex] : null;
            const selectedSubitemDefinitionId = selectedSubitemOption ? selectedSubitemOption.dataset.itemDefinitionId : null;

            const items = lineOptions.items.filter(function(it) {
                return !lotId || String(it.lot_id) === String(lotId);
            });
            const subitems = lineOptions.subitems.filter(function(it) {
                if (lotId && String(it.lot_id) !== String(lotId)) {
                    return false;
                }
                if (selectedItemDefinitionId && String(it.item_definition_id) !== String(selectedItemDefinitionId)) {
                    return false;
                }
                if (!selectedItemDefinitionId && selectedSubitemDefinitionId && String(it.item_definition_id) !== String(selectedSubitemDefinitionId)) {
                    return false;
                }
                return true;
            });

            setOptions(els.item, items, selectedItem);
            setOptions(els.subitem, subitems, selectedSubitem);
            updateRowSelectionFlow(row);
            setDefaultUnitPriceFromSelection(row);
            updateRowHints(row);
            renderRowTotal(row);
            renderGrandTotal();
        }

        function setFieldEnabled(field, enabled) {
            if (!field) return;
            field.disabled = !enabled;
            if (window.jQuery) {
                jQuery(field).prop('disabled', !enabled);
            }

            const wrapper = field.closest('td');
            if (wrapper) {
                if (enabled) {
                    wrapper.classList.remove('select-step-disabled');
                } else {
                    wrapper.classList.add('select-step-disabled');
                }
            }

            triggerSelect2Change(field);
        }

        function updateRowSelectionFlow(row) {
            const els = rowElements(row);
            const hasLot = !!(els.lot && els.lot.value);
            const hasSelectedSubitem = !!(els.subitem && els.subitem.value);

            const selectedItemOption = (els.item && els.item.selectedIndex >= 0) ? els.item.options[els.item.selectedIndex] : null;
            const selectedItemDefinitionId = selectedItemOption ? selectedItemOption.dataset.itemDefinitionId : null;
            const itemHasSubitems = !!(
                hasLot &&
                selectedItemDefinitionId &&
                lineOptions.subitems.some(function(sub) {
                    return String(sub.lot_id) === String(els.lot.value) && String(sub.item_definition_id) === String(selectedItemDefinitionId);
                })
            );

            setFieldEnabled(els.item, hasLot);
            setFieldEnabled(els.subitem, hasLot && (itemHasSubitems || hasSelectedSubitem));

            if (!hasLot) {
                if (els.item) {
                    resetSelectValue(els.item);
                }
                if (els.subitem) {
                    resetSelectValue(els.subitem);
                }
                if (els.unitPrice) {
                    els.unitPrice.value = '';
                    els.unitPrice.dataset.normalizedValue = '';
                }
            } else if (!itemHasSubitems && !hasSelectedSubitem) {
                if (els.subitem) {
                    resetSelectValue(els.subitem);
                }
            }

            updateRowHints(row);
        }

        function clearInvalidState(row) {
            row.classList.remove('danger');
            clearFieldErrors(row);
            const next = row.nextElementSibling;
            if (next && next.classList.contains('js-line-error-row')) {
                next.remove();
            }
        }

        function clearFieldErrors(row) {
            row.querySelectorAll('.js-client-invalid').forEach(function(field) {
                field.classList.remove('js-client-invalid');
            });
            row.querySelectorAll('.js-inline-field-error').forEach(function(errorNode) {
                errorNode.remove();
            });
        }

        function markFieldInvalid(field, message) {
            if (!field) return;
            field.classList.add('js-client-invalid');
            if (!message) return;

            const cell = field.closest('td');
            if (!cell) return;

            const errorNode = document.createElement('small');
            errorNode.className = 'text-danger js-inline-field-error';
            errorNode.textContent = message;
            cell.appendChild(errorNode);
        }

        function markInvalidFields(row, els, fields, message) {
            clearInvalidState(row);
            row.classList.add('danger');

            const normalizedFields = Array.isArray(fields) ? fields : [fields];
            normalizedFields.forEach(function(fieldKey, index) {
                const field = els[fieldKey];
                markFieldInvalid(field, index === 0 ? message : '');
            });
        }

        function markInvalid(row, message) {
            row.classList.add('danger');
            clearInvalidState(row);
            const td = document.createElement('td');
            const table = row.closest('table');
            td.colSpan = table ? table.querySelectorAll('thead th').length : 8;
            td.className = 'text-danger js-line-error';
            td.textContent = message;
            const tr = document.createElement('tr');
            tr.className = 'js-line-error-row';
            tr.appendChild(td);
            row.insertAdjacentElement('afterend', tr);
        }

        function validateRow(row, options) {
            const showErrors = !!(options && options.showErrors);
            const els = rowElements(row);

            function fail(message, fields) {
                if (showErrors) {
                    if (fields) {
                        markInvalidFields(row, els, fields, message);
                    } else {
                        markInvalid(row, message);
                    }
                } else {
                    clearInvalidState(row);
                }
                return false;
            }

            if (els.del && els.del.checked) {
                clearInvalidState(row);
                return true;
            }

            const hasAny = [els.lot?.value, els.item?.value, els.subitem?.value, els.quantity?.value, els.unitPrice?.value].some(Boolean);
            if (!hasAny) {
                clearInvalidState(row);
                return true;
            }

            const qty = parseQuantity(els.quantity?.value || '0');
            const price = parseNumber(els.unitPrice?.dataset?.normalizedValue || els.unitPrice?.value || '0');
            const hasItem = !!(els.item && els.item.value);
            const hasSubitem = !!(els.subitem && els.subitem.value);

            if (!els.lot?.value) return fail('Debe seleccionar lote.', 'lot');
            if (hasItem === hasSubitem) return fail('Debe seleccionar solo item o solo subitem.', ['item', 'subitem']);
            if (!(qty > 0)) return fail('La cantidad debe ser mayor a cero.', 'quantity');
            if (!(price > 0)) return fail('El precio unitario debe ser mayor a cero.', 'unitPrice');

            if (hasItem) {
                const opt = els.item.options[els.item.selectedIndex];
                const enforceQuantityLimit = String(opt?.dataset?.enforceQuantityLimit || '').toLowerCase() === 'true';
                if (enforceQuantityLimit) {
                    const max = parseFloat(opt?.dataset?.availableQuantity || '0');
                    if (max > 0 && qty > max) return fail(`La cantidad excede el saldo disponible (${max}).`, 'quantity');
                }
            }

            if (hasSubitem) {
                const opt = els.subitem.options[els.subitem.selectedIndex];
                const enforceQuantityLimit = String(opt?.dataset?.enforceQuantityLimit || '').toLowerCase() === 'true';
                if (enforceQuantityLimit) {
                    const max = parseFloat(opt?.dataset?.availableQuantity || '0');
                    if (max > 0 && qty > max) return fail(`La cantidad excede el saldo disponible (${max}).`, 'quantity');
                }
            }

            clearInvalidState(row);
            return true;
        }

        function validateAllRows(options) {
            return getRows().every(function(row) {
                return validateRow(row, options);
            });
        }

        function hasAtLeastOneDetailLine() {
            return getRows().some(function(row) {
                const els = rowElements(row);
                if (!els || (els.del && els.del.checked)) return false;

                const values = [
                    els.lot?.value,
                    els.item?.value,
                    els.subitem?.value,
                    els.quantity?.value,
                    els.unitPrice?.value,
                ];

                return values.some(function(value) {
                    return String(value || '').trim() !== '';
                });
            });
        }

        function firstInvalidRow() {
            return getRows().find(function(row) {
                return row.classList.contains('danger');
            }) || null;
        }

        async function loadContractOptions(contractId) {
            if (!contractId) {
                lineOptions = { lots: [], items: [], subitems: [] };
                getRows().forEach(function(row) {
                    const els = rowElements(row);
                    setOptions(els.lot, []);
                    setOptions(els.item, []);
                    setOptions(els.subitem, []);
                    initSelect2In(row);
                });
                refreshTotals();
                return;
            }

            const url = buildContractUrl(urlTemplate, contractId, 'line-options');
            try {
                const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!response.ok) {
                    showLoadError(`No se pudo cargar lotes/items/subitems del contrato (${response.status}).`);
                    return;
                }

                lineOptions = await response.json();
                if (lineOptions.contract) {
                    renderContractInfo(lineOptions.contract);
                }
            } catch (error) {
                showLoadError('Error de conexion al cargar opciones del contrato.');
                return;
            }

            getRows().forEach(function(row) {
                const els = rowElements(row);
                const selectedLot = els.lot ? els.lot.value : '';
                setOptions(els.lot, lineOptions.lots, selectedLot);
                filterRowOptions(row);
                updateRowSelectionFlow(row);
                initSelect2In(row);
            });
            refreshTotals();
        }

        async function loadContractSuppliers(contractId) {
            if (!supplierSelect) return;
            if (!contractId) {
                supplierPayload = null;
                setOptions(supplierSelect, []);
                renderContractInfo(null);
                return;
            }

            const url = buildContractUrl(supplierUrlTemplate, contractId, 'suppliers');
            let payload;
            try {
                const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!response.ok) {
                    showLoadError(`No se pudo cargar proveedores del contrato (${response.status}).`);
                    return;
                }

                payload = await response.json();
            } catch (error) {
                showLoadError('Error de conexion al cargar proveedores del contrato.');
                return;
            }

            supplierPayload = payload;
            const selected = supplierSelect.value;
            setOptions(supplierSelect, payload.suppliers || [], selected);

            if ((!supplierSelect.value || supplierSelect.value === '') && payload.preferred_supplier_id) {
                supplierSelect.value = String(payload.preferred_supplier_id);
                if (window.jQuery) {
                    jQuery(supplierSelect).trigger('change.select2');
                }
            }

            renderContractInfo(payload.contract || null);
            initSelect2In(form);
            refreshTotals();
        }

        async function handleContractChange() {
            const contractId = contractSelect ? contractSelect.value : '';
            showFormFeedback('', 'danger');
            if (saveOrderButton) {
                saveOrderButton.disabled = true;
            }
            await loadContractOptions(contractId);
            await loadContractSuppliers(contractId);
            if (saveOrderButton) {
                saveOrderButton.disabled = false;
            }
        }

        function bindRowEventsForRow(row) {
            const els = rowElements(row);
            if (!els.lot || row.dataset.bound === '1') return;
            row.dataset.bound = '1';

            bindSelectChangeEvents(els.lot, function() {
                filterRowOptions(row);
                updateRowSelectionFlow(row);
                validateRow(row);
            });

            if (els.item) {
                bindSelectChangeEvents(els.item, function() {
                    if (els.item.value && els.subitem) {
                        resetSelectValue(els.subitem);
                    }
                    filterRowOptions(row);
                    updateRowSelectionFlow(row);
                    setDefaultUnitPriceFromSelection(row);
                    validateRow(row);
                });
            }

            if (els.subitem) {
                bindSelectChangeEvents(els.subitem, function() {
                    if (els.subitem.value && els.item) {
                        resetSelectValue(els.item);
                    }
                    filterRowOptions(row);
                    updateRowSelectionFlow(row);
                    setDefaultUnitPriceFromSelection(row);
                    validateRow(row);
                });
            }

            if (els.quantity) {
                coerceQuantityFromBackendPadding(els.quantity);
                if (numberUtils.bindInputFormatting) {
                    numberUtils.bindInputFormatting(els.quantity, {
                        kind: 'quantity',
                        locale: 'es-PY',
                        precision: 0,
                    });
                } else {
                    normalizeQuantityInputDisplay(els.quantity);
                }

                els.quantity.addEventListener('input', function() {
                    validateRow(row);
                    renderGrandTotal();
                });

                els.quantity.addEventListener('blur', function() {
                    validateRow(row);
                    renderGrandTotal();
                });
            }
            if (els.unitPrice) {
                if (numberUtils.bindInputFormatting) {
                    numberUtils.bindInputFormatting(els.unitPrice, {
                        kind: 'money',
                        locale: 'es-PY',
                        currency: currentCurrency,
                        precision: getMoneyPrecision(),
                    });
                } else {
                    formatMoneyInputDisplay(els.unitPrice);
                }

                els.unitPrice.addEventListener('input', function() {
                    refreshRowAmounts(row, { validate: true });
                });

                els.unitPrice.addEventListener('blur', function() {
                    refreshRowAmounts(row);
                });
            }
            if (els.del) {
                els.del.addEventListener('change', function() {
                    validateRow(row);
                    updateDeleteRowState(row);
                    refreshRowAmounts(row);
                });
            }

            if (els.deleteBtn && els.del) {
                els.deleteBtn.addEventListener('click', function() {
                    els.del.checked = !els.del.checked;
                    els.del.dispatchEvent(new Event('change', { bubbles: true }));
                });
            }

            updateRowHints(row);
            updateDeleteRowState(row);
            renderRowTotal(row);
        }

        function addLineRow() {
            if (!lineTemplate || !linesBody || !totalFormsInput) return;
            const total = parseInt(totalFormsInput.value, 10) || 0;
            const html = lineTemplate.innerHTML.replace(/__prefix__/g, String(total));
            linesBody.insertAdjacentHTML('beforeend', html);
            totalFormsInput.value = String(total + 1);

            const rows = getRows();
            const newRow = rows[rows.length - 1];
            if (!newRow) return;

            const els = rowElements(newRow);
            initSelect2In(newRow);
            setOptions(els.lot, lineOptions.lots);
            filterRowOptions(newRow);
            updateRowSelectionFlow(newRow);
            bindRowEventsForRow(newRow);
            refreshTotals();
        }

        function bindRowEvents() {
            getRows().forEach(function(row) {
                bindRowEventsForRow(row);
                updateRowSelectionFlow(row);
            });
            refreshTotals();
        }

        form.addEventListener('submit', function(event) {
            if (!hasAtLeastOneDetailLine()) {
                event.preventDefault();
                showFormFeedback('Debe agregar al menos una linea de detalle para guardar la orden.', 'danger');
                const firstRow = getRows()[0];
                if (firstRow) {
                    firstRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                return;
            }

            if (!validateAllRows({ showErrors: true })) {
                event.preventDefault();
                showFormFeedback('Hay lineas con errores. Revise lote/item/subitem, cantidad y precio.', 'danger');
                const invalidRow = firstInvalidRow();
                if (invalidRow) {
                    invalidRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                return;
            }

            showFormFeedback('', 'danger');

            getRows().forEach(function(row) {
                const els = rowElements(row);
                if (els.quantity) {
                    if (numberUtils.normalizeInputForSubmit) {
                        numberUtils.normalizeInputForSubmit(els.quantity, {
                            kind: 'quantity',
                            precision: 0,
                        });
                    } else {
                        const normalizedQty = normalizeQuantityValue(els.quantity.value);
                        if (normalizedQty) {
                            els.quantity.value = normalizedQty;
                        }
                    }
                }
                if (els.unitPrice) {
                    if (numberUtils.normalizeInputForSubmit) {
                        numberUtils.normalizeInputForSubmit(els.unitPrice, {
                            kind: 'money',
                            currency: currentCurrency,
                            precision: getMoneyPrecision(),
                        });
                    } else {
                        const normalized = normalizeMoneyValue(els.unitPrice.dataset.normalizedValue || els.unitPrice.value);
                        if (normalized) {
                            els.unitPrice.value = normalized;
                        }
                    }
                }
            });
        });

        if (contractSelect) {
            contractSelect.addEventListener('change', handleContractChange);
            if (window.jQuery) {
                jQuery(contractSelect).on('select2:select select2:clear', handleContractChange);
            }
        }

        if (addLineButton) {
            addLineButton.addEventListener('click', addLineRow);
        }

        decorateFieldsWithErrors(form);
        initSelect2In(form);
        bindRowEvents();

        if (contractSelect && contractSelect.value && isEditMode) {
            renderContractInfo(initialContractSummary || null);
            refreshTotals();
        }

        if (contractSelect) {
            handleContractChange();
        }
    })();
