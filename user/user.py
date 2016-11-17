#!/usr/bin/python3
import json
import os
import getopt

import sys, inspect




this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
src_folder = os.path.realpath(os.path.abspath(os.path.join(this_folder,"..", "src")))
if src_folder not in sys.path:
    sys.path.insert(0, src_folder)

# must first init loadenv
from log import initlogging
initlogging("docklet-user")
from log import logger

import tools, env
config = env.getenv("CONFIG")
tools.loadenv(config)


from flask import Flask, request, session, render_template, redirect, send_from_directory, make_response, url_for, abort
from functools import wraps
import userManager,beansapplicationmgr, notificationmgr
import threading


app = Flask(__name__)


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global G_usermgr
        logger.info ("get request, path: %s" % request.path)
        token = request.form.get("token", None)
        if (token == None):
            return json.dumps({'success':'false', 'message':'user or key is null'})
        cur_user = G_usermgr.auth_token(token)
        if (cur_user == None):
            return json.dumps({'success':'false', 'message':'token failed or expired', 'Unauthorized': 'True'})
        return func(cur_user, cur_user.username, request.form, *args, **kwargs)

    return wrapper



@app.route("/login/", methods=['POST'])
def login():
    global G_usermgr
    logger.info("handle request : user login")
    user = request.form.get("user", None)
    key = request.form.get("key", None)
    if user == None or key == None:
        return json.dumps({'success': 'false', 'message':'user or key is null'})
    auth_result = G_usermgr.auth(user,key)
    if auth_result['success'] == 'false':
        logger.info("%s login failed" % user)
        return json.dumps({'success':'false', 'message':'auth failed'})
    logger.info("%s login success" % user)
    return json.dumps({'success':'true', 'action':'login', 'data': auth_result['data']})

@app.route("/register/", methods=['POST'])
def register():
    global G_usermgr
    if request.form.get('activate', None) == None:
        logger.info ("handle request : user register")
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        email = request.form.get('email', '')
        description = request.form.get('description','')
        if (username == '' or password == '' or email == ''):
            return json.dumps({'success':'false'})
        newuser = G_usermgr.newuser()
        newuser.username = request.form.get('username')
        newuser.password = request.form.get('password')
        newuser.e_mail = request.form.get('email')
        newuser.student_number = request.form.get('studentnumber')
        newuser.department = request.form.get('department')
        newuser.nickname = request.form.get('truename')
        newuser.truename = request.form.get('truename')
        newuser.description = request.form.get('description')
        newuser.status = "init"
        newuser.auth_method = "local"
        result = G_usermgr.register(user = newuser)
        return json.dumps(result)
    else:
        logger.info ("handle request, user activating")
        token = request.form.get("token", None)
        if (token == None):
            return json.dumps({'success':'false', 'message':'user or key is null'})
        cur_user = G_usermgr.auth_token(token)
        if (cur_user == None):
            return json.dumps({'success':'false', 'message':'token failed or expired', 'Unauthorized': 'True'})
        newuser = G_usermgr.newuser()
        newuser.username = cur_user.username
        newuser.nickname = cur_user.truename
        newuser.status = 'applying'
        newuser.user_group = cur_user.user_group
        newuser.auth_method = cur_user.auth_method
        newuser.e_mail = request.form.get('email','')
        newuser.student_number = request.form.get('studentnumber', '')
        newuser.department = request.form.get('department', '')
        newuser.truename = request.form.get('truename', '')
        newuser.tel = request.form.get('tel', '')
        newuser.description = request.form.get('description', '')
        result = G_usermgr.register(user = newuser)
        userManager.send_remind_activating_email(newuser.username)
        return json.dumps(result)

@app.route("/authtoken/", methods=['POST'])
@login_required
def auth_token(cur_user, user, form):
     logger.info("authing")
     req = json.dumps({'success':'true','username':cur_user.username,'beans':cur_user.beans})
     logger.info("auth success")
     return req

@app.route("/user/modify/", methods=['POST'])
@login_required
def modify_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/modify/")
    result = G_usermgr.modify(newValue = form, cur_user = cur_user)
    return json.dumps(result)

@app.route("/user/groupModify/", methods=['POST'])
@login_required
def groupModify_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupModify/")
    result = G_usermgr.groupModify(newValue = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/query/", methods=['POST'])
@login_required
def query_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/query/")
    #result = G_usermgr.query(ID = form.get("ID"), cur_user = cur_user)
    result = G_usermgr.query(username = user, cur_user = cur_user)
    if (result.get('success', None) == None or result.get('success', None) == "false"):
        return json.dumps(result)
    else:
        result = G_usermgr.queryForDisplay(user = result['token'])
        return json.dumps(result)


@app.route("/user/add/", methods=['POST'])
@login_required
def add_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/add/")
    user = G_usermgr.newuser(cur_user = cur_user)
    user.username = form.get('username', None)
    user.password = form.get('password', None)
    user.e_mail = form.get('e_mail', '')
    user.status = "normal"
    result = G_usermgr.register(user = user, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupadd/", methods=['POST'])
@login_required
def groupadd_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupadd/")
    result = G_usermgr.groupadd(form = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/chdefault/", methods=['POST'])
@login_required
def chdefault(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/chdefault/")
    result = G_usermgr.change_default_group(form = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/quotaadd/", methods=['POST'])
@login_required
def quotaadd_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/quotaadd/")
    result = G_usermgr.quotaadd(form = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupdel/", methods=['POST'])
@login_required
def groupdel_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupdel/")
    result = G_usermgr.groupdel(name = form.get('name', None), cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/data/", methods=['POST'])
@login_required
def data_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/data/")
    result = G_usermgr.userList(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupNameList/", methods=['POST'])
@login_required
def groupNameList_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupNameList/")
    result = G_usermgr.groupListName(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupList/", methods=['POST'])
@login_required
def groupList_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupList/")
    result = G_usermgr.groupList(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupQuery/", methods=['POST'])
@login_required
def groupQuery_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupQuery/")
    result = G_usermgr.groupQuery(name = form.get("name"), cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/selfQuery/", methods=['POST'])
@login_required
def selfQuery_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/selfQuery/")
    result = G_usermgr.selfQuery(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/selfModify/", methods=['POST'])
@login_required
def selfModify_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/selfModify/")
    result = G_usermgr.selfModify(cur_user = cur_user, newValue = form)
    return json.dumps(result)

@app.route("/user/usageQuery/" , methods=['POST'])
@login_required
def usageQuery_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/usageQuery/")
    result = G_usermgr.usageQuery(cur_user = cur_user)
    return json.dumps(result)

@app.route("/user/usageInc/", methods=['POST'])
@login_required
def usageInc_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/usageInc/")
    setting = form.get('setting')
    result = G_usermgr.usageInc(cur_user = cur_user, modification = json.loads(setting))
    return json.dumps(result)

@app.route("/user/usageRelease/", methods=['POST'])
@login_required
def usageRelease_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/usageInc/")
    result = G_usermgr.usageRelease(cur_user = cur_user, clustername = form.get('clustername'), containername = form.get('containername'), allcontainer = form.get('allcontainer'))
    return json.dumps(result)

@app.route("/user/usageRecover/", methods=['POST'])
@login_required
def usageRecover_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/usageInc/")
    result = G_usermgr.usageRecover(cur_user = cur_user, modification = json.loads(form.get('setting')))
    return json.dumps(result)

@app.route("/user/lxcsettingList/", methods=['POST'])
@login_required
def lxcsettingList_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/lxcsettingList/")
    result = G_usermgr.lxcsettingList(cur_user = cur_user, form = form)
    return json.dumps(result)

@app.route("/user/chlxcsetting/", methods=['POST'])
@login_required
def chlxcsetting_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/chlxcsetting/")
    result = G_usermgr.chlxcsetting(cur_user = cur_user, form = form)
    return json.dumps(result)

@app.route("/notification/list/", methods=['POST'])
@login_required
def list_notifications(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/list/")
    result = G_notificationmgr.list_notifications(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/create/", methods=['POST'])
@login_required
def create_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/create/")
    result = G_notificationmgr.create_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/modify/", methods=['POST'])
@login_required
def modify_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/modify/")
    result = G_notificationmgr.modify_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/delete/", methods=['POST'])
@login_required
def delete_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/delete/")
    result = G_notificationmgr.delete_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/query_self/", methods=['POST'])
@login_required
def query_self_notification_simple_infos(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/query_self/")
    result = G_notificationmgr.query_self_notification_simple_infos(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/query/", methods=['POST'])
@login_required
def query_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/query/")
    result = G_notificationmgr.query_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/query/all/", methods=['POST'])
@login_required
def query_self_notifications_infos(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/query/all/")
    result = G_notificationmgr.query_self_notifications_infos(cur_user=cur_user, form=form)
    return json.dumps(result)

@app.route("/beans/<issue>/", methods=['POST'])
@login_required
def beans_apply(cur_user,user,form,issue):
    global G_applicationmgr
    if issue == 'apply':
        number = form.get("number",None)
        reason = form.get("reason",None)
        if number is None or reason is None:
            return json.dumps({'success':'false', 'message':'Number and reason can\'t be null.'})
        [success,message] = G_applicationmgr.apply(user,number,reason)
        if not success:
            return json.dumps({'success':'false', 'message':message})
        else:
            return json.dumps({'success':'true'})
    elif issue == 'applymsgs':
        applymsgs = G_applicationmgr.query(user)
        return json.dumps({'success':'true','applymsgs':applymsgs})
    else:
        return json.dumps({'success':'false','message':'Unsupported URL!'})

@app.route("/beans/admin/<issue>/", methods=['POST'])
@login_required
def beans_admin(cur_user,user,form,issue):
    global G_applicationmgr
    if issue == 'applymsgs':
        result = G_applicationmgr.queryUnRead(cur_user = cur_user)
        logger.debug("applymsg success")
        return json.dumps(result)
    elif issue == 'agree':
        msgid = form.get("msgid",None)
        if msgid is None:
            return json.dumps({'success':'false', 'message':'msgid can\'t be null.'})
        result = G_applicationmgr.agree(msgid, cur_user = cur_user)
        return json.dumps(result)
    elif issue == 'reject':
        msgid = form.get("msgid",None)
        if msgid is None:
            return json.dumps({'success':'false', 'message':'msgid can\'t be null.'})
        result = G_applicationmgr.reject(msgid, cur_user = cur_user)
        return json.dumps(result)
    else:
        return json.dumps({'success':'false', 'message':'Unsupported URL!'})

if __name__  ==  '__main__':
    logger.info('Start Flask...:')
    try:
        secret_key_file = open(env.getenv('FS_PREFIX') + '/local/user_secret_key.txt')
        app.secret_key = secret_key_file.read()
        secret_key_file.close()
    except:
        from base64 import b64encode
        from os import urandom
        secret_key = urandom(24)
        secret_key = b64encode(secret_key).decode('utf-8')
        app.secret_key = secret_key
        secret_key_file = open(env.getenv('FS_PREFIX') + '/local/user_secret_key.txt', 'w')
        secret_key_file.write(secret_key)
        secret_key_file.close()

    os.environ['APP_KEY'] = app.secret_key
    runcmd = sys.argv[0]
    app.runpath = runcmd.rsplit('/', 1)[0]

    global G_usermgr
    global G_notificationmgr
    global G_sysmgr
    global G_historymgr
    global G_applicationmgr

    fs_path = env.getenv("FS_PREFIX")
    logger.info("using FS_PREFIX %s" % fs_path)

    mode = 'recovery'
    if len(sys.argv) > 1 and sys.argv[1] == "new":
        mode = 'new'


    G_usermgr = userManager.userManager('root',"unias")
    #if mode == "new":
    #    G_usermgr.initUsage()
    G_notificationmgr = notificationmgr.NotificationMgr()

    #userip = env.getenv('USER_IP')
    userip = "0.0.0.0"
    logger.info("using USER_IP %s", userip)

    #userport = env.getenv('USER_PORT')
    userport = 9100
    logger.info("using USER_PORT %d", int(userport))

    G_applicationmgr = beansapplicationmgr.ApplicationMgr()
    approvalrbt = beansapplicationmgr.ApprovalRobot()
    approvalrbt.start()
    
    # server = http.server.HTTPServer((masterip, masterport), DockletHttpHandler)
    logger.info("starting user server")

    app.run(host = userip, port = userport, threaded=True,)