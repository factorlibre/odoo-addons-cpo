from openerp import models, fields, api


class ComputedPurchaseOrderLine(models.Model):
    _inherit = 'computed.purchase.order.line'

    discount = fields.Float(
        'Discount', compute='_get_discount',
        help="The discount for the supplier.")

    @api.multi
    def _get_discount(self):
        for cpol in self:
            psi = cpol._line_product_supplier_info()
            if psi and psi.price and cpol.purchase_qty >= psi.min_qty:
                cpol.discount = psi.discount
