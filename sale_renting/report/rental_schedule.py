# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools


class RentalSchedule(models.Model):
    _name = "sale.rental.schedule"
    _description = "Rental Schedule"
    _auto = False
    _order = 'order_date desc'
    _rec_name = 'card_name'

    @api.model
    def _read_group_report_line_status(self, report_line_status, domain, order):
        return [key for key, val in self._fields['report_line_status'].selection]

    @api.model
    def _read_group_product_ids(self, products, domain, order):
        if self._context.get('restrict_renting_products'):
            return products
        all_rental_products = products.search([('rent_ok', '=', True)], order=order)
        if len(all_rental_products) > 80:
            return products
        return all_rental_products

    name = fields.Char('Order Reference', readonly=True)
    product_name = fields.Char('Product Reference', readonly=True)
    description = fields.Char('Description', readonly=True)
    order_date = fields.Datetime('Order Date', readonly=True)
    pickup_date = fields.Datetime('Pickup Date', readonly=True)
    return_date = fields.Datetime('Return Date', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True, group_expand="_read_group_product_ids")
    product_uom = fields.Many2one('uom.uom', 'Unit of Measure', readonly=True)
    product_uom_qty = fields.Float('Qty Ordered', readonly=True)
    qty_delivered = fields.Float('Qty Picked-Up', readonly=True)
    qty_returned = fields.Float('Qty Returned', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    card_name = fields.Char(string="Customer Name", readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    user_id = fields.Many2one('res.users', 'Salesperson', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', 'Product Category', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True)
    team_id = fields.Many2one('crm.team', 'Sales Team', readonly=True)
    country_id = fields.Many2one('res.country', 'Customer Country', readonly=True)
    commercial_partner_id = fields.Many2one('res.partner', 'Customer Entity', readonly=True)
    rental_status = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('pickup', 'Reserved'),
        ('return', 'Pickedup'),
        ('returned', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string="Rental Status", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Sales Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)

    order_id = fields.Many2one('sale.order', 'Order #', readonly=True)
    order_line_id = fields.Many2one('sale.order.line', 'Order line #', readonly=True)

    report_line_status = fields.Selection([
        ('reserved', 'Reserved'),
        ('pickedup', 'Pickedup'),
        ('returned', 'Returned'),
    ], string="Rental Status (advanced)", readonly=True, group_expand="_read_group_report_line_status")
    color = fields.Integer(readonly=True)
    late = fields.Boolean("Is Late", readonly=True)

    def _with(self):
        return """ """

    def _id(self):
        return """sol.id as id"""

    def _get_product_name(self):
        return """t.name as product_name"""

    def _quantity(self):
        return """
            sum(sol.product_uom_qty / u.factor * u2.factor) as product_uom_qty,
            sum(sol.qty_delivered / u.factor * u2.factor) as qty_delivered,
            sum(sol.qty_returned / u.factor * u2.factor) as qty_returned
        """

    def _late(self):
        return """
            CASE WHEN sol.state NOT IN ('sale', 'done') THEN FALSE
                WHEN sol.pickup_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_delivered < sol.product_uom_qty THEN TRUE
                WHEN sol.return_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_returned < sol.qty_delivered THEN TRUE
            ELSE FALSE
            END as late
        """

    def _report_line_status(self):
        return """
            CASE WHEN sol.qty_returned = sol.qty_delivered
                    AND sol.qty_delivered = sol.product_uom_qty THEN 'returned'
                WHEN sol.qty_delivered = sol.product_uom_qty THEN 'pickedup'
            ELSE 'reserved'
            END as report_line_status
        """

    def _color(self):
        """2 = orange (pickedup), 4 = blue(reserved), 6 = red(late return), 7 = green(returned)"""
        return """
            CASE WHEN sol.pickup_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_delivered < sol.product_uom_qty THEN 4
                WHEN sol.return_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_returned < sol.qty_delivered THEN 6
                WHEN sol.qty_returned = sol.qty_delivered AND sol.qty_delivered = sol.product_uom_qty THEN 7
                WHEN sol.qty_delivered = sol.product_uom_qty THEN 2
            ELSE 4
            END as color
        """

    def _select(self):
        return """%s,
            %s,
            sol.product_id as product_id,
            t.uom_id as product_uom,
            sol.name as description,
            s.name as name,
            %s,
            s.date_order as order_date,
            sol.pickup_date as pickup_date,
            sol.return_date as return_date,
            s.state as state,
            s.rental_status as rental_status,
            s.partner_id as partner_id,
            s.user_id as user_id,
            s.company_id as company_id,
            extract(epoch from avg(date_trunc('day',sol.return_date)-date_trunc('day',sol.pickup_date)))/(24*60*60)::decimal(16,2) as delay,
            t.categ_id as categ_id,
            s.pricelist_id as pricelist_id,
            s.analytic_account_id as analytic_account_id,
            s.team_id as team_id,
            p.product_tmpl_id,
            partner.country_id as country_id,
            partner.commercial_partner_id as commercial_partner_id,
            CONCAT(partner.name, ', ', s.name) as card_name,
            s.id as order_id,
            sol.id as order_line_id,
            %s,
            %s,
            %s
        """ % (self._id(), self._get_product_name(), self._quantity(), self._report_line_status(), self._late(), self._color())

    def _from(self):
        return """
            sale_order_line sol
                join sale_order s on (sol.order_id=s.id)
                join res_partner partner on s.partner_id = partner.id
                left join product_product p on (sol.product_id=p.id)
                left join product_template t on (p.product_tmpl_id=t.id)
                left join uom_uom u on (u.id=sol.product_uom)
                left join uom_uom u2 on (u2.id=t.uom_id)
        """

    def _groupby(self):
        return """
            sol.product_id,
            sol.order_id,
            t.uom_id,
            t.categ_id,
            t.name,
            s.name,
            s.date_order,
            sol.pickup_date,
            sol.return_date,
            s.partner_id,
            s.user_id,
            s.rental_status,
            s.company_id,
            s.pricelist_id,
            s.analytic_account_id,
            s.team_id,
            p.product_tmpl_id,
            partner.country_id,
            partner.commercial_partner_id,
            partner.name,
            s.id,
            sol.id
        """

    def _query(self):
        return """
            %s (SELECT %s
                FROM %s
                WHERE sol.product_id IS NOT NULL
                    AND sol.is_rental
                GROUP BY %s)
        """ % (
            self._with(),
            self._select(),
            self._from(),
            self._groupby()
        )

    def init(self):
        # self._table = sale_rental_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
