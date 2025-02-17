# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.test_marketing_automation.tests.common import TestMACommon
from odoo.tests import tagged, users
from odoo.tools import mute_logger


@tagged('marketing_automation')
class MarketingCampaignTest(TestMACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_records = cls._create_marketauto_records(model='marketing.test.sms', count=2)

    @users('user_marketing_automation')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_campaign_archive(self):
        """ Ensures that campaigns are stopped when archived. """
        campaign = self.env['marketing.campaign'].create({
            'domain': [('id', 'in', self.test_records[0].ids)],
            'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'Test Campaign',
        })

        mailing = self._create_mailing('marketing.test.sms')
        self._create_activity(campaign, mailing=mailing, interval_number=0)

        campaign.action_start_campaign()
        self.assertEqual(campaign.state, 'running')

        campaign.active = False
        self.assertEqual(campaign.state, 'stopped')

    @users('user_marketing_automation')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_campaign_duplicate(self):
        """ The copy/duplicate of a campaign :
            - COPY activities, new activities related to the new campaign
            - DO NOT COPY the recipients AND the trace_ids AND the state (draft by default)
            - Normal Copy of other fields
            - Copy child of activity and keep coherence in parent_id
        """
        campaign = self.env['marketing.campaign'].create({
            'domain': [('id', 'in', self.test_records.ids)],
            'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'My First Campaign',
        })
        mailing = self._create_mailing('marketing.test.sms')
        activity = self._create_activity(
            campaign,
            mailing=mailing,
            name="ShouldDuplicate",
        )
        activity2 = self._create_activity(
            campaign,
            mailing=mailing,
            name="ShouldDuplicate2",
            parent_id=activity.id,
            trigger_type="mail_open",
        )

        self.assertEqual(
            self.env['marketing.activity'].search([('name', '=', "ShouldDuplicate")]),
            activity
        )

        campaign.action_start_campaign()
        self.assertEqual(campaign.state, 'running')
        campaign.sync_participants()
        self.assertEqual(
            activity.trace_ids.mapped('participant_id'),
            campaign.participant_ids,
        )

        # copy campaign
        campaign2 = campaign.copy()

        # check campaign state
        self.assertEqual(campaign2.state, 'draft')
        self.assertEqual(campaign2.participant_ids, self.env['marketing.participant'])

        # Two activities with the same name but not related to the same campaign
        activities = self.env['marketing.activity'].search([('name', '=', "ShouldDuplicate")])
        activities2 = self.env['marketing.activity'].search([('name', '=', "ShouldDuplicate2")])
        activity_dup = campaign2.marketing_activity_ids.filtered(lambda activity: not activity.parent_id)
        activity2_dup = campaign2.marketing_activity_ids.filtered(lambda activity: activity.parent_id)
        self.assertEqual(activities, activity | activity_dup)
        self.assertEqual(activities2, activity2 | activity2_dup)
        self.assertEqual(activities.campaign_id, campaign | campaign2)
        self.assertEqual(activity_dup.trace_ids, self.env['marketing.trace'])
        self.assertEqual(activity2_dup.trace_ids, self.env['marketing.trace'])
        self.assertEqual(campaign2.marketing_activity_ids, activity_dup | activity2_dup)

        # check relationships
        self.assertEqual(activity2.parent_id, activity)
        self.assertEqual(activity2_dup.parent_id, activity_dup)

    @users('user_marketing_automation')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_campaign_unique_field(self):
        # initial data: 0-1-2 have unique partners, 3-4 are void, 4 will receive same partner as 0 to test uniqueness
        test_records = self.test_records[:5]
        self.assertEqual(len(test_records), 5)
        test_records[-1].write({'name': test_records[0].name})

        name_field = self.env['ir.model.fields'].search([
            ('model_id', '=', self.env['ir.model']._get_id('marketing.test.sms')),
            ('name', '=', 'name')
        ])

        campaign = self.env['marketing.campaign'].create({
            'domain': [('id', 'in', test_records.ids)],
            'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'My First Campaign',
            'unique_field_id': name_field.id,
        })
        mailing = self._create_mailing('marketing.test.sms')
        _activity = self._create_activity(campaign, mailing=mailing)

        campaign.action_start_campaign()
        campaign.sync_participants()

        self.assertEqual(campaign.running_participant_count, 4)
        self.assertEqual(campaign.participant_ids.mapped('res_id'), test_records[:4].ids)

        test_records[-1].write({'name': 'Unique Again'})
        campaign.sync_participants()

        self.assertEqual(campaign.running_participant_count, 5)
        self.assertEqual(campaign.participant_ids.mapped('res_id'), test_records.ids)

    @users('user_marketing_automation')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_campaign_unique_field_many2one(self):
        # initial data: 0-1-2 have unique partners, 3-4 are void, 4 will receive same partner as 0 to test uniqueness
        test_records = self.test_records[:5]
        self.assertEqual(len(test_records), 5)
        self.assertEqual(len(test_records.mapped('customer_id')), 3)
        test_records[-1].write({'customer_id': test_records[0].customer_id.id})
        self.assertEqual(test_records[3].customer_id, self.env['res.partner'])

        partner_field = self.env['ir.model.fields'].search([
            ('model_id', '=', self.env['ir.model']._get_id('marketing.test.sms')),
            ('name', '=', 'customer_id')
        ])

        campaign = self.env['marketing.campaign'].create({
            'domain': [('id', 'in', test_records.ids)],
            'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'My First Campaign',
            'unique_field_id': partner_field.id,
        })
        mailing = self._create_mailing('marketing.test.sms')
        _activity = self._create_activity(campaign, mailing=mailing)

        campaign.action_start_campaign()
        campaign.sync_participants()

        self.assertEqual(campaign.running_participant_count, 3)
        self.assertEqual(campaign.participant_ids.mapped('res_id'), test_records[0:3].ids)

        # new partner -> will be added to set of participants as not duplicated anymore
        test_records[-1].write({'customer_id': self.env['res.partner'].create({'name': 'JustHere'})})
        campaign.sync_participants()

        self.assertEqual(campaign.running_participant_count, 4)
        self.assertEqual(campaign.participant_ids.mapped('res_id'), (test_records[0:3] | test_records[-1]).ids)
