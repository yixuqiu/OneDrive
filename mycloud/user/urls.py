#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: leeyoshinari

import os
import time
import json
import shutil
import traceback
from fastapi import APIRouter, Request, Response, Depends
from tortoise import transactions
from tortoise.exceptions import DoesNotExist
from mycloud import models
from mycloud.auth_middleware import auth
from common.calc import str_md5, parse_pwd
from common.results import Result
from common.logging import logger
from common.messages import Msg
import settings


root_path = json.loads(settings.get_config("rootPath"))
router = APIRouter(prefix='/user', tags=['user (用户管理)'], responses={404: {'description': 'Not found'}})


@router.get("/status", summary="Get login status (获取用户登录状态)")
async def get_status(request: Request):
    username = request.cookies.get("u", 's')
    token = request.cookies.get("token", None)
    if not username or username not in settings.TOKENs or token != settings.TOKENs[username]:
        return Result(code=-1)
    return Result()


@router.get("/test/createUser", summary="Create user (创建用户)")
async def create_user(username: str, password: str, password1: str, request: Request):
    result = Result()
    lang = request.headers.get('lang', 'en')
    try:
        if not username.isalnum():
            result.code = 1
            result.msg = Msg.MsgUserCheckUsername[lang]
            return result
        if password != password1:
            result.code = 1
            result.msg = Msg.MsgUserCheckPassword[lang]
            return result
        user = await models.User.filter(username=username.strip())
        if user:
            result.code = 1
            result.msg = f"{Msg.MsgExistUserError[lang].format(username)}"
            logger.error(f"{result.msg}, IP: {request.headers.get('x-real-ip', '')}")
            return result
        async with transactions.in_transaction():
            password = str_md5(password)
            user = await models.User.create(username=username, password=password)
            for k, v in root_path.items():
                folder = await models.Catalog.filter(id=k)
                if not folder:
                    await models.Catalog.create(id=k, parent=None, name=v)
                folder = await models.Catalog.filter(id=f"{k}{user.username}")
                if not folder:
                    await models.Catalog.create(id=f"{k}{user.username}", name=user.username, parent_id=k)
                user_path = os.path.join(v, user.username)
                if not os.path.exists(user_path):
                    os.mkdir(user_path)
            back_path = os.path.join(settings.path, 'web/img/pictures', user.username)
            if not os.path.exists(back_path):
                os.mkdir(back_path)
            source_file = os.path.join(settings.path, 'web/img/pictures/undefined/background.jpg')
            target_file = os.path.join(back_path, 'background.jpg')
            shutil.copy(source_file, target_file)
        result.msg = f"{Msg.MsgCreateUser[lang].format(user.username)}{Msg.Success[lang]}"
        logger.info(f"{result.msg}, IP: {request.headers.get('x-real-ip', '')}")
    except:
        result.code = 1
        result.msg = f"{Msg.MsgCreateUser[lang].format(username)}{Msg.Failure[lang]}"
        logger.error(traceback.format_exc())
    return result


@router.post("/modify/pwd", summary="Modify password (修改用户密码)")
async def modify_pwd(query: models.CreateUser, hh: dict = Depends(auth)):
    result = Result()
    try:
        if query.password != query.password1:
            result.code = 1
            result.msg = Msg.MsgUserCheckPassword[hh['lang']]
            return result
        user = await models.User.get(username=query.username)
        user.password = str_md5(parse_pwd(query.password, query.t))
        await user.save()
        result.msg = f"{Msg.MsgModifyPwd[hh['lang']].format(user.username)}{Msg.Success[hh['lang']]}"
        logger.info(f"{Msg.CommonLog[hh['lang']].format(result.msg, hh['u'], hh['ip'])}")
    except:
        result.code = 1
        result.msg = f"{Msg.MsgModifyPwd[hh['lang']].format(query.username)}{Msg.Failure[hh['lang']]}"
        logger.error(traceback.format_exc())
    return result


@router.post("/login", summary="Login (用户登陆)")
async def login(query: models.UserBase, request: Request, response: Response):
    result = Result()
    lang = request.headers.get('lang', 'en')
    try:
        user = await models.User.get(username=query.username, password=str_md5(parse_pwd(query.password, query.t)))
        if user:
            for k, v in root_path.items():
                folder = await models.Catalog.filter(id=k)
                if not folder:
                    await models.Catalog.create(id=k, parent=None, name=v)
                folder = await models.Catalog.filter(id=f"{k}{user.username}")
                if not folder:
                    await models.Catalog.create(id=f"{k}{user.username}", name=user.username, parent_id=k)
                user_path = os.path.join(v, user.username)
                if not os.path.exists(user_path):
                    os.mkdir(user_path)
            pwd_str = f'{time.time()}_{user.username}_{int(time.time())}'
            token = str_md5(pwd_str)
            settings.TOKENs.update({user.username: token})
            response.set_cookie('u', user.username)
            response.set_cookie('t', str(int(time.time() / 1000)))
            response.set_cookie('token', token)
            result.msg = f"{Msg.MsgLogin[lang].format(user.username)}{Msg.Success[lang]}"
            logger.info(f"{result.msg}, IP: {request.headers.get('x-real-ip', '')}")
        else:
            result.code = 1
            result.msg = f"{Msg.MsgLoginUserOrPwdError[lang]}"
            logger.error(f"{result.msg}, IP: {request.headers.get('x-real-ip', '')}")
    except DoesNotExist:
        result.code = 1
        result.msg = f"{Msg.MsgLoginUserOrPwdError[lang]}"
        logger.error(f"{result.msg}, IP: {request.headers.get('x-real-ip', '')}")
    except:
        result.code = 1
        result.msg = f"{Msg.MsgLogin[lang].format(query.username)}{Msg.Failure[lang]}"
        logger.error(traceback.format_exc())
    return result


@router.get("/logout", summary="Logout (退出登陆)")
async def logout(hh: dict = Depends(auth)):
    settings.TOKENs.pop(hh['u'], 0)
    logger.info(f"{Msg.MsgLogout[hh['lang']].format(hh['u'])}{Msg.Success[hh['lang']]}, IP: {hh['ip']}")
    return Result()
