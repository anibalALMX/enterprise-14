# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import json

import logging
import requests
import werkzeug
from werkzeug.urls import url_encode, url_join

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.social.controllers.main import SocialValidationException

_logger = logging.getLogger(__name__)


class SocialTwitterController(http.Controller):
    # ========================================================
    # Accounts management
    # ========================================================

    @http.route('/social_twitter/callback', type='http', auth='user')
    def twitter_account_callback(self, oauth_token=None, oauth_verifier=None, iap_twitter_consumer_key=None, **kw):
        """ When we add accounts though IAP, we copy the 'iap_twitter_consumer_key' to our media's twitter_consumer_key.
        This allows preparing the signature process and the information is not sensitive so we can take advantage of it. """
        if not request.env.user.has_group('social.group_social_manager'):
            return request.render('social.social_http_error_view',
                                  {'error_message': _('Unauthorized. Please contact your administrator.')})

        if not kw.get('denied'):
            if not oauth_token or not oauth_verifier:
                return request.render('social.social_http_error_view',
                                      {'error_message': _('Twitter did not provide a valid access token.')})

            if iap_twitter_consumer_key:
                request.env['ir.config_parameter'].sudo().set_param('social.twitter_consumer_key', iap_twitter_consumer_key)

            media = request.env['social.media'].search([('media_type', '=', 'twitter')], limit=1)

            try:
                self._create_twitter_accounts(oauth_token, oauth_verifier, media)
            except (SocialValidationException, UserError) as e:
                return request.render('social.social_http_error_view',
                                      {'error_message': str(e)})

        url_params = {
            'action': request.env.ref('social.action_social_stream_post').id,
            'view_type': 'kanban',
            'model': 'social.stream.post',
        }

        url = '/web?#%s' % url_encode(url_params)
        return werkzeug.utils.redirect(url)

    def _create_twitter_accounts(self, oauth_token, oauth_verifier, media):
        twitter_consumer_key = request.env['ir.config_parameter'].sudo().get_param('social.twitter_consumer_key')

        twitter_access_token_url = url_join(request.env['social.media']._TWITTER_ENDPOINT, "oauth/access_token")
        response = requests.post(twitter_access_token_url, data={
            'oauth_consumer_key': twitter_consumer_key,
            'oauth_token': oauth_token,
            'oauth_verifier': oauth_verifier,
        }, timeout=10)

        if response.status_code != 200:
            raise SocialValidationException(_('Twitter did not provide a valid access token or it may have expired.'))

        response_values = {
            response_value.split('=')[0]: response_value.split('=')[1]
            for response_value in response.text.split('&')
        }

        existing_account = request.env['social.account'].search([
            ('media_id', '=', media.id),
            ('twitter_user_id', '=', response_values['user_id'])
        ])

        if existing_account:
            existing_account.write({
                'is_media_disconnected': False,
                'twitter_screen_name': response_values['screen_name'],
                'twitter_oauth_token': response_values['oauth_token'],
                'twitter_oauth_token_secret': response_values['oauth_token_secret']
            })
        else:
            twitter_account_information = self._get_twitter_account_information(
                media,
                response_values['oauth_token'],
                response_values['oauth_token_secret'],
            )

            request.env['social.account'].create({
                'media_id': media.id,
                'name': twitter_account_information['name'],
                'twitter_user_id': response_values['user_id'],
                'twitter_screen_name': response_values['screen_name'],
                'twitter_oauth_token': response_values['oauth_token'],
                'twitter_oauth_token_secret': response_values['oauth_token_secret'],
                'image': base64.b64encode(requests.get(twitter_account_information['profile_image_url'], timeout=10).content),
            })

    def _get_twitter_account_information(self, media, oauth_token, oauth_token_secret, screen_name=None):
        """Get the information about the Twitter account.

        TODO: screen_name is not used, remove in master
        """
        twitter_account_info_url = url_join(
            request.env['social.media']._TWITTER_ENDPOINT,
            '/2/users/me')

        params = {'user.fields': 'profile_image_url'}
        headers = media._get_twitter_oauth_header(
            twitter_account_info_url,
            headers={
                'oauth_token': oauth_token,
                'oauth_token_secret': oauth_token_secret,
            },
            params=params,
            method='GET',
        )
        response = requests.get(twitter_account_info_url, headers=headers, params=params, timeout=10)
        return response.json()['data']

    # ========================================================
    # Comments and likes
    # ========================================================

    @http.route('/social_twitter/<int:stream_id>/like_tweet', type='json')
    def like_tweet(self, stream_id, tweet_id, like):
        stream = request.env['social.stream'].browse(stream_id)
        if not stream or stream.media_id.media_type != 'twitter':
            return {}

        if like:
            endpoint = url_join(
                request.env['social.media']._TWITTER_ENDPOINT,
                '/2/users/%s/likes' % stream.account_id.twitter_user_id)
            headers = stream.account_id._get_twitter_oauth_header(endpoint)
            result = requests.post(
                endpoint,
                json={'tweet_id': tweet_id},
                headers=headers,
                timeout=10,
            )
        else:
            endpoint = url_join(
                request.env['social.media']._TWITTER_ENDPOINT,
                '/2/users/%s/likes/%s' % (stream.account_id.twitter_user_id, tweet_id))
            headers = stream.account_id._get_twitter_oauth_header(endpoint, method='DELETE')
            result = requests.delete(endpoint, headers=headers, timeout=10)

        if not result.ok:
            raise UserError(_('Can not like / unlike the tweet\n%s.', result.text))

        post = request.env['social.stream.post'].search([('twitter_tweet_id', '=', tweet_id)])
        if post:
            post.twitter_user_likes = like

    @http.route('/social_twitter/<int:stream_id>/comment', type='http')
    def comment(self, stream_id=None, post_id=None, comment_id=None, message=None, **kwargs):
        """Create a Tweet in response of an other.

        The Twitter API does not return the created tweet, so we manually build
        the response to save one API call.
        """
        stream = request.env['social.stream'].browse(stream_id)
        if not stream or stream.media_id.media_type != 'twitter':
            return {}

        post = request.env['social.stream.post'].browse(int(post_id))
        tweet_id = comment_id or post.twitter_tweet_id
        message = request.env["social.live.post"]._remove_mentions(message)

        data = {
            'text': message,
            'reply': {'in_reply_to_tweet_id': tweet_id},
        }

        files = request.httprequest.files.getlist('attachment')
        attachment = files and files[0]

        images_attachments_ids = None
        if attachment:
            bytes_data = attachment.read()
            images_attachments_ids = stream.account_id._format_images_twitter([{
                'bytes': bytes_data,
                'file_size': len(bytes_data),
                'mimetype': attachment.content_type,
            }])
            if images_attachments_ids:
                data['media'] = {'media_ids': images_attachments_ids}

        post_endpoint_url = url_join(request.env['social.media']._TWITTER_ENDPOINT, '/2/tweets')
        headers = stream.account_id._get_twitter_oauth_header(post_endpoint_url)
        result = requests.post(
            post_endpoint_url,
            json=data,
            headers=headers,
            timeout=10,
        )

        if not result.ok:
            raise UserError(_('Failed to post comment: %s with the account %i.'), result.text, stream.account_id.name)

        tweet = result.json()['data']

        # we can not use fields expansion when creating a tweet,
        # so we fill manually the missing values to not recall the API
        tweet.update({
            'author': {
                'id': post.account_id.twitter_user_id,
                'name': post.account_id.name,
                'profile_image_url': '/web/image/social.account/%s/image' % stream.account_id.id,
            }
        })
        if images_attachments_ids:
            # the image didn't create an attachment, and it will require an extra
            # API call to get the URL, so we just base 64 encode the image data
            b64_image = base64.b64encode(bytes_data).decode()
            link = "data:%s;base64,%s" % (attachment.content_type, b64_image)
            tweet['medias'] = [{'url': link, 'type': 'photo'}]

        return json.dumps(request.env['social.media']._format_tweet(tweet))
