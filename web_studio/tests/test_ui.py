# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-

import odoo.tests


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    def test_new_app_and_report(self):
        self.start_tour("/web?studio=app_creator&debug=tests", 'web_studio_new_app_tour', login="admin")

        # the report tour is based on the result of the former tour
        self.start_tour("/web?debug=tests", 'web_studio_new_report_tour', login="admin")
        self.start_tour("/web?debug=tests", "web_studio_new_report_basic_layout_tour", login="admin")

    def test_optional_fields(self):
        self.start_tour("/web", 'web_studio_hide_fields_tour', login="admin")

    def test_rename(self):
        self.start_tour("/web?studio=app_creator", 'web_studio_tests_tour', login="admin", timeout=120)

    def test_approval(self):
        self.start_tour("/web?debug=tests", 'web_studio_approval_tour', login="admin")

    def test_address_view_id_no_edit(self):
        self.testView = self.env["ir.ui.view"].create({
            "name": "simple partner",
            "model": "res.partner",
            "type": "form",
            "arch": '''
                <form>
                    <div class="o_address_format">
                        <field name="lang"/>
                    </div>
                </form>
            '''
        })
        self.testAction = self.env["ir.actions.act_window"].create({
            "name": "simple partner",
            "res_model": "res.partner",
            "view_mode": "form",
            "view_id": self.testView.id,
        })
        self.testActionXmlId = self.env["ir.model.data"].create({
            "name": "studio_test_partner_action",
            "model": "ir.actions.act_window",
            "module": "web_studio",
            "res_id": self.testAction.id,
        })
        self.testMenu = self.env["ir.ui.menu"].create({
            "name": "Studio Test Partner",
            "action": "ir.actions.act_window,%s" % self.testAction.id,
        })
        self.testMenuXmlId = self.env["ir.model.data"].create({
            "name": "studio_test_partner_menu",
            "model": "ir.ui.menu",
            "module": "web_studio",
            "res_id": self.testMenu.id,
        })

        self.env.company.country_id.address_view_id = self.env.ref('base.view_partner_address_form')
        self.start_tour("/web?debug=tests", 'web_studio_test_address_view_id_no_edit', login="admin", timeout=200)
