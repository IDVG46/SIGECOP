(function(window) {
    'use strict';

    function parseNumber(value) {
        if (value === null || value === undefined) return NaN;
        if (typeof value === 'number') return value;

        var raw = String(value).trim().replace(/\s+/g, '');
        if (!raw) return NaN;

        var hasComma = raw.indexOf(',') !== -1;
        var hasDot = raw.indexOf('.') !== -1;
        var normalized = raw;

        if (hasComma && hasDot) {
            var lastComma = raw.lastIndexOf(',');
            var lastDot = raw.lastIndexOf('.');
            var decimalSep = lastComma > lastDot ? ',' : '.';
            var thousandSep = decimalSep === ',' ? '.' : ',';
            normalized = raw.split(thousandSep).join('');
            normalized = normalized.replace(decimalSep, '.');
        } else if (hasDot) {
            if (/^\d{1,3}(\.\d{3})+$/.test(raw)) {
                normalized = raw.replace(/\./g, '');
            }
        } else if (hasComma) {
            if (/^\d{1,3}(,\d{3})+$/.test(raw)) {
                normalized = raw.replace(/,/g, '');
            } else {
                normalized = raw.replace(',', '.');
            }
        }

        return Number(normalized);
    }

    function parseQuantity(value) {
        if (value === null || value === undefined) return NaN;
        if (typeof value === 'number') return value;

        var raw = String(value).trim().replace(/\s+/g, '');
        if (!raw) return NaN;

        var hasComma = raw.indexOf(',') !== -1;
        var hasDot = raw.indexOf('.') !== -1;
        var normalized = raw;

        if (hasComma && hasDot) {
            var lastComma = raw.lastIndexOf(',');
            var lastDot = raw.lastIndexOf('.');
            var decimalSep = lastComma > lastDot ? ',' : '.';
            var otherSep = decimalSep === ',' ? '.' : ',';
            normalized = raw.split(otherSep).join('');
            normalized = normalized.replace(decimalSep, '.');
        } else if (hasDot) {
            if (/^\d{1,3}(\.\d{3})+$/.test(raw)) {
                normalized = raw.replace(/\./g, '');
            } else {
                var dotParts = raw.split('.');
                var intPart = dotParts[0] || '';
                var fracPart = dotParts.length === 2 ? (dotParts[1] || '') : '';

                // While typing large integers, the grouped value can look like 1.2345.
                // Treat that as thousands progression, not decimal.
                if (
                    dotParts.length === 2 &&
                    /^\d+$/.test(intPart) &&
                    /^\d+$/.test(fracPart) &&
                    intPart.length <= 3 &&
                    fracPart.length > 3
                ) {
                    normalized = raw.replace(/\./g, '');
                }
            }
        } else if (hasComma) {
            if (/^\d{1,3}(,\d{3})+$/.test(raw)) {
                normalized = raw.replace(/,/g, '');
            } else {
                normalized = raw.replace(',', '.');
            }
        }

        return Number(normalized);
    }

    function normalizeQuantityValue(value, precision) {
        var parsed = parseQuantity(value);
        if (!Number.isFinite(parsed)) return '';
        var decimals = Number.isInteger(precision) ? precision : 0;
        return parsed.toFixed(decimals);
    }

    function formatQuantityDisplay(value, options) {
        var parsed = parseQuantity(value);
        if (!Number.isFinite(parsed)) return '';

        var opts = options || {};
        var locale = opts.locale || 'es-PY';
        var maxFractionDigits = Number.isInteger(opts.maxFractionDigits) ? opts.maxFractionDigits : 0;

        var rounded = Math.round(parsed * 1000) / 1000;
        return new Intl.NumberFormat(locale, {
            minimumFractionDigits: 0,
            maximumFractionDigits: maxFractionDigits,
            useGrouping: true
        }).format(rounded);
    }

    function normalizeQuantityInput(input, options) {
        if (!input) return;

        var opts = options || {};
        var precision = Number.isInteger(opts.precision) ? opts.precision : 0;
        var normalized = normalizeQuantityValue(input.value, precision);

        if (!normalized) {
            return;
        }

        input.dataset.normalizedValue = normalized;
        input.value = formatQuantityDisplay(normalized, {
            locale: opts.locale || 'es-PY',
            maxFractionDigits: precision,
        });
    }

    function formatQuantityInputKeepingCaret(input, options) {
        if (!input) return;
        var originalValue = input.value || '';
        var caretStart = typeof input.selectionStart === 'number' ? input.selectionStart : originalValue.length;
        var digitsRight = countDigitsFromPosition(originalValue, caretStart);

        var parsed = parseQuantity(originalValue);
        if (!Number.isFinite(parsed)) {
            input.dataset.normalizedValue = '';
            return;
        }

        var opts = options || {};
        var precision = Number.isInteger(opts.precision) ? opts.precision : 0;
        var formatted = formatQuantityDisplay(parsed, {
            locale: opts.locale || 'es-PY',
            maxFractionDigits: precision,
        });
        if (!formatted) return;

        input.dataset.normalizedValue = String(parsed);
        input.value = formatted;

        var nextCursor = cursorFromDigitsRight(formatted, digitsRight);
        try {
            input.setSelectionRange(nextCursor, nextCursor);
        } catch (error) {
        }
    }

    function isGuaraniCurrency(currency) {
        var label = String(currency || '').toLowerCase();
        return label.indexOf('gs') !== -1 || label.indexOf('guarani') !== -1;
    }

    function getMoneyPrecision(currency) {
        return isGuaraniCurrency(currency) ? 0 : 2;
    }

    function formatAmountDisplay(value, options) {
        var parsed = parseNumber(value);
        if (!Number.isFinite(parsed)) return '-';

        var opts = options || {};
        var locale = opts.locale || 'es-PY';
        var withDecimals = !!opts.withDecimals;
        var precision = Number.isInteger(opts.precision) ? opts.precision : (withDecimals ? 2 : 0);

        return new Intl.NumberFormat(locale, {
            minimumFractionDigits: precision,
            maximumFractionDigits: precision,
            useGrouping: true
        }).format(parsed);
    }

    function formatCurrencyDisplay(value, options) {
        var opts = options || {};
        var amount = formatAmountDisplay(value, {
            locale: opts.locale,
            withDecimals: opts.withDecimals,
            precision: opts.precision
        });
        if (amount === '-') return '-';
        return ((opts.currency || '') + ' ' + amount).trim();
    }

    function normalizeMoneyValue(value, options) {
        var opts = options || {};
        var precision = Number.isInteger(opts.precision) ? opts.precision : getMoneyPrecision(opts.currency);
        var raw = String(value === null || value === undefined ? '' : value).trim().replace(/\s+/g, '');
        if (!raw) return '';

        if (precision === 0) {
            if (/^\d+[\.,]\d{1,2}$/.test(raw)) {
                var decimalLikeMatch = raw.match(/^(\d+)[\.,](\d{1,2})$/);
                var integerPart = decimalLikeMatch ? decimalLikeMatch[1] : '';

                if (integerPart.length >= 4) {
                    var parsedDecimal = parseNumber(raw);
                    if (!Number.isFinite(parsedDecimal)) return '';
                    return Math.round(parsedDecimal).toFixed(0);
                }

                var integerDigitsFromEdit = raw.replace(/\D/g, '');
                if (!integerDigitsFromEdit) return '';
                var parsedFromEdit = Number(integerDigitsFromEdit);
                if (!Number.isFinite(parsedFromEdit)) return '';
                return parsedFromEdit.toFixed(0);
            }

            var integerDigits = raw.replace(/\D/g, '');
            if (!integerDigits) return '';
            var parsedInteger = Number(integerDigits);
            if (!Number.isFinite(parsedInteger)) return '';
            return parsedInteger.toFixed(0);
        }

        var parsed = parseNumber(raw);
        if (!Number.isFinite(parsed)) return '';
        return parsed.toFixed(precision);
    }

    function normalizeMoneyInput(input, options) {
        if (!input) return;
        var normalized = normalizeMoneyValue(input.value, options);
        if (!normalized) return;

        var opts = options || {};
        var precision = Number.isInteger(opts.precision) ? opts.precision : getMoneyPrecision(opts.currency);
        input.dataset.normalizedValue = normalized;
        input.value = formatAmountDisplay(normalized, {
            locale: opts.locale || 'es-PY',
            withDecimals: precision > 0,
            precision: precision
        });
    }

    function countDigitsFromPosition(value, startPosition) {
        if (!value) return 0;
        var text = String(value);
        var safeStart = Number.isInteger(startPosition) ? startPosition : text.length;
        var rightSlice = text.slice(safeStart);
        var onlyDigits = rightSlice.match(/\d/g);
        return onlyDigits ? onlyDigits.length : 0;
    }

    function cursorFromDigitsRight(value, digitsRight) {
        var text = String(value || '');
        var targetDigits = Math.max(0, digitsRight || 0);
        if (targetDigits === 0) return text.length;

        var seen = 0;
        for (var i = text.length - 1; i >= 0; i -= 1) {
            if (/\d/.test(text.charAt(i))) {
                seen += 1;
                if (seen === targetDigits) {
                    return i;
                }
            }
        }

        return 0;
    }

    function formatMoneyInputDisplay(input, options) {
        if (!input) return;
        var normalized = normalizeMoneyValue(input.dataset.normalizedValue || input.value, options);
        if (!normalized) return;

        var opts = options || {};
        input.dataset.normalizedValue = normalized;
        input.value = formatAmountDisplay(normalized, {
            locale: opts.locale,
            withDecimals: Number.isInteger(opts.precision) ? opts.precision > 0 : getMoneyPrecision(opts.currency) > 0,
            precision: Number.isInteger(opts.precision) ? opts.precision : undefined
        });
    }

    function formatMoneyInputKeepingCaret(input, options) {
        if (!input) return;
        var originalValue = input.value || '';
        var caretStart = typeof input.selectionStart === 'number' ? input.selectionStart : originalValue.length;
        var digitsRight = countDigitsFromPosition(originalValue, caretStart);

        var normalized = normalizeMoneyValue(originalValue, options) || '';
        input.dataset.normalizedValue = normalized;
        if (!normalized) return;

        var opts = options || {};
        var precision = Number.isInteger(opts.precision) ? opts.precision : getMoneyPrecision(opts.currency);
        var formatted = formatAmountDisplay(normalized, {
            locale: opts.locale,
            withDecimals: precision > 0,
            precision: precision
        });
        input.value = formatted;

        var nextCursor = cursorFromDigitsRight(formatted, digitsRight);
        try {
            input.setSelectionRange(nextCursor, nextCursor);
        } catch (error) {
        }
    }

    function setMoneyInputValue(input, value, options) {
        if (!input) return;
        var normalized = normalizeMoneyValue(value, options);
        if (!normalized) return;

        var opts = options || {};
        var precision = Number.isInteger(opts.precision) ? opts.precision : getMoneyPrecision(opts.currency);
        input.dataset.normalizedValue = normalized;
        input.value = formatAmountDisplay(normalized, {
            locale: opts.locale,
            withDecimals: precision > 0,
            precision: precision
        });
    }

    function bindInputFormatting(input, options) {
        if (!input) return;

        var opts = options || {};
        var kind = opts.kind === 'quantity' ? 'quantity' : 'money';
        var locale = opts.locale || 'es-PY';
        var precision = Number.isInteger(opts.precision)
            ? opts.precision
            : (kind === 'quantity' ? 0 : getMoneyPrecision(opts.currency));

        var baseOptions = {
            locale: locale,
            precision: precision,
            currency: opts.currency,
        };

        if (kind === 'quantity') {
            normalizeQuantityInput(input, { locale: locale, precision: precision });
            input.addEventListener('input', function() {
                formatQuantityInputKeepingCaret(input, { locale: locale, precision: precision });
            });
            input.addEventListener('blur', function() {
                normalizeQuantityInput(input, { locale: locale, precision: precision });
            });
            return;
        }

        formatMoneyInputDisplay(input, baseOptions);
        input.addEventListener('focus', function() {
            formatMoneyInputDisplay(input, baseOptions);
        });
        input.addEventListener('input', function() {
            formatMoneyInputKeepingCaret(input, baseOptions);
        });
        input.addEventListener('blur', function() {
            normalizeMoneyInput(input, baseOptions);
        });
    }

    function normalizeInputForSubmit(input, options) {
        if (!input) return;

        var opts = options || {};
        var kind = opts.kind === 'quantity' ? 'quantity' : 'money';
        var precision = Number.isInteger(opts.precision)
            ? opts.precision
            : (kind === 'quantity' ? 0 : getMoneyPrecision(opts.currency));

        if (kind === 'quantity') {
            var normalizedQuantity = normalizeQuantityValue(input.value, precision);
            if (normalizedQuantity) {
                input.value = normalizedQuantity;
            }
            return;
        }

        var normalizedMoney = normalizeMoneyValue(input.dataset.normalizedValue || input.value, {
            currency: opts.currency,
            precision: precision,
            locale: opts.locale || 'es-PY',
        });
        if (normalizedMoney) {
            input.value = normalizedMoney;
        }
    }

    window.SIGECOPNumbers = {
        parseNumber: parseNumber,
        parseQuantity: parseQuantity,
        normalizeQuantityValue: normalizeQuantityValue,
        formatQuantityDisplay: formatQuantityDisplay,
        normalizeQuantityInput: normalizeQuantityInput,
        formatQuantityInputKeepingCaret: formatQuantityInputKeepingCaret,
        isGuaraniCurrency: isGuaraniCurrency,
        getMoneyPrecision: getMoneyPrecision,
        formatAmountDisplay: formatAmountDisplay,
        formatCurrencyDisplay: formatCurrencyDisplay,
        normalizeMoneyValue: normalizeMoneyValue,
        normalizeMoneyInput: normalizeMoneyInput,
        formatMoneyInputDisplay: formatMoneyInputDisplay,
        formatMoneyInputKeepingCaret: formatMoneyInputKeepingCaret,
        setMoneyInputValue: setMoneyInputValue,
        bindInputFormatting: bindInputFormatting,
        normalizeInputForSubmit: normalizeInputForSubmit
    };
})(window);
