# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import re
import threading

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SocialPost(models.Model):
    """ A social.post represents a post that will be published on multiple social.accounts at once.
    It doesn't do anything on its own except storing the global post configuration (message, images, ...).

    When posted, it actually creates several instances of social.live.posts (one per social.account)
    that will publish their content through the third party API of the social.account. """

    _name = 'social.post'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Social Post'
    _order = 'create_date desc'

    def _get_default_account_ids(self):
        """
        If there are less than 3 social accounts available, select them all by default.
        """
        all_accounts = self.env['social.account'].search([])
        if len(all_accounts) <= 3:
            return all_accounts
        return False

    message = fields.Text("Message", required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('posting', 'Posting'),
        ('posted', 'Posted')],
        string='Status', default='draft', readonly=True, required=True,
        help="The post is considered as 'Posted' when all its sub-posts (one per social account) are either 'Failed' or 'Posted'")
    has_post_errors = fields.Boolean("There are post errors on sub-posts", compute='_compute_has_post_errors')
    account_ids = fields.Many2many('social.account', 'social_post_social_account', 'post_id', 'account_id',
                                   string='Social Accounts',
                                   help="The accounts on which this post will be published.",
                                   default=_get_default_account_ids)
    has_active_accounts = fields.Boolean('Are Accounts Available?', compute='_compute_has_active_accounts')
    media_ids = fields.Many2many('social.media', compute='_compute_media_ids', store=True,
        help="The social medias linked to the selected social accounts.")
    live_post_ids = fields.One2many('social.live.post', 'post_id', string="Posts By Account", readonly=True,
        help="Sub-posts that will be published on each selected social accounts.")
    live_posts_by_media = fields.Char('Live Posts by Social Media', compute='_compute_live_posts_by_media', readonly=True,
        help="Special technical field that holds a dict containing the live posts names by media ids (used for kanban view).")

    image_ids = fields.Many2many('ir.attachment', string='Attach Images',
        help="Will attach images to your posts (if the social media supports it).")
    image_urls = fields.Text('Images URLs', compute='_compute_image_urls',
        help="Technical JSON array capturing the URLs of the images to make it easy to display them in the kanban view.")
    post_method = fields.Selection([
        ('now', 'Send now'),
        ('scheduled', 'Schedule later')], string="When", default='now', required=True,
        help="Publish your post immediately or schedule it at a later time.")
    scheduled_date = fields.Datetime('Scheduled post date')
    published_date = fields.Datetime('Published date', readonly=True,
        help="When the global post was published. The actual sub-posts published dates may be different depending on the media.")
    # stored for better calendar view performance
    calendar_date = fields.Datetime('Calendar Date', compute='_compute_calendar_date', store=True, readonly=False,
        help="Technical field for the calendar view.")
    #UTM
    utm_campaign_id = fields.Many2one('utm.campaign', domain="[('is_website', '=', False)]", string="UTM Campaign")
    utm_source_id = fields.Many2one('utm.source', string="UTM Source", readonly=True, required=True)
    # Statistics
    stream_posts_count = fields.Integer("Feed Posts Count", compute='_compute_stream_posts_count',
        help="Number of linked Feed Posts")
    engagement = fields.Integer("Engagement", compute='_compute_post_engagement',
        help="Number of people engagements with the post (Likes, comments...)")
    click_count = fields.Integer('Number of clicks', compute="_compute_click_count")

    @api.constrains('image_ids')
    def _check_image_ids_mimetype(self):
        for social_post in self:
            if any(not image.mimetype.startswith('image') for image in social_post.image_ids):
                raise UserError(_('Uploaded file does not seem to be a valid image.'))

    @api.depends('live_post_ids.engagement')
    def _compute_post_engagement(self):
        results = self.env['social.live.post'].read_group(
            [('post_id', 'in', self.ids)],
            ['post_id', 'engagement_total:sum(engagement)'],
            ['post_id'],
            lazy=False
        )
        engagement_per_post = {
            result['post_id'][0]: result['engagement_total']
            for result in results
        }
        for post in self:
            post.engagement = engagement_per_post.get(post.id, 0)

    # TODO awa: this shouldn't depend on account_ids but it doesn't work without it
    @api.depends('account_ids')
    def _compute_has_active_accounts(self):
        has_active_accounts = self.env['social.account'].search_count([]) > 0
        for post in self:
            post.has_active_accounts = has_active_accounts

    @api.depends('live_post_ids')
    def _compute_stream_posts_count(self):
        for post in self:
            post.stream_posts_count = 0

    @api.depends('live_post_ids.state')
    def _compute_has_post_errors(self):
        for post in self:
            post.has_post_errors = any(live_post.state == 'failed' for live_post in post.live_post_ids)

    @api.depends('account_ids.media_id')
    def _compute_media_ids(self):
        for post in self:
            post.media_ids = post.with_context(active_test=False).account_ids.mapped('media_id')

    @api.depends('state', 'scheduled_date', 'published_date')
    def _compute_calendar_date(self):
        for post in self:
            post.calendar_date = post.published_date if post.state == 'posted' else post.scheduled_date

    @api.depends('image_ids')
    def _compute_image_urls(self):
        """ See field 'help' for more information. """
        for post in self:
            post.image_urls = json.dumps(['web/image/%s' % image_id.id for image_id in post.image_ids if image_id.id])

    @api.depends('live_post_ids.account_id', 'live_post_ids.display_name')
    def _compute_live_posts_by_media(self):
        """ See field 'help' for more information. """
        for post in self:
            accounts_by_media = dict((media_id.id, list()) for media_id in post.media_ids)
            for live_post in post.live_post_ids.filtered(lambda lp: lp.account_id.media_id.ids):
                accounts_by_media[live_post.account_id.media_id.id].append(live_post.display_name)
            post.live_posts_by_media = json.dumps(accounts_by_media)

    def _compute_click_count(self):
        if not self.utm_source_id.ids:
            # not "utm_source_id", the records are not yet created
            for post in self:
                post.click_count = 0
        else:
            query = """SELECT COUNT(DISTINCT(click.id)) as click_count, link.source_id
                        FROM link_tracker_click click
                        INNER JOIN link_tracker link ON link.id = click.link_id
                        WHERE link.source_id IN %s
                        GROUP BY link.source_id"""

            self.env.cr.execute(query, [tuple(self.utm_source_id.ids)])
            click_data = self.env.cr.dictfetchall()
            mapped_data = {datum['source_id']: datum['click_count'] for datum in click_data}
            for post in self:
                post.click_count = mapped_data.get(post.utm_source_id.id, 0)

    def name_get(self):
        """ We use the first 20 chars of the message (or "Post" if no message yet).
        We also add "(Draft)" at the end if the post is still in draft state. """
        result = []
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        draft_translated = state_description_values.get('draft')
        for post in self:
            name = _('Post')
            message = post.message and post.message.replace('\n', ' ').strip()
            if message:
                if len(message) < 20:
                    name = message
                else:
                    name = message[:20] + '...'

            if post.state == 'draft':
                name += ' (' + draft_translated + ')'

            result.append((post.id, name))

        return result

    @api.model
    def default_get(self, fields):
        """ When created from the calendar view, we set the post as scheduled at the selected date. """

        result = super(SocialPost, self).default_get(fields)
        default_calendar_date = self.env.context.get('default_calendar_date')
        if default_calendar_date and ('post_method' in fields or 'scheduled_date' in fields):
            result.update({
                'post_method': 'scheduled',
                'scheduled_date': default_calendar_date
            })
        return result

    def _set_attachemnt_res_id(self):
        """ Set res_id of created attachements, the many2many_binary widget
                might create them without res_id, and if it's the case,
                only the current user will be able to read the attachments
                (other user will get an access error). """
        for post in self:
            if post.image_ids:
                attachments = self.env['ir.attachment'].sudo().browse(post.image_ids.ids).filtered(
                    lambda a: a.res_model == self._name and not a.res_id and a.create_uid.id == self._uid)
                if attachments:
                    attachments.write({'res_id': post.id})

    @api.model_create_multi
    def create(self, vals_list):
        """Every post will have a unique corresponding utm.source for statistics computation purposes.
        This way, it will be possible to see every leads/quotations generated through a particular post."""

        if not self.env.is_superuser() and \
           not self.user_has_groups('social.group_social_manager') and \
           any(vals.get('state', 'draft') != 'draft' for vals in vals_list):
            raise AccessError(_('You are not allowed to create/update posts in a state other than "Draft".'))

        if vals_list:
            sources = self.env['utm.source'].create({
                'name': "Post %s_%s" % (fields.datetime.now(), i)
            } for i in range(len(vals_list)))

            for index, vals in enumerate(vals_list):
                vals['utm_source_id'] = sources[index].id

            # if a scheduled_date / published_date is specified, it should be the one used as the calendar date
            # this is normally handled by the `_compute_calendar_date` but in create mode,
            # it is not called when a default value for the calendar_date field is passed
            for vals in vals_list:
                if vals.get('state') == 'posted' and 'published_date' in vals:
                    vals['calendar_date'] = vals['published_date']
                elif 'scheduled_date' in vals:
                    vals['calendar_date'] = vals['scheduled_date']

        res = super(SocialPost, self).create(vals_list)
        res._set_attachemnt_res_id()
        return res

    def write(self, vals):
        if not self.env.is_superuser() and \
           not self.user_has_groups('social.group_social_manager') and \
           (vals.get('state', 'draft') != 'draft' or any(post.state != 'draft' for post in self)):
            raise AccessError(_('You are not allowed to create/update posts in a state other than "Draft".'))

        if vals.get('calendar_date'):
            if any(post.state != 'scheduled' for post in self):
                raise UserError(_("You can only move posts that are scheduled."))

            vals['scheduled_date'] = vals['calendar_date']

        return super(SocialPost, self).write(vals)

    def social_stream_post_action_my(self):
        action = self.env["ir.actions.actions"]._for_xml_id("social.action_social_stream_post")
        action['name'] = _('Feed Posts')
        action['domain'] = self._get_stream_post_domain()
        action['context'] = {
            'search_default_search_my_streams': True,
            'search_default_group_by_stream': True
        }
        return action

    def _has_no_accounts(self):
        self.ensure_one()
        return not self.account_ids

    def _check_post_access(self):
        """
        Raise an error if the user cannot post on a social media
        """
        if not self.user_has_groups('social.group_social_manager'):
            raise AccessError(_('You are not allowed to do this operation.'))

        if any(not post.message or post._has_no_accounts() for post in self):
            raise UserError(_('Please specify a message and at least one account to post into.'))

    def action_schedule(self):
        self._check_post_access()
        self.write({'state': 'scheduled'})

    def action_post(self):
        self._check_post_access()

        self.write({
            'post_method': 'now',
            'scheduled_date': False
        })

        self._action_post()

    def action_redirect_to_clicks(self):
        action = self.env["ir.actions.actions"]._for_xml_id("link_tracker.link_tracker_action")
        action['domain'] = [('source_id', '=', self.utm_source_id.id)]
        return action

    def _action_post(self):
        """ Called when the post is published on its social.accounts.
        It will create one social.live.post per social.account and call '_post' on each of them. """

        for post in self:
            post.write({
                'state': 'posting',
                'published_date': fields.Datetime.now(),
                'live_post_ids': [
                    (0, 0, live_post)
                    for live_post in post._prepare_live_post_values()]
            })

        if not getattr(threading.currentThread(), 'testing', False):
            # If there's a link in the message, the Facebook / Twitter API will fetch it
            # to build a preview. But when posting, the SQL transaction will not
            # yet be committed, and so the link tracker associated to this link
            # will not yet exist for the Facebook API and the preview will be
            # broken
            for live_post in self.mapped('live_post_ids'):
                # Force the compute of the link trackers
                # Note that when the social media implementations call this method again when posting, it will NOT
                # create new trackers thanks to the handy create override in the <link.tracker> model
                self.env['mail.render.mixin'].sudo()._shorten_links_text(live_post.post_id.message, live_post._get_utm_values())

            self.env.cr.commit()

        for post in self:
            # send the live posts
            failed_posts = self.env['social.live.post']
            for live_post in post.live_post_ids:
                try:
                    live_post._post()
                except Exception:
                    failed_posts |= live_post
            failed_posts.write({
                'state': 'failed',
                'failure_reason': _('Unknown error')
            })

    def _prepare_live_post_values(self):
        self.ensure_one()

        return [{
            'post_id': self.id,
            'account_id': account.id,
        } for account in self.account_ids]

    def _get_stream_post_domain(self):
        return []

    @api.model
    def _extract_url_from_message(self, message):
        """ Utility method that extracts an URL (ex: https://www.google.com) from a string message.
        Copied from: https://daringfireball.net/2010/07/improved_regex_for_matching_urls """
        # TDE FIXME: use a tool method instead
        url_regex = re.compile(r"""((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|(([^\s()<>]+|(([^\s()<>]+)))*))+(?:(([^\s()<>]+|(([^\s()<>]+)))*)|[^\s`!()[]{};:'".,<>?«»“”‘’]))""", re.DOTALL)
        urls = url_regex.search(message)
        if urls:
            return urls.group(0)
        return None

    def _check_post_completion(self):
        """ This method will check if all live.posts related to the post are completed ('posted' / 'failed').
        If it's the case, we can mark the post itself as 'posted'. """

        posts_to_complete = self.filtered(
            lambda post: all(
                live_post.state in ('posted', 'failed')
                for live_post in post.live_post_ids
            )
        )

        for post in posts_to_complete:
            posts_failed = '<br>'.join([
                '  - ' + live_post.display_name
                for live_post in post.live_post_ids
                if live_post.state == 'failed'
            ])

            if posts_failed:
                post._message_log(body=_("Message posted partially. These are the ones that couldn't be posted: <br>%s", posts_failed))
            else:
                post._message_log(body=_("Message posted"))

        if posts_to_complete:
            posts_to_complete.sudo().write({'state': 'posted'})

    @api.model
    def _cron_publish_scheduled(self):
        """ Method called by the cron job that searches for social.posts that were scheduled and need
        to be published and calls _action_post() on them."""

        self.search([
            ('post_method', '=', 'scheduled'),
            ('state', '=', 'scheduled'),
            ('scheduled_date', '<=', fields.Datetime.now())
        ])._action_post()
