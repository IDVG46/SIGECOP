(function() {
        const form = document.getElementById('order-form');
        if (!form) return;
    form.setAttribute('novalidate', 'novalidate');

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
        const applicationScopeCreateUrl = form.dataset.applicationScopeCreateUrl || '';
        const scopeModal = document.getElementById('application-scope-modal');
        const scopeNameInput = document.getElementById('application-scope-name-input');
        const scopeTypeInput = document.getElementById('application-scope-type-input');
        const scopeSaveBtn = document.getElementById('application-scope-modal-save-btn');
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
        let contractChangeRequestToken = 0;
        let lastHandledContractId = null;
        let currentCurrency = 'Gs.';
        const grandTotalElement = document.getElementById('order-grand-total');
        const feedbackBox = document.getElementById('form-feedback');
        const saveOrderButton = document.getElementById('save-order-button');
        const numberUtils = window.SIGECOPNumbers || {};
        const formErrors = window.SIGECOPFormErrors || {};
        const detailPlaceholders = {
            lot: 'Buscar lote...',
            item: 'Buscar item...',
            subitem: 'Buscar subitem...'
        };
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

        function openScopeModal() {
            if (!scopeModal) {
                showFormFeedback('No se encontró el modal para crear ámbito.', 'warning');
                return;
            }

            if (scopeNameInput) {
                scopeNameInput.value = '';
            }
            if (scopeTypeInput && !scopeTypeInput.value) {
                scopeTypeInput.value = 'sector';
            }

            if (window.jQuery && window.jQuery.fn && window.jQuery.fn.modal) {
                window.jQuery(scopeModal).modal('show');
                window.setTimeout(function() {
                    if (scopeNameInput) {
                        scopeNameInput.focus();
                    }
                }, 220);
                return;
            }

            scopeModal.style.display = 'block';
            scopeModal.classList.add('in');
            if (scopeNameInput) {
                scopeNameInput.focus();
            }
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

            return document.getElementById('id_application_scope');
        }

        async function createApplicationScopeQuick(targetField) {
            if (!applicationScopeCreateUrl) {
                showFormFeedback('No se configuró el endpoint para crear ámbitos.', 'warning');
                return;
            }

            if (!targetField) {
                showFormFeedback('No se encontró el campo de ámbito para asignar el valor.', 'warning');
                return;
            }

            const name = scopeNameInput ? String(scopeNameInput.value || '').trim() : '';
            if (!name) return;
            const scopeType = scopeTypeInput ? String(scopeTypeInput.value || 'sector').trim() : 'sector';

            if (scopeSaveBtn) {
                scopeSaveBtn.disabled = true;
            }

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
                if (scopeSaveBtn) {
                    scopeSaveBtn.disabled = false;
                }
                return;
            }

            if (!response.ok) {
                showFormFeedback('No se pudo crear el ámbito.', 'danger');
                if (scopeSaveBtn) {
                    scopeSaveBtn.disabled = false;
                }
                return;
            }

            const payload = await response.json();
            const scope = payload.scope;
            if (!scope || !scope.id) {
                showFormFeedback('Respuesta inválida al crear ámbito.', 'danger');
                if (scopeSaveBtn) {
                    scopeSaveBtn.disabled = false;
                }
                return;
            }

            const value = String(scope.id);
            if (targetField.tomselect) {
                if (!targetField.tomselect.options[value]) {
                    targetField.tomselect.addOption({ value: value, text: scope.name });
                }
                targetField.tomselect.setValue(value, true);
            } else {
                let option = Array.from(targetField.options || []).find(function(opt) {
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
            showFormFeedback('Ámbito agregado correctamente.', 'success');
            closeScopeModal();
            if (scopeSaveBtn) {
                scopeSaveBtn.disabled = false;
            }
            pendingScopeTargetField = null;
        }

        function triggerSelect2Change(field) {
            if (!field) return;
            // NO disparar change aquí - causaría cascada infinita de eventos
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

        function applyDetailPlaceholders(row) {
            const els = rowElements(row);
            setSelectPlaceholder(els.lot, detailPlaceholders.lot);
            setSelectPlaceholder(els.item, detailPlaceholders.item);
            setSelectPlaceholder(els.subitem, detailPlaceholders.subitem);
        }

        function bindSelectChangeEvents(field, handler) {
            if (!field || typeof handler !== 'function') return;
            field.addEventListener('change', handler);
            
            // También registrar listener para Tom Select si está disponible
            if (field.tomselect && typeof field.tomselect.on === 'function') {
                field.tomselect.off('change');
                field.tomselect.on('change', handler);
            }
        }

        function resetSelectValue(field) {
            if (!field) return;
            if (field.tomselect) {
                field.tomselect.clear(true);
            } else {
                field.value = '';
            }
            // No disparar change: el reset es interno, no debe cascadear
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
            if (window.SIGECOPUI && window.SIGECOPUI.enhanceSelects) {
                window.SIGECOPUI.enhanceSelects(container || form);
            }
        }

        function disableNativeRequiredOnEnhancedSelects(container) {
            const root = container || form;
            root.querySelectorAll('select.select2[required]').forEach(function(select) {
                select.dataset.requiredManaged = '1';
                select.removeAttribute('required');
            });
        }

        function clearSingleFieldError(field) {
            if (!field) return;
            if (formErrors.clearFieldError) {
                formErrors.clearFieldError(field);
            }
        }

        function validateHeaderRequiredFields() {
            const requiredFields = [
                { key: 'order_number', message: 'Debe completar N° de orden.' },
                { key: 'contract', message: 'Debe seleccionar un contrato.' },
                { key: 'supplier', message: 'Debe seleccionar un proveedor.' },
                { key: 'issue_date', message: 'Debe completar la fecha de emisión.' },
                { key: 'expense_object', message: 'Debe seleccionar un objeto de gasto.' },
            ];

            requiredFields.forEach(function(entry) {
                const field = document.getElementById('id_' + entry.key);
                if (!field) return;
                clearSingleFieldError(field);
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

                markFieldInvalid(field, entry.message);
                return field;
            }

            return null;
        }

        function decorateFieldsWithErrors(container) {
            if (formErrors.decorateFieldsWithErrors) {
                formErrors.decorateFieldsWithErrors(container || form);
            }
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

        function setSupplierReadonlyState(isReadonly) {
            if (!supplierSelect) return;

            if (supplierSelect.tomselect) {
                if (isReadonly) {
                    supplierSelect.tomselect.lock();
                } else {
                    supplierSelect.tomselect.unlock();
                }
            }

            if (isReadonly) {
                supplierSelect.dataset.readonly = '1';
            } else {
                delete supplierSelect.dataset.readonly;
            }
        }

        function setOptions(select, options, selectedValue) {
            if (!select) return;

            const normalizedSelected = selectedValue ? String(selectedValue) : '';
            const normalizedOptions = (options || []).map(function(opt) {
                const optionValue = String(opt.id);
                const optionData = {
                    value: optionValue,
                    text: opt.text,
                };

                if (opt.item_definition_id !== undefined) {
                    optionData.itemDefinitionId = String(opt.item_definition_id);
                }
                if (opt.unit_price !== undefined) {
                    optionData.unitPrice = String(opt.unit_price);
                }
                if (opt.available_quantity !== undefined) {
                    optionData.availableQuantity = String(opt.available_quantity);
                }
                if (opt.enforce_quantity_limit !== undefined) {
                    optionData.enforceQuantityLimit = String(opt.enforce_quantity_limit);
                }
                if (opt.quantity_control_mode !== undefined) {
                    optionData.quantityControlMode = String(opt.quantity_control_mode);
                }
                if (opt.available_amount !== undefined) {
                    optionData.availableAmount = String(opt.available_amount);
                }

                return optionData;
            });

            if (select.tomselect) {
                const ts = select.tomselect;
                ts.clearOptions();
                ts.addOption({ value: '', text: '' });
                normalizedOptions.forEach(function(opt) {
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

            const first = document.createElement('option');
            first.value = '';
            first.textContent = '';
            select.innerHTML = '';
            select.appendChild(first);

            normalizedOptions.forEach(function(opt) {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.text;

                if (opt.itemDefinitionId !== undefined) {
                    option.dataset.itemDefinitionId = opt.itemDefinitionId;
                }
                if (opt.unitPrice !== undefined) {
                    option.dataset.unitPrice = opt.unitPrice;
                }
                if (opt.availableQuantity !== undefined) {
                    option.dataset.availableQuantity = opt.availableQuantity;
                }
                if (opt.enforceQuantityLimit !== undefined) {
                    option.dataset.enforceQuantityLimit = opt.enforceQuantityLimit;
                }
                if (opt.quantityControlMode !== undefined) {
                    option.dataset.quantityControlMode = opt.quantityControlMode;
                }
                if (opt.availableAmount !== undefined) {
                    option.dataset.availableAmount = opt.availableAmount;
                }

                select.appendChild(option);
            });

            select.value = normalizedSelected;
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

        function getSelectedOptionData(select) {
            if (!select || !select.value) return null;

            if (select.tomselect) {
                return select.tomselect.options[select.value] || null;
            }

            if (select.selectedIndex >= 0 && select.options) {
                return select.options[select.selectedIndex].dataset || null;
            }

            return null;
        }

        function getItemHasSubitemsForRow(row) {
            const els = rowElements(row);
            if (!els.lot || !els.lot.value || !els.item || !els.item.value) return false;

            const selectedItemData = getSelectedOptionData(els.item);
            const selectedItemDefinitionId = selectedItemData ? selectedItemData.itemDefinitionId : null;
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
            if (window.SIGECOPLineDelete && typeof window.SIGECOPLineDelete.applyState === 'function') {
                window.SIGECOPLineDelete.applyState(row, {
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

        function updateRowHints(row) {
            return row;
        }

        function setDefaultUnitPriceFromSelection(row) {
            const els = rowElements(row);
            if (!els.unitPrice) return;

            const selectedItemData = getSelectedOptionData(els.item);
            const selectedSubitemData = getSelectedOptionData(els.subitem);
            const itemHasSubitems = getItemHasSubitemsForRow(row);

            if (selectedSubitemData?.unitPrice) {
                setMoneyInputValue(els.unitPrice, selectedSubitemData.unitPrice);
            } else if (selectedItemData?.unitPrice && !itemHasSubitems) {
                setMoneyInputValue(els.unitPrice, selectedItemData.unitPrice);
            } else if (itemHasSubitems && !selectedSubitemData) {
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
            const selectedItemData = getSelectedOptionData(els.item);
            const selectedItemDefinitionId = selectedItemData ? selectedItemData.itemDefinitionId : null;
            const selectedSubitemData = getSelectedOptionData(els.subitem);
            const selectedSubitemDefinitionId = selectedSubitemData ? selectedSubitemData.itemDefinitionId : null;

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
            const isDisabled = !enabled;
            if (field.disabled === isDisabled) {
                return;
            }

            field.disabled = isDisabled;
            if (window.jQuery) {
                jQuery(field).prop('disabled', isDisabled);
            }

            if (field.tomselect) {
                if (isDisabled) {
                    field.tomselect.disable();
                } else {
                    field.tomselect.enable();
                }
            }

            const wrapper = field.closest('td');
            if (wrapper) {
                if (enabled) {
                    wrapper.classList.remove('select-step-disabled');
                } else {
                    wrapper.classList.add('select-step-disabled');
                }
            }

        }

        function updateRowSelectionFlow(row) {
            const els = rowElements(row);
            const hasLot = !!(els.lot && els.lot.value);
            const hasSelectedSubitem = !!(els.subitem && els.subitem.value);

            const selectedItemData = getSelectedOptionData(els.item);
            const selectedItemDefinitionId = selectedItemData ? selectedItemData.itemDefinitionId : null;
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
            if (formErrors.clearInvalidInContainer) {
                formErrors.clearInvalidInContainer(row);
            }
        }

        function markFieldInvalid(field, message) {
            if (formErrors.markFieldInvalid) {
                formErrors.markFieldInvalid(field, message);
            }
        }

        function markInvalidFields(row, els, fields, message) {
            clearInvalidState(row);
            row.classList.add('danger');

            if (fields && !Array.isArray(fields) && typeof fields === 'object') {
                Object.keys(fields).forEach(function(fieldKey) {
                    const field = els[fieldKey];
                    markFieldInvalid(field, fields[fieldKey] || '');
                });
                return;
            }

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
            const requireCompleted = !!(options && options.requireCompleted);
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
                if (requireCompleted) {
                    return fail('Debe seleccionar lote.', 'lot');
                }
                clearInvalidState(row);
                return true;
            }

            const qty = parseQuantity(els.quantity?.value || '0');
            const price = parseNumber(els.unitPrice?.dataset?.normalizedValue || els.unitPrice?.value || '0');
            const hasItem = !!(els.item && els.item.value);
            const hasSubitem = !!(els.subitem && els.subitem.value);
            const itemRequiresSubitem = hasItem && getItemHasSubitemsForRow(row);

            if (!els.lot?.value) return fail('Debe seleccionar lote.', 'lot');
            if (!hasItem) {
                return fail('Debe seleccionar un item.', 'item');
            }
            if (itemRequiresSubitem && !hasSubitem) return fail('Debe seleccionar un subitem.', 'subitem');
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

        function hasActiveDetailRows() {
            return getRows().some(function(row) {
                const els = rowElements(row);
                return !!(els && !(els.del && els.del.checked));
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
                setSupplierReadonlyState(false);
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
            const preferredSupplierId = payload.preferred_supplier_id ? String(payload.preferred_supplier_id) : '';
            const selected = preferredSupplierId || supplierSelect.value;
            setOptions(supplierSelect, payload.suppliers || [], selected);

            if (preferredSupplierId) {
                if (supplierSelect.tomselect) {
                    supplierSelect.tomselect.setValue(preferredSupplierId, true);
                } else {
                    supplierSelect.value = preferredSupplierId;
                }
            }

            setSupplierReadonlyState(!!preferredSupplierId);

            renderContractInfo(payload.contract || null);
            refreshTotals();
        }

        async function handleContractChange(options) {
            const force = !!(options && options.force);
            const contractId = contractSelect ? String(contractSelect.value || '') : '';
            if (!force && contractId === lastHandledContractId) {
                return;
            }

            lastHandledContractId = contractId;
            const requestToken = ++contractChangeRequestToken;
            showFormFeedback('', 'danger');
            if (saveOrderButton) {
                saveOrderButton.disabled = true;
            }
            await loadContractOptions(contractId);
            if (requestToken !== contractChangeRequestToken) {
                return;
            }
            await loadContractSuppliers(contractId);
            if (requestToken !== contractChangeRequestToken) {
                return;
            }
            if (saveOrderButton) {
                saveOrderButton.disabled = false;
            }
        }

        function bindContractChangeSources() {
            if (!contractSelect) {
                return;
            }

            contractSelect.addEventListener('change', function() {
                handleContractChange();
            });

            if (contractSelect.tomselect) {
                contractSelect.tomselect.off('change');
                contractSelect.tomselect.on('change', function() {
                    handleContractChange();
                });
            }
        }

        function bindRowEventsForRow(row) {
            const els = rowElements(row);
            applyDetailPlaceholders(row);
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
                    if (window.SIGECOPLineDelete && typeof window.SIGECOPLineDelete.toggleRow === 'function') {
                        window.SIGECOPLineDelete.toggleRow(row, {
                            labels: {
                                deleteText: 'Eliminar detalle',
                                restoreText: 'Restaurar detalle',
                            },
                        });
                        validateRow(row);
                        refreshRowAmounts(row);
                    } else {
                        els.del.checked = !els.del.checked;
                        els.del.dispatchEvent(new Event('change', { bubbles: true }));
                    }
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
            applyDetailPlaceholders(newRow);
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
            const invalidHeaderField = validateHeaderRequiredFields();
            if (invalidHeaderField) {
                event.preventDefault();
                showFormFeedback('Complete los campos obligatorios de la cabecera.', 'danger');
                const wrapper = invalidHeaderField.closest('.row') || invalidHeaderField;
                if (wrapper && wrapper.scrollIntoView) {
                    wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                if (!invalidHeaderField.matches('select') && typeof invalidHeaderField.focus === 'function') {
                    invalidHeaderField.focus();
                }
                return;
            }

            if (!hasActiveDetailRows()) {
                event.preventDefault();
                showFormFeedback('Debe agregar al menos una linea de detalle para guardar la orden.', 'danger');
                const firstRow = getRows()[0];
                if (firstRow) {
                    firstRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                return;
            }

            if (!validateAllRows({ showErrors: true, requireCompleted: true })) {
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

        bindContractChangeSources();

        if (addLineButton) {
            addLineButton.addEventListener('click', addLineRow);
        }

        form.addEventListener('click', function(event) {
            const button = event.target.closest('.js-add-scope-btn');
            if (!button) return;
            event.preventDefault();
            pendingScopeTargetField = resolveScopeTargetField(button);
            openScopeModal();
        });

        if (scopeSaveBtn) {
            scopeSaveBtn.addEventListener('click', function() {
                if (!pendingScopeTargetField) {
                    showFormFeedback('No se encontró el campo destino para el ámbito.', 'warning');
                    return;
                }
                createApplicationScopeQuick(pendingScopeTargetField);
            });
        }

        if (scopeNameInput) {
            scopeNameInput.addEventListener('keydown', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    if (scopeSaveBtn) {
                        scopeSaveBtn.click();
                    }
                }
            });
        }

        decorateFieldsWithErrors(form);
        bindRowEvents();
        initSelect2In(form);
        disableNativeRequiredOnEnhancedSelects(form);

        if (contractSelect && contractSelect.value && isEditMode) {
            renderContractInfo(initialContractSummary || null);
            refreshTotals();
        }

        if (contractSelect) {
            handleContractChange({ force: true });
        }
    })();
