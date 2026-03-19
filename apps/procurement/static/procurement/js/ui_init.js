(function () {
    function getDefaultPlaceholder(select) {
        if (!select || !select.id) {
            return "Buscar...";
        }

        var label = document.querySelector('label[for="' + select.id + '"]');
        if (!label) {
            return "Buscar...";
        }

        var cleanLabel = (label.textContent || "").replace(/\*/g, "").trim();
        return cleanLabel ? "Buscar " + cleanLabel.toLowerCase() + "..." : "Buscar...";
    }

    function normalizeEmptyOptionLabel(select) {
        if (!select || !select.options || !select.options.length) {
            return;
        }

        var firstOption = select.options[0];
        if (!firstOption || firstOption.value !== "") {
            return;
        }

        var optionText = (firstOption.textContent || "").trim();
        if (/^-+$/.test(optionText)) {
            firstOption.textContent = "";
        }
    }

    function enhanceSelectElement(select) {
        if (!select || select.dataset.uiEnhanced === "1") {
            return;
        }

        if (!window.TomSelect) {
            return;
        }

        normalizeEmptyOptionLabel(select);

        var placeholder =
            select.getAttribute("placeholder") ||
            select.dataset.placeholder ||
            getDefaultPlaceholder(select);

        if ((select.value || "") === "") {
            Array.from(select.options || []).forEach(function(opt) {
                opt.selected = false;
            });
            select.selectedIndex = -1;
        }

        var options = {
            create: false,
            allowEmptyOption: true,
            maxOptions: 500,
            plugins: {},
            placeholder: placeholder,
            hidePlaceholder: true,
            dropdownParent: 'body'
        };

        if ((select.value || "") === "") {
            options.items = [];
        }

        if (select.multiple) {
            options.plugins.remove_button = { title: "Quitar" };
        }

        if (select.tomselect) {
            select.dataset.uiEnhanced = "1";
            return;
        }

        try {
            new TomSelect(select, options);
            select.dataset.uiEnhanced = "1";
        } catch (error) {
            if (window.console && console.warn) {
                console.warn("No se pudo inicializar Tom Select para", select, error);
            }
        }
    }

    function enhanceSelects(root) {
        var container = root || document;
        var selects = container.querySelectorAll("select.select2, select.js-enhanced-select");
        selects.forEach(enhanceSelectElement);
    }

    function initDataTables(root) {
        if (!window.jQuery || !jQuery.fn || !jQuery.fn.DataTable) {
            return;
        }

        var container = root || document;
        jQuery(container).find(".datatable").each(function () {
            if (jQuery.fn.DataTable.isDataTable(this)) {
                return;
            }

            var orderColumn = jQuery(this).data("order-column");
            var orderDir = jQuery(this).data("order-dir");
            var defaultOrder = [[0, "desc"]];
            if (orderColumn !== undefined && orderColumn !== null && orderColumn !== "") {
                var parsedColumn = Number(orderColumn);
                if (!Number.isNaN(parsedColumn)) {
                    defaultOrder = [[parsedColumn, orderDir || "asc"]];
                }
            }

            jQuery(this).DataTable({
                language: {
                    sProcessing: "Procesando...",
                    sLengthMenu: "Mostrar _MENU_ registros",
                    sZeroRecords: "No se encontraron resultados",
                    sEmptyTable: "Ningún dato disponible en esta tabla",
                    sInfo: "Mostrando registros del _START_ al _END_ de un total de _TOTAL_ registros",
                    sInfoEmpty: "Mostrando registros del 0 al 0 de un total de 0 registros",
                    sInfoFiltered: "(filtrado de un total de _MAX_ registros)",
                    sInfoPostFix: "",
                    sSearch: "Buscar:",
                    sUrl: "",
                    sInfoThousands: ",",
                    sLoadingRecords: "Cargando...",
                    oPaginate: {
                        sFirst: "Primero",
                        sLast: "Último",
                        sNext: "Siguiente",
                        sPrevious: "Anterior"
                    },
                    oAria: {
                        sSortAscending: ": Activar para ordenar la columna de manera ascendente",
                        sSortDescending: ": Activar para ordenar la columna de manera descendente"
                    }
                },
                pageLength: 10,
                bAutoWidth: false,
                order: defaultOrder,
                buttons: ["copy", "csv", "excel", "pdf", "print"]
            });
        });
    }

    window.SIGECOPUI = window.SIGECOPUI || {};
    window.SIGECOPUI.enhanceSelects = enhanceSelects;
    window.SIGECOPUI.initDataTables = initDataTables;

    document.addEventListener("DOMContentLoaded", function () {
        enhanceSelects(document);
        initDataTables(document);
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        var target = event.detail && event.detail.target ? event.detail.target : document;
        enhanceSelects(target);
        initDataTables(target);
    });
})();
