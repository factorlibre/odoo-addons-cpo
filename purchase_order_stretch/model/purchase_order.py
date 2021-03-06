# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# © 2018 FactorLibre - Álvaro Marcos <alvaro.marcos@factorlibre.com>
from openerp import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    calculate_qty_line = fields.Boolean("Calculate quantities", default=True)

    @api.multi
    def _get_product_tmpl(self):
        for line in self:
            if line.product_id.product_tmpl_id:
                line.product_tmpl_id = line.product_id.product_tmpl_id

    supplier_id = fields.Many2one('product.supplierinfo', 'Proveedor')
    product_tmpl_id = fields.Many2one('product.template', 'Plantilla',
                                      compute='_get_product_tmpl')

    @api.multi
    def onchange_supplier(self):
        psi = False
        now = datetime.today()
        if self.calculate_qty_line:
            package_quantity = 1
            temp_value = 0
            quantity = self.product_qty
            psi = self.env['product.supplierinfo'].search([
                ('name', '=', self.partner_id.id),
                ('product_tmpl_id', '=',
                 self.product_id.product_tmpl_id.id),
                ('min_qty', '<=', quantity),
                '|', ('date_start', '=', False),
                ('date_start', '<=', now),
                '|', ('date_end', '=', False),
                ('date_end', '>=', now)
            ], order='price, discount desc', limit=1)
            if psi:
                package_quantity = hasattr(
                    self.supplier_id,
                    'qty_multiple') and psi.qty_multiple or 1
                resto = quantity % package_quantity
                temp_value = quantity
                if resto:
                    quantity = quantity + package_quantity - resto
                # Pasa otra vez para recomprobar el proveedor

                psi = self.env['product.supplierinfo'].search([
                    ('name', '=', self.partner_id.id),
                    ('product_tmpl_id', '=',
                     self.product_id.product_tmpl_id.id),
                    ('min_qty', '<=', quantity),
                    '|', ('date_start', '=', False),
                    ('date_start', '<=', now),
                    '|', ('date_end', '=', False),
                    ('date_end', '>=', now)
                ], order='price, discount desc', limit=1)
                package_quantity = hasattr(
                    self.supplier_id,
                    'qty_multiple') and psi.qty_multiple or 1
                resto = temp_value % package_quantity
                # temp_value = quantity
                if resto:
                    quantity = temp_value + package_quantity - resto
            else:
                psi = self.env['product.supplierinfo'].search([
                    ('name', '=', self.partner_id.id),
                    ('product_tmpl_id', '=',
                     self.product_id.product_tmpl_id.id),
                    '|', ('date_start', '=', False),
                    ('date_start', '<=', now),
                    '|', ('date_end', '=', False),
                    ('date_end', '>=', now)
                ], order='min_qty, price, discount desc', limit=1)
                if psi:
                    quantity = psi.min_qty
                else:
                    quantity = self.product_qty
            if psi:
                data_dict = {
                    'name': psi.product_name or self.product_id.name,
                    'product_qty': quantity,
                    'price_unit': psi.price or 0,
                    'discount': psi.discount or 0,
                }
            else:
                data_dict = {
                    'name': self.product_id.name,
                    'product_qty': quantity,
                    'price_unit': self.product_id.standard_price or 0,
                    'discount': 0,
                }
        else:
            psi = self.env['product.supplierinfo'].search([
                ('name', '=', self.partner_id.id),
                ('product_tmpl_id', '=',
                 self.product_id.product_tmpl_id.id),
                '|', ('date_start', '=', False),
                ('date_start', '<=', now),
                '|', ('date_end', '=', False),
                ('date_end', '>=', now)
            ], order='price, discount', limit=1)
            data_dict = {
                'name': psi.product_name or self.product_id.name,
                'price_unit': psi.price or self.product_id.standard_price or 0,
                'discount': psi.discount or 0,
            }
        self.update(data_dict)
        self.supplier_id = psi

    @api.multi
    def update_line(self, supplier):
        self.ensure_one
        data_dict = {
            'name': supplier.product_name or self.product_id.name or "",
            'product_qty': supplier.min_qty or 1,
            'price_unit': supplier.price or self.product_id.standard_price,
            'discount': supplier.discount or 0,
        }
        self.update(data_dict)

    @api.onchange('product_id')
    def onchange_product_id_supp(self):
        now = datetime.today()
        for line in self:
            if line.calculate_qty_line:
                if len(line.order_id.order_line.filtered(
                        lambda r: r.product_id == line.product_id)) > 2:
                    raise ValidationError((
                        "Ya hay una línea para este producto"))
                if line.product_id.product_tmpl_id.id:
                    psi = self.env['product.supplierinfo'].search([
                        ('name', '=', line.order_id.partner_id.id),
                        ('product_tmpl_id', '=',
                         line.product_id.product_tmpl_id.id),
                        '|', ('date_start', '=', False),
                        ('date_start', '<=', now),
                        '|', ('date_end', '=', False),
                        ('date_end', '>=', now)
                    ], order='sequence', limit=1)
                    if psi:
                        line.supplier_id = psi
                    else:
                        line.supplier_id = False
                else:
                    line.supplier_id = False
                # product = line.product_id
                # line.name = "[%s] %s" % (product.default_code, product.name)
                line._get_product_tmpl()

    @api.onchange('product_qty')
    def onchange_product_qty(self):
        for line in self:
            line.onchange_supplier()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    calculate_qty = fields.Boolean("Calculate quantities", default=True)

    @api.onchange('partner_id')
    def onchange_partner(self):
        now = datetime.today()
        for order in self:
            for line in order.order_line:
                psi = False
                if line.product_id.product_tmpl_id.id:
                    psi = self.env['product.supplierinfo'].search([
                        ('name', '=', line.order_id.partner_id.id),
                        ('product_tmpl_id', '=',
                         line.product_id.product_tmpl_id.id),
                        '|', ('date_start', '=', False),
                        ('date_start', '<=', now),
                        '|', ('date_end', '=', False),
                        ('date_end', '>=', now)
                    ], order='sequence', limit=1)
                    if psi:
                        line.supplier_id = psi
                    else:
                        line.supplier_id = False
                else:
                    line.supplier_id = False
                line._get_product_tmpl()
                line.update_line(psi)

    @api.onchange('calculate_qty')
    def _on_change_calculate_qty(self):
        for order in self:
            for line in order.order_line:
                line.update({
                    'calculate_qty_line': order.calculate_qty
                })
                if order.calculate_qty:
                    line.onchange_supplier()


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    @api.multi
    def name_get(self):
        return [(s.id, "%s - %s" % (s.name.name, s.product_name or ""))
                for s in self]
