(function () {
    function getElements(row) {
        return {
            del: row ? row.querySelector('input[name$="-DELETE"]') : null,
            deleteBtn: row ? row.querySelector('.js-delete-line-btn') : null,
            deleteLabel: row ? row.querySelector('.js-delete-line-label') : null,
        };
    }

    function applyState(row, options) {
        if (!row) return false;

        const opts = options || {};
        const labels = opts.labels || {};
        const deleteText = labels.deleteText || 'Eliminar detalle';
        const restoreText = labels.restoreText || 'Restaurar detalle';
        const hideNextErrorRow = !!opts.hideNextErrorRow;

        const els = getElements(row);
        const isDeleted = !!(els.del && els.del.checked);
        row.classList.toggle('line-row-deleted', isDeleted);

        if (hideNextErrorRow) {
            const nextRow = row.nextElementSibling;
            if (nextRow && nextRow.querySelector('td.text-danger')) {
                nextRow.style.display = isDeleted ? 'none' : '';
            }
        }

        if (els.deleteLabel) {
            els.deleteLabel.textContent = isDeleted ? restoreText : deleteText;
        }

        if (els.deleteBtn) {
            const icon = els.deleteBtn.querySelector('i');
            if (icon) {
                icon.className = isDeleted
                    ? 'ace-icon fa fa-undo bigger-130'
                    : 'ace-icon fa fa-trash-o bigger-130';
            }
            els.deleteBtn.title = isDeleted ? restoreText : deleteText;
        }

        return isDeleted;
    }

    function toggleRow(row, options) {
        if (!row) return { removed: false, toggled: false, isDeleted: false };

        const opts = options || {};
        const els = getElements(row);

        if (els.del) {
            els.del.checked = !els.del.checked;
            const isDeleted = applyState(row, opts);
            return { removed: false, toggled: true, isDeleted: isDeleted };
        }

        const parent = row.parentElement;
        row.remove();
        if (typeof opts.onRemoved === 'function') {
            opts.onRemoved(parent);
        }
        return { removed: true, toggled: false, isDeleted: false };
    }

    window.SIGECOPLineDelete = {
        applyState: applyState,
        toggleRow: toggleRow,
    };
})();
