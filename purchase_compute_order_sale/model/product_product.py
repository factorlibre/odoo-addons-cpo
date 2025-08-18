# -*- encoding: utf-8 -*-
##############################################################################
#
#    Purchase - Computed Purchase Order Glue Module for Sale for Odoo
#    Copyright (C) 2013-Today GRAP (http://www.grap.coop)
#    @author Julien WESTE
#    @author Sylvain LE GAL (https://twitter.com/legalsylvain)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import models, api
from datetime import datetime, timedelta


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Private section
    @api.multi
    def _get_draft_outgoing_qty(self):
        super(ProductProduct, self)._get_draft_outgoing_qty()
        domain = self._get_outgoing_product_qty_domain()
        sol_obj = self.env['sale.order.line']
        domain = self.transform_domain(domain)
        sol_ids = sol_obj.search(domain)
        draft_qty = {}
        for line in sol_ids:
            draft_qty.setdefault(line.product_id.id, 0)
            draft_qty[line.product_id.id] += \
                line.product_uom_qty / line.product_uom.factor\
                * line.product_id.uom_id.factor
        for pp in self:
            pp.draft_outgoing_qty += draft_qty.get(pp.id, 0)

    @api.multi
    def _get_outgoing_product_qty_domain(self):
        return [
            ('order_id.state', 'in', ['draft', 'sent']),
            ('product_id', 'in', self.ids)]

    def transform_domain(self, domain):
        sale_order_domain = []
        sale_order_line_domain = []
        for condition in domain:
            if condition[0].startswith("order_id."):
                # Condición para sale.order
                sale_order_domain.append((condition[0][9:],) + condition[1:])
            else:
                # Condición para sale.order.line
                sale_order_line_domain.append(condition)
        # Realizar la búsqueda de sale.order
        if sale_order_domain:
            # Añadir filtro de últimos 2 años
            one_year_ago = datetime.now() - timedelta(days=365)
            sale_order_domain.append(
                ("date_order", ">=", one_year_ago.strftime("%Y-%m-%d"))
            )
            sale_ids = self.env["sale.order"].search(sale_order_domain)
            # Añadir la condición de order_id a sale_order_line_domain
            sale_order_line_domain.append(("order_id", "in", sale_ids.ids))
        return sale_order_line_domain
