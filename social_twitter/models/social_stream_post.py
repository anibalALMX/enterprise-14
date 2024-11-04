# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests

from odoo import models, fields, _
from odoo.exceptions import UserError
from werkzeug.urls import url_join

_logger = logging.getLogger(__name__)


class SocialStreamPostTwitter(models.Model):
    _inherit = 'social.stream.post'

    twitter_tweet_id = fields.Char('Twitter Tweet ID', index=True)
    twitter_author_id = fields.Char('Twitter Author ID')
    twitter_screen_name = fields.Char('Twitter Screen Name')
    twitter_profile_image_url = fields.Char('Twitter Profile Image URL')
    twitter_likes_count = fields.Integer('Twitter Likes')
    twitter_user_likes = fields.Boolean('Twitter User Likes')
    twitter_comments_count = fields.Integer('Twitter Comments')
    twitter_retweet_count = fields.Integer('Re-tweets')

    def _compute_author_link(self):
        twitter_posts = self.filtered(lambda post: post.stream_id.media_id.media_type == 'twitter')
        super(SocialStreamPostTwitter, (self - twitter_posts))._compute_author_link()

        for post in twitter_posts:
            post.author_link = 'https://twitter.com/intent/user?user_id=%s' % post.twitter_author_id

    def _compute_post_link(self):
        twitter_posts = self.filtered(lambda post: post.stream_id.media_id.media_type == 'twitter')
        super(SocialStreamPostTwitter, (self - twitter_posts))._compute_post_link()

        for post in twitter_posts:
            post.post_link = 'https://www.twitter.com/%s/statuses/%s' % (post.twitter_author_id, post.twitter_tweet_id)

    def delete_tweet(self, tweet_id):
        self.ensure_one()
        delete_endpoint = url_join(
            self.env['social.media']._TWITTER_ENDPOINT,
            '/2/tweets/%s' % tweet_id)
        headers = self.stream_id.account_id._get_twitter_oauth_header(
            delete_endpoint,
            method='DELETE',
        )
        response = requests.delete(
            delete_endpoint,
            headers=headers,
            timeout=10,
        )
        if not response.ok:
            raise UserError(_('Failed to delete the Tweet\n%s.', response.text))

    def get_twitter_comments(self, page=1):
        """Find the tweets in the same thread, but after the current one.

        All tweets have a `conversation_id` field, which correspond to the first tweet
        in the same thread. "comments" do not really exist in Twitter, so we take all
        the tweet in the same thread (same `conversation_id`), after the current one.

        https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query
        """
        self.ensure_one()

        # Find the conversation id of the Tweet
        # TODO in master: store "conversation_id" and "created_at" as field when we fetch the stream post
        endpoint_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, '/2/tweets')
        query_params = {'ids': self.twitter_tweet_id, 'tweet.fields': 'conversation_id,created_at'}
        headers = self.stream_id.account_id._get_twitter_oauth_header(
            endpoint_url,
            params=query_params,
            method='GET',
        )
        result = requests.get(
            endpoint_url,
            query_params,
            headers=headers,
            timeout=10,
        )
        if not result.ok:
            raise UserError(_("Failed to fetch the conversation id: '%s' using the account %i."), result.text, self.stream_id.account_id.name)
        result = result.json()['data'][0]

        endpoint_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, '/2/tweets/search/recent')
        query_params = {
            'query': 'conversation_id:%s' % result['conversation_id'],
            'since_id': self.twitter_tweet_id,
            'max_results': 100,
            'tweet.fields': 'conversation_id,created_at,public_metrics',
            'expansions': 'author_id,attachments.media_keys',
            'user.fields': 'id,name,username,profile_image_url',
            'media.fields': 'type,url,preview_image_url',
        }

        headers = self.stream_id.account_id._get_twitter_oauth_header(
            endpoint_url,
            params=query_params,
            method='GET',
        )
        result = requests.get(
            endpoint_url,
            params=query_params,
            headers=headers,
            timeout=10,
        )
        if not result.ok:
            raise UserError(_("Failed to fetch the tweets in the same thread: '%s' using the account %i."), result.text, self.stream_id.account_id.name)

        users = {
            user['id']: user
            for user in result.json().get('includes', {}).get('users', [])
        }
        medias = {
            media['media_key']: media
            for media in result.json().get('includes', {}).get('media', [])
        }
        return {
            'comments': [
                self.env['social.media']._format_tweet({
                    **tweet,
                    'author': users.get(tweet['author_id'], {}),
                    'medias': [
                        medias.get(media)
                        for media in tweet.get('attachments', {}).get('media_keys', [])
                    ],
                })
                for tweet in result.json().get('data', [])
            ]
        }

    def _add_comments_favorites(self, filtered_tweets):
        # TODO: remove in master
        return []

    def _accumulate_tweets(self, endpoint_url, query_params, search_query, query_count=1, force_max_id=None):
        # TODO: remove in master
        return []
