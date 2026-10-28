/** @odoo-module */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class OptiMultiInvoicePayment extends Interaction {
    static selector = ".o_opti_pay_bar";
    dynamicContent = {
        ".o_opti_pay_selected": { "t-on-click": this.onPay },
        ".o_opti_invoice_check": { "t-on-change": this.update },
        ".o_opti_invoice_check_all": { "t-on-change": this.onSelectAll },
    };

    setup() {
        this.checkboxes = [...document.querySelectorAll(".o_opti_invoice_check")];
        this.selectAll = document.querySelector(".o_opti_invoice_check_all");
        this.warning = document.querySelector(".o_opti_currency_warning");
        this.update();
    }

    selected() {
        return this.checkboxes.filter((checkbox) => checkbox.checked);
    }

    update() {
        const selected = this.selected();
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
            this.selectAll.checked = this.checkboxes.length > 0 && selected.length === this.checkboxes.length;
        }
    }

    onSelectAll(ev) {
        for (const checkbox of this.checkboxes) {
            checkbox.checked = ev.currentTarget.checked;
        }
        this.update();
    }

    onPay(ev) {
        ev.preventDefault();
        const selected = this.selected();
        if (!selected.length) {
            return;
        }
        const currencies = new Set(selected.map((checkbox) => checkbox.dataset.currencyId));
        if (currencies.size > 1) {
            this.update();
            return;
        }
        const ids = document.getElementById("o_opti_invoice_ids");
        const form = document.getElementById("o_opti_multi_pay_form");
        if (!ids || !form) {
            return;
        }
        ids.value = selected.map((checkbox) => checkbox.value).join(",");
        form.submit();
    }
}

registry.category("public.interactions").add(
    "opti_multi_invoice_payment.pay_bar",
    OptiMultiInvoicePayment,
);
