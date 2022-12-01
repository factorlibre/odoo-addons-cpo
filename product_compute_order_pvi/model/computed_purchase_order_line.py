# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# © 2018 FactorLibre - Álvaro Marcos <alvaro.marcos@factorlibre.com>
from odoo import models, api, fields
from odoo.addons.queue_job.job import job


class ComputedPurchaseOrderLine(models.Model):
    _inherit = 'computed.purchase.order.line'

    # @api.onchange('product_id')
    # def onchange_product_id(self):
    #     super(ComputedPurchaseOrderLine, self).onchange_product_id()
    #     self.average_consumption = self.product_id.average_consumption_pvi
    pvi_draft_qty = fields.Float(
        'PVI Draft Outgoing Quantity',
        help="Draft sales")
    pvi_qty = fields.Float(
        'PVI Outgoing Quantity',
        help="Draft sales")

    @api.multi
    def _pvi_qty_available(self):
        cpol_lines = {}
        for cpol in self:
            if cpol.product_id.id:
                product_id = cpol.change_product_context(cpol.product_id)
                pvi = [True]
                parametres = ['draft', 'sent']
                line_dict = {}
                if cpol.computed_purchase_order_id.compute_pvi_d_quantity:
                    line_dict['pvi_draft_qty'] = product_id.\
                        custom_average_consumption(parametres, pvi)[0]
                if cpol.computed_purchase_order_id.compute_pvi_quantity:
                    parametres = ['pvi_confirmed']
                    line_dict['pvi_qty'] = product_id.\
                        custom_average_consumption(parametres, pvi)[0]
                cpol_lines[cpol.id] = line_dict
        return cpol_lines

    @job(default_channel='root.update_computed_qty')
    @api.multi
    def _get_computed_qty(self):
        """ Update computed purchase order quantities """
        cpol_lines = self._pvi_qty_available() or {}
        self._product_qty_available()
        for cpol in self:
            computed_qty = 0
            computed_qty = cpol.qty_available
            if cpol.computed_purchase_order_id.compute_pending_quantity:
                computed_qty += (cpol.incoming_qty - cpol.outgoing_qty)
            if cpol.computed_purchase_order_id.compute_draft_quantity:
                computed_qty += (cpol.draft_incoming_qty -
                                 cpol.draft_outgoing_qty)
            if cpol.computed_purchase_order_id.compute_pvi_d_quantity:
                computed_qty -= cpol.pvi_draft_qty
            if cpol.computed_purchase_order_id.compute_pvi_quantity:
                computed_qty -= cpol.pvi_qty
            values = {
                "computed_qty": computed_qty
            }
            pvi_value = cpol_lines.get(cpol.id)
            if pvi_value:
                if pvi_value.get("pvi_qty"):
                    values['pvi_qty'] = pvi_value.get("pvi_qty")
                if pvi_value.get("pvi_draft_qty"):
                    values['pvi_draft_qty'] = pvi_value.get("pvi_draft_qty")
            cpol.write(values)
