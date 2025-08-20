# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
# © 2018 FactorLibre - Álvaro Marcos <alvaro.marcos@factorlibre.com>
from openerp import models, api, fields
import datetime
import time


class ProductProduct(models.Model):
    _inherit = "product.product"

    average_consumption_pvi = fields.Float(
        "Average Consumption with PVI", compute="_average_consumption_pvi"
    )

    @api.multi
    def _average_consumption_pvi(self):
        parametres = ["draft", "pvi_confirmed", "sent"]
        self.calculate_average_consumption_pvi(parametres)

    @api.multi
    def calculate_average_consumption_pvi(self, parametres):
        for product in self:
            begin_date = (
                datetime.datetime.today() - datetime.timedelta(days=365)
            ).strftime("%Y-%m-%d")
            dates_to_consider = [begin_date, self._min_date_draft()]
            # Incluir date_start del contexto si existe
            context_date_start = product.env.context.get("date_start")
            if context_date_start:
                dates_to_consider.append(context_date_start)
            date = max(dates_to_consider)
            sale_ids = (
                self.env["sale.order"]
                .search(
                    [
                        ("date_order", ">=", date),
                        ("state", "in", parametres),
                    ]
                )
                .ids
            )
            domain = self._get_average_consumption_domain(parametres, sale_ids)
            line_ids = self.env["sale.order.line"].search(domain)
            consumption = 0
            nb_days = (
                datetime.datetime.today()
                - datetime.datetime.strptime(min(product._min_date(), date), "%Y-%m-%d")
            ).days or 1.0
            for line in line_ids:
                consumption += line.product_uom_qty
            product.average_consumption_pvi = (
                consumption + product.total_consumption
            ) / nb_days

    @api.multi
    def custom_average_consumption(self, parametres, pvi):
        """
        Versión ultra optimizada con search_read para eliminar bucles Python
        """
        self.ensure_one()
        begin_date = (
            datetime.datetime.today() - datetime.timedelta(days=365)
        ).strftime("%Y-%m-%d")

        dates_to_consider = [begin_date, self._min_date_draft()]
        context_date_start = self.env.context.get("date_start")
        if context_date_start:
            dates_to_consider.append(context_date_start)

        date = max(dates_to_consider)
        sale_domain = [
            ("date_order", ">=", date),
            ("state", "in", parametres),
        ]
        if True in pvi and False not in pvi:
            sale_domain.append(("initial_order", "=", True))
        elif False in pvi and True not in pvi:
            sale_domain.append(("initial_order", "=", False))

        # OPTIMIZACIÓN 1: Usar search_read para sale_orders
        sale_orders_data = self.env["sale.order"].search_read(
            domain=sale_domain,
            fields=['id', 'state']
        )

        if not sale_orders_data:
            return [0, 0]

        sale_order_ids = [order['id'] for order in sale_orders_data]
        order_states = {order['id']: order['state'] for order in sale_orders_data}

        # OPTIMIZACIÓN 2: Separar condiciones del dominio original
        original_domain = self._get_average_consumption_domain(parametres, sale_order_ids)

        sale_order_conditions = []
        sale_line_conditions = []

        for condition in original_domain:
            if len(condition) == 3:
                field, operator, value = condition
                if '.' in field and field.startswith('order_id.'):
                    sale_order_field = field.replace('order_id.', '')
                    sale_order_conditions.append((sale_order_field, operator, value))
                else:
                    sale_line_conditions.append(condition)
            else:
                sale_line_conditions.append(condition)

        # OPTIMIZACIÓN 3: Filtrar sale_orders si hay condiciones JOIN
        if sale_order_conditions:
            filtered_orders_data = self.env["sale.order"].search_read(
                domain=[('id', 'in', sale_order_ids)] + sale_order_conditions,
                fields=['id', 'state']
            )
            sale_order_ids = [order['id'] for order in filtered_orders_data]
            order_states = {order['id']: order['state'] for order in filtered_orders_data}

        if not sale_order_ids:
            return [0, 0]

        # OPTIMIZACIÓN 4: search_read para sale_order_line (sin JOINs)
        optimized_domain = [('order_id', 'in', sale_order_ids)] + sale_line_conditions

        lines_data = self.env["sale.order.line"].search_read(
            domain=optimized_domain,
            fields=['product_uom_qty', 'uom_remaining_qty', 'order_id']
        )

        # OPTIMIZACIÓN 5: Calcular consumo sin bucle de objetos ORM
        consumption = 0
        nb_days = (
            datetime.datetime.today()
            - datetime.datetime.strptime(min(self._min_date(), date), "%Y-%m-%d")
        ).days or 1.0

        for line_data in lines_data:
            order_id = line_data['order_id'][0] if line_data['order_id'] else None
            order_state = order_states.get(order_id, '')

            if order_state == "pvi_confirmed":
                consumption += line_data['uom_remaining_qty'] or 0
            else:
                consumption += line_data['product_uom_qty'] or 0

        return [consumption, (consumption / nb_days)]

    @api.multi
    def _min_date_draft(self):
        self.ensure_one()
        query = """SELECT to_char(min(so.date_order), 'YYYY-MM-DD') \
                from sale_order as so
                inner join sale_order_line as sol
                    on so.id = sol.order_id
                where sol.product_id = %s""" % (
            self.id
        )
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        return results and results[0] and results[0][0] or time.strftime("%Y-%m-%d")

    @api.multi
    def _get_draft_outgoing_qty(self):
        super(ProductProduct, self)._get_draft_outgoing_qty()
        sol_obj = self.env["sale.order.line"]
        domain = self._get_pvi_outgoing_product_qty_domain()
        sol_ids = sol_obj.search(domain)
        draft_qty = {}
        for line in sol_ids:
            draft_qty.setdefault(line.product_id.id, 0)
            draft_qty[line.product_id.id] += (
                line.product_uom_qty
                / line.product_uom.factor
                * line.product_id.uom_id.factor
            )
        for pp in self:
            pp.draft_outgoing_qty -= draft_qty.get(pp.id, 0)

    @api.multi
    def _get_pvi_outgoing_product_qty_domain(self):
        one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
        sale_ids = (
            self.env["sale.order"]
            .search(
                [
                    ("initial_order", "=", True),
                    ("state", "in", ["draft", "sent"]),
                    ("date_order", ">=", one_year_ago.strftime("%Y-%m-%d")),
                ]
            )
            .ids
        )
        return [("order_id", "in", sale_ids), ("product_id", "in", self.ids)]

    @api.multi
    def _get_average_consumption_domain(self, parametres, sale_ids):
        return [("order_id", "in", sale_ids), ("product_id", "=", self.id)]
