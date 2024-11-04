# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import datetime

from unittest.mock import patch

from odoo.addons.social.tests.common import SocialCase
from odoo.addons.social_push_notifications.models.social_account import SocialAccountPushNotifications


class SocialPushNotificationsCase(SocialCase):
    @classmethod
    def setUpClass(cls):
        super(SocialPushNotificationsCase, cls).setUpClass()

        cls.website_1 = cls.env['website'].create({
            'name': 'Website 1 WITHOUT push notifications',
            'domain': 'website1.example.com',
            'firebase_enable_push_notifications': False,
        })
        cls.website_2 = cls.env['website'].create({
            'name': 'Website 2 WITH push notifications',
            'domain': 'website2.example.com',
            'firebase_enable_push_notifications': True,
            'firebase_use_own_account': True,
            'firebase_admin_key_file': base64.b64encode(b'{}')
        })
        cls.website_3 = cls.env['website'].create({
            'name': 'Website 3 WITH push notifications',
            'domain': 'website3.example.com',
            'firebase_enable_push_notifications': True,
            'firebase_use_own_account': True,
            'firebase_admin_key_file': base64.b64encode(b'{}')
        })
        cls.websites = cls.website_1 | cls.website_2 | cls.website_3

        cls.social_accounts = cls.env['social.account'].search(
            [('website_id', 'in', cls.websites.ids)]
        )

        cls.social_post.write({
            'account_ids': [(6, 0, cls.social_accounts.filtered(lambda a: a.website_id.id != cls.website_3.id).ids)],
        })

    def test_post(self):
        """ Test that the push notifications are sent to the right visitors depending:
            - on the website's configuration (firebase_enable_push_notifications)
            - on the social account's configuration (website_id)
            - on the visitor's configuration (push_token set , website_id)
        """
        Visitor = self.env['website.visitor']
        self.visitors = Visitor.create([{
            'name': 'Visitor %s' % i,
            'push_token': 'fake_token_%s' % i if i != 0 else False,
            'website_id': self.websites[i].id,
        } for i in range(0, 3)])

        # Remove the visitor domain to ensure that the push notifications are still sent
        # to only the visitors of websites with push notifications enabled
        self.social_post.write({
            'visitor_domain': [],
            'use_visitor_timezone': False,
        })

        self.assertEqual(self.social_post.state, 'draft')

        self.social_post._action_post()

        live_posts = self.env['social.live.post'].search([('post_id', '=', self.social_post.id)])
        # make sure live_posts' create_date is before 'now'
        live_posts.write({'create_date': live_posts[0].create_date - datetime.timedelta(minutes=1)})
        self.assertEqual(len(live_posts), 2)

        def _firebase_send_message_from_configuration(this, data, visitors):
            website = visitors.website_id
            push_enabled = website.firebase_enable_push_notifications
            # Ensure that only visitors from the website with push notifications enabled
            # and linked to the social account are notified
            self.assertEqual(len(visitors), 1 if push_enabled else 0)
            if visitors:
                self.assertEqual(visitors.website_id, self.website_2)
            return visitors.mapped('push_token'), []

        with patch.object(SocialAccountPushNotifications, '_firebase_send_message_from_configuration',
             _firebase_send_message_from_configuration):
            live_posts._post_push_notifications()

        self._checkPostedStatus(True)

    def test_post_with_timezone(self):
        # Create some visitors with or without push_token in different timezone (or no timezone)
        timezones = ['Europe/Brussels', 'America/New_York', 'Asia/Vladivostok', False]
        Visitor = self.env['website.visitor']
        visitor_vals = []
        for i in range(0, 4):
            visitor_vals.append({
                'name': timezones[i] or 'Visitor',
                'timezone': timezones[i],
                'push_token': 'fake_token_%s' % i if i != 0 else False,
                'website_id': self.website_2.id,
            })
        self.visitors = Visitor.create(visitor_vals)
        self.social_post.create_uid.write({'tz': timezones[0]})

        self.assertEqual(self.social_post.state, 'draft')

        self.social_post._action_post()

        live_posts = self.env['social.live.post'].search([('post_id', '=', self.social_post.id)])
        # make sure live_posts' create_date is before 'now'
        live_posts.write({'create_date': live_posts[0].create_date - datetime.timedelta(minutes=1)})
        self.assertEqual(len(live_posts), 2)

        self.assertTrue(all(live_post.state == 'ready' for live_post in live_posts))
        self.assertEqual(self.social_post.state, 'posting')

        with patch.object(
             SocialAccountPushNotifications,
             '_firebase_send_message_from_configuration',
             lambda self, data, visitors: visitors.mapped('push_token'), []):
            live_posts._post_push_notifications()

        self.assertFalse(all(live_post.state == 'posted' for live_post in live_posts))
        self.assertEqual(self.social_post.state, 'posting')

        # simulate that everyone can receive the push notif (because their time >= time of the one who created the post)
        self.visitors.write({'timezone': self.env.user.tz})

        with patch.object(
             SocialAccountPushNotifications,
             '_firebase_send_message_from_configuration',
             lambda self, data, visitors: visitors.mapped('push_token'), []):
            live_posts._post_push_notifications()

        self._checkPostedStatus(True)

    @classmethod
    def _get_social_media(cls):
        return cls.env.ref('social_push_notifications.social_media_push_notifications')
