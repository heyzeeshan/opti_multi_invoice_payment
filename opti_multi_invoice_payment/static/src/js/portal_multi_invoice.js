/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.OptiMultiInvoicePayment = publicWidget.Widget.extend({
    selector: ".o_opti_pay_bar",
    events: {
        "click .o_opti_pay_selected": "_onPay",
    },

    /**
     * Keep the pay button in step with the invoice checkboxes.
     *
     * @override
     */
    start() {
        this.checkboxes = [...document.querySelectorAll(".o_opti_invoice_check")];
        this.selectAll = document.querySelector(".o_opti_invoice_check_all");
        this.warning = document.querySelector(".o_opti_currency_warning");
        const refresh = () => this._update();
        for (const checkbox of this.checkboxes) {
            checkbox.addEventListener("change", refresh);
        }
        if (this.selectAll) {
            this.selectAll.addEventListener("change", (event) => {
                for (const checkbox of this.checkboxes) {
                    checkbox.checked = event.currentTarget.checked;
                }
                this._update();
            });
        }
        this._update();
        return this._super(...arguments);
    },

    /**
     * @private
     * @returns {HTMLInputElement[]}
     */
    _selected() {
        return this.checkboxes.filter((checkbox) => checkbox.checked);
    },

    /**
     * @private
     */
    _update() {
        const selected = this._selected();
        const button = this.el.querySelector(".o_opti_pay_selected");
        const count = this.el.querySelector(".o_opti_pay_count");
        const currencies = new Set(selected.map((checkbox) => checkbox.dataset.currencyId));
        const mixedCurrency = currencies.size > 1;
        if (this.warning) {
            this.warning.classList.toggle("d-none", !mixedCurrency);
        }
        if (button) {
            button.disabled = !selected.length || mixedCurrency;
        }
        if (count) {
            if (!selected.length) {
                count.textContent = "No invoices selected";
            } else if (selected.length === 1) {
                count.textContent = "1 invoice selected";
            } else {
                count.textContent = `${selected.length} invoices selected`;
            }
        }
        if (this.selectAll) {
            this.selectAll.checked = this.checkboxes.length > 0
                && selected.length === this.checkboxes.length;
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onPay(ev) {
        ev.preventDefault();
        const selected = this._selected();
        if (!selected.length) {
            return;
        }
        const currencies = new Set(selected.map((checkbox) => checkbox.dataset.currencyId));
        if (currencies.size > 1) {
            this._update();
            return;
        }
        const ids = document.getElementById("o_opti_invoice_ids");
        const form = document.getElementById("o_opti_multi_pay_form");
        if (!ids || !form) {
            return;
        }
        ids.value = selected.map((checkbox) => checkbox.value).join(",");
        form.submit();
    },
});
