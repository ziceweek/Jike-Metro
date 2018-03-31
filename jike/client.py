# -*- coding: utf-8 -*-

"""
Client that Jikers play with
"""

import webbrowser
from .session import JikeSession
from .objects import List, Stream, User, Topic
from .utils import *
from .constants import ENDPOINTS, URL_VALIDATION_PATTERN


class JikeClient:
    def __init__(self):
        self.auth_token = read_token()
        if self.auth_token is None:
            self.auth_token = login()
            write_token(self.auth_token)
        self.jike_session = JikeSession(self.auth_token)

        self.collection = None
        self.news_feed = None
        self.following_update = None

    def get_my_profile(self):
        return self.get_user_profile(username=None)

    def get_news_feed_unread_count(self):
        res = self.jike_session.get(ENDPOINTS['news_feed_unread_count'])
        if res.status_code == 200:
            result = res.json()
            return result['newMessageCount']
        res.raise_for_status()

    def get_my_collection(self):
        if self.collection is None:
            self.collection = List(self.jike_session, ENDPOINTS['my_collections'])
            self.collection.load_more()
        return self.collection

    def get_news_feed(self):
        if self.news_feed is None:
            self.news_feed = Stream(self.jike_session, ENDPOINTS['news_feed'])
            self.news_feed.load_more()
        return self.news_feed

    def get_following_update(self):
        if self.following_update is None:
            self.following_update = Stream(self.jike_session, ENDPOINTS['following_update'])
            self.following_update.load_more()
        return self.following_update

    def get_user_profile(self, username):
        res = self.jike_session.get(ENDPOINTS['user_profile'], {
            'username': username
        })
        if res.status_code == 200:
            result = res.json()
            result['user'].update(result['statsCount'])
            return User(**result['user'])
        res.raise_for_status()

    def get_user_post(self, username, limit=20):
        posts = List(self.jike_session, ENDPOINTS['user_post'], {'username': username})
        posts.load_more(limit)
        return posts

    def get_user_created_topic(self, username, limit=20):
        created_topics = List(self.jike_session, ENDPOINTS['user_created_topic'], {'username': username}, Topic)
        created_topics.load_more(limit)
        return created_topics

    def get_user_subscribed_topic(self, username, limit=20):
        subscribed_topics = List(self.jike_session, ENDPOINTS['user_subscribed_topic'], {'username': username}, Topic)
        subscribed_topics.load_more(limit)
        return subscribed_topics

    def get_user_following(self, username, limit=20):
        user_followings = List(self.jike_session, ENDPOINTS['user_following'], {'username': username}, User)
        user_followings.load_more(limit)
        return user_followings

    def get_user_follower(self, username, limit=20):
        user_followers = List(self.jike_session, ENDPOINTS['user_follower'], {'username': username}, User)
        user_followers.load_more(limit)
        return user_followers

    def get_comment(self, target_id, target_type):
        comments = Stream(self.jike_session, ENDPOINTS['list_comment'], {
            'targetId': target_id,
            'targetType': target_type
        })
        comments.load_more()
        return comments

    def get_topic_selected(self, topic_id):
        topic_selected = Stream(self.jike_session, ENDPOINTS['topic_selected'], {
            'topic': topic_id
        })
        topic_selected.load_more()
        return topic_selected

    def get_topic_square(self, topic_id):
        topic_square = Stream(self.jike_session, ENDPOINTS['topic_square'], {
            'topicId': topic_id
        })
        topic_square.load_more()
        return topic_square

    @staticmethod
    def open_in_browser(url_or_message):
        if isinstance(url_or_message, str):
            url = url_or_message
        elif hasattr(url_or_message, 'linkInfo'):
            url = url_or_message.linkInfo['linkUrl']
        elif 'linkInfo' in url_or_message:
            url = url_or_message['linkInfo']['linkUrl']
        elif hasattr(url_or_message, 'content'):
            urls = extract_url(url_or_message.content)
            if urls:
                for url in urls:
                    webbrowser.open(url)
                return
        else:
            raise ValueError('No url found')

        if not URL_VALIDATION_PATTERN.match(url):
            raise ValueError('Url invalid')
        else:
            webbrowser.open(url)

    def create_my_post(self, content, link=None, topic_id=None, pictures=None):
        assert isinstance(content, str)
        if link and pictures:
            raise ValueError('Jike cannot post thought with both pictures and link')

        payload = {
            'content': content
        }
        if link:
            assert URL_VALIDATION_PATTERN.match(link), 'Invalid link'
            payload.update({'linkInfo': extract_link(self.jike_session, link)})
        if topic_id:
            payload.update({'submitToTopic': topic_id})
        if pictures:
            uploaded_picture_keys = upload_picture(pictures)
            payload.update({'pictureKeys': uploaded_picture_keys})

        res = self.jike_session.post(ENDPOINTS['create_post'], json=payload)
        post = None
        if res.status_code == 200:
            result = res.json()
            if result['success']:
                post = OriginalPost(**result['data'])
            else:
                raise RuntimeError('Post fail')
        res.raise_for_status()
        return post

    def delete_my_post(self, post_id):
        assert post_id, 'No post id provided'
        res = self.jike_session.post(ENDPOINTS['delete_post'], json={
            'id': post_id
        })
        if res.status_code == 200:
            return res.json()['success']
        res.raise_for_status()

    def __like_action(self, message, action):
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        assert action in ['like_it', 'unlike_it']
        message_type = ''.join([w.title() if i != 0 else w.lower()
                                for i, w in enumerate(message.type.split('_'))]) + 's'
        endpoint = ENDPOINTS[action].format(t=message_type)
        payload = {
            'id': message.id,
        }
        if hasattr(message, 'targetType'):
            payload.update({'targetType': message.targetType})
        res = self.jike_session.post(endpoint, json=payload)
        if res.status_code == 200:
            return res.json()['success']
        res.raise_for_status()

    def like_it(self, message):
        return self.__like_action(message, 'like_it')

    def unlike_it(self, message):
        return self.__like_action(message, 'unlike_it')

    def __collect_action(self, message, action):
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        assert action in ['collect_it', 'uncollect_it']
        message_type = ''.join([w.title() if i != 0 else w.lower()
                                for i, w in enumerate(message.type.split('_'))]) + 's'
        endpoint = ENDPOINTS[action].format(t=message_type)
        payload = {
            'id': message.id,
        }
        res = self.jike_session.post(endpoint, json=payload)
        if res.status_code == 200:
            return res.json()['success']
        res.raise_for_status()

    def collect_it(self, message):
        return self.__collect_action(message, 'collect_it')

    def uncollect_it(self, message):
        return self.__collect_action(message, 'uncollect_it')

    def repost_it(self, content, message, sync_comment=True):
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        payload = {
            'content': content,
            'syncComment': sync_comment,
            'targetId': message.id,
            'targetType': message.type,
        }
        res = self.jike_session.post(ENDPOINTS['repost_it'], json=payload)
        repost = None
        if res.status_code == 200:
            result = res.json()
            if result['success']:
                repost = Repost(**result['data'])
            else:
                raise RuntimeError('Repost fail')
        res.raise_for_status()
        return repost

    def comment_it(self, content, message, pictures=None, sync2personal_updates=True):
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        payload = {
            'content': content,
            'pictureKeys': [],
            'syncToPersonalUpdates': sync2personal_updates,
            'targetId': message.id,
            'targetType': message.type,
        }
        if pictures:
            uploaded_picture_keys = upload_picture(pictures)
            payload.update({'pictureKeys': uploaded_picture_keys})
        res = self.jike_session.post(ENDPOINTS['comment_it'], json=payload)
        comment = None
        if res.status_code == 200:
            result = res.json()
            if result['success']:
                comment = Comment(**result['data'])
            else:
                raise RuntimeError('Comment fail')
        res.raise_for_status()
        return comment
