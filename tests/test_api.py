import unittest
import json
import re
from base64 import b64encode
from flask import url_for
from app import create_app, db
from app.models import User, Role, Post, Comment


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def get_api_headers(self, username, password):
        return {
            'Authorization': 'Basic ' + b64encode(
                (username + ':' + password).encode('utf-8')).decode('utf-8'),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def test_404(self):
        response = self.client.get(
            '/wrong/url',
            headers=self.get_api_headers('email', 'password'))
        self.assertTrue(response.status_code == 404)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(json_response['error'] == 'not found')

    def test_no_auth(self):
        response = self.client.get(url_for('api.get_posts'),
                                   content_type='application/json')
        self.assertTrue(response.status_code == 200)

    def test_bad_auth(self):
        # 添加用户
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=True,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # 检验密码
        response = self.client.get(
            url_for('api.get_posts'),
            headers=self.get_api_headers('john@example.com', 'dog'))
        self.assertTrue(response.status_code == 401)

    def test_token_auth(self):
        # 添加用户
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=True,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # 发送错误请求
        response = self.client.get(
            url_for('api.get_posts'),
            headers=self.get_api_headers('bad-token', ''))
        self.assertTrue(response.status_code == 401)

        # 接受请求
        response = self.client.get(
            url_for('api.get_token'),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertIsNotNone(json_response.get('token'))
        token = json_response['token']

        # 发送错误请求
        response = self.client.get(
            url_for('api.get_posts'),
            headers=self.get_api_headers(token, ''))
        self.assertTrue(response.status_code == 200)

    def test_anonymous(self):
        response = self.client.get(
            url_for('api.get_posts'),
            headers=self.get_api_headers('', ''))
        self.assertTrue(response.status_code == 200)

    def test_unconfirmed_account(self):
        # 添加未确认用户
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=False,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # 获取未确认的账号列表
        response = self.client.get(
            url_for('api.get_posts'),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertTrue(response.status_code == 403)

    def test_posts(self):
        # 新用户
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=True,
                 role=r)
        db.session.add(u)
        db.session.commit()

        #
        response = self.client.post(
            url_for('api.new_post'),
            headers=self.get_api_headers('john@example.com', 'cat'),
            data=json.dumps({'body': ''}))
        self.assertTrue(response.status_code == 400)

        # 写请求
        response = self.client.post(
            url_for('api.new_post'),
            headers=self.get_api_headers('john@example.com', 'cat'),
            data=json.dumps({'body': 'body of the *blog* post'}))
        self.assertTrue(response.status_code == 201)
        url = response.headers.get('Location')
        self.assertIsNotNone(url)

        # 获取新的请求
        response = self.client.get(
            url,
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(json_response['url'] == url)
        self.assertTrue(json_response['body'] == 'body of the *blog* post')
        self.assertTrue(json_response['body_html'] ==
                        '<p>body of the <em>blog</em> post</p>')
        json_post = json_response

        # 从用户那里获取请求
        response = self.client.get(
            url_for('api.get_user_posts', id=u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertIsNotNone(json_response.get('posts'))
        self.assertTrue(json_response.get('count', 0) == 1)
        self.assertTrue(json_response['posts'][0] == json_post)

        #从用户中获取关注者的帖子
        response = self.client.get(
            url_for('api.get_user_followed_posts', id=u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertIsNotNone(json_response.get('posts'))
        self.assertTrue(json_response.get('count', 0) == 1)
        self.assertTrue(json_response['posts'][0] == json_post)

        # 编辑请求
        response = self.client.put(
            url,
            headers=self.get_api_headers('john@example.com', 'cat'),
            data=json.dumps({'body': 'updated body'}))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(json_response['url'] == url)
        self.assertTrue(json_response['body'] == 'updated body')
        self.assertTrue(json_response['body_html'] == '<p>updated body</p>')

    def test_users(self):
        # 添加两个用户
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        db.session.add_all([u1, u2])
        db.session.commit()

        # 获取多名用户
        response = self.client.get(
            url_for('api.get_user', id=u1.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(json_response['username'] == 'john')
        response = self.client.get(
            url_for('api.get_user', id=u2.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(json_response['username'] == 'susan')

    def test_comments(self):
        # 添加两名用户
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        db.session.add_all([u1, u2])
        db.session.commit()

        # 添加请求
        post = Post(body='body of the post', author=u1)
        db.session.add(post)
        db.session.commit()

        # 写评论
        response = self.client.post(
            url_for('api.new_post_comment', id=post.id),
            headers=self.get_api_headers('susan@example.com', 'dog'),
            data=json.dumps({'body': 'Good [post](http://example.com)!'}))
        self.assertTrue(response.status_code == 201)
        json_response = json.loads(response.data.decode('utf-8'))
        url = response.headers.get('Location')
        self.assertIsNotNone(url)
        self.assertTrue(json_response['body'] ==
                        'Good [post](http://example.com)!')
        self.assertTrue(
            re.sub('<.*?>', '', json_response['body_html']) == 'Good post!')

        # 获取新的评论
        response = self.client.get(
            url,
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(json_response['url'] == url)
        self.assertTrue(json_response['body'] ==
                        'Good [post](http://example.com)!')

        # 获取其他评论
        comment = Comment(body='Thank you!', author=u1, post=post)
        db.session.add(comment)
        db.session.commit()

        # 获取两个评论请求
        response = self.client.get(
            url_for('api.get_post_comments', id=post.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertIsNotNone(json_response.get('comments'))
        self.assertTrue(json_response.get('count', 0) == 2)

        # 获取所有评论
        response = self.client.get(
            url_for('api.get_comments', id=post.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertTrue(response.status_code == 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertIsNotNone(json_response.get('comments'))
        self.assertTrue(json_response.get('count', 0) == 2)