/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { rpc, RPCError } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';
import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {
    setup() {
        super.setup();
        this.braintreeData = {};
    },

    /**
     * Prepare the inline form of Braintree for direct payment.
     *
     * @private
     * @param {number} providerId
     * @param {string} providerCode
     * @param {number} paymentOptionId
     * @param {string} paymentMethodCode
     * @param {string} flow
     * @return {void}
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'braintree') {
            await super._prepareInlineForm(...arguments);
            return;
        }
        if (this.braintreeData[paymentOptionId]) {
            this._setPaymentFlow('direct');
            return;
        }

        this._setPaymentFlow('direct');
        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const inlineForm = this._getInlineForm(radio);
        const braintreeForm = inlineForm.querySelector('[name="o_braintree_form"]');
        const clientToken = braintreeForm.dataset.braintreeClientToken;

        if (!clientToken) {
            console.error('Braintree client token is missing.');
            return;
        }

        this.braintreeData[paymentOptionId] = {
            clientToken: clientToken,
            form: braintreeForm,
        };

        try {
            const dropinInstance = await new Promise((resolve, reject) => {
                braintree.dropin.create({
                    authorization: clientToken,
                    container: '#dropin-container'
                }, function (err, instance) {
                    if (err) {
                        reject(err);
                    } else {
                        resolve(instance);
                    }
                });
            });
            this.braintreeData[paymentOptionId].dropinInstance = dropinInstance;
        } catch (err) {
            console.error('Error creating Braintree Drop-in UI:', err);
            this._displayErrorDialog(_t("Error"), _t("Could not load Braintree Drop-in UI."));
        }
    },

    /**
     * Trigger the payment processing by submitting the data.
     *
     * @override method from payment.payment_form
     */
    async _initiatePaymentFlow(providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'braintree' || flow === 'token') {
            await super._initiatePaymentFlow(...arguments);
            return;
        }
        if (!this.braintreeData[paymentOptionId] || !this.braintreeData[paymentOptionId].dropinInstance) {
            this._displayErrorDialog(_t("Error"), _t("Braintree is not ready."));
            this._enableButton();
            return;
        }
        await super._initiatePaymentFlow(...arguments);
    },

    /**
     * Process the direct payment flow.
     *
     * @override method from payment.payment_form
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'braintree') {
            await super._processDirectFlow(...arguments);
            return;
        }

        const dropinInstance = this.braintreeData[paymentOptionId].dropinInstance;

        try {
            const payload = await new Promise((resolve, reject) => {
                dropinInstance.requestPaymentMethod((err, payload) => {
                    if (err) {
                        reject(err);
                    } else {
                        resolve(payload);
                    }
                });
            });

            const nonce = payload.nonce;
            const response = await this.waitFor(rpc('/payment/braintree/process', {
                'reference': processingValues.reference,
                'nonce': nonce,
            }));

            if (response.success) {
                window.location = '/payment/status';
            } else {
                this._displayErrorDialog(_t("Payment Failed"), response.message);
                this._enableButton();
            }
        } catch (error) {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("Payment processing failed"), error.data.message);
            } else {
                this._displayErrorDialog(_t("Error"), _t("Failed to retrieve payment nonce from Braintree. Please check your payment details."));
            }
            this._enableButton();
        }
    },
});
