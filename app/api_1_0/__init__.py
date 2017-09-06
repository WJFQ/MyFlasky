from flask import Blueprint

api = Blueprint('api', __name__)

from . import authentication, posts, users, comments, errors
#API蓝本的构造文件  p 157